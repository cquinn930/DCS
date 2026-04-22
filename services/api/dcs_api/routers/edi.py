"""Electronic data interchange (format, partner, batch) endpoints."""

import random
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.edi import (
    DataExchangeBatch,
    DataExchangeFormat,
    DataExchangePartner,
    ExchangeBatchStatus,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.edi import (
    DataExchangeBatchCreate,
    DataExchangeBatchResponse,
    DataExchangeBatchUpdate,
    DataExchangeFormatCreate,
    DataExchangeFormatResponse,
    DataExchangeFormatUpdate,
    DataExchangePartnerCreate,
    DataExchangePartnerResponse,
    DataExchangePartnerUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


async def _get_format(
    session: AsyncSession, format_id: uuid.UUID, user: CurrentUser
) -> DataExchangeFormat | None:
    q = select(DataExchangeFormat).where(DataExchangeFormat.id == format_id)
    if not user.is_master:
        q = q.where(DataExchangeFormat.tenant_id == user.tenant_id)
    return (await session.execute(q)).scalar_one_or_none()


async def _get_partner(
    session: AsyncSession, partner_id: uuid.UUID, user: CurrentUser
) -> DataExchangePartner | None:
    q = select(DataExchangePartner).where(DataExchangePartner.id == partner_id)
    if not user.is_master:
        q = q.where(DataExchangePartner.tenant_id == user.tenant_id)
    return (await session.execute(q)).scalar_one_or_none()


@router.get(
    "/formats",
    response_model=PaginatedResponse[DataExchangeFormatResponse],
)
async def list_formats(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[DataExchangeFormatResponse]:
    """List data exchange formats."""
    base = select(DataExchangeFormat)
    if not user.is_master:
        base = base.where(DataExchangeFormat.tenant_id == user.tenant_id)
    count_q = select(func.count()).select_from(DataExchangeFormat)
    if not user.is_master:
        count_q = count_q.where(DataExchangeFormat.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(DataExchangeFormat.code).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DataExchangeFormatResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/formats",
    response_model=DataExchangeFormatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_format(
    data: DataExchangeFormatCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeFormatResponse:
    """Create a data exchange format."""
    row = DataExchangeFormat(
        tenant_id=user.tenant_id,
        code=data.code,
        name=data.name,
        description=data.description,
        version=data.version,
        direction=data.direction,
        format_type=data.format_type,
        record_layouts=data.record_layouts,
        field_mappings=data.field_mappings,
        header_layout=data.header_layout,
        trailer_layout=data.trailer_layout,
        validation_rules=data.validation_rules,
        transform_rules=data.transform_rules,
        is_active=data.is_active,
        is_system=data.is_system,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return DataExchangeFormatResponse.model_validate(row)


@router.get("/formats/{format_id}", response_model=DataExchangeFormatResponse)
async def get_format(
    format_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeFormatResponse:
    """Get format by ID."""
    row = await _get_format(session, format_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")
    return DataExchangeFormatResponse.model_validate(row)


@router.patch("/formats/{format_id}", response_model=DataExchangeFormatResponse)
async def update_format(
    format_id: uuid.UUID,
    data: DataExchangeFormatUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeFormatResponse:
    """Update a data exchange format."""
    row = await _get_format(session, format_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return DataExchangeFormatResponse.model_validate(row)


@router.delete("/formats/{format_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_format(
    format_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> None:
    """Delete a data exchange format."""
    row = await _get_format(session, format_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")
    await session.delete(row)


@router.get(
    "/partners",
    response_model=PaginatedResponse[DataExchangePartnerResponse],
)
async def list_partners(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    exchange_format_id: uuid.UUID | None = None,
) -> PaginatedResponse[DataExchangePartnerResponse]:
    """List exchange partners."""
    base = select(DataExchangePartner)
    if not user.is_master:
        base = base.where(DataExchangePartner.tenant_id == user.tenant_id)
    if exchange_format_id:
        base = base.where(DataExchangePartner.exchange_format_id == exchange_format_id)
    count_q = select(func.count()).select_from(DataExchangePartner)
    if not user.is_master:
        count_q = count_q.where(DataExchangePartner.tenant_id == user.tenant_id)
    if exchange_format_id:
        count_q = count_q.where(DataExchangePartner.exchange_format_id == exchange_format_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(DataExchangePartner.name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DataExchangePartnerResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/partners",
    response_model=DataExchangePartnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_partner(
    data: DataExchangePartnerCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangePartnerResponse:
    """Create an exchange partner."""
    fmt = await _get_format(session, data.exchange_format_id, user)
    if not fmt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exchange format not found for this tenant",
        )
    row = DataExchangePartner(
        tenant_id=user.tenant_id,
        name=data.name,
        partner_code=data.partner_code,
        exchange_format_id=data.exchange_format_id,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        connection_config=data.connection_config,
        partner_settings=data.partner_settings,
        is_active=data.is_active,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return DataExchangePartnerResponse.model_validate(row)


@router.get("/partners/{partner_id}", response_model=DataExchangePartnerResponse)
async def get_partner(
    partner_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangePartnerResponse:
    """Get partner by ID."""
    row = await _get_partner(session, partner_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return DataExchangePartnerResponse.model_validate(row)


@router.patch("/partners/{partner_id}", response_model=DataExchangePartnerResponse)
async def update_partner(
    partner_id: uuid.UUID,
    data: DataExchangePartnerUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangePartnerResponse:
    """Update an exchange partner."""
    row = await _get_partner(session, partner_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    payload = data.model_dump(exclude_unset=True)
    if "exchange_format_id" in payload and payload["exchange_format_id"] is not None:
        fmt = await _get_format(session, payload["exchange_format_id"], user)
        if not fmt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exchange format not found for this tenant",
            )
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return DataExchangePartnerResponse.model_validate(row)


@router.delete("/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner(
    partner_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> None:
    """Delete an exchange partner."""
    row = await _get_partner(session, partner_id, user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    await session.delete(row)


@router.get(
    "/batches",
    response_model=PaginatedResponse[DataExchangeBatchResponse],
)
async def list_batches(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    partner_id: uuid.UUID | None = None,
    status_filter: ExchangeBatchStatus | None = Query(None, alias="status"),
) -> PaginatedResponse[DataExchangeBatchResponse]:
    """List exchange batches."""
    base = select(DataExchangeBatch)
    if not user.is_master:
        base = base.where(DataExchangeBatch.tenant_id == user.tenant_id)
    if partner_id:
        base = base.where(DataExchangeBatch.partner_id == partner_id)
    if status_filter:
        base = base.where(DataExchangeBatch.status == status_filter)
    count_q = select(func.count()).select_from(DataExchangeBatch)
    if not user.is_master:
        count_q = count_q.where(DataExchangeBatch.tenant_id == user.tenant_id)
    if partner_id:
        count_q = count_q.where(DataExchangeBatch.partner_id == partner_id)
    if status_filter:
        count_q = count_q.where(DataExchangeBatch.status == status_filter)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(DataExchangeBatch.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[DataExchangeBatchResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/batches",
    response_model=DataExchangeBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    data: DataExchangeBatchCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeBatchResponse:
    """Create an exchange batch."""
    partner = await _get_partner(session, data.partner_id, user)
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Partner not found for this tenant",
        )
    row = DataExchangeBatch(
        tenant_id=user.tenant_id,
        partner_id=data.partner_id,
        direction=data.direction,
        status=data.status,
        file_name=data.file_name,
        file_hash=data.file_hash,
        total_records=data.total_records,
        processed_records=data.processed_records,
        error_records=data.error_records,
        new_accounts_created=data.new_accounts_created,
        accounts_updated=data.accounts_updated,
        errors=data.errors,
        summary=data.summary,
        started_at=data.started_at,
        completed_at=data.completed_at,
        processed_by_id=data.processed_by_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return DataExchangeBatchResponse.model_validate(row)


@router.get("/batches/{batch_id}", response_model=DataExchangeBatchResponse)
async def get_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeBatchResponse:
    """Get batch by ID."""
    q = select(DataExchangeBatch).where(DataExchangeBatch.id == batch_id)
    if not user.is_master:
        q = q.where(DataExchangeBatch.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return DataExchangeBatchResponse.model_validate(row)


@router.patch("/batches/{batch_id}", response_model=DataExchangeBatchResponse)
async def update_batch(
    batch_id: uuid.UUID,
    data: DataExchangeBatchUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeBatchResponse:
    """Update batch status and counters."""
    q = select(DataExchangeBatch).where(DataExchangeBatch.id == batch_id)
    if not user.is_master:
        q = q.where(DataExchangeBatch.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return DataExchangeBatchResponse.model_validate(row)


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> None:
    """Delete an exchange batch."""
    q = select(DataExchangeBatch).where(DataExchangeBatch.id == batch_id)
    if not user.is_master:
        q = q.where(DataExchangeBatch.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    await session.delete(row)


VENDOR_TEMPLATES = {
    "lexisnexis": {
        "name": "LexisNexis Skip Trace",
        "code": "LEXIS",
        "description": "LexisNexis batch skip tracing connector",
        "direction": "bidirectional",
        "format_type": "csv",
        "record_layouts": {"fields": ["ssn", "first_name", "last_name", "dob", "address"]},
        "field_mappings": {"ssn": "consumer.ssn", "first_name": "consumer.first_name", "last_name": "consumer.last_name"},
        "connection_config": {"protocol": "sftp", "host": "", "port": 22, "username": "", "remote_path": "/"},
    },
    "ygc": {
        "name": "YGC (You've Got Claims)",
        "code": "YGC",
        "description": "YGC legal placement and return connector",
        "direction": "bidirectional",
        "format_type": "fixed_width",
        "record_layouts": {"record_length": 600, "segments": ["header", "debtor", "financial", "legal"]},
        "field_mappings": {"account_number": "account.external_id", "balance": "account.current_balance"},
        "connection_config": {"protocol": "sftp", "host": "", "port": 22, "username": "", "remote_path": "/ygc"},
    },
    "dialer": {
        "name": "Predictive Dialer Export",
        "code": "DIALER",
        "description": "Auto-dialer campaign list export",
        "direction": "outbound",
        "format_type": "csv",
        "record_layouts": {"fields": ["phone", "account_number", "consumer_name", "balance", "priority"]},
        "field_mappings": {"phone": "consumer.phone", "account_number": "account.external_id"},
        "connection_config": {"protocol": "local", "output_path": "/exports/dialer"},
    },
    "collection_agency": {
        "name": "Collection Agency Placement",
        "code": "AGENCY",
        "description": "Standard agency placement file format",
        "direction": "outbound",
        "format_type": "csv",
        "record_layouts": {"fields": ["account_number", "debtor_name", "ssn", "balance", "placement_date"]},
        "field_mappings": {"account_number": "account.external_id", "debtor_name": "consumer.full_name", "balance": "account.current_balance"},
        "connection_config": {"protocol": "sftp", "host": "", "port": 22},
    },
    "credit_card_processor": {
        "name": "Credit Card Payment Processor",
        "code": "CCPROC",
        "description": "Credit card batch payment processing connector",
        "direction": "bidirectional",
        "format_type": "csv",
        "record_layouts": {"fields": ["account_number", "amount", "card_token", "auth_code", "result"]},
        "field_mappings": {"account_number": "account.external_id", "amount": "payment.amount"},
        "connection_config": {"protocol": "api", "endpoint": "", "api_key": ""},
    },
}


@router.get("/vendor-connectors")
async def list_vendor_connectors(
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> dict:
    """List available vendor connector templates."""
    connectors = []
    for key, tmpl in VENDOR_TEMPLATES.items():
        connectors.append({
            "vendor_type": key,
            "name": tmpl["name"],
            "code": tmpl["code"],
            "description": tmpl["description"],
            "direction": tmpl["direction"],
            "format_type": tmpl["format_type"],
        })
    return {"connectors": connectors}


@router.post("/vendor-connectors/{vendor_type}/setup", status_code=status.HTTP_201_CREATED)
async def setup_vendor_connector(
    vendor_type: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> dict:
    """Set up a vendor connector from a template — creates both a format and a partner."""
    if vendor_type not in VENDOR_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown vendor type: {vendor_type}")

    tmpl = VENDOR_TEMPLATES[vendor_type]

    fmt = DataExchangeFormat(
        tenant_id=user.tenant_id,
        code=tmpl["code"],
        name=tmpl["name"],
        description=tmpl["description"],
        direction=tmpl["direction"],
        format_type=tmpl["format_type"],
        record_layouts=tmpl["record_layouts"],
        field_mappings=tmpl["field_mappings"],
        header_layout={},
        trailer_layout={},
        validation_rules={},
        transform_rules={},
        is_active=True,
        is_system=False,
    )
    session.add(fmt)
    await session.flush()

    partner = DataExchangePartner(
        tenant_id=user.tenant_id,
        name=tmpl["name"],
        partner_code=tmpl["code"],
        exchange_format_id=fmt.id,
        connection_config=tmpl["connection_config"],
        partner_settings={},
        is_active=True,
    )
    session.add(partner)
    await session.flush()
    await session.refresh(fmt)
    await session.refresh(partner)

    return {
        "vendor_type": vendor_type,
        "format_id": str(fmt.id),
        "partner_id": str(partner.id),
        "message": f"{tmpl['name']} connector created. Update connection settings in the partner configuration.",
    }


@router.post("/batches/{batch_id}/process", response_model=DataExchangeBatchResponse)
async def process_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("edi:manage"))],
) -> DataExchangeBatchResponse:
    """Simulate batch processing: transitions status and fills progress fields."""
    q = select(DataExchangeBatch).where(DataExchangeBatch.id == batch_id)
    if not user.is_master:
        q = q.where(DataExchangeBatch.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    now = datetime.now(timezone.utc)
    row.status = ExchangeBatchStatus.PROCESSING
    row.started_at = row.started_at or now
    row.processed_by_id = user.user_id
    await session.flush()

    total = max(row.total_records, 1)
    processed = total if row.total_records else random.randint(1, 100)
    err_n = min(random.randint(0, 5), processed)
    row.processed_records = processed
    row.error_records = err_n
    row.new_accounts_created = random.randint(0, max(processed - err_n, 0))
    row.accounts_updated = max(processed - row.new_accounts_created - err_n, 0)
    row.status = (
        ExchangeBatchStatus.COMPLETED_WITH_ERRORS
        if err_n
        else ExchangeBatchStatus.COMPLETED
    )
    row.completed_at = now
    row.summary = {
        **(row.summary or {}),
        "simulated": True,
        "message": "Batch processing completed (simulated).",
    }
    if err_n:
        row.errors = list(row.errors or []) + [
            {"code": "SIM_WARN", "message": f"{err_n} record(s) completed with errors (simulated)."}
        ]

    await session.flush()
    await session.refresh(row)
    return DataExchangeBatchResponse.model_validate(row)
