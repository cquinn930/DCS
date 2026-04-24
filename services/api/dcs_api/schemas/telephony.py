"""Telephony schemas — config, capabilities, calls, dispositions, DIDs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from dcs_api.models.telephony import (
    CallDirection,
    CallEventType,
    CallStatus,
    PhoneNumberRole,
)
from dcs_api.schemas.common import BaseSchema, TimestampSchema


# ---------------------------------------------------------------------------
# Tenant config (lives in tenant.settings.telephony)
# ---------------------------------------------------------------------------


class TelephonyTenantConfig(BaseModel):
    """Per-tenant telephony configuration.

    ``adapter_id`` selects the active adapter; ``provider_config`` is
    the free-form per-adapter dict whose shape is described by the
    adapter's ``config_schema``. The remaining fields are
    cross-adapter behaviors.
    """

    adapter_id: str = "none"
    provider_config: dict[str, Any] = Field(default_factory=dict)

    record_calls_default: bool = False
    require_recording_disclosure: bool = True
    recording_disclosure_text: str | None = None

    enforce_call_window_local: bool = True
    call_window_start_hour: int = Field(default=8, ge=0, le=23)
    call_window_end_hour: int = Field(default=21, ge=0, le=23)

    suppress_dnc: bool = True

    default_outbound_caller_id: str | None = None


class TelephonyTenantConfigUpdate(BaseModel):
    adapter_id: str | None = None
    provider_config: dict[str, Any] | None = None
    record_calls_default: bool | None = None
    require_recording_disclosure: bool | None = None
    recording_disclosure_text: str | None = None
    enforce_call_window_local: bool | None = None
    call_window_start_hour: int | None = Field(default=None, ge=0, le=23)
    call_window_end_hour: int | None = Field(default=None, ge=0, le=23)
    suppress_dnc: bool | None = None
    default_outbound_caller_id: str | None = None


# ---------------------------------------------------------------------------
# Capabilities + adapter catalog (UI uses these to render the picker)
# ---------------------------------------------------------------------------


class TelephonyCapabilitiesOut(BaseModel):
    click_to_call: bool
    inbound_screen_pop: bool
    server_recording: bool
    realtime_events: bool
    presence: bool
    softphone_in_app: bool
    sms: bool
    fax: bool
    dialer: Literal["none", "preview", "progressive", "predictive"]
    requires_electron: bool
    requires_lan_bridge: bool
    notes: str = ""


class TelephonyAdapterDescriptorOut(BaseModel):
    id: str
    label: str
    family: Literal["cloud", "microsoft_teams", "on_prem_pbx", "sip", "none"]
    capabilities: TelephonyCapabilitiesOut
    config_schema: dict[str, Any]
    docs_url: str | None = None


class TelephonyMeResponse(BaseModel):
    """Returned to the agent's softphone on page-load.

    ``capabilities`` reflects the *active* adapter so the UI can hide
    the Recording toggle on tellink, the Softphone tab on Teams Graph,
    etc. ``configured`` is False when ``adapter_id == 'none'``.
    """

    adapter_id: str
    configured: bool
    capabilities: TelephonyCapabilitiesOut


# ---------------------------------------------------------------------------
# Call dispositions (CRUD)
# ---------------------------------------------------------------------------


class CallDispositionCreate(BaseModel):
    code: str = Field(..., max_length=64)
    label: str = Field(..., max_length=255)
    description: str | None = None
    is_contact: bool = False
    is_rpc: bool = False
    requires_note: bool = False
    triggers_followup_days: int | None = Field(default=None, ge=0, le=365)
    sort_order: int = 100


class CallDispositionUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_contact: bool | None = None
    is_rpc: bool | None = None
    requires_note: bool | None = None
    triggers_followup_days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None
    sort_order: int | None = None


class CallDispositionResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    label: str
    description: str | None
    is_contact: bool
    is_rpc: bool
    requires_note: bool
    triggers_followup_days: int | None
    is_active: bool
    sort_order: int


# ---------------------------------------------------------------------------
# Phone numbers (CRUD)
# ---------------------------------------------------------------------------


class PhoneNumberCreate(BaseModel):
    e164: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")
    label: str | None = None
    adapter_id: str
    roles: list[PhoneNumberRole] = Field(default_factory=list)
    routing: dict[str, Any] = Field(default_factory=dict)


class PhoneNumberUpdate(BaseModel):
    label: str | None = None
    adapter_id: str | None = None
    roles: list[PhoneNumberRole] | None = None
    routing: dict[str, Any] | None = None
    is_active: bool | None = None


class PhoneNumberResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    e164: str
    label: str | None
    adapter_id: str
    roles: list[Any]
    routing: dict[str, Any]
    is_active: bool


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


class ClickToCallRequest(BaseModel):
    to_e164: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")
    from_e164: str | None = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")
    consumer_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    note: str | None = None


class CallEventResponse(BaseSchema):
    id: uuid.UUID
    event_type: CallEventType
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    payload: dict[str, Any]


class CallResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    adapter_id: str
    provider_call_sid: str | None
    direction: CallDirection
    status: CallStatus
    from_e164: str | None
    to_e164: str | None
    consumer_id: uuid.UUID | None
    account_id: uuid.UUID | None
    agent_user_id: uuid.UUID | None
    queued_at: datetime | None
    started_at: datetime | None
    answered_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    cost_micros: int | None
    disposition_id: uuid.UUID | None
    notes: str | None
    recording_url: str | None
    recording_consent: bool


class CallDispositionAssign(BaseModel):
    disposition_id: uuid.UUID
    notes: str | None = None
