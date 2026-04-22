"""Flash message API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.flash_messages import AccountFlashMessage, FlashMessageTemplate
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.flash_messages import (
    AccountFlashMessageCreate,
    AccountFlashMessageResponse,
    FlashMessageTemplateCreate,
    FlashMessageTemplateResponse,
    FlashMessageTemplateUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("/templates", response_model=PaginatedResponse[FlashMessageTemplateResponse])
async def list_templates(
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(FlashMessageTemplate).where(FlashMessageTemplate.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(FlashMessageTemplate.created_at.desc()))
    items = [FlashMessageTemplateResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/templates/{template_id}", response_model=FlashMessageTemplateResponse)
async def get_template(
    template_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(FlashMessageTemplate).where(FlashMessageTemplate.id == template_id, FlashMessageTemplate.tenant_id == user.tenant_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return FlashMessageTemplateResponse.model_validate(tmpl)


@router.post("/templates", response_model=FlashMessageTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: FlashMessageTemplateCreate,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    tmpl = FlashMessageTemplate(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(tmpl)
    await session.flush()
    await session.refresh(tmpl)
    return FlashMessageTemplateResponse.model_validate(tmpl)


@router.patch("/templates/{template_id}", response_model=FlashMessageTemplateResponse)
async def update_template(
    template_id: str,
    body: FlashMessageTemplateUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(FlashMessageTemplate).where(FlashMessageTemplate.id == template_id, FlashMessageTemplate.tenant_id == user.tenant_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    await session.flush()
    await session.refresh(tmpl)
    return FlashMessageTemplateResponse.model_validate(tmpl)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(FlashMessageTemplate).where(FlashMessageTemplate.id == template_id, FlashMessageTemplate.tenant_id == user.tenant_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.delete(tmpl)
    await session.flush()


@router.get("", response_model=PaginatedResponse[AccountFlashMessageResponse])
async def list_account_alerts(
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
    active_only: bool = True,
):
    q = select(AccountFlashMessage).where(AccountFlashMessage.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(AccountFlashMessage.account_id == account_id)
    if active_only:
        q = q.where(AccountFlashMessage.is_active == True)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(AccountFlashMessage.created_at.desc()))
    items = [AccountFlashMessageResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("", response_model=AccountFlashMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AccountFlashMessageCreate,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    alert = AccountFlashMessage(**body.model_dump(), tenant_id=user.tenant_id, source="manual")
    session.add(alert)
    await session.flush()
    await session.refresh(alert)
    return AccountFlashMessageResponse.model_validate(alert)


@router.post("/{alert_id}/acknowledge", response_model=AccountFlashMessageResponse)
async def acknowledge_alert(
    alert_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("flash_messages:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(AccountFlashMessage).where(AccountFlashMessage.id == alert_id, AccountFlashMessage.tenant_id == user.tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(alert)
    return AccountFlashMessageResponse.model_validate(alert)
