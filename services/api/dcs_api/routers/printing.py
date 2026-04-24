"""Print & Mail endpoints — adapters, printers, jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.printing import (
    Printer,
    PrintJob,
    PrintJobStatus,
    PrintTarget,
)
from dcs_api.models.tenant import Tenant
from dcs_api.printing import (
    PrintAdapterDescriptor,
    PrintCapabilities,
    get_bureau_adapter,
    list_bureau_descriptors,
    list_local_descriptors,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.printing import (
    PrintAdapterDescriptorOut,
    PrintCapabilitiesOut,
    PrinterCreate,
    PrinterResponse,
    PrinterUpdate,
    PrintingTenantConfig,
    PrintJobCreate,
    PrintJobResponse,
    PrintMeResponse,
)

router = APIRouter()
MAX_PAGE_SIZE = 200


def _caps_to_out(c: PrintCapabilities) -> PrintCapabilitiesOut:
    return PrintCapabilitiesOut(
        duplex=c.duplex,
        color=c.color,
        certified_mail=c.certified_mail,
        bulk=c.bulk,
        silent=c.silent,
        address_validation=c.address_validation,
        return_envelope=c.return_envelope,
        tracking=c.tracking,
        paper_sizes=list(c.paper_sizes),
        requires_electron=c.requires_electron,
        notes=c.notes,
    )


def _desc_to_out(d: PrintAdapterDescriptor) -> PrintAdapterDescriptorOut:
    return PrintAdapterDescriptorOut(
        id=d.id,
        label=d.label,
        family=d.family,
        capabilities=_caps_to_out(d.capabilities),
        config_schema=d.config_schema,
        docs_url=d.docs_url,
    )


async def _get_printing_config(
    session: AsyncSession, tenant_id: uuid.UUID
) -> PrintingTenantConfig:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    raw = (tenant.settings or {}).get("printing") or {}
    try:
        return PrintingTenantConfig.model_validate(raw)
    except Exception:
        return PrintingTenantConfig()


# ---------------------------------------------------------------------------
# Adapter catalog
# ---------------------------------------------------------------------------


@router.get("/adapters/bureau", response_model=list[PrintAdapterDescriptorOut])
async def list_bureau_adapters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PrintAdapterDescriptorOut]:
    return [_desc_to_out(d) for d in list_bureau_descriptors()]


@router.get("/adapters/local", response_model=list[PrintAdapterDescriptorOut])
async def list_local_adapters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PrintAdapterDescriptorOut]:
    return [_desc_to_out(d) for d in list_local_descriptors()]


@router.get("/me", response_model=PrintMeResponse)
async def print_me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrintMeResponse:
    cfg = await _get_printing_config(session, user.tenant_id)
    bureau_caps: PrintCapabilitiesOut | None = None
    if cfg.bureau_adapter_id:
        for d in list_bureau_descriptors():
            if d.id == cfg.bureau_adapter_id:
                bureau_caps = _caps_to_out(d.capabilities)
                break
    return PrintMeResponse(
        bureau_adapter_id=cfg.bureau_adapter_id,
        bureau_configured=bool(cfg.bureau_adapter_id and cfg.bureau_config),
        local_default_printer_id=cfg.default_local_printer_id,
        bureau_capabilities=bureau_caps,
    )


@router.post("/test-bureau-connection")
async def test_bureau(
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_PRINTING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    cfg = await _get_printing_config(session, user.tenant_id)
    if not cfg.bureau_adapter_id:
        raise HTTPException(status_code=400, detail="No bureau provider configured")
    adapter = get_bureau_adapter(cfg.bureau_adapter_id, str(user.tenant_id), cfg.bureau_config)
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Unknown bureau adapter: {cfg.bureau_adapter_id}")
    return await adapter.healthcheck()


# ---------------------------------------------------------------------------
# Printer CRUD
# ---------------------------------------------------------------------------


@router.get("/printers", response_model=list[PrinterResponse])
async def list_printers(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_inactive: bool = False,
) -> list[Printer]:
    q = select(Printer).where(Printer.tenant_id == user.tenant_id)
    if not include_inactive:
        q = q.where(Printer.is_active.is_(True))
    return list((await session.execute(q.order_by(Printer.name))).scalars().all())


@router.post(
    "/printers",
    response_model=PrinterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_printer(
    payload: PrinterCreate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_PRINTING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Printer:
    if payload.is_default:
        await session.execute(
            update(Printer)
            .where(Printer.tenant_id == user.tenant_id, Printer.is_default.is_(True))
            .values(is_default=False)
        )
    printer = Printer(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(printer)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Printer name already exists")
    await session.refresh(printer)
    return printer


@router.patch("/printers/{printer_id}", response_model=PrinterResponse)
async def update_printer(
    printer_id: uuid.UUID,
    payload: PrinterUpdate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_PRINTING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Printer:
    printer = (
        await session.execute(
            select(Printer).where(
                Printer.id == printer_id, Printer.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default"):
        await session.execute(
            update(Printer)
            .where(Printer.tenant_id == user.tenant_id, Printer.is_default.is_(True))
            .values(is_default=False)
        )
    for k, v in data.items():
        setattr(printer, k, v)
    await session.commit()
    await session.refresh(printer)
    return printer


@router.delete("/printers/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer(
    printer_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_PRINTING))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    printer = (
        await session.execute(
            select(Printer).where(
                Printer.id == printer_id, Printer.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    printer.is_active = False
    await session.commit()


# ---------------------------------------------------------------------------
# Print jobs
# ---------------------------------------------------------------------------


@router.post(
    "/jobs",
    response_model=PrintJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_print_job(
    payload: PrintJobCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrintJob:
    if payload.target == PrintTarget.LOCAL and not payload.printer_id:
        raise HTTPException(status_code=400, detail="LOCAL print job requires printer_id")
    if payload.target == PrintTarget.BUREAU and not payload.bureau_provider:
        cfg = await _get_printing_config(session, user.tenant_id)
        if not cfg.bureau_adapter_id:
            raise HTTPException(
                status_code=400, detail="BUREAU print job requires bureau_provider or tenant default"
            )
        payload.bureau_provider = cfg.bureau_adapter_id

    job = PrintJob(
        tenant_id=user.tenant_id,
        target=payload.target,
        status=PrintJobStatus.QUEUED,
        document_id=payload.document_id,
        account_id=payload.account_id,
        consumer_id=payload.consumer_id,
        printer_id=payload.printer_id,
        bureau_provider=payload.bureau_provider,
        copies=payload.copies,
        options=payload.options,
        recipient=payload.recipient,
        requires_certified_mail=payload.requires_certified_mail,
        requested_by_id=user.user_id,
        raw_metadata={},
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.get("/jobs", response_model=PaginatedResponse[PrintJobResponse])
async def list_print_jobs(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    target: PrintTarget | None = None,
    status_filter: PrintJobStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[PrintJobResponse]:
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = select(PrintJob).where(PrintJob.tenant_id == user.tenant_id)
    if target:
        q = q.where(PrintJob.target == target)
    if status_filter:
        q = q.where(PrintJob.status == status_filter)

    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            q.order_by(desc(PrintJob.created_at)).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse[PrintJobResponse](
        items=[PrintJobResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/jobs/{job_id}", response_model=PrintJobResponse)
async def get_print_job(
    job_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrintJob:
    job = (
        await session.execute(
            select(PrintJob).where(PrintJob.id == job_id, PrintJob.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=PrintJobResponse)
async def cancel_print_job(
    job_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrintJob:
    job = (
        await session.execute(
            select(PrintJob).where(PrintJob.id == job_id, PrintJob.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")
    if job.status not in (PrintJobStatus.QUEUED, PrintJobStatus.SUBMITTED):
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel a job in status {job.status.value}"
        )
    job.status = PrintJobStatus.CANCELED
    job.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(job)
    return job


# Bureau status webhooks live on the public intake router so providers
# can call them without a tenant JWT. See ``routers/intake.py``.
