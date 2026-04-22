"""Condition template API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.conditions import ConditionTemplate
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.conditions import (
    ConditionConvertRequest,
    ConditionConvertResponse,
    ConditionTemplateCreate,
    ConditionTemplateResponse,
    ConditionTemplateUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


def _convert_json_to_script(condition_json: dict) -> str:
    """Convert a visual condition JSON to DCS Script condition string."""
    rules = condition_json.get("rules", [])
    operator = condition_json.get("operator", "AND")
    parts = []
    for rule in rules:
        field = rule.get("field", "")
        op = rule.get("operator", "eq")
        value = rule.get("value", "")
        if op == "eq":
            parts.append(f'{field} == "{value}"')
        elif op == "neq":
            parts.append(f'{field} != "{value}"')
        elif op == "gt":
            parts.append(f"{field} > {value}")
        elif op == "gte":
            parts.append(f"{field} >= {value}")
        elif op == "lt":
            parts.append(f"{field} < {value}")
        elif op == "lte":
            parts.append(f"{field} <= {value}")
        elif op == "contains":
            parts.append(f'{field} LIKE "%{value}%"')
        elif op == "is_null":
            parts.append(f"{field} IS NULL")
        elif op == "not_null":
            parts.append(f"{field} IS NOT NULL")
        else:
            parts.append(f'{field} {op} "{value}"')
    joiner = f" {operator} "
    return joiner.join(parts) if parts else "TRUE"


@router.get("", response_model=PaginatedResponse[ConditionTemplateResponse])
async def list_conditions(
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    category: str | None = None,
):
    q = select(ConditionTemplate).where(ConditionTemplate.tenant_id == user.tenant_id)
    if category:
        q = q.where(ConditionTemplate.category == category)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(ConditionTemplate.name))
    items = [ConditionTemplateResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{condition_id}", response_model=ConditionTemplateResponse)
async def get_condition(
    condition_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ConditionTemplate).where(ConditionTemplate.id == condition_id, ConditionTemplate.tenant_id == user.tenant_id)
    )
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=404, detail="Condition not found")
    return ConditionTemplateResponse.model_validate(cond)


@router.post("", response_model=ConditionTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    body: ConditionTemplateCreate,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    script = body.condition_script or _convert_json_to_script(body.condition_json)
    cond = ConditionTemplate(**body.model_dump(exclude={"condition_script"}), condition_script=script, tenant_id=user.tenant_id)
    session.add(cond)
    await session.flush()
    await session.refresh(cond)
    return ConditionTemplateResponse.model_validate(cond)


@router.patch("/{condition_id}", response_model=ConditionTemplateResponse)
async def update_condition(
    condition_id: str,
    body: ConditionTemplateUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ConditionTemplate).where(ConditionTemplate.id == condition_id, ConditionTemplate.tenant_id == user.tenant_id)
    )
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=404, detail="Condition not found")
    updates = body.model_dump(exclude_unset=True)
    if "condition_json" in updates and "condition_script" not in updates:
        updates["condition_script"] = _convert_json_to_script(updates["condition_json"])
    for k, v in updates.items():
        setattr(cond, k, v)
    await session.flush()
    await session.refresh(cond)
    return ConditionTemplateResponse.model_validate(cond)


@router.delete("/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    condition_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ConditionTemplate).where(ConditionTemplate.id == condition_id, ConditionTemplate.tenant_id == user.tenant_id)
    )
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=404, detail="Condition not found")
    await session.delete(cond)
    await session.flush()


@router.post("/convert", response_model=ConditionConvertResponse)
async def convert_condition(
    body: ConditionConvertRequest,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
):
    try:
        script = _convert_json_to_script(body.condition_json)
        return ConditionConvertResponse(condition_script=script, valid=True)
    except Exception as e:
        return ConditionConvertResponse(condition_script="", valid=False, errors=[str(e)])
