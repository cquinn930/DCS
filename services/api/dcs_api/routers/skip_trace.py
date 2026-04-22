"""Skip trace request and vendor result endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account
from dcs_api.models.consumer import Consumer, ContactMethod, ContactType
from dcs_api.models.skip_trace import (
    SkipRequestStatus,
    SkipResultType,
    SkipTraceRequest,
    SkipTraceResult,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.skip_trace import (
    SkipTraceRequestCreate,
    SkipTraceRequestResponse,
    SkipTraceRequestUpdate,
    SkipTraceResultCreate,
    SkipTraceResultResponse,
    SkipTraceResultUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


async def _load_request(
    session: AsyncSession, request_id: uuid.UUID, user: CurrentUser
) -> SkipTraceRequest | None:
    q = select(SkipTraceRequest).where(SkipTraceRequest.id == request_id)
    if not user.is_master:
        q = q.where(SkipTraceRequest.tenant_id == user.tenant_id)
    return (await session.execute(q)).scalar_one_or_none()


async def _verify_account_consumer(
    session: AsyncSession,
    account_id: uuid.UUID,
    consumer_id: uuid.UUID,
    user: CurrentUser,
) -> None:
    acc_q = select(Account).where(Account.id == account_id)
    if not user.is_master:
        acc_q = acc_q.where(Account.tenant_id == user.tenant_id)
    acc = (await session.execute(acc_q)).scalar_one_or_none()
    if not acc or acc.consumer_id != consumer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account and consumer mismatch or not found in tenant",
        )
    cons_q = select(Consumer).where(Consumer.id == consumer_id)
    if not user.is_master:
        cons_q = cons_q.where(Consumer.tenant_id == user.tenant_id)
    cons = (await session.execute(cons_q)).scalar_one_or_none()
    if not cons:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consumer not found in tenant",
        )


def _contact_type_for_result(result_type: SkipResultType) -> ContactType:
    mapping: dict[SkipResultType, ContactType] = {
        SkipResultType.ADDRESS: ContactType.ADDRESS_HOME,
        SkipResultType.PHONE: ContactType.PHONE_MOBILE,
        SkipResultType.EMAIL: ContactType.EMAIL,
        SkipResultType.EMPLOYER: ContactType.PHONE_WORK,
        SkipResultType.ASSET: ContactType.ADDRESS_HOME,
        SkipResultType.RELATIVE: ContactType.PHONE_HOME,
        SkipResultType.ASSOCIATE: ContactType.PHONE_HOME,
        SkipResultType.DECEASED: ContactType.ADDRESS_HOME,
        SkipResultType.BANKRUPTCY: ContactType.ADDRESS_HOME,
    }
    return mapping.get(result_type, ContactType.PHONE_MOBILE)


def _build_contact_value(data: dict[str, Any], result_type: SkipResultType) -> str:
    if result_type == SkipResultType.EMAIL:
        return str(data.get("email") or data.get("value") or "")
    if result_type in (SkipResultType.PHONE, SkipResultType.RELATIVE, SkipResultType.ASSOCIATE):
        return str(data.get("phone") or data.get("value") or "")
    if result_type == SkipResultType.ADDRESS:
        parts = [
            data.get("address_line_1"),
            data.get("city"),
            data.get("state"),
            data.get("postal_code"),
        ]
        return ", ".join(str(p) for p in parts if p)
    return str(data.get("value") or data.get("notes") or "skip-trace-result")


async def _apply_result_to_contact(
    session: AsyncSession,
    result: SkipTraceResult,
    user: CurrentUser,
) -> ContactMethod:
    req = result.request
    if req is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request not loaded")
    cons_q = select(Consumer).where(Consumer.id == req.consumer_id)
    if not user.is_master:
        cons_q = cons_q.where(Consumer.tenant_id == user.tenant_id)
    consumer = (await session.execute(cons_q)).scalar_one_or_none()
    if not consumer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumer not found")
    if consumer.legal_hold:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consumer is on legal hold; cannot apply skip trace result",
        )

    ct = _contact_type_for_result(result.result_type)
    data = dict(result.data or {})
    value = _build_contact_value(data, result.result_type)

    cm = ContactMethod(
        tenant_id=consumer.tenant_id,
        consumer_id=consumer.id,
        contact_type=ct,
        value=value or "(skip trace)",
        is_primary=False,
        is_valid=True,
        is_suppressed=False,
        address_line_1=data.get("address_line_1"),
        address_line_2=data.get("address_line_2"),
        city=data.get("city"),
        state=data.get("state"),
        postal_code=data.get("postal_code"),
        country=str(data.get("country") or "US"),
    )
    session.add(cm)
    result.is_applied = True
    result.applied_at = datetime.now(timezone.utc)
    result.applied_by_id = user.user_id
    return cm


@router.get(
    "/requests",
    response_model=PaginatedResponse[SkipTraceRequestResponse],
)
async def list_skip_requests(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
) -> PaginatedResponse[SkipTraceRequestResponse]:
    """List skip trace requests; filter by account."""
    base = select(SkipTraceRequest)
    if not user.is_master:
        base = base.where(SkipTraceRequest.tenant_id == user.tenant_id)
    if account_id:
        base = base.where(SkipTraceRequest.account_id == account_id)
    count_q = select(func.count()).select_from(SkipTraceRequest)
    if not user.is_master:
        count_q = count_q.where(SkipTraceRequest.tenant_id == user.tenant_id)
    if account_id:
        count_q = count_q.where(SkipTraceRequest.account_id == account_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(SkipTraceRequest.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[SkipTraceRequestResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/requests",
    response_model=SkipTraceRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_skip_request(
    data: SkipTraceRequestCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceRequestResponse:
    """Create a skip trace request."""
    await _verify_account_consumer(session, data.account_id, data.consumer_id, user)
    row = SkipTraceRequest(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        consumer_id=data.consumer_id,
        vendor=data.vendor,
        request_type=data.request_type,
        status=data.status,
        search_parameters=data.search_parameters,
        vendor_reference=data.vendor_reference,
        cost_cents=data.cost_cents,
        submitted_at=data.submitted_at,
        completed_at=data.completed_at,
        requested_by_id=data.requested_by_id or user.user_id,
        error_message=data.error_message,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return SkipTraceRequestResponse.model_validate(row)


@router.get("/requests/{request_id}", response_model=SkipTraceRequestResponse)
async def get_skip_request(
    request_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceRequestResponse:
    """Get skip trace request by ID."""
    row = await _load_request(session, request_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return SkipTraceRequestResponse.model_validate(row)


@router.patch("/requests/{request_id}", response_model=SkipTraceRequestResponse)
async def update_skip_request(
    request_id: uuid.UUID,
    data: SkipTraceRequestUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceRequestResponse:
    """Update a skip trace request."""
    row = await _load_request(session, request_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return SkipTraceRequestResponse.model_validate(row)


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skip_request(
    request_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> None:
    """Delete a skip trace request."""
    row = await _load_request(session, request_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    await session.delete(row)


@router.post("/requests/{request_id}/submit", response_model=SkipTraceRequestResponse)
async def submit_skip_request(
    request_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceRequestResponse:
    """Submit request to vendor (simulated): marks submitted with timestamp."""
    row = await _load_request(session, request_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    row.status = SkipRequestStatus.SUBMITTED
    row.submitted_at = datetime.now(timezone.utc)
    row.vendor_reference = row.vendor_reference or f"SIM-{row.id.hex[:12]}"
    await session.flush()
    await session.refresh(row)
    return SkipTraceRequestResponse.model_validate(row)


@router.post(
    "/requests/{request_id}/results",
    response_model=SkipTraceResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_skip_result(
    request_id: uuid.UUID,
    data: SkipTraceResultCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceResultResponse:
    """Record a skip trace result row for a request."""
    if data.request_id != request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request_id in path and body must match",
        )
    req = await _load_request(session, request_id, user)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    row = SkipTraceResult(
        tenant_id=req.tenant_id,
        request_id=request_id,
        result_type=data.result_type,
        confidence_score=data.confidence_score,
        data=data.data,
        is_applied=data.is_applied,
        applied_at=data.applied_at,
        applied_by_id=data.applied_by_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return SkipTraceResultResponse.model_validate(row)


@router.get("/results/{result_id}", response_model=SkipTraceResultResponse)
async def get_skip_result(
    result_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceResultResponse:
    """Get skip trace result by ID."""
    q = select(SkipTraceResult).where(SkipTraceResult.id == result_id)
    if not user.is_master:
        q = q.where(SkipTraceResult.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return SkipTraceResultResponse.model_validate(row)


@router.patch("/results/{result_id}", response_model=SkipTraceResultResponse)
async def update_skip_result(
    result_id: uuid.UUID,
    data: SkipTraceResultUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceResultResponse:
    """Update a skip trace result."""
    q = select(SkipTraceResult).where(SkipTraceResult.id == result_id)
    if not user.is_master:
        q = q.where(SkipTraceResult.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return SkipTraceResultResponse.model_validate(row)


@router.post("/results/{result_id}/apply", response_model=SkipTraceResultResponse)
async def apply_skip_result_to_consumer(
    result_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("skip_trace:manage"))],
) -> SkipTraceResultResponse:
    """Apply vendor result to the consumer by creating contact method(s)."""
    q = (
        select(SkipTraceResult)
        .where(SkipTraceResult.id == result_id)
        .options(joinedload(SkipTraceResult.request))
    )
    if not user.is_master:
        q = q.where(SkipTraceResult.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    if row.is_applied:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Result already applied",
        )
    await _apply_result_to_contact(session, row, user)
    await session.flush()
    await session.refresh(row)
    return SkipTraceResultResponse.model_validate(row)
