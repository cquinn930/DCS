"""Legal review checklist API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.reviews import AccountReview, AccountReviewItem, ReviewItemResult, ReviewStatus, ReviewTemplate, ReviewTemplateItem
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.reviews import (
    AccountReviewCreate,
    AccountReviewItemResponse,
    AccountReviewItemUpdate,
    AccountReviewResponse,
    ReviewTemplateCreate,
    ReviewTemplateResponse,
    ReviewTemplateUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("/templates", response_model=PaginatedResponse[ReviewTemplateResponse])
async def list_templates(
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(ReviewTemplate).where(ReviewTemplate.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).options(selectinload(ReviewTemplate.items)))
    items = [ReviewTemplateResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/templates", response_model=ReviewTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: ReviewTemplateCreate,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    items_data = body.items
    tmpl = ReviewTemplate(**body.model_dump(exclude={"items"}), tenant_id=user.tenant_id)
    session.add(tmpl)
    await session.flush()
    for item_data in items_data:
        item = ReviewTemplateItem(**item_data.model_dump(), template_id=tmpl.id, tenant_id=user.tenant_id)
        session.add(item)
    await session.flush()
    await session.refresh(tmpl)
    result = await session.execute(
        select(ReviewTemplate).where(ReviewTemplate.id == tmpl.id).options(selectinload(ReviewTemplate.items))
    )
    return ReviewTemplateResponse.model_validate(result.scalar_one())


@router.patch("/templates/{template_id}", response_model=ReviewTemplateResponse)
async def update_template(
    template_id: str,
    body: ReviewTemplateUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ReviewTemplate).where(ReviewTemplate.id == template_id, ReviewTemplate.tenant_id == user.tenant_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    await session.flush()
    await session.refresh(tmpl)
    return ReviewTemplateResponse.model_validate(tmpl)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ReviewTemplate).where(ReviewTemplate.id == template_id, ReviewTemplate.tenant_id == user.tenant_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.delete(tmpl)
    await session.flush()


@router.get("", response_model=PaginatedResponse[AccountReviewResponse])
async def list_reviews(
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    q = select(AccountReview).where(AccountReview.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(AccountReview.account_id == account_id)
    if status_filter:
        q = q.where(AccountReview.status == status_filter)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(AccountReview.created_at.desc()))
    items = [AccountReviewResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("", response_model=AccountReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    body: AccountReviewCreate,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    tmpl_result = await session.execute(
        select(ReviewTemplate).where(ReviewTemplate.id == body.template_id, ReviewTemplate.tenant_id == user.tenant_id)
        .options(selectinload(ReviewTemplate.items))
    )
    tmpl = tmpl_result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Review template not found")

    review = AccountReview(
        account_id=body.account_id,
        template_id=body.template_id,
        reviewer_id=user.id,
        status=ReviewStatus.IN_PROGRESS,
        started_at=datetime.now(timezone.utc),
        tenant_id=user.tenant_id,
    )
    session.add(review)
    await session.flush()

    for tmpl_item in tmpl.items:
        review_item = AccountReviewItem(
            review_id=review.id,
            template_item_id=tmpl_item.id,
            result=ReviewItemResult.PENDING,
            tenant_id=user.tenant_id,
        )
        session.add(review_item)
    await session.flush()
    await session.refresh(review)
    return AccountReviewResponse.model_validate(review)


@router.get("/{review_id}", response_model=AccountReviewResponse)
async def get_review(
    review_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(AccountReview).where(AccountReview.id == review_id, AccountReview.tenant_id == user.tenant_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return AccountReviewResponse.model_validate(review)


@router.get("/{review_id}/items", response_model=list[AccountReviewItemResponse])
async def get_review_items(
    review_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(AccountReviewItem).where(AccountReviewItem.review_id == review_id)
    )
    return [AccountReviewItemResponse.model_validate(r) for r in result.scalars().all()]


@router.patch("/{review_id}/items/{item_id}", response_model=AccountReviewItemResponse)
async def update_review_item(
    review_id: str,
    item_id: str,
    body: AccountReviewItemUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("reviews:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(AccountReviewItem).where(AccountReviewItem.id == item_id, AccountReviewItem.review_id == review_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.result = body.result
    item.fail_code = body.fail_code
    item.notes = body.notes
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(item)
    return AccountReviewItemResponse.model_validate(item)
