"""Compliance engine.

Centralizes the runtime checks required before any outbound contact, dispute
response, validation-notice send, or balance change. Federal floor is the
FDCPA (15 U.S.C. § 1692 et seq.) plus CFPB Regulation F (12 C.F.R. Part 1006).
Jurisdiction-specific overlays come from the active PolicyPack for the
account's `jurisdiction` field.

Key contracts:
  - `evaluate_contact_attempt(...)` returns a `ContactDecision` describing
    whether an outbound contact is permitted *right now* and, if not, why.
  - `evaluate_account_compliance(...)` returns a multi-rule snapshot for
    dashboards (validation window, holds, SOL, suppression, missing consent).
  - `record_consent(...)` / `revoke_consent(...)` / `add_suppression(...)`
    are write helpers that the API/automation layer should funnel through.

All failures attach the controlling source (FDCPA/Reg F section, NJ rule,
NY CPLR section, etc.) so audit logs are defensible.

Non-legal guidance: This module assists with compliance but does not
guarantee it. Verify outputs against current law and qualified counsel.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.account import Account, AccountStatus
from dcs_api.models.compliance import (
    DebtCategory,
    PolicyPack,
    PolicyPackStatus,
    StatuteOfLimitationsRule,
    UsuryRule,
)
from dcs_api.models.consumer import (
    Consent,
    ConsentChannel,
    ConsentStatus,
    Consumer,
    SuppressionEntry,
    SuppressionType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel taxonomy
# ---------------------------------------------------------------------------

class ContactChannel(str, Enum):
    """Outbound contact channels evaluated by the engine."""

    VOICE_AUTODIALED = "voice_autodialed"  # TCPA prior-express-written-consent required
    VOICE_MANUAL = "voice_manual"          # Live agent dial
    SMS = "sms"                            # TCPA + Reg F E-Sign
    EMAIL = "email"                        # Reg F § 1006.6(d) opt-out + § 1006.42
    LETTER = "letter"                      # Postal mail


# Channels for which the TCPA requires prior express written consent.
TCPA_RESTRICTED_CHANNELS: frozenset[ContactChannel] = frozenset(
    {ContactChannel.VOICE_AUTODIALED, ContactChannel.SMS}
)

# Reg F § 1006.14(b) governs telephone-call frequency; counts apply to
# voice channels only.
PHONE_FREQUENCY_CHANNELS: frozenset[ContactChannel] = frozenset(
    {ContactChannel.VOICE_AUTODIALED, ContactChannel.VOICE_MANUAL}
)


# Map ContactChannel -> the SuppressionType that blocks it.
SUPPRESSION_BLOCKERS: dict[ContactChannel, frozenset[SuppressionType]] = {
    ContactChannel.VOICE_AUTODIALED: frozenset(
        {SuppressionType.DO_NOT_CALL, SuppressionType.DO_NOT_CONTACT,
         SuppressionType.CEASE_AND_DESIST}
    ),
    ContactChannel.VOICE_MANUAL: frozenset(
        {SuppressionType.DO_NOT_CALL, SuppressionType.DO_NOT_CONTACT,
         SuppressionType.CEASE_AND_DESIST}
    ),
    ContactChannel.SMS: frozenset(
        {SuppressionType.DO_NOT_TEXT, SuppressionType.DO_NOT_CONTACT,
         SuppressionType.CEASE_AND_DESIST}
    ),
    ContactChannel.EMAIL: frozenset(
        {SuppressionType.DO_NOT_EMAIL, SuppressionType.DO_NOT_CONTACT,
         SuppressionType.CEASE_AND_DESIST}
    ),
    ContactChannel.LETTER: frozenset(
        {SuppressionType.DO_NOT_CONTACT, SuppressionType.CEASE_AND_DESIST}
    ),
}

# Map ContactChannel -> the ConsentChannel record that satisfies it.
CHANNEL_TO_CONSENT: dict[ContactChannel, ConsentChannel] = {
    ContactChannel.VOICE_AUTODIALED: ConsentChannel.VOICE_AUTODIALED,
    ContactChannel.VOICE_MANUAL: ConsentChannel.VOICE_MANUAL,
    ContactChannel.SMS: ConsentChannel.SMS,
    ContactChannel.EMAIL: ConsentChannel.EMAIL,
}


# ---------------------------------------------------------------------------
# Decision result types
# ---------------------------------------------------------------------------

class BlockReason(str, Enum):
    """Why an outbound contact was blocked."""

    OUTSIDE_CONTACT_WINDOW = "outside_contact_window"          # FDCPA § 1692c(a)(1)
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    WEEKLY_LIMIT_EXCEEDED = "weekly_limit_exceeded"            # Reg F § 1006.14(b)
    SUPPRESSED = "suppressed"
    MISSING_TCPA_CONSENT = "missing_tcpa_consent"              # 47 U.S.C. § 227
    LEGAL_HOLD = "legal_hold"
    BREACH_LOCKDOWN = "breach_lockdown"
    ACCOUNT_INACTIVE = "account_inactive"
    DISPUTE_OPEN = "dispute_open"                              # § 1006.38(d)
    POLICY_PACK_MISSING = "policy_pack_missing"


@dataclass
class BlockEvidence:
    """One blocking finding."""

    reason: BlockReason
    detail: str
    source: str  # statute / rule citation


@dataclass
class ContactDecision:
    """Result of evaluating an outbound-contact request."""

    allowed: bool
    channel: ContactChannel
    blocks: list[BlockEvidence] = field(default_factory=list)
    policy_pack_id: uuid.UUID | None = None
    policy_pack_version: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_audit_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "channel": self.channel.value,
            "blocks": [
                {"reason": b.reason.value, "detail": b.detail, "source": b.source}
                for b in self.blocks
            ],
            "policy_pack_id": str(self.policy_pack_id) if self.policy_pack_id else None,
            "policy_pack_version": self.policy_pack_version,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class AccountComplianceSnapshot:
    """Multi-rule view used for account dashboards / pre-call screens."""

    account_id: uuid.UUID
    jurisdiction: str
    on_legal_hold: bool
    legal_hold_reason: str | None
    validation_notice_sent: bool
    in_validation_window: bool         # Within § 1692g 30-day dispute window
    open_dispute: bool
    sol_status: str                    # "in_sol" | "near_sol" | "time_barred" | "unknown"
    sol_years: int | None
    sol_citation: str | None
    contact_window_local: tuple[str, str]
    daily_contacts_used: int
    weekly_contacts_used: int
    suppression_active: list[str]      # SuppressionType values
    consent_present: dict[str, bool]   # ConsentChannel.value -> bool
    policy_pack_version: str | None
    blocks: list[BlockEvidence]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Policy pack loader (small in-process cache)
# ---------------------------------------------------------------------------

_PACK_CACHE_TTL = timedelta(minutes=5)
_pack_cache: dict[str, tuple[datetime, PolicyPack]] = {}


async def load_active_policy_pack(
    session: AsyncSession, jurisdiction: str
) -> PolicyPack | None:
    """Fetch the ACTIVE policy pack for a jurisdiction (case-insensitive)."""
    juris = (jurisdiction or "").upper()[:2]
    if not juris:
        return None

    cached = _pack_cache.get(juris)
    now = datetime.now(timezone.utc)
    if cached and now - cached[0] < _PACK_CACHE_TTL:
        return cached[1]

    result = await session.execute(
        select(PolicyPack).where(
            PolicyPack.jurisdiction == juris,
            PolicyPack.status == PolicyPackStatus.ACTIVE,
        )
    )
    pack = result.scalar_one_or_none()
    if pack is not None:
        _pack_cache[juris] = (now, pack)
    return pack


def invalidate_pack_cache(jurisdiction: str | None = None) -> None:
    """Drop the cached ACTIVE pack(s). Call after policy-pack publishes."""
    if jurisdiction is None:
        _pack_cache.clear()
    else:
        _pack_cache.pop(jurisdiction.upper()[:2], None)


# ---------------------------------------------------------------------------
# Contact-rule helpers
# ---------------------------------------------------------------------------

# FDCPA defaults if no policy pack is found. These are the federal floor.
FEDERAL_DEFAULT_CONTACT_WINDOW = (time(8, 0), time(21, 0))  # § 1692c(a)(1)
FEDERAL_DEFAULT_MAX_DAILY_CONTACTS = 1
FEDERAL_DEFAULT_MAX_WEEKLY_CONTACTS = 7  # Reg F § 1006.14(b)(2)(i)


def _parse_window(start_str: str, end_str: str) -> tuple[time, time]:
    try:
        start = time.fromisoformat(start_str)
        end = time.fromisoformat(end_str)
    except (TypeError, ValueError):
        return FEDERAL_DEFAULT_CONTACT_WINDOW
    return start, end


def _within_window(now_local: datetime, window: tuple[time, time]) -> bool:
    start, end = window
    cur = now_local.time()
    if start <= end:
        return start <= cur <= end
    # window crosses midnight (unusual but be defensive)
    return cur >= start or cur <= end


async def _count_recent_contacts(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    since: datetime,
    channels: Iterable[ContactChannel],
) -> int:
    """Count prior contact attempts for an account in the time window.

    Uses the Notice table as the system of record for outbound communications
    that have been sent. If the deployment uses a separate `contact_attempts`
    table, swap the query here.
    """
    from dcs_api.models.account import Notice, NoticeStatus

    channel_values = {c.value for c in channels}
    if not channel_values:
        return 0

    query = (
        select(func.count())
        .select_from(Notice)
        .where(
            Notice.account_id == account_id,
            Notice.channel.in_(channel_values),
            Notice.status.in_([NoticeStatus.SENT, NoticeStatus.DELIVERED]),
            Notice.sent_at.isnot(None),
            Notice.sent_at >= since,
        )
    )
    result = await session.execute(query)
    return int(result.scalar_one() or 0)


async def _has_unresolved_dispute(
    session: AsyncSession, account_id: uuid.UUID
) -> bool:
    """True if the account has an open dispute that should pause contact."""
    # Lazy import to avoid a circular import; Dispute lives in models.account
    # in current codebase but may move; we resolve dynamically.
    try:
        from dcs_api.models.account import Dispute, DisputeStatus
    except ImportError:
        return False

    open_states = {
        getattr(DisputeStatus, n)
        for n in ("PENDING", "OPEN", "UNDER_REVIEW", "RECEIVED")
        if hasattr(DisputeStatus, n)
    }
    if not open_states:
        return False

    result = await session.execute(
        select(func.count())
        .select_from(Dispute)
        .where(
            Dispute.account_id == account_id,
            Dispute.status.in_([s for s in open_states]),
        )
    )
    return int(result.scalar_one() or 0) > 0


async def _consent_present(
    session: AsyncSession,
    *,
    consumer_id: uuid.UUID,
    channel: ConsentChannel,
    scope_value: str | None,
) -> bool:
    """True iff a current GRANTED consent exists for the channel + scope."""
    now = datetime.now(timezone.utc)
    query = select(Consent).where(
        Consent.consumer_id == consumer_id,
        Consent.channel == channel,
        Consent.status == ConsentStatus.GRANTED,
    )
    result = await session.execute(query)
    rows = list(result.scalars())
    for c in rows:
        if c.expires_at is not None and c.expires_at <= now:
            continue
        if scope_value and c.scope_value and c.scope_value != scope_value:
            continue
        return True
    return False


async def _active_suppressions(
    session: AsyncSession,
    *,
    consumer_id: uuid.UUID,
    value: str | None,
) -> list[SuppressionEntry]:
    """Return active SuppressionEntry rows touching the consumer."""
    now = datetime.now(timezone.utc)
    query = select(SuppressionEntry).where(
        SuppressionEntry.consumer_id == consumer_id,
        SuppressionEntry.is_active.is_(True),
    )
    result = await session.execute(query)
    out: list[SuppressionEntry] = []
    for entry in result.scalars():
        if entry.expires_at is not None and entry.expires_at <= now:
            continue
        # If the entry targets a specific value, require exact match;
        # otherwise it suppresses for the whole consumer.
        if entry.value and value and entry.value != value:
            continue
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Public engine API
# ---------------------------------------------------------------------------

async def evaluate_contact_attempt(
    session: AsyncSession,
    *,
    account: Account,
    consumer: Consumer,
    channel: ContactChannel,
    target_value: str | None = None,
    now: datetime | None = None,
    consumer_local_now: datetime | None = None,
) -> ContactDecision:
    """Decide whether a single outbound contact attempt is permitted.

    Parameters
    ----------
    target_value
        For phone/SMS: the destination number. For email: the address. Used
        to scope suppression / consent matching and recorded in the audit
        decision. Optional; when omitted, consumer-wide suppression still
        applies.
    consumer_local_now
        Caller may pre-localize "now" to the consumer's home time zone.
        When omitted, UTC now is used. NOTE: localize before calling for
        accurate FDCPA § 1692c(a)(1) enforcement.
    """
    now = now or datetime.now(timezone.utc)
    local_now = consumer_local_now or now

    pack = await load_active_policy_pack(session, account.jurisdiction)
    blocks: list[BlockEvidence] = []

    if pack is None:
        blocks.append(
            BlockEvidence(
                BlockReason.POLICY_PACK_MISSING,
                f"No ACTIVE policy pack for jurisdiction {account.jurisdiction}.",
                "Operational requirement",
            )
        )
        # Fall through using federal defaults so we still apply hard floors.
        window = FEDERAL_DEFAULT_CONTACT_WINDOW
        max_daily = FEDERAL_DEFAULT_MAX_DAILY_CONTACTS
        max_weekly = FEDERAL_DEFAULT_MAX_WEEKLY_CONTACTS
    else:
        window = _parse_window(pack.contact_window_start, pack.contact_window_end)
        max_daily = pack.max_daily_contacts or FEDERAL_DEFAULT_MAX_DAILY_CONTACTS
        max_weekly = pack.max_weekly_contacts or FEDERAL_DEFAULT_MAX_WEEKLY_CONTACTS

    # 1. Account / consumer status gates
    if account.status == AccountStatus.LEGAL_HOLD or account.legal_hold:
        blocks.append(
            BlockEvidence(
                BlockReason.LEGAL_HOLD,
                f"Account {account.id} is on legal hold "
                f"({account.legal_hold_reason or 'no reason recorded'}).",
                "Internal policy / litigation hold",
            )
        )
    if consumer.legal_hold:
        blocks.append(
            BlockEvidence(
                BlockReason.LEGAL_HOLD,
                f"Consumer {consumer.id} is on legal hold "
                f"({consumer.legal_hold_reason or 'no reason recorded'}).",
                "Internal policy / litigation hold",
            )
        )
    if account.status in (
        AccountStatus.PAID_IN_FULL,
        AccountStatus.SETTLED,
        AccountStatus.CLOSED,
        AccountStatus.RECALLED,
        AccountStatus.STATUTE_BARRED,
    ):
        blocks.append(
            BlockEvidence(
                BlockReason.ACCOUNT_INACTIVE,
                f"Account status is {account.status.value}.",
                "Internal policy",
            )
        )

    # 2. Open dispute pauses outbound under § 1006.38(d) until verification
    if await _has_unresolved_dispute(session, account.id):
        blocks.append(
            BlockEvidence(
                BlockReason.DISPUTE_OPEN,
                "Open dispute on account; verification required before "
                "further collection activity.",
                "12 C.F.R. § 1006.38(d); 15 U.S.C. § 1692g(b)",
            )
        )

    # 3. Time-of-day window — FDCPA § 1692c(a)(1) presumes 8am-9pm consumer-local
    if not _within_window(local_now, window):
        blocks.append(
            BlockEvidence(
                BlockReason.OUTSIDE_CONTACT_WINDOW,
                f"Local time {local_now.time().isoformat()} outside permitted "
                f"window {window[0].isoformat()}-{window[1].isoformat()}.",
                "15 U.S.C. § 1692c(a)(1); 12 C.F.R. § 1006.6(b)(1)",
            )
        )

    # 4. Suppression list
    suppressions = await _active_suppressions(
        session, consumer_id=consumer.id, value=target_value
    )
    blocking_types = SUPPRESSION_BLOCKERS.get(channel, frozenset())
    for entry in suppressions:
        if entry.suppression_type in blocking_types:
            blocks.append(
                BlockEvidence(
                    BlockReason.SUPPRESSED,
                    f"Suppression entry {entry.id} ({entry.suppression_type.value}) "
                    f"blocks {channel.value}.",
                    (
                        "15 U.S.C. § 1692c(c) (cease) / "
                        "12 C.F.R. § 1006.6(c) (opt-out)"
                    ),
                )
            )

    # 5. TCPA consent for autodialed voice + SMS
    if channel in TCPA_RESTRICTED_CHANNELS:
        consent_channel = CHANNEL_TO_CONSENT[channel]
        if not await _consent_present(
            session,
            consumer_id=consumer.id,
            channel=consent_channel,
            scope_value=target_value,
        ):
            blocks.append(
                BlockEvidence(
                    BlockReason.MISSING_TCPA_CONSENT,
                    f"No current GRANTED consent for {channel.value} "
                    f"to {target_value or '(unspecified)'}.",
                    "47 U.S.C. § 227(b); 47 C.F.R. § 64.1200",
                )
            )

    # 6. Frequency caps — Reg F § 1006.14(b) for phone
    if channel in PHONE_FREQUENCY_CHANNELS:
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = local_now - timedelta(days=7)
        daily_count = await _count_recent_contacts(
            session,
            account_id=account.id,
            since=day_start,
            channels=PHONE_FREQUENCY_CHANNELS,
        )
        weekly_count = await _count_recent_contacts(
            session,
            account_id=account.id,
            since=week_start,
            channels=PHONE_FREQUENCY_CHANNELS,
        )
        if daily_count >= max_daily:
            blocks.append(
                BlockEvidence(
                    BlockReason.DAILY_LIMIT_EXCEEDED,
                    f"{daily_count} prior phone contact(s) today; daily cap is {max_daily}.",
                    "Tenant policy; informed by 12 C.F.R. § 1006.14(b)",
                )
            )
        if weekly_count >= max_weekly:
            blocks.append(
                BlockEvidence(
                    BlockReason.WEEKLY_LIMIT_EXCEEDED,
                    f"{weekly_count} phone contact(s) in last 7 days; weekly cap is {max_weekly}.",
                    "12 C.F.R. § 1006.14(b)(2)(i) (7-in-7 rule)",
                )
            )

    return ContactDecision(
        allowed=not blocks,
        channel=channel,
        blocks=blocks,
        policy_pack_id=pack.id if pack else None,
        policy_pack_version=pack.version if pack else None,
    )


async def evaluate_account_compliance(
    session: AsyncSession,
    *,
    account: Account,
    consumer: Consumer,
    now: datetime | None = None,
) -> AccountComplianceSnapshot:
    """Return a multi-rule snapshot for dashboards / pre-call screens."""
    now = now or datetime.now(timezone.utc)
    pack = await load_active_policy_pack(session, account.jurisdiction)

    blocks: list[BlockEvidence] = []
    in_validation_window = False
    if account.validation_notice_sent and account.validation_notice_date:
        days_since = (now - account.validation_notice_date).days
        # § 1692g — 30-day dispute window from receipt of validation
        in_validation_window = days_since <= 30

    open_dispute = await _has_unresolved_dispute(session, account.id)
    if open_dispute:
        blocks.append(
            BlockEvidence(
                BlockReason.DISPUTE_OPEN,
                "Open dispute pending verification.",
                "12 C.F.R. § 1006.38(d); 15 U.S.C. § 1692g(b)",
            )
        )
    if account.legal_hold or consumer.legal_hold:
        blocks.append(
            BlockEvidence(
                BlockReason.LEGAL_HOLD,
                "Legal hold active.",
                "Internal policy / litigation hold",
            )
        )

    # SOL: try to map the debt type to a category and look up the rule
    sol_status, sol_years, sol_citation = await _evaluate_sol(
        session, account=account, pack=pack, now=now
    )

    # Frequency snapshot (today + 7-day rolling)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    daily = await _count_recent_contacts(
        session,
        account_id=account.id,
        since=day_start,
        channels=PHONE_FREQUENCY_CHANNELS,
    )
    weekly = await _count_recent_contacts(
        session,
        account_id=account.id,
        since=week_start,
        channels=PHONE_FREQUENCY_CHANNELS,
    )

    # Active suppressions (consumer-wide)
    sup_rows = await _active_suppressions(session, consumer_id=consumer.id, value=None)
    suppression_active = sorted({s.suppression_type.value for s in sup_rows})

    # Consent map
    consent_present: dict[str, bool] = {}
    for ch in ConsentChannel:
        consent_present[ch.value] = await _consent_present(
            session, consumer_id=consumer.id, channel=ch, scope_value=None
        )

    if pack:
        window = (pack.contact_window_start, pack.contact_window_end)
    else:
        window = ("08:00", "21:00")

    return AccountComplianceSnapshot(
        account_id=account.id,
        jurisdiction=account.jurisdiction,
        on_legal_hold=bool(account.legal_hold or consumer.legal_hold),
        legal_hold_reason=account.legal_hold_reason or consumer.legal_hold_reason,
        validation_notice_sent=account.validation_notice_sent,
        in_validation_window=in_validation_window,
        open_dispute=open_dispute,
        sol_status=sol_status,
        sol_years=sol_years,
        sol_citation=sol_citation,
        contact_window_local=window,
        daily_contacts_used=daily,
        weekly_contacts_used=weekly,
        suppression_active=suppression_active,
        consent_present=consent_present,
        policy_pack_version=pack.version if pack else None,
        blocks=blocks,
    )


# ---------------------------------------------------------------------------
# SOL evaluation
# ---------------------------------------------------------------------------

# Map account.debt_type -> compliance.DebtCategory for SOL lookups
_DEBT_TYPE_TO_CATEGORY = {
    "consumer": DebtCategory.OPEN_ACCOUNT,
    "commercial": DebtCategory.WRITTEN_CONTRACT,
    "medical": DebtCategory.OPEN_ACCOUNT,
    "judgment": DebtCategory.JUDGMENT,
    "student": DebtCategory.WRITTEN_CONTRACT,
    "utility": DebtCategory.OPEN_ACCOUNT,
    "telecom": DebtCategory.OPEN_ACCOUNT,
    "other": DebtCategory.WRITTEN_CONTRACT,
}


async def _evaluate_sol(
    session: AsyncSession,
    *,
    account: Account,
    pack: PolicyPack | None,
    now: datetime,
) -> tuple[str, int | None, str | None]:
    """Compare the account's last-activity date to the SOL rule.

    Returns (status, years, citation) where status is one of:
      "in_sol", "near_sol" (within 6 months of expiry), "time_barred",
      or "unknown".
    """
    if pack is None:
        return ("unknown", None, None)

    debt_type = account.debt_type.value if account.debt_type else "other"
    category = _DEBT_TYPE_TO_CATEGORY.get(debt_type, DebtCategory.WRITTEN_CONTRACT)

    result = await session.execute(
        select(StatuteOfLimitationsRule).where(
            StatuteOfLimitationsRule.policy_pack_id == pack.id,
            StatuteOfLimitationsRule.debt_category == category,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        return ("unknown", None, None)

    last_activity = (
        getattr(account, "last_activity_date", None)
        or getattr(account, "date_placed", None)
    )
    if last_activity is None:
        return ("unknown", rule.limitation_years, rule.statute_citation)

    if isinstance(last_activity, datetime):
        last_activity_d = last_activity.date()
    else:
        last_activity_d = last_activity

    expires = date(
        last_activity_d.year + rule.limitation_years,
        last_activity_d.month,
        last_activity_d.day,
    )
    today = now.date()
    if today >= expires:
        return ("time_barred", rule.limitation_years, rule.statute_citation)
    if (expires - today).days <= 180:
        return ("near_sol", rule.limitation_years, rule.statute_citation)
    return ("in_sol", rule.limitation_years, rule.statute_citation)


# ---------------------------------------------------------------------------
# Write helpers (consent / suppression / hold)
# ---------------------------------------------------------------------------

async def record_consent(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    consumer_id: uuid.UUID,
    contact_method_id: uuid.UUID | None,
    channel: ConsentChannel,
    scope_value: str | None,
    granted_source: str,
    granted_ip: str | None = None,
    expires_at: datetime | None = None,
    audit_notes: str | None = None,
) -> Consent:
    """Record explicit TCPA-grade consent.

    Per 47 C.F.R. § 64.1200(f)(8), consent must be:
      - In writing (or electronic signature compliant with E-SIGN);
      - Bearing the consumer's signature;
      - Identifying the specific number authorized;
      - Disclosing autodialed nature and that consent is not a condition
        of purchase.
    Callers are responsible for capturing and storing the underlying
    artifact (web-form HTML, IVR recording, etc.) — this row records the
    cryptographic proof reference in `audit_notes`.
    """
    now = datetime.now(timezone.utc)
    consent = Consent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        consumer_id=consumer_id,
        contact_method_id=contact_method_id,
        channel=channel,
        status=ConsentStatus.GRANTED,
        granted_at=now,
        granted_source=granted_source,
        granted_ip=granted_ip,
        scope_value=scope_value,
        expires_at=expires_at,
        audit_notes=audit_notes,
    )
    session.add(consent)
    await session.flush()
    return consent


async def revoke_consent(
    session: AsyncSession,
    *,
    consumer_id: uuid.UUID,
    channel: ConsentChannel | None = None,
    scope_value: str | None = None,
    revoked_source: str = "consumer_request",
) -> int:
    """Revoke matching active consents. Returns count revoked."""
    now = datetime.now(timezone.utc)
    query = select(Consent).where(
        Consent.consumer_id == consumer_id,
        Consent.status == ConsentStatus.GRANTED,
    )
    if channel is not None:
        query = query.where(Consent.channel == channel)
    if scope_value is not None:
        query = query.where(Consent.scope_value == scope_value)
    result = await session.execute(query)
    count = 0
    for c in result.scalars():
        c.status = ConsentStatus.REVOKED
        c.revoked_at = now
        c.revoked_source = revoked_source
        count += 1
    await session.flush()
    return count


async def add_suppression(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    consumer_id: uuid.UUID,
    suppression_type: SuppressionType,
    value: str | None,
    requested_source: str,
    expires_at: datetime | None = None,
) -> SuppressionEntry:
    """Add an opt-out / cease-and-desist suppression. Idempotent on (consumer,
    type, value)."""
    existing = await session.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.consumer_id == consumer_id,
            SuppressionEntry.suppression_type == suppression_type,
            SuppressionEntry.value == value,
            SuppressionEntry.is_active.is_(True),
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    entry = SuppressionEntry(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        consumer_id=consumer_id,
        suppression_type=suppression_type,
        value=value,
        requested_at=datetime.now(timezone.utc),
        requested_source=requested_source,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(entry)
    await session.flush()
    return entry


async def apply_legal_hold(
    session: AsyncSession,
    *,
    account: Account,
    reason: str,
    cascade_to_consumer: bool = False,
) -> None:
    """Apply a legal hold to an account (and optionally the consumer).

    Triggers per docs/01_policies.md: dispute opened, litigation initiated,
    bankruptcy notice received, regulatory inquiry/subpoena.
    """
    now = datetime.now(timezone.utc)
    account.legal_hold = True
    account.legal_hold_reason = reason
    account.legal_hold_date = now
    account.status = AccountStatus.LEGAL_HOLD

    if cascade_to_consumer:
        consumer_result = await session.execute(
            select(Consumer).where(Consumer.id == account.consumer_id)
        )
        consumer = consumer_result.scalar_one_or_none()
        if consumer is not None:
            consumer.legal_hold = True
            consumer.legal_hold_reason = reason
            consumer.legal_hold_date = now
    await session.flush()


# ---------------------------------------------------------------------------
# Rate / usury validation
# ---------------------------------------------------------------------------

async def validate_interest_rate(
    session: AsyncSession,
    *,
    jurisdiction: str,
    debt_category: DebtCategory,
    proposed_rate: Decimal,
) -> dict:
    """Validate a contractual / charged rate against the active pack's usury rules.

    Returns a dict suitable for direct API echo. Multiple usury rules may
    apply (civil + criminal); the most restrictive non-criminal cap controls
    enforceability and the criminal cap controls criminal exposure.
    """
    pack = await load_active_policy_pack(session, jurisdiction)
    if pack is None:
        return {
            "valid": None,
            "message": f"No active policy pack for {jurisdiction.upper()}",
            "requires_review": True,
        }

    result = await session.execute(
        select(UsuryRule).where(
            UsuryRule.policy_pack_id == pack.id,
            UsuryRule.debt_category == debt_category,
        )
    )
    rules = list(result.scalars())
    if not rules:
        return {
            "valid": None,
            "message": "No usury rule recorded for category",
            "requires_review": True,
        }

    civil = [r for r in rules if not r.is_criminal]
    criminal = [r for r in rules if r.is_criminal]
    civil_cap = min((r.max_rate for r in civil), default=None)
    criminal_cap = min((r.max_rate for r in criminal), default=None)

    findings: list[dict] = []
    if civil_cap is not None and proposed_rate > civil_cap:
        findings.append({
            "kind": "civil_usury",
            "cap": float(civil_cap),
            "citation": next(
                (r.statute_citation for r in civil if r.max_rate == civil_cap), None
            ),
        })
    if criminal_cap is not None and proposed_rate > criminal_cap:
        findings.append({
            "kind": "criminal_usury",
            "cap": float(criminal_cap),
            "citation": next(
                (r.statute_citation for r in criminal if r.max_rate == criminal_cap),
                None,
            ),
        })

    return {
        "valid": not findings,
        "proposed_rate": float(proposed_rate),
        "civil_cap": float(civil_cap) if civil_cap is not None else None,
        "criminal_cap": float(criminal_cap) if criminal_cap is not None else None,
        "findings": findings,
        "policy_pack_version": pack.version,
        "requires_review": bool(findings),
    }
