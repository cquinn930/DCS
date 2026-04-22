"""Audit trail API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.audit import AccountAccessLog, AuditConfig, LoginAuditLog
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.audit_trail import (
    AccountAccessLogResponse,
    AuditConfigCreate,
    AuditConfigResponse,
    AuditConfigUpdate,
    LoginAuditLogResponse,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("/access-logs", response_model=PaginatedResponse[AccountAccessLogResponse])
async def list_access_logs(
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
):
    q = select(AccountAccessLog).where(AccountAccessLog.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(AccountAccessLog.account_id == account_id)
    if user_id:
        q = q.where(AccountAccessLog.user_id == user_id)
    if action:
        q = q.where(AccountAccessLog.action == action)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(AccountAccessLog.created_at.desc()))
    items = [AccountAccessLogResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/login-logs", response_model=PaginatedResponse[LoginAuditLogResponse])
async def list_login_logs(
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    user_id: str | None = None,
):
    q = select(LoginAuditLog).where(LoginAuditLog.tenant_id == user.tenant_id)
    if user_id:
        q = q.where(LoginAuditLog.user_id == user_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(LoginAuditLog.created_at.desc()))
    items = [LoginAuditLogResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/configs", response_model=PaginatedResponse[AuditConfigResponse])
async def list_audit_configs(
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(AuditConfig).where(AuditConfig.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size))
    items = [AuditConfigResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/configs", response_model=AuditConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_config(
    body: AuditConfigCreate,
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    cfg = AuditConfig(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(cfg)
    await session.flush()
    await session.refresh(cfg)
    return AuditConfigResponse.model_validate(cfg)


@router.patch("/configs/{config_id}", response_model=AuditConfigResponse)
async def update_audit_config(
    config_id: str,
    body: AuditConfigUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(AuditConfig).where(AuditConfig.id == config_id, AuditConfig.tenant_id == user.tenant_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Audit config not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    await session.flush()
    await session.refresh(cfg)
    return AuditConfigResponse.model_validate(cfg)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_config(
    config_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("audit:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(AuditConfig).where(AuditConfig.id == config_id, AuditConfig.tenant_id == user.tenant_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Audit config not found")
    await session.delete(cfg)
    await session.flush()
