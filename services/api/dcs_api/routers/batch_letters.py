"""Batch letter processing API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.batch_letters import BatchLetterConfig, BatchLetterRule
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.batch_letters import (
    BatchLetterConfigCreate,
    BatchLetterConfigResponse,
    BatchLetterConfigUpdate,
    BatchLetterRuleCreate,
    BatchLetterRuleResponse,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[BatchLetterConfigResponse])
async def list_configs(
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(BatchLetterConfig).where(BatchLetterConfig.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).options(selectinload(BatchLetterConfig.rules)).order_by(BatchLetterConfig.name))
    items = [BatchLetterConfigResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{config_id}", response_model=BatchLetterConfigResponse)
async def get_config(
    config_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(BatchLetterConfig).where(BatchLetterConfig.id == config_id, BatchLetterConfig.tenant_id == user.tenant_id)
        .options(selectinload(BatchLetterConfig.rules))
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return BatchLetterConfigResponse.model_validate(cfg)


@router.post("", response_model=BatchLetterConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    body: BatchLetterConfigCreate,
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    rules_data = body.rules
    cfg = BatchLetterConfig(**body.model_dump(exclude={"rules"}), tenant_id=user.tenant_id)
    session.add(cfg)
    await session.flush()
    for rule_data in rules_data:
        rule = BatchLetterRule(**rule_data.model_dump(), config_id=cfg.id, tenant_id=user.tenant_id)
        session.add(rule)
    await session.flush()
    result = await session.execute(
        select(BatchLetterConfig).where(BatchLetterConfig.id == cfg.id).options(selectinload(BatchLetterConfig.rules))
    )
    return BatchLetterConfigResponse.model_validate(result.scalar_one())


@router.patch("/{config_id}", response_model=BatchLetterConfigResponse)
async def update_config(
    config_id: str,
    body: BatchLetterConfigUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(BatchLetterConfig).where(BatchLetterConfig.id == config_id, BatchLetterConfig.tenant_id == user.tenant_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    await session.flush()
    await session.refresh(cfg)
    return BatchLetterConfigResponse.model_validate(cfg)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(BatchLetterConfig).where(BatchLetterConfig.id == config_id, BatchLetterConfig.tenant_id == user.tenant_id)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    await session.delete(cfg)
    await session.flush()


@router.post("/{config_id}/rules", response_model=BatchLetterRuleResponse, status_code=status.HTTP_201_CREATED)
async def add_rule(
    config_id: str,
    body: BatchLetterRuleCreate,
    user: Annotated[CurrentUser, Depends(require_permission("batch_letters:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(BatchLetterConfig).where(BatchLetterConfig.id == config_id, BatchLetterConfig.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Config not found")
    rule = BatchLetterRule(**body.model_dump(), config_id=config_id, tenant_id=user.tenant_id)
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return BatchLetterRuleResponse.model_validate(rule)
