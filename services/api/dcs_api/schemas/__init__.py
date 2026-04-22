"""Pydantic schemas for API request/response validation."""

from dcs_api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
)
from dcs_api.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)
from dcs_api.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
)
from dcs_api.schemas.consumer import (
    ConsumerCreate,
    ConsumerResponse,
    ConsumerUpdate,
    ConsentCreate,
    ConsentResponse,
)
from dcs_api.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from dcs_api.schemas.dispute import (
    DisputeCreate,
    DisputeResponse,
    DisputeUpdate,
)
from dcs_api.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
)
from dcs_api.schemas.calculation import (
    CalculationRequest,
    CalculationResponse,
    InterestCalculationRequest,
    InterestCalculationResponse,
)
from dcs_api.schemas.common import (
    PaginatedResponse,
    ErrorResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "TokenResponse",
    # Tenant
    "TenantCreate",
    "TenantResponse",
    "TenantUpdate",
    # User
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Consumer
    "ConsumerCreate",
    "ConsumerResponse",
    "ConsumerUpdate",
    "ConsentCreate",
    "ConsentResponse",
    # Account
    "AccountCreate",
    "AccountResponse",
    "AccountUpdate",
    # Dispute
    "DisputeCreate",
    "DisputeResponse",
    "DisputeUpdate",
    # Payment
    "PaymentCreate",
    "PaymentResponse",
    # Calculation
    "CalculationRequest",
    "CalculationResponse",
    "InterestCalculationRequest",
    "InterestCalculationResponse",
    # Common
    "PaginatedResponse",
    "ErrorResponse",
]
