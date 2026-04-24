"""Telephony models — provider-agnostic call records and configuration.

Designed so a single tenant can swap between Vonage, Twilio, Microsoft
Teams (in any of its three CTI flavors), Asterisk/FreePBX/3CX, Cisco
UCM, or a generic SIP PBX without changing any downstream code. The
*adapter* layer (``dcs_api/telephony/adapters/``) translates the
provider's wire format into the canonical shape on these tables.

Per-provider credentials live in ``tenant.settings.telephony`` (see
``schemas/telephony.py``), not on a row here, so rotating a secret is
one PATCH and so we can support tenants who use *different* providers
for inbound vs outbound (a common Teams + Vonage split).
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class CallStatus(str, Enum):
    QUEUED = "queued"
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    CANCELED = "canceled"
    VOICEMAIL = "voicemail"


class CallEventType(str, Enum):
    """State transitions emitted by adapters into ``CallEvent``.

    Adapters are not required to emit every type — the canonical
    timeline is built from whatever the provider supports. Use
    ``TelephonyCapabilities.realtime_events`` to feature-flag UI that
    expects a live timeline.
    """

    DIAL_REQUESTED = "dial_requested"
    INBOUND_RECEIVED = "inbound_received"
    RINGING = "ringing"
    ANSWERED = "answered"
    HOLD = "hold"
    UNHOLD = "unhold"
    TRANSFER = "transfer"
    CONFERENCE = "conference"
    DTMF = "dtmf"
    HANGUP = "hangup"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    DISPOSITION_SET = "disposition_set"
    NOTE_ADDED = "note_added"
    PROVIDER_ERROR = "provider_error"


class PhoneNumberRole(str, Enum):
    """How a DID participates in routing.

    A single E.164 may carry multiple roles (a number used both for
    inbound consumer calls and for outbound caller-ID is common); we
    model that with a JSONB ``roles`` array rather than this enum, but
    keep the enum here for filtering and for the UI dropdown.
    """

    INBOUND = "inbound"
    OUTBOUND_CALLER_ID = "outbound_caller_id"
    SMS = "sms"
    FAX = "fax"


class Call(TenantScopedModel):
    """The canonical call record. One row per call leg owned by the agent.

    A provider's call SID lives in ``provider_call_sid`` and the
    provider name in ``adapter_id`` so we can correlate webhooks back
    to the right row when a tenant is running multiple adapters
    side-by-side.
    """

    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_call_account", "account_id"),
        Index("ix_call_consumer", "consumer_id"),
        Index("ix_call_agent", "agent_user_id"),
        Index("ix_call_started", "started_at"),
        Index("ix_call_provider_sid", "adapter_id", "provider_call_sid"),
    )

    adapter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_call_sid: Mapped[str | None] = mapped_column(String(255))

    direction: Mapped[CallDirection] = mapped_column(
        SQLEnum(CallDirection), nullable=False
    )
    status: Mapped[CallStatus] = mapped_column(
        SQLEnum(CallStatus), default=CallStatus.QUEUED, nullable=False
    )

    from_e164: Mapped[str | None] = mapped_column(String(32))
    to_e164: Mapped[str | None] = mapped_column(String(32))

    consumer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consumers.id", ondelete="SET NULL")
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL")
    )
    agent_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    cost_micros: Mapped[int | None] = mapped_column(Integer)

    disposition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_dispositions.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    recording_url: Mapped[str | None] = mapped_column(String(2048))
    recording_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recording_disclosed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    disposition: Mapped["CallDisposition | None"] = relationship(
        "CallDisposition", lazy="joined"
    )
    events: Mapped[list["CallEvent"]] = relationship(
        "CallEvent", back_populates="call", cascade="all, delete-orphan"
    )


class CallEvent(TenantScopedModel):
    """An ordered timeline of state changes for one ``Call``."""

    __tablename__ = "call_events"
    __table_args__ = (
        Index("ix_callevent_call", "call_id", "occurred_at"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[CallEventType] = mapped_column(
        SQLEnum(CallEventType), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="events")


class CallDisposition(TenantScopedModel):
    """Tenant-defined wrap-up code (RPC, NoContact, PromiseToPay, etc.).

    Owners/Admins manage the list from the Telephony settings tab so
    no SQL is required. Inactive rows are kept for historical
    reference but are hidden from new-disposition pickers.
    """

    __tablename__ = "call_dispositions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_disposition_code"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    is_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_rpc: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    triggers_followup_days: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)


class PhoneNumber(TenantScopedModel):
    """A DID owned by the tenant, mapped to one or more adapters/roles.

    Used for inbound webhook → tenant resolution and for selecting an
    appropriate caller-ID on outbound calls. Multiple adapters can
    share the same E.164 (e.g., Vonage rents the number, but the
    Asterisk dialplan also uses it for internal routing).
    """

    __tablename__ = "phone_numbers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "e164", "adapter_id", name="uq_phone_per_adapter"),
        Index("ix_phone_e164", "e164"),
    )

    e164: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    adapter_id: Mapped[str] = mapped_column(String(64), nullable=False)

    roles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    routing: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
