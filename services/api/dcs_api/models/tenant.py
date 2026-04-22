"""Tenant, user, role, and audit models.

These models handle multi-tenancy, authentication, authorization,
and immutable audit logging.
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import BaseModel, TenantScopedModel

if TYPE_CHECKING:
    from dcs_api.models.consumer import Consumer
    from dcs_api.models.account import Account, Case


class TenantStatus(str, Enum):
    """Tenant lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOCKED_DOWN = "locked_down"  # Breach response state
    DEACTIVATED = "deactivated"


class BusinessModel(str, Enum):
    """Tenant business model type."""

    SUBSCRIPTION = "subscription"
    PER_ACCOUNT = "per_account"
    CONTINGENCY = "contingency"
    DEBT_BUYER = "debt_buyer"


class Tenant(BaseModel):
    """Multi-tenant organization.

    Each tenant represents a collection organization with isolated data.
    """

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        SQLEnum(TenantStatus),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )
    business_model: Mapped[BusinessModel] = mapped_column(
        SQLEnum(BusinessModel),
        default=BusinessModel.SUBSCRIPTION,
        nullable=False,
    )

    # Compliance
    default_jurisdiction: Mapped[str] = mapped_column(String(2), default="NJ", nullable=False)
    retention_years: Mapped[int] = mapped_column(default=7, nullable=False)
    license_number: Mapped[str | None] = mapped_column(String(100))
    bond_amount: Mapped[int | None] = mapped_column()  # cents
    license_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="tenant")
    consumers: Mapped[list["Consumer"]] = relationship("Consumer", back_populates="tenant")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="tenant")


class User(TenantScopedModel):
    """User account within a tenant.

    Users authenticate via local credentials or external IdP (OIDC/SAML).
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_tenant", "email", "tenant_id", unique=True),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))  # None if OIDC-only
    external_id: Mapped[str | None] = mapped_column(String(255))  # OIDC subject
    idp_provider: Mapped[str | None] = mapped_column(String(50))  # azure, okta, etc.

    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user")
    assigned_cases: Mapped[list["Case"]] = relationship("Case", back_populates="assigned_to")


class RoleType(str, Enum):
    """Built-in role types."""

    COLLECTOR = "collector"
    SUPERVISOR = "supervisor"
    LEGAL = "legal"
    ADMIN = "admin"
    OWNER = "owner"
    MASTER = "master"
    CUSTOM = "custom"


class Role(TenantScopedModel):
    """User role with associated permissions.

    Roles can be built-in (collector, supervisor, etc.) or custom.
    """

    __tablename__ = "roles"
    __table_args__ = (
        Index("ix_roles_name_tenant", "name", "tenant_id", unique=True),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[RoleType] = mapped_column(
        SQLEnum(RoleType),
        default=RoleType.CUSTOM,
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="roles")
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role"
    )
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")


class Permission(BaseModel):
    """System-wide permission definition.

    Permissions are defined at the system level and assigned to roles.
    """

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_owner_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission"
    )


class RolePermission(BaseModel):
    """Association between roles and permissions."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ix_role_permissions_unique", "role_id", "permission_id", unique=True),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="role_permissions")


class UserRole(BaseModel):
    """Association between users and roles."""

    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ix_user_roles_unique", "user_id", "role_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")


class AuditAction(str, Enum):
    """Types of auditable actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PERMISSION_CHANGE = "permission_change"
    CONFIG_CHANGE = "config_change"
    CONTACT_ATTEMPT = "contact_attempt"
    DISPUTE_FILED = "dispute_filed"
    PAYMENT_RECEIVED = "payment_received"
    LEGAL_HOLD_APPLIED = "legal_hold_applied"
    LEGAL_HOLD_RELEASED = "legal_hold_released"
    BREACH_LOCKDOWN = "breach_lockdown"
    BREACH_UNLOCK = "breach_unlock"


class AuditLog(BaseModel):
    """Immutable, append-only audit log.

    All significant actions are recorded for compliance and defensibility.
    This table should be append-only with no UPDATE or DELETE operations.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_action", "tenant_id", "action"),
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[AuditAction] = mapped_column(SQLEnum(AuditAction), nullable=False)

    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    description: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Store complete before/after state for compliance
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)

    # Policy and calculation metadata for defensibility
    policy_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    calculation_version: Mapped[str | None] = mapped_column(String(50))
