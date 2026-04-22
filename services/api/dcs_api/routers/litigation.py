"""Litigation case endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account
from dcs_api.models.litigation import LitigationCase, LitigationStatus
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.litigation import (
    LitigationCaseCreate,
    LitigationCaseResponse,
    LitigationCaseUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[LitigationCaseResponse])
async def list_litigation_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("litigation:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    status_filter: LitigationStatus | None = None,
) -> PaginatedResponse[LitigationCaseResponse]:
    """List litigation cases in the tenant."""
    query = select(LitigationCase).where(LitigationCase.tenant_id == user.tenant_id)
    if account_id:
        query = query.where(LitigationCase.account_id == account_id)
    if status_filter:
        query = query.where(LitigationCase.status == status_filter)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(LitigationCase.created_at.desc())
    result = await session.execute(query)
    cases = list(result.scalars().all())

    return PaginatedResponse(
        items=[LitigationCaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/{case_id}", response_model=LitigationCaseResponse)
async def get_litigation_case(
    case_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("litigation:manage"))],
) -> LitigationCaseResponse:
    """Get litigation case by ID."""
    query = select(LitigationCase).where(
        LitigationCase.id == case_id,
        LitigationCase.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Litigation case not found",
        )
    return LitigationCaseResponse.model_validate(row)


@router.post("", response_model=LitigationCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_litigation_case(
    data: LitigationCaseCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("litigation:create"))],
) -> LitigationCaseResponse:
    """Create a litigation case."""
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

    case = LitigationCase(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        court_id=data.court_id,
        court_name=data.court_name,
        court_type=data.court_type,
        docket_number=data.docket_number,
        case_number=data.case_number,
        status=data.status,
        filed_date=data.filed_date,
        served_date=data.served_date,
        answer_due_date=data.answer_due_date,
        trial_date=data.trial_date,
        principal_claimed=data.principal_claimed,
        interest_claimed=data.interest_claimed,
        fees_claimed=data.fees_claimed,
        costs_claimed=data.costs_claimed,
        attorney_name=data.attorney_name,
        attorney_bar_id=data.attorney_bar_id,
        notes=data.notes,
        documents=data.documents,
        efiling_submission_id=data.efiling_submission_id,
        efiling_status=data.efiling_status,
    )
    session.add(case)
    await session.flush()
    await session.refresh(case)
    return LitigationCaseResponse.model_validate(case)


@router.patch("/{case_id}", response_model=LitigationCaseResponse)
async def update_litigation_case(
    case_id: uuid.UUID,
    data: LitigationCaseUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("litigation:manage"))],
) -> LitigationCaseResponse:
    """Update litigation case."""
    query = select(LitigationCase).where(
        LitigationCase.id == case_id,
        LitigationCase.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Litigation case not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)

    await session.flush()
    await session.refresh(case)
    return LitigationCaseResponse.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_litigation_case(
    case_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("litigation:manage"))],
) -> None:
    """Delete litigation case."""
    query = select(LitigationCase).where(
        LitigationCase.id == case_id,
        LitigationCase.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Litigation case not found",
        )
    await session.delete(case)
    await session.flush()
