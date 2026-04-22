"""Collection case endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Case, CaseStatus
from dcs_api.schemas.case import (
    CaseAssignRequest,
    CaseBulkStatusRequest,
    CaseCreate,
    CaseResponse,
    CaseStatusUpdateRequest,
    CaseUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[CaseResponse])
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    status_filter: CaseStatus | None = None,
    assigned_to_id: uuid.UUID | None = None,
) -> PaginatedResponse[CaseResponse]:
    """List cases in the tenant."""
    query = select(Case).where(Case.tenant_id == user.tenant_id)
    if account_id:
        query = query.where(Case.account_id == account_id)
    if status_filter:
        query = query.where(Case.status == status_filter)
    if assigned_to_id:
        query = query.where(Case.assigned_to_id == assigned_to_id)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Case.created_at.desc())
    result = await session.execute(query)
    cases = list(result.scalars().all())

    return PaginatedResponse(
        items=[CaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post("/bulk-status", response_model=list[CaseResponse])
async def bulk_update_case_status(
    body: CaseBulkStatusRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> list[CaseResponse]:
    """Bulk update case status for multiple cases."""
    query = select(Case).where(
        Case.tenant_id == user.tenant_id,
        Case.id.in_(body.case_ids),
    )
    result = await session.execute(query)
    cases = list(result.scalars().all())
    found_ids = {c.id for c in cases}
    missing = set(body.case_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cases not found: {sorted(missing)}",
        )
    for case in cases:
        case.status = body.status
    await session.flush()
    for case in cases:
        await session.refresh(case)
    return [CaseResponse.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> CaseResponse:
    """Get case by ID."""
    query = select(Case).where(Case.id == case_id, Case.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return CaseResponse.model_validate(row)


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    data: CaseCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> CaseResponse:
    """Create a case."""
    acc_query = select(Account).where(
        Account.id == data.account_id,
        Account.tenant_id == user.tenant_id,
    )
    acc_result = await session.execute(acc_query)
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    case = Case(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        assigned_to_id=data.assigned_to_id,
        status=data.status,
        priority=data.priority,
        workflow_state=data.workflow_state,
        next_action_date=data.next_action_date,
        notes=data.notes,
    )
    session.add(case)
    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    data: CaseUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> CaseResponse:
    """Update case."""
    query = select(Case).where(Case.id == case_id, Case.tenant_id == user.tenant_id)
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)

    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> None:
    """Delete case."""
    query = select(Case).where(Case.id == case_id, Case.tenant_id == user.tenant_id)
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    await session.delete(case)
    await session.flush()


@router.post("/{case_id}/assign", response_model=CaseResponse)
async def assign_case_collector(
    case_id: uuid.UUID,
    body: CaseAssignRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> CaseResponse:
    """Assign a collector to the case."""
    query = select(Case).where(Case.id == case_id, Case.tenant_id == user.tenant_id)
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    case.assigned_to_id = body.assigned_to_id
    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.post("/{case_id}/status", response_model=CaseResponse)
async def change_case_status(
    case_id: uuid.UUID,
    body: CaseStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("cases:manage"))],
) -> CaseResponse:
    """Change case status."""
    query = select(Case).where(Case.id == case_id, Case.tenant_id == user.tenant_id)
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    case.status = body.status
    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)
