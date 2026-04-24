"""Scan & Capture endpoints — scanner CRUD, jobs, intake, checks."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.scanning import (
    Check,
    CheckStatus,
    ScanJob,
    ScanJobStatus,
    Scanner,
    ScannerKind,
)
from dcs_api.scanning import (
    ScanAdapterDescriptor,
    ScanCapabilities,
    list_check_descriptors,
    list_document_descriptors,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.scanning import (
    CheckResponse,
    CheckUpdate,
    ScanAdapterDescriptorOut,
    ScanCapabilitiesOut,
    ScanJobResponse,
    ScannerCreate,
    ScannerResponse,
    ScannerUpdate,
    ScannerWithIntakeToken,
)

router = APIRouter()
MAX_PAGE_SIZE = 200


def _caps_to_out(c: ScanCapabilities) -> ScanCapabilitiesOut:
    return ScanCapabilitiesOut(
        duplex=c.duplex,
        color=c.color,
        multi_page=c.multi_page,
        auto_feeder=c.auto_feeder,
        barcode_detect=c.barcode_detect,
        blank_page_drop=c.blank_page_drop,
        ocr_inline=c.ocr_inline,
        micr_parse=c.micr_parse,
        endorse=c.endorse,
        image_quality_assurance=c.image_quality_assurance,
        requires_electron=c.requires_electron,
        notes=c.notes,
    )


def _desc_to_out(d: ScanAdapterDescriptor) -> ScanAdapterDescriptorOut:
    return ScanAdapterDescriptorOut(
        id=d.id,
        label=d.label,
        family=d.family,
        kind=d.kind,
        capabilities=_caps_to_out(d.capabilities),
        config_schema=d.config_schema,
        docs_url=d.docs_url,
    )


def _scanner_to_out(scanner: Scanner) -> ScannerResponse:
    base = ScannerResponse.model_validate(scanner)
    base.has_intake_token = bool(scanner.intake_token_hash)
    return base


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Adapter catalog
# ---------------------------------------------------------------------------


@router.get("/adapters/document", response_model=list[ScanAdapterDescriptorOut])
async def list_document_adapters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ScanAdapterDescriptorOut]:
    return [_desc_to_out(d) for d in list_document_descriptors()]


@router.get("/adapters/check", response_model=list[ScanAdapterDescriptorOut])
async def list_check_adapters(
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.HANDLE_CHECKS))],
) -> list[ScanAdapterDescriptorOut]:
    return [_desc_to_out(d) for d in list_check_descriptors()]


# ---------------------------------------------------------------------------
# Scanner CRUD
# ---------------------------------------------------------------------------


@router.get("/scanners", response_model=list[ScannerResponse])
async def list_scanners(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: ScannerKind | None = None,
    include_inactive: bool = False,
) -> list[ScannerResponse]:
    q = select(Scanner).where(Scanner.tenant_id == user.tenant_id)
    if kind:
        q = q.where(Scanner.kind == kind)
    if not include_inactive:
        q = q.where(Scanner.is_active.is_(True))
    rows = (await session.execute(q.order_by(Scanner.name))).scalars().all()
    return [_scanner_to_out(s) for s in rows]


@router.post(
    "/scanners",
    response_model=ScannerWithIntakeToken,
    status_code=status.HTTP_201_CREATED,
)
async def create_scanner(
    payload: ScannerCreate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_SCANNING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScannerWithIntakeToken:
    if payload.kind == ScannerKind.CHECK and not user.has_permission(Permissions.HANDLE_CHECKS):
        raise HTTPException(
            status_code=403,
            detail="Configuring check scanners requires the 'checks:handle' permission",
        )

    raw_token = secrets.token_urlsafe(32)
    scanner = Scanner(
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        location=payload.location,
        kind=payload.kind,
        transport=payload.transport,
        config=payload.config,
        intake_inbox_email=payload.intake_inbox_email,
        intake_token_hash=_hash_token(raw_token),
        deposit_account_id=payload.deposit_account_id,
        is_active=payload.is_active,
    )
    session.add(scanner)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Scanner name already exists")
    await session.refresh(scanner)

    out = ScannerWithIntakeToken.model_validate(scanner)
    out.has_intake_token = True
    out.intake_token = raw_token
    return out


@router.patch("/scanners/{scanner_id}", response_model=ScannerResponse)
async def update_scanner(
    scanner_id: uuid.UUID,
    payload: ScannerUpdate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_SCANNING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScannerResponse:
    scanner = (
        await session.execute(
            select(Scanner).where(
                Scanner.id == scanner_id, Scanner.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("kind") == ScannerKind.CHECK and not user.has_permission(Permissions.HANDLE_CHECKS):
        raise HTTPException(
            status_code=403,
            detail="Configuring check scanners requires the 'checks:handle' permission",
        )
    for k, v in data.items():
        setattr(scanner, k, v)
    await session.commit()
    await session.refresh(scanner)
    return _scanner_to_out(scanner)


@router.post("/scanners/{scanner_id}/rotate-token", response_model=ScannerWithIntakeToken)
async def rotate_intake_token(
    scanner_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_SCANNING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScannerWithIntakeToken:
    scanner = (
        await session.execute(
            select(Scanner).where(
                Scanner.id == scanner_id, Scanner.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")
    raw = secrets.token_urlsafe(32)
    scanner.intake_token_hash = _hash_token(raw)
    await session.commit()
    await session.refresh(scanner)
    out = ScannerWithIntakeToken.model_validate(scanner)
    out.has_intake_token = True
    out.intake_token = raw
    return out


@router.delete("/scanners/{scanner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scanner(
    scanner_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_SCANNING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    scanner = (
        await session.execute(
            select(Scanner).where(
                Scanner.id == scanner_id, Scanner.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner.is_active = False
    scanner.intake_token_hash = None
    await session.commit()


# ---------------------------------------------------------------------------
# Scan jobs
# ---------------------------------------------------------------------------


@router.get("/jobs", response_model=PaginatedResponse[ScanJobResponse])
async def list_scan_jobs(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    scanner_id: uuid.UUID | None = None,
    status_filter: ScanJobStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[ScanJobResponse]:
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = select(ScanJob).where(ScanJob.tenant_id == user.tenant_id)
    if scanner_id:
        q = q.where(ScanJob.scanner_id == scanner_id)
    if status_filter:
        q = q.where(ScanJob.status == status_filter)

    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            q.order_by(desc(ScanJob.created_at)).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse[ScanJobResponse](
        items=[ScanJobResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/jobs/{job_id}", response_model=ScanJobResponse)
async def get_scan_job(
    job_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScanJob:
    job = (
        await session.execute(
            select(ScanJob).where(ScanJob.id == job_id, ScanJob.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


# MFP intake lives on the public intake router so MFPs can call it
# without a tenant JWT (auth is the per-scanner intake token).
# See ``routers/intake.py``.


# ---------------------------------------------------------------------------
# Check pipeline
# ---------------------------------------------------------------------------


@router.get("/checks", response_model=PaginatedResponse[CheckResponse])
async def list_checks(
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.HANDLE_CHECKS))],
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: CheckStatus | None = None,
    account_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[CheckResponse]:
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = select(Check).where(Check.tenant_id == user.tenant_id)
    if status_filter:
        q = q.where(Check.status == status_filter)
    if account_id:
        q = q.where(Check.account_id == account_id)

    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            q.order_by(desc(Check.created_at)).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse[CheckResponse](
        items=[CheckResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/checks/{check_id}", response_model=CheckResponse)
async def get_check(
    check_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.HANDLE_CHECKS))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Check:
    chk = (
        await session.execute(
            select(Check).where(Check.id == check_id, Check.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not chk:
        raise HTTPException(status_code=404, detail="Check not found")
    return chk


@router.patch("/checks/{check_id}", response_model=CheckResponse)
async def update_check(
    check_id: uuid.UUID,
    payload: CheckUpdate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.HANDLE_CHECKS))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Check:
    chk = (
        await session.execute(
            select(Check).where(Check.id == check_id, Check.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not chk:
        raise HTTPException(status_code=404, detail="Check not found")
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status == CheckStatus.DEPOSITED and chk.status != CheckStatus.DEPOSITED:
        chk.deposited_at = datetime.now(timezone.utc)
    if new_status == CheckStatus.CLEARED and chk.status != CheckStatus.CLEARED:
        chk.cleared_at = datetime.now(timezone.utc)
    if new_status == CheckStatus.RETURNED and chk.status != CheckStatus.RETURNED:
        chk.returned_at = datetime.now(timezone.utc)
    for k, v in data.items():
        setattr(chk, k, v)
    await session.commit()
    await session.refresh(chk)
    return chk
