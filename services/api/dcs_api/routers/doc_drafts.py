"""Document draft/approval workflow API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.documents import DocumentGeneration

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("")
async def list_drafts(
    user: Annotated[CurrentUser, Depends(require_permission("documents:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: str | None = Query(None, alias="status"),
):
    q = select(DocumentGeneration).where(DocumentGeneration.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(DocumentGeneration.status == status_filter)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(DocumentGeneration.created_at.desc()))
    items = [{"id": str(r.id), "tenant_id": str(r.tenant_id), "status": r.status, "created_at": str(r.created_at)} for r in rows.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}


@router.post("/{doc_id}/submit-for-review")
async def submit_for_review(
    doc_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("documents:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(DocumentGeneration).where(DocumentGeneration.id == doc_id, DocumentGeneration.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "pending_review"
    await session.flush()
    return {"status": "submitted_for_review", "id": str(doc.id)}


@router.post("/{doc_id}/approve")
async def approve_draft(
    doc_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("documents:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(DocumentGeneration).where(DocumentGeneration.id == doc_id, DocumentGeneration.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "approved"
    await session.flush()
    return {"status": "approved", "id": str(doc.id)}


@router.post("/{doc_id}/reject")
async def reject_draft(
    doc_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("documents:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(DocumentGeneration).where(DocumentGeneration.id == doc_id, DocumentGeneration.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "rejected"
    await session.flush()
    return {"status": "rejected", "id": str(doc.id)}
