"""Demographics sync across linked consumer records (same SSN / client ID)."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.consumer import Consumer

router = APIRouter()

ALLOWED_DEMO_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "middle_name",
        "suffix",
        "ssn_last_four",
        "date_of_birth",
        "language_preference",
        "timezone",
        "is_deceased",
        "is_represented",
        "attorney_name",
        "attorney_contact",
        "external_id",
    }
)


class DemographicsSyncRequest(BaseModel):
    """Which consumer to use as source and which fields to propagate."""

    source_consumer_id: uuid.UUID
    fields: list[str] = Field(
        default_factory=lambda: sorted(ALLOWED_DEMO_FIELDS),
        description="Subset of demographic fields to sync",
    )


class FieldChange(BaseModel):
    """Single-field before/after for one consumer."""

    field: str
    from_value: Any
    to_value: Any


class TargetPreview(BaseModel):
    """Preview of updates for one linked consumer."""

    consumer_id: uuid.UUID
    changes: list[FieldChange]


class DemographicsPreviewResponse(BaseModel):
    """Preview of demographic propagation."""

    source_consumer_id: uuid.UUID
    linked_targets: int
    targets: list[TargetPreview]


class DemographicsApplyResponse(BaseModel):
    """Result of applying demographic sync."""

    updated_consumer_ids: list[uuid.UUID]
    fields_applied: list[str]
    applied_at: datetime


def _validate_fields(fields: list[str]) -> list[str]:
    bad = [f for f in fields if f not in ALLOWED_DEMO_FIELDS]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or disallowed fields: {bad}",
        )
    return fields


def _link_predicate(source: Consumer):
    """Match other consumers in the tenant that represent the same person."""
    clauses: list = []
    if source.ssn_last_four:
        ssn_match = Consumer.ssn_last_four == source.ssn_last_four
        if source.date_of_birth is not None:
            dob_match = or_(
                Consumer.date_of_birth.is_(None),
                Consumer.date_of_birth == source.date_of_birth,
            )
            clauses.append(and_(ssn_match, dob_match))
        else:
            clauses.append(ssn_match)
    if source.external_id:
        clauses.append(Consumer.external_id == source.external_id)
    if not clauses:
        return None
    return or_(*clauses)


async def _get_consumer(
    session: AsyncSession, consumer_id: uuid.UUID, user: CurrentUser
) -> Consumer | None:
    q = select(Consumer).where(Consumer.id == consumer_id)
    if not user.is_master:
        q = q.where(Consumer.tenant_id == user.tenant_id)
    return (await session.execute(q)).scalar_one_or_none()


async def _linked_consumers(
    session: AsyncSession, source: Consumer, user: CurrentUser
) -> list[Consumer]:
    pred = _link_predicate(source)
    if pred is None:
        return []
    q = select(Consumer).where(
        Consumer.tenant_id == source.tenant_id,
        Consumer.id != source.id,
        pred,
    )
    rows = list((await session.execute(q)).scalars().all())
    return [c for c in rows if not c.legal_hold]


@router.post("/preview", response_model=DemographicsPreviewResponse)
async def preview_demographics_sync(
    body: DemographicsSyncRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("demographics:manage"))],
) -> DemographicsPreviewResponse:
    """Show what would change on linked consumers before applying."""
    fields = _validate_fields(body.fields)
    source = await _get_consumer(session, body.source_consumer_id, user)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source consumer not found")
    targets = await _linked_consumers(session, source, user)
    previews: list[TargetPreview] = []
    for t in targets:
        changes: list[FieldChange] = []
        for fname in fields:
            new_val = getattr(source, fname)
            old_val = getattr(t, fname)
            if old_val != new_val:
                changes.append(
                    FieldChange(field=fname, from_value=old_val, to_value=new_val),
                )
        if changes:
            previews.append(TargetPreview(consumer_id=t.id, changes=changes))
    return DemographicsPreviewResponse(
        source_consumer_id=source.id,
        linked_targets=len(targets),
        targets=previews,
    )


@router.post("/apply", response_model=DemographicsApplyResponse)
async def apply_demographics_sync(
    body: DemographicsSyncRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("demographics:manage"))],
) -> DemographicsApplyResponse:
    """Propagate demographic fields from the source consumer to linked records."""
    fields = _validate_fields(body.fields)
    source = await _get_consumer(session, body.source_consumer_id, user)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source consumer not found")
    if source.legal_hold:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source consumer is on legal hold",
        )
    targets = await _linked_consumers(session, source, user)
    updated: list[uuid.UUID] = []
    for t in targets:
        for fname in fields:
            setattr(t, fname, getattr(source, fname))
        updated.append(t.id)
    await session.flush()
    return DemographicsApplyResponse(
        updated_consumer_ids=updated,
        fields_applied=fields,
        applied_at=datetime.now(timezone.utc),
    )
