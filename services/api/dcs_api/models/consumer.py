"""Consumer-related models.

Handles PII, contact methods, consent tracking, and suppression lists.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel

if TYPE_CHECKING:
    from dcs_api.models.tenant import Tenant
    from dcs_api.models.account import Account


class Consumer(TenantScopedModel):
    """Consumer (debtor) record.

    Contains PII and links to contact methods, accounts, and consent records.
    """

    __tablename__ = "consumers"
    __table_args__ = (
        Index("ix_consumers_tenant_ssn", "tenant_id", "ssn_last_four"),
    )

    # Identity
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100))
    suffix: Mapped[str | None] = mapped_column(String(20))
    ssn_last_four: Mapped[str | None] = mapped_column(String(4))
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Preferences
    language_preference: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York", nullable=False)

    # Compliance flags
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_represented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attorney_name: Mapped[str | None] = mapped_column(String(255))
    attorney_contact: Mapped[str | None] = mapped_column(Text)

    # Legal hold prevents modifications
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(Text)
    legal_hold_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Metadata
    external_id: Mapped[str | None] = mapped_column(String(255))  # Client's ID
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="consumers")
    contact_methods: Mapped[list["ContactMethod"]] = relationship(
        "ContactMethod", back_populates="consumer"
    )
    consents: Mapped[list["Consent"]] = relationship("Consent", back_populates="consumer")
    suppression_entries: Mapped[list["SuppressionEntry"]] = relationship(
        "SuppressionEntry", back_populates="consumer"
    )
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="consumer")


class ContactType(str, Enum):
    """Types of contact methods."""

    PHONE_HOME = "phone_home"
    PHONE_WORK = "phone_work"
    PHONE_MOBILE = "phone_mobile"
    EMAIL = "email"
    ADDRESS_HOME = "address_home"
    ADDRESS_WORK = "address_work"


class ContactMethod(TenantScopedModel):
    """Consumer contact method (phone, email, address).

    Each contact method can be individually suppressed or marked as invalid.
    """

    __tablename__ = "contact_methods"
    __table_args__ = (
        Index("ix_contact_methods_consumer", "consumer_id"),
    )

    consumer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumers.id", ondelete="CASCADE"),
        nullable=False,
    )

    contact_type: Mapped[ContactType] = mapped_column(SQLEnum(ContactType), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)  # Phone, email, or address
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # For addresses
    address_line_1: Mapped[str | None] = mapped_column(String(255))
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), default="US", nullable=False)

    # Validation tracking
    last_validated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_source: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    consumer: Mapped["Consumer"] = relationship("Consumer", back_populates="contact_methods")


class ConsentChannel(str, Enum):
    """Communication channels requiring consent."""

    VOICE_AUTODIALED = "voice_autodialed"
    VOICE_MANUAL = "voice_manual"
    SMS = "sms"
    EMAIL = "email"


class ConsentStatus(str, Enum):
    """Consent status."""

    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Consent(TenantScopedModel):
    """Consent record for TCPA compliance.

    Tracks explicit consent for communications by channel and contact method.
    Consent cannot be inferred and must be explicitly recorded.
    """

    __tablename__ = "consents"
    __table_args__ = (
        Index("ix_consents_consumer", "consumer_id"),
        Index("ix_consents_status", "status"),
    )

    consumer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumers.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contact_methods.id", ondelete="SET NULL"),
    )

    channel: Mapped[ConsentChannel] = mapped_column(SQLEnum(ConsentChannel), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(
        SQLEnum(ConsentStatus),
        default=ConsentStatus.GRANTED,
        nullable=False,
    )

    # When and how consent was obtained
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_source: Mapped[str] = mapped_column(String(255), nullable=False)  # web_form, ivr, etc.
    granted_ip: Mapped[str | None] = mapped_column(String(45))

    # Scope (what number/email was consented)
    scope_value: Mapped[str | None] = mapped_column(String(500))

    # Revocation tracking
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_source: Mapped[str | None] = mapped_column(String(255))

    # Expiration (if applicable)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Audit
    audit_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    consumer: Mapped["Consumer"] = relationship("Consumer", back_populates="consents")


class SuppressionType(str, Enum):
    """Types of suppression entries."""

    DO_NOT_CALL = "do_not_call"
    DO_NOT_TEXT = "do_not_text"
    DO_NOT_EMAIL = "do_not_email"
    DO_NOT_CONTACT = "do_not_contact"  # All channels
    CEASE_AND_DESIST = "cease_and_desist"


class SuppressionEntry(TenantScopedModel):
    """Suppression list entry.

    Tracks opt-outs and cease-and-desist requests. Suppression is applied
    immediately across all outbound channels.
    """

    __tablename__ = "suppression_entries"
    __table_args__ = (
        Index("ix_suppression_consumer", "consumer_id"),
        Index("ix_suppression_type", "suppression_type"),
    )

    consumer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumers.id", ondelete="CASCADE"),
    )

    suppression_type: Mapped[SuppressionType] = mapped_column(
        SQLEnum(SuppressionType),
        nullable=False,
    )

    # What is suppressed (phone, email, or "all")
    value: Mapped[str | None] = mapped_column(String(500))

    # When and how suppression was requested
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_source: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional expiration (usually permanent)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    consumer: Mapped["Consumer"] = relationship("Consumer", back_populates="suppression_entries")
