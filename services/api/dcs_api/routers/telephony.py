"""Telephony endpoints — adapter capabilities, calls, dispositions, DIDs.

Layout:

* ``/adapters`` — UI catalog of every registered telephony adapter.
* ``/me`` — what the *current* tenant's active adapter can do.
* ``/click-to-call`` — agents kick off outbound through the active adapter.
* ``/calls`` — call history + per-call disposition setting.
* ``/dispositions`` — owners/admins manage the wrap-up code list.
* ``/phone-numbers`` — owners/admins manage the DID inventory.
* ``/webhooks/{adapter_id}`` — provider → DCS event ingest.

Configuration of the adapter itself (credentials, defaults) lives
in ``settings.telephony`` on the tenant and is exposed through
``/api/v1/tenants/{id}/telephony-config`` so we keep tenant-scoped
secrets in a single place (parallel to SSO).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.telephony import (
    Call,
    CallDirection,
    CallDisposition,
    CallEvent,
    CallEventType,
    CallStatus,
    PhoneNumber,
)
from dcs_api.models.tenant import Tenant
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.telephony import (
    CallDispositionAssign,
    CallDispositionCreate,
    CallDispositionResponse,
    CallDispositionUpdate,
    CallResponse,
    ClickToCallRequest,
    PhoneNumberCreate,
    PhoneNumberResponse,
    PhoneNumberUpdate,
    TelephonyAdapterDescriptorOut,
    TelephonyCapabilitiesOut,
    TelephonyMeResponse,
    TelephonyTenantConfig,
)
from dcs_api.telephony import (
    CallContext,
    TelephonyCapabilities,
    get_adapter,
    get_adapter_class,
    list_adapter_descriptors,
)

router = APIRouter()
MAX_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capabilities_to_out(c: TelephonyCapabilities) -> TelephonyCapabilitiesOut:
    return TelephonyCapabilitiesOut(
        click_to_call=c.click_to_call,
        inbound_screen_pop=c.inbound_screen_pop,
        server_recording=c.server_recording,
        realtime_events=c.realtime_events,
        presence=c.presence,
        softphone_in_app=c.softphone_in_app,
        sms=c.sms,
        fax=c.fax,
        dialer=c.dialer,
        requires_electron=c.requires_electron,
        requires_lan_bridge=c.requires_lan_bridge,
        notes=c.notes,
    )


async def _get_tenant_telephony_config(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TelephonyTenantConfig:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    raw = (tenant.settings or {}).get("telephony") or {}
    try:
        return TelephonyTenantConfig.model_validate(raw)
    except Exception:
        return TelephonyTenantConfig()


# ---------------------------------------------------------------------------
# Adapter catalog & capability discovery
# ---------------------------------------------------------------------------


@router.get("/adapters", response_model=list[TelephonyAdapterDescriptorOut])
async def list_adapters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[TelephonyAdapterDescriptorOut]:
    """Used by Settings → Telephony to render the provider picker."""
    out: list[TelephonyAdapterDescriptorOut] = []
    for d in list_adapter_descriptors():
        out.append(
            TelephonyAdapterDescriptorOut(
                id=d.id,
                label=d.label,
                family=d.family,
                capabilities=_capabilities_to_out(d.capabilities),
                config_schema=d.config_schema,
                docs_url=d.docs_url,
            )
        )
    return out


@router.get("/me", response_model=TelephonyMeResponse)
async def telephony_me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TelephonyMeResponse:
    """What the active adapter for *this user's* tenant can do.

    The softphone widget calls this on every page load so it can hide
    controls (recording toggle, dialer button, SMS panel) when the
    active adapter doesn't support them.
    """
    cfg = await _get_tenant_telephony_config(session, user.tenant_id)
    cls = get_adapter_class(cfg.adapter_id)
    if cls is None:
        return TelephonyMeResponse(
            adapter_id=cfg.adapter_id,
            configured=False,
            capabilities=_capabilities_to_out(TelephonyCapabilities()),
        )
    return TelephonyMeResponse(
        adapter_id=cfg.adapter_id,
        configured=cfg.adapter_id != "none",
        capabilities=_capabilities_to_out(cls.capabilities),
    )


@router.post("/test-connection")
async def test_connection(
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """The 'Test connection' button on the telephony settings tab."""
    cfg = await _get_tenant_telephony_config(session, user.tenant_id)
    adapter = get_adapter(cfg.adapter_id, str(user.tenant_id), cfg.provider_config)
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Unknown telephony adapter: {cfg.adapter_id}")
    return await adapter.healthcheck()


# ---------------------------------------------------------------------------
# Click-to-call
# ---------------------------------------------------------------------------


@router.post("/click-to-call", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def click_to_call(
    payload: ClickToCallRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Call:
    """Initiate an outbound call through the active adapter.

    Persists the canonical ``Call`` row first (so we always have an
    audit trail even if the provider call fails), then asks the
    adapter to dial. The adapter's returned SID is stored on the row.
    """
    cfg = await _get_tenant_telephony_config(session, user.tenant_id)
    adapter = get_adapter(cfg.adapter_id, str(user.tenant_id), cfg.provider_config)
    if adapter is None or not adapter.capabilities.click_to_call:
        raise HTTPException(
            status_code=400,
            detail="Active telephony adapter does not support click-to-call",
        )

    from_e164 = payload.from_e164 or cfg.default_outbound_caller_id

    call = Call(
        tenant_id=user.tenant_id,
        adapter_id=cfg.adapter_id,
        direction=CallDirection.OUTBOUND,
        status=CallStatus.QUEUED,
        from_e164=from_e164,
        to_e164=payload.to_e164,
        consumer_id=payload.consumer_id,
        account_id=payload.account_id,
        agent_user_id=user.user_id,
        queued_at=datetime.now(timezone.utc),
        notes=payload.note,
        recording_consent=False,
        raw_metadata={},
    )
    session.add(call)
    await session.flush()

    try:
        sid = await adapter.click_to_call(
            to_e164=payload.to_e164,
            from_e164=from_e164,
            ctx=CallContext(
                agent_user_id=str(user.user_id),
                consumer_id=str(payload.consumer_id) if payload.consumer_id else None,
                account_id=str(payload.account_id) if payload.account_id else None,
                note=payload.note,
            ),
        )
        call.provider_call_sid = sid
        call.status = CallStatus.INITIATED
        call.started_at = datetime.now(timezone.utc)
    except NotImplementedError as exc:
        call.status = CallStatus.FAILED
        call.notes = (call.notes or "") + f"\n[stub adapter] {exc}"
    except Exception as exc:  # noqa: BLE001
        call.status = CallStatus.FAILED
        call.notes = (call.notes or "") + f"\n[provider error] {exc}"

    session.add(
        CallEvent(
            tenant_id=user.tenant_id,
            call_id=call.id,
            event_type=CallEventType.DIAL_REQUESTED,
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=user.user_id,
            payload={"to_e164": payload.to_e164, "from_e164": from_e164},
        )
    )
    await session.commit()
    await session.refresh(call)
    return call


# ---------------------------------------------------------------------------
# Calls list / detail
# ---------------------------------------------------------------------------


@router.get("/calls", response_model=PaginatedResponse[CallResponse])
async def list_calls(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    consumer_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    agent_user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[CallResponse]:
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = select(Call).where(Call.tenant_id == user.tenant_id)
    if consumer_id:
        q = q.where(Call.consumer_id == consumer_id)
    if account_id:
        q = q.where(Call.account_id == account_id)
    if agent_user_id:
        q = q.where(Call.agent_user_id == agent_user_id)

    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (
        await session.execute(
            q.order_by(desc(Call.created_at)).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse[CallResponse](
        items=[CallResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/calls/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Call:
    call = (
        await session.execute(
            select(Call).where(Call.id == call_id, Call.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.post("/calls/{call_id}/disposition", response_model=CallResponse)
async def set_call_disposition(
    call_id: uuid.UUID,
    payload: CallDispositionAssign,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Call:
    call = (
        await session.execute(
            select(Call).where(Call.id == call_id, Call.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    disp = (
        await session.execute(
            select(CallDisposition).where(
                CallDisposition.id == payload.disposition_id,
                CallDisposition.tenant_id == user.tenant_id,
                CallDisposition.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disposition not found")

    if disp.requires_note and not (payload.notes or call.notes):
        raise HTTPException(status_code=400, detail="Disposition requires a note")

    call.disposition_id = disp.id
    if payload.notes:
        call.notes = payload.notes

    session.add(
        CallEvent(
            tenant_id=user.tenant_id,
            call_id=call.id,
            event_type=CallEventType.DISPOSITION_SET,
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=user.user_id,
            payload={"disposition_code": disp.code, "label": disp.label},
        )
    )
    await session.commit()
    await session.refresh(call)
    return call


# ---------------------------------------------------------------------------
# Disposition CRUD
# ---------------------------------------------------------------------------


@router.get("/dispositions", response_model=list[CallDispositionResponse])
async def list_dispositions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_inactive: bool = False,
) -> list[CallDisposition]:
    q = select(CallDisposition).where(CallDisposition.tenant_id == user.tenant_id)
    if not include_inactive:
        q = q.where(CallDisposition.is_active.is_(True))
    q = q.order_by(CallDisposition.sort_order, CallDisposition.code)
    return list((await session.execute(q)).scalars().all())


@router.post(
    "/dispositions",
    response_model=CallDispositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_disposition(
    payload: CallDispositionCreate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CallDisposition:
    disp = CallDisposition(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(disp)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Disposition code already exists")
    await session.refresh(disp)
    return disp


@router.patch("/dispositions/{disposition_id}", response_model=CallDispositionResponse)
async def update_disposition(
    disposition_id: uuid.UUID,
    payload: CallDispositionUpdate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CallDisposition:
    disp = (
        await session.execute(
            select(CallDisposition).where(
                CallDisposition.id == disposition_id,
                CallDisposition.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disposition not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(disp, k, v)
    await session.commit()
    await session.refresh(disp)
    return disp


@router.delete("/dispositions/{disposition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_disposition(
    disposition_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Soft-delete: keeps historical references but hides from pickers."""
    disp = (
        await session.execute(
            select(CallDisposition).where(
                CallDisposition.id == disposition_id,
                CallDisposition.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not disp:
        raise HTTPException(status_code=404, detail="Disposition not found")
    disp.is_active = False
    await session.commit()


# ---------------------------------------------------------------------------
# Phone-number CRUD
# ---------------------------------------------------------------------------


@router.get("/phone-numbers", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PhoneNumber]:
    q = (
        select(PhoneNumber)
        .where(PhoneNumber.tenant_id == user.tenant_id)
        .order_by(PhoneNumber.e164)
    )
    return list((await session.execute(q)).scalars().all())


@router.post(
    "/phone-numbers",
    response_model=PhoneNumberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_phone_number(
    payload: PhoneNumberCreate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhoneNumber:
    pn = PhoneNumber(
        tenant_id=user.tenant_id,
        e164=payload.e164,
        label=payload.label,
        adapter_id=payload.adapter_id,
        roles=[r.value for r in payload.roles],
        routing=payload.routing,
    )
    session.add(pn)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Phone number already configured for that adapter")
    await session.refresh(pn)
    return pn


@router.patch("/phone-numbers/{number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    number_id: uuid.UUID,
    payload: PhoneNumberUpdate,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhoneNumber:
    pn = (
        await session.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == number_id,
                PhoneNumber.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not pn:
        raise HTTPException(status_code=404, detail="Phone number not found")
    data = payload.model_dump(exclude_unset=True)
    if "roles" in data and data["roles"] is not None:
        data["roles"] = [r.value for r in data["roles"]]
    for k, v in data.items():
        setattr(pn, k, v)
    await session.commit()
    await session.refresh(pn)
    return pn


@router.delete("/phone-numbers/{number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    number_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_TELEPHONY))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    pn = (
        await session.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == number_id,
                PhoneNumber.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not pn:
        raise HTTPException(status_code=404, detail="Phone number not found")
    await session.delete(pn)
    await session.commit()


# Inbound provider webhooks live on the public intake router
# (``/api/v1/intake/telephony/{adapter}/{tenant_slug}``) so they can
# be reached without a tenant JWT. See ``routers/intake.py``.
