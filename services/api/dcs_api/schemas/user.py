"""User schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from dcs_api.schemas.common import TimestampSchema


class UserCreate(BaseModel):
    """Create user request."""

    email: EmailStr
    password: str | None = Field(None, min_length=12, max_length=128)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    role_ids: list[uuid.UUID] = []

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserUpdate(BaseModel):
    """Update user request."""

    email: EmailStr | None = None
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    role_ids: list[uuid.UUID] | None = None


class UserResponse(TimestampSchema):
    """User response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_owner: bool
    last_login: datetime | None = None
    roles: list[str] = []


class RoleResponse(TimestampSchema):
    """Role response."""

    id: uuid.UUID
    name: str
    description: str | None = None
    role_type: str
    is_system: bool
    permissions: list[str] = []
