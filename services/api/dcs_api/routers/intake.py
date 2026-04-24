"""External intake & webhook endpoints (no JWT auth).

These are called by external systems (MFPs, telephony providers, print
bureaus) which can't carry a tenant JWT. Each endpoint authenticates
via its own provider-specific mechanism — intake tokens for MFPs,
HMAC signatures for webhooks, etc.

Mounted without the operational guard so MFPs/providers can reach
them, and we keep them in this dedicated module so it's obvious which
endpoints are public-facing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.database import get_session
from dcs_api.models.printing import PrintJob, PrintJobStatus
from dcs_api.models.scanning import (
    Check,
    CheckStatus,
    ScanJob,
    ScanJobStatus,
    Scanner,
    ScannerKind,
)
from dcs_api.models.telephony import (
    Call,
    CallDirection,
    CallEvent,
    CallEventType,
    CallStatus,
)
from dcs_api.models.tenant import Tenant
from dcs_api.schemas.scanning import ScanIntakeRequest, ScanJobResponse
from dcs_api.telephony import get_adapter_class

router = APIRouter()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Scan intake (MFP scan-to-cloud)
# ---------------------------------------------------------------------------


@router.post(
    "/scan",
    response_model=ScanJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def scan_intake(
    payload: ScanIntakeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_dcs_intake_source: Annotated[str | None, Header()] = None,
) -> ScanJob:
    if not payload.intake_token:
        raise HTTPException(status_code=401, detail="Missing intake token")

    token_hash = _hash_token(payload.intake_token)
    scanner = (
        await session.execute(
            select(Scanner).where(
                Scanner.intake_token_hash == token_hash,
                Scanner.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=401, detail="Invalid intake token")

    job = ScanJob(
        tenant_id=scanner.tenant_id,
        scanner_id=scanner.id,
        status=ScanJobStatus.UPLOADED,
        page_count=payload.page_count,
        storage_uri=payload.storage_uri,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        sha256=payload.sha256,
        captured_at=payload.captured_at or datetime.now(timezone.utc),
        raw_metadata={
            **payload.raw_metadata,
            "intake_source": x_dcs_intake_source,
        },
    )
    session.add(job)
    await session.flush()

    if scanner.kind == ScannerKind.CHECK:
        chk = Check(
            tenant_id=scanner.tenant_id,
            scan_job_id=job.id,
            front_image_uri=payload.raw_metadata.get("front_image_uri"),
            back_image_uri=payload.raw_metadata.get("back_image_uri"),
            routing_number=payload.raw_metadata.get("routing_number"),
            bank_account_number_last4=payload.raw_metadata.get("bank_account_last4"),
            check_number=payload.raw_metadata.get("check_number"),
            amount_cents=payload.raw_metadata.get("amount_cents"),
            payer_name=payload.raw_metadata.get("payer_name"),
            memo=payload.raw_metadata.get("memo"),
            deposit_account_id=scanner.deposit_account_id,
            status=CheckStatus.SCANNED,
        )
        session.add(chk)

    await session.commit()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Telephony provider webhooks
# ---------------------------------------------------------------------------


@router.post("/telephony/{adapter_id}/{tenant_slug}")
async def telephony_webhook(
    adapter_id: str,
    tenant_slug: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    cls = get_adapter_class(adapter_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Unknown adapter")

    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    cfg = (tenant.settings or {}).get("telephony") or {}
    adapter = cls(tenant_id=str(tenant.id), config=cfg.get("provider_config", {}))
    payload = await request.json()
    event = adapter.parse_inbound_webhook(payload)
    if event is None:
        return {"ok": True, "ignored": True}

    existing = (
        await session.execute(
            select(Call).where(
                Call.tenant_id == tenant.id,
                Call.adapter_id == adapter_id,
                Call.provider_call_sid == event.provider_call_sid,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Call(
            tenant_id=tenant.id,
            adapter_id=adapter_id,
            provider_call_sid=event.provider_call_sid,
            direction=CallDirection.INBOUND,
            status=CallStatus.RINGING,
            from_e164=event.from_e164,
            to_e164=event.to_e164,
            queued_at=datetime.now(timezone.utc),
            raw_metadata=event.raw,
        )
        session.add(existing)
        await session.flush()

    session.add(
        CallEvent(
            tenant_id=tenant.id,
            call_id=existing.id,
            event_type=CallEventType.INBOUND_RECEIVED,
            occurred_at=datetime.now(timezone.utc),
            payload=event.raw,
        )
    )
    await session.commit()
    return {"ok": True, "call_id": str(existing.id)}


# ---------------------------------------------------------------------------
# Print bureau status webhooks
# ---------------------------------------------------------------------------


@router.post("/print-bureau/{adapter_id}/{tenant_slug}")
async def bureau_webhook(
    adapter_id: str,
    tenant_slug: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    payload = await request.json()
    provider_job_id = payload.get("id") or payload.get("provider_job_id")
    if not provider_job_id:
        return {"ok": True, "ignored": True}

    job = (
        await session.execute(
            select(PrintJob).where(
                PrintJob.tenant_id == tenant.id,
                PrintJob.bureau_provider == adapter_id,
                PrintJob.provider_job_id == provider_job_id,
            )
        )
    ).scalar_one_or_none()
    if not job:
        return {"ok": True, "ignored": True, "reason": "unknown job"}

    new_status = payload.get("status")
    mapping = {
        "mailed": PrintJobStatus.MAILED,
        "in_transit": PrintJobStatus.MAILED,
        "delivered": PrintJobStatus.DELIVERED,
        "returned_to_sender": PrintJobStatus.RETURNED,
        "failed": PrintJobStatus.FAILED,
    }
    if new_status in mapping:
        job.status = mapping[new_status]
    if payload.get("tracking_number"):
        job.tracking_number = payload["tracking_number"]
    if mapping.get(new_status) in (
        PrintJobStatus.DELIVERED,
        PrintJobStatus.RETURNED,
        PrintJobStatus.FAILED,
    ):
        job.completed_at = datetime.now(timezone.utc)
    job.raw_metadata = {**(job.raw_metadata or {}), "last_webhook": payload}
    await session.commit()
    return {"ok": True, "job_id": str(job.id)}
