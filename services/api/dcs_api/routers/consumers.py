"""Consumer management endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.consumer import Consent, ConsentStatus, Consumer, ContactMethod
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.consumer import (
    ConsentCreate,
    ConsentResponse,
    ConsumerCreate,
    ConsumerResponse,
    ConsumerUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[ConsumerResponse])
async def list_consumers(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, max_length=200),
) -> PaginatedResponse[ConsumerResponse]:
    """List consumers in the tenant."""
    query = select(Consumer).where(Consumer.tenant_id == user.tenant_id)

    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        query = query.where(
            (Consumer.first_name.ilike(f"%{safe_search}%"))
            | (Consumer.last_name.ilike(f"%{safe_search}%"))
            | (Consumer.external_id.ilike(f"%{safe_search}%"))
        )

    # Count total
    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    # Get paginated results
    offset = (page - 1) * page_size
    query = query.options(selectinload(Consumer.contact_methods)).offset(offset).limit(page_size)
    result = await session.execute(query)
    consumers = list(result.scalars().all())

    return PaginatedResponse(
        items=[ConsumerResponse.model_validate(c) for c in consumers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{consumer_id}", response_model=ConsumerResponse)
async def get_consumer(
    consumer_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> ConsumerResponse:
    """Get consumer by ID."""
    query = (
        select(Consumer)
        .where(Consumer.id == consumer_id, Consumer.tenant_id == user.tenant_id)
        .options(selectinload(Consumer.contact_methods))
    )
    result = await session.execute(query)
    consumer = result.scalar_one_or_none()

    if not consumer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    return ConsumerResponse.model_validate(consumer)


@router.post("", response_model=ConsumerResponse, status_code=status.HTTP_201_CREATED)
async def create_consumer(
    data: ConsumerCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> ConsumerResponse:
    """Create a new consumer."""
    consumer = Consumer(
        tenant_id=user.tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        middle_name=data.middle_name,
        suffix=data.suffix,
        ssn_last_four=data.ssn_last_four,
        date_of_birth=data.date_of_birth,
        language_preference=data.language_preference,
        timezone=data.timezone,
        external_id=data.external_id,
        extra_data=data.extra_data,
    )
    session.add(consumer)
    await session.flush()

    # Add contact methods
    for cm_data in data.contact_methods:
        contact_method = ContactMethod(
            tenant_id=user.tenant_id,
            consumer_id=consumer.id,
            contact_type=cm_data.contact_type,
            value=cm_data.value,
            is_primary=cm_data.is_primary,
            address_line_1=cm_data.address_line_1,
            address_line_2=cm_data.address_line_2,
            city=cm_data.city,
            state=cm_data.state,
            postal_code=cm_data.postal_code,
            country=cm_data.country,
        )
        session.add(contact_method)

    await session.flush()
    await session.refresh(consumer)

    return ConsumerResponse.model_validate(consumer)


@router.patch("/{consumer_id}", response_model=ConsumerResponse)
async def update_consumer(
    consumer_id: uuid.UUID,
    data: ConsumerUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> ConsumerResponse:
    """Update consumer.

    Note: Consumers under legal hold have restricted modifications.
    """
    query = (
        select(Consumer)
        .where(Consumer.id == consumer_id, Consumer.tenant_id == user.tenant_id)
        .options(selectinload(Consumer.contact_methods))
    )
    result = await session.execute(query)
    consumer = result.scalar_one_or_none()

    if not consumer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    # Check legal hold
    if consumer.legal_hold:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Consumer is under legal hold - modifications restricted",
        )

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(consumer, key, value)

    await session.flush()
    return ConsumerResponse.model_validate(consumer)


@router.post("/{consumer_id}/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    consumer_id: uuid.UUID,
    data: ConsentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> ConsentResponse:
    """Record consent for a consumer.

    Non-legal guidance: TCPA requires explicit consent for autodialed calls and SMS.
    Consent cannot be inferred from prior payments or account ownership.
    """
    # Verify consumer exists
    query = select(Consumer).where(
        Consumer.id == consumer_id, Consumer.tenant_id == user.tenant_id
    )
    result = await session.execute(query)
    consumer = result.scalar_one_or_none()

    if not consumer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    consent = Consent(
        tenant_id=user.tenant_id,
        consumer_id=consumer_id,
        contact_method_id=data.contact_method_id,
        channel=data.channel,
        status=ConsentStatus.GRANTED,
        granted_at=datetime.now(timezone.utc),
        granted_source=data.granted_source,
        scope_value=data.scope_value,
    )
    session.add(consent)
    await session.flush()

    return ConsentResponse.model_validate(consent)


@router.delete("/{consumer_id}/consents/{consent_id}")
async def revoke_consent(
    consumer_id: uuid.UUID,
    consent_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Revoke a consent record.

    Non-legal guidance: Revocation must be honored immediately per TCPA.
    """
    query = select(Consent).where(
        Consent.id == consent_id,
        Consent.consumer_id == consumer_id,
        Consent.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent not found",
        )

    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = datetime.now(timezone.utc)
    consent.revoked_source = "api"

    await session.flush()
    return {"message": "Consent revoked"}
