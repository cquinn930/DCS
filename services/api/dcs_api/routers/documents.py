"""Document templates, generation, and batch runs."""

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, AccountStatus
from dcs_api.models.documents import (
    DeliveryChannel,
    DocumentBatch,
    DocumentGeneration,
    DocumentTemplate,
    GenerationStatus,
)
from dcs_api.schemas.documents import (
    DocumentBatchCreate,
    DocumentBatchResponse,
    DocumentBatchUpdate,
    DocumentGenerationResponse,
    DocumentTemplateCreate,
    DocumentTemplateResponse,
    DocumentTemplateUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "documents:manage"


async def _get_template(
    session: AsyncSession, template_id: uuid.UUID, user: CurrentUser
) -> DocumentTemplate | None:
    q = select(DocumentTemplate).where(DocumentTemplate.id == template_id)
    if not user.is_master:
        q = q.where(DocumentTemplate.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


def _merge_field_map(account: Account, consumer: Any) -> dict[str, str]:
    name = f"{consumer.first_name or ''} {consumer.last_name or ''}".strip()
    return {
        "consumer.full_name": name,
        "consumer.first_name": consumer.first_name or "",
        "consumer.last_name": consumer.last_name or "",
        "account.account_reference": account.account_reference,
        "account.total_balance": str(account.total_balance),
        "account.status": account.status.value,
        "account.current_principal": str(account.current_principal),
        "account.current_interest": str(account.current_interest),
        "account.current_fees": str(account.current_fees),
    }


def _render_template(body: str, field_map: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1).strip()
        return field_map.get(key, m.group(0))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", repl, body)


class GenerateDocumentRequest(BaseModel):
    account_id: uuid.UUID
    channel: DeliveryChannel = DeliveryChannel.PRINT


# --- Templates ---


@router.get("/templates", response_model=PaginatedResponse[DocumentTemplateResponse])
async def list_document_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[DocumentTemplateResponse]:
    """List document templates."""
    count_q = select(func.count()).select_from(DocumentTemplate)
    if not user.is_master:
        count_q = count_q.where(DocumentTemplate.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(DocumentTemplate)
    if not user.is_master:
        q = q.where(DocumentTemplate.tenant_id == user.tenant_id)
    q = q.order_by(DocumentTemplate.code).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DocumentTemplateResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/templates/{template_id}", response_model=DocumentTemplateResponse)
async def get_document_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentTemplateResponse:
    """Get a document template by ID."""
    tpl = await _get_template(session, template_id, user)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return DocumentTemplateResponse.model_validate(tpl)


@router.post("/templates", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_document_template(
    data: DocumentTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentTemplateResponse:
    """Create a document template."""
    tpl = DocumentTemplate(
        tenant_id=user.tenant_id,
        code=data.code,
        name=data.name,
        description=data.description,
        category=data.category,
        template_format=data.template_format,
        subject=data.subject,
        body=data.body,
        header=data.header,
        footer=data.footer,
        merge_fields=data.merge_fields,
        pre_merge_script_id=data.pre_merge_script_id,
        version=data.version,
        is_active=data.is_active,
        is_system=data.is_system,
        config=data.config,
    )
    session.add(tpl)
    await session.flush()
    await session.refresh(tpl)
    return DocumentTemplateResponse.model_validate(tpl)


@router.patch("/templates/{template_id}", response_model=DocumentTemplateResponse)
async def update_document_template(
    template_id: uuid.UUID,
    data: DocumentTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentTemplateResponse:
    """Update a document template."""
    tpl = await _get_template(session, template_id, user)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tpl, k, v)
    await session.flush()
    return DocumentTemplateResponse.model_validate(tpl)


@router.post(
    "/templates/{template_id}/generate-for-account",
    response_model=DocumentGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_document_for_account(
    template_id: uuid.UUID,
    body: GenerateDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentGenerationResponse:
    """Generate a document for an account with merge fields resolved."""
    tpl = await _get_template(session, template_id, user)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    aq = (
        select(Account)
        .where(Account.id == body.account_id)
        .options(selectinload(Account.consumer))
    )
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    ar = await session.execute(aq)
    account = ar.scalar_one_or_none()
    if not account or not account.consumer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    field_map = _merge_field_map(account, account.consumer)
    rendered_body = _render_template(tpl.body, field_map)
    rendered_subject = _render_template(tpl.subject or "", field_map) if tpl.subject else None

    gen = DocumentGeneration(
        tenant_id=tpl.tenant_id,
        template_id=template_id,
        account_id=body.account_id,
        status=GenerationStatus.COMPLETED,
        channel=body.channel,
        rendered_subject=rendered_subject or None,
        rendered_body=rendered_body,
        merge_data=field_map,
        generated_at=datetime.now(timezone.utc),
        generated_by_id=user.user_id,
    )
    session.add(gen)
    await session.flush()
    await session.refresh(gen)
    return DocumentGenerationResponse.model_validate(gen)


# --- Batches ---


async def _get_batch(
    session: AsyncSession, batch_id: uuid.UUID, user: CurrentUser
) -> DocumentBatch | None:
    q = select(DocumentBatch).where(DocumentBatch.id == batch_id)
    if not user.is_master:
        q = q.where(DocumentBatch.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.post("/batches", response_model=DocumentBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_document_batch(
    data: DocumentBatchCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentBatchResponse:
    """Create a batch document generation run and enqueue generations from filter criteria."""
    tpl = await _get_template(session, data.template_id, user)
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    batch = DocumentBatch(
        tenant_id=tpl.tenant_id,
        name=data.name,
        template_id=data.template_id,
        filter_criteria=data.filter_criteria,
        total_accounts=0,
        completed_count=0,
        failed_count=0,
        status="generating",
        started_at=datetime.now(timezone.utc),
        started_by_id=user.user_id,
    )
    session.add(batch)
    await session.flush()

    aq = select(Account).where(Account.tenant_id == tpl.tenant_id).options(selectinload(Account.consumer))
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    status_filter = data.filter_criteria.get("status") if data.filter_criteria else None
    if status_filter:
        try:
            st = AccountStatus(status_filter)
            aq = aq.where(Account.status == st)
        except ValueError:
            pass
    accounts = list((await session.execute(aq)).scalars().all())
    batch.total_accounts = len(accounts)
    ok = 0
    fail = 0
    for acc_full in accounts:
        if not acc_full.consumer:
            fail += 1
            continue
        field_map = _merge_field_map(acc_full, acc_full.consumer)
        rendered_body = _render_template(tpl.body, field_map)
        rendered_subject = _render_template(tpl.subject or "", field_map) if tpl.subject else None
        gen = DocumentGeneration(
            tenant_id=tpl.tenant_id,
            template_id=data.template_id,
            account_id=acc_full.id,
            status=GenerationStatus.COMPLETED,
            channel=DeliveryChannel.PRINT,
            rendered_subject=rendered_subject or None,
            rendered_body=rendered_body,
            merge_data=field_map,
            generated_at=datetime.now(timezone.utc),
            generated_by_id=user.user_id,
            batch_id=batch.id,
        )
        session.add(gen)
        ok += 1
    batch.completed_count = ok
    batch.failed_count = fail
    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(batch)
    return DocumentBatchResponse.model_validate(batch)


@router.get("/batches", response_model=PaginatedResponse[DocumentBatchResponse])
async def list_document_batches(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[DocumentBatchResponse]:
    """List document batches."""
    count_q = select(func.count()).select_from(DocumentBatch)
    if not user.is_master:
        count_q = count_q.where(DocumentBatch.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(DocumentBatch)
    if not user.is_master:
        q = q.where(DocumentBatch.tenant_id == user.tenant_id)
    q = q.order_by(DocumentBatch.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DocumentBatchResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/batches/{batch_id}", response_model=DocumentBatchResponse)
async def get_document_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentBatchResponse:
    """Get a document batch by ID."""
    b = await _get_batch(session, batch_id, user)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return DocumentBatchResponse.model_validate(b)


@router.patch("/batches/{batch_id}", response_model=DocumentBatchResponse)
async def update_document_batch(
    batch_id: uuid.UUID,
    data: DocumentBatchUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentBatchResponse:
    """Update a document batch."""
    b = await _get_batch(session, batch_id, user)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    await session.flush()
    return DocumentBatchResponse.model_validate(b)


# --- Generations ---


@router.get("/generations", response_model=PaginatedResponse[DocumentGenerationResponse])
async def list_document_generations(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    account_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[DocumentGenerationResponse]:
    """List document generations."""
    count_q = select(func.count()).select_from(DocumentGeneration)
    if not user.is_master:
        count_q = count_q.where(DocumentGeneration.tenant_id == user.tenant_id)
    if account_id:
        count_q = count_q.where(DocumentGeneration.account_id == account_id)
    if batch_id:
        count_q = count_q.where(DocumentGeneration.batch_id == batch_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(DocumentGeneration)
    if not user.is_master:
        q = q.where(DocumentGeneration.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(DocumentGeneration.account_id == account_id)
    if batch_id:
        q = q.where(DocumentGeneration.batch_id == batch_id)
    q = q.order_by(DocumentGeneration.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DocumentGenerationResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/generations/{generation_id}", response_model=DocumentGenerationResponse)
async def get_document_generation(
    generation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> DocumentGenerationResponse:
    """Get a single document generation."""
    q = select(DocumentGeneration).where(DocumentGeneration.id == generation_id)
    if not user.is_master:
        q = q.where(DocumentGeneration.tenant_id == user.tenant_id)
    r = await session.execute(q)
    gen = r.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
    return DocumentGenerationResponse.model_validate(gen)
