"""Remittance API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.remittance import RemittanceConfig, RemittanceLineItem, RemittanceStatement, RemittanceStatus
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.remittance import (
    RemittanceConfigCreate,
    RemittanceConfigResponse,
    RemittanceConfigUpdate,
    RemittanceLineItemCreate,
    RemittanceLineItemResponse,
    RemittanceStatementCreate,
    RemittanceStatementResponse,
    RemittanceStatementUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("/configs", response_model=PaginatedResponse[RemittanceConfigResponse])
async def list_configs(
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(RemittanceConfig).where(RemittanceConfig.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size))
    items = [RemittanceConfigResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/configs", response_model=RemittanceConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    body: RemittanceConfigCreate,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    cfg = RemittanceConfig(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(cfg)
    await session.flush()
    await session.refresh(cfg)
    return RemittanceConfigResponse.model_validate(cfg)


@router.patch("/configs/{config_id}", response_model=RemittanceConfigResponse)
async def update_config(
    config_id: str,
    body: RemittanceConfigUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(RemittanceConfig).where(RemittanceConfig.id == config_id, RemittanceConfig.tenant_id == user.tenant_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    await session.flush()
    await session.refresh(cfg)
    return RemittanceConfigResponse.model_validate(cfg)


@router.get("", response_model=PaginatedResponse[RemittanceStatementResponse])
async def list_statements(
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: str | None = Query(None, alias="status"),
    client_id: str | None = None,
):
    q = select(RemittanceStatement).where(RemittanceStatement.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(RemittanceStatement.status == status_filter)
    if client_id:
        q = q.where(RemittanceStatement.client_id == client_id)
    q = q.order_by(RemittanceStatement.created_at.desc())

    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).options(selectinload(RemittanceStatement.line_items)))
    items = [RemittanceStatementResponse.model_validate(r) for r in rows.scalars().all()]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{statement_id}", response_model=RemittanceStatementResponse)
async def get_statement(
    statement_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(RemittanceStatement)
        .where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
        .options(selectinload(RemittanceStatement.line_items))
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    return RemittanceStatementResponse.model_validate(stmt)


@router.post("", response_model=RemittanceStatementResponse, status_code=status.HTTP_201_CREATED)
async def create_statement(
    body: RemittanceStatementCreate,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    stmt = RemittanceStatement(**body.model_dump(), tenant_id=user.tenant_id, generated_by=user.id)
    session.add(stmt)
    await session.flush()
    await session.refresh(stmt)
    return RemittanceStatementResponse.model_validate(stmt)


@router.patch("/{statement_id}", response_model=RemittanceStatementResponse)
async def update_statement(
    statement_id: str,
    body: RemittanceStatementUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(RemittanceStatement).where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(stmt, k, v)
    await session.flush()
    await session.refresh(stmt)
    return RemittanceStatementResponse.model_validate(stmt)


@router.delete("/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_statement(
    statement_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(RemittanceStatement).where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    await session.delete(stmt)
    await session.flush()


@router.post("/{statement_id}/approve", response_model=RemittanceStatementResponse)
async def approve_statement(
    statement_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(RemittanceStatement).where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    stmt.status = RemittanceStatus.APPROVED
    stmt.approved_by = user.id
    stmt.approved_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(stmt)
    return RemittanceStatementResponse.model_validate(stmt)


@router.post("/{statement_id}/finalize", response_model=RemittanceStatementResponse)
async def finalize_statement(
    statement_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(RemittanceStatement).where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    if stmt.status != RemittanceStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Statement must be approved before finalizing")
    stmt.status = RemittanceStatus.FINALIZED
    stmt.finalized_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(stmt)
    return RemittanceStatementResponse.model_validate(stmt)


@router.post("/{statement_id}/items", response_model=RemittanceLineItemResponse, status_code=status.HTTP_201_CREATED)
async def add_line_item(
    statement_id: str,
    body: RemittanceLineItemCreate,
    user: Annotated[CurrentUser, Depends(require_permission("remittance:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(RemittanceStatement).where(RemittanceStatement.id == statement_id, RemittanceStatement.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Statement not found")
    item = RemittanceLineItem(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return RemittanceLineItemResponse.model_validate(item)
