"""Credit bureau configuration and batch reporting endpoints."""

import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Dispute, DisputeStatus
from dcs_api.models.credit_reporting import (
    BureauBatch,
    BureauBatchStatus,
    BureauConfig,
    BureauRecord,
    BureauRecordStatus,
)
from dcs_api.schemas.credit_reporting import (
    BureauBatchCreate,
    BureauBatchResponse,
    BureauBatchUpdate,
    BureauConfigCreate,
    BureauConfigResponse,
    BureauConfigUpdate,
    BureauRecordResponse,
    BureauRecordUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "bureau:manage"

_OPEN_DISPUTE = (DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW)


async def _get_bureau_config(
    session: AsyncSession, config_id: uuid.UUID, user: CurrentUser
) -> BureauConfig | None:
    q = select(BureauConfig).where(BureauConfig.id == config_id)
    if not user.is_master:
        q = q.where(BureauConfig.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def _get_batch(
    session: AsyncSession, batch_id: uuid.UUID, user: CurrentUser
) -> BureauBatch | None:
    q = select(BureauBatch).where(BureauBatch.id == batch_id)
    if not user.is_master:
        q = q.where(BureauBatch.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


def _days_delinquent(dof: datetime | None, as_of: date) -> int | None:
    if dof is None:
        return None
    d = dof.date() if isinstance(dof, datetime) else dof
    return (as_of - d).days


def _eligible_for_batch(account: Account, cfg: BureauConfig, as_of: date) -> tuple[bool, BureauRecordStatus | None, str | None]:
    if account.total_balance < cfg.min_balance_to_report:
        return False, BureauRecordStatus.SUPPRESSED_BALANCE, "below_min_balance"
    dof = account.date_of_first_delinquency
    days = _days_delinquent(dof, as_of)
    if cfg.min_days_delinquent > 0 and (days is None or days < cfg.min_days_delinquent):
        return False, BureauRecordStatus.SUPPRESSED_BALANCE, "min_days_delinquent"
    return True, None, None


# --- Bureau configs ---


@router.get("/configs", response_model=PaginatedResponse[BureauConfigResponse])
async def list_bureau_configs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[BureauConfigResponse]:
    """List bureau configurations."""
    count_q = select(func.count()).select_from(BureauConfig)
    if not user.is_master:
        count_q = count_q.where(BureauConfig.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(BureauConfig)
    if not user.is_master:
        q = q.where(BureauConfig.tenant_id == user.tenant_id)
    q = q.order_by(BureauConfig.bureau).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[BureauConfigResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/configs/{config_id}", response_model=BureauConfigResponse)
async def get_bureau_config(
    config_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauConfigResponse:
    """Get a bureau configuration by ID."""
    cfg = await _get_bureau_config(session, config_id, user)
    if not cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau config not found")
    return BureauConfigResponse.model_validate(cfg)


@router.post("/configs", response_model=BureauConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_bureau_config(
    data: BureauConfigCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauConfigResponse:
    """Create a bureau configuration."""
    cfg = BureauConfig(
        tenant_id=user.tenant_id,
        bureau=data.bureau,
        subscriber_code=data.subscriber_code,
        subscriber_name=data.subscriber_name,
        sic_code=data.sic_code,
        portfolio_type=data.portfolio_type,
        account_type=data.account_type,
        suppress_during_dispute=data.suppress_during_dispute,
        min_balance_to_report=data.min_balance_to_report,
        min_days_delinquent=data.min_days_delinquent,
        reporting_schedule=data.reporting_schedule,
        field_mapping=data.field_mapping,
        config=data.config,
        is_active=data.is_active,
    )
    session.add(cfg)
    await session.flush()
    await session.refresh(cfg)
    return BureauConfigResponse.model_validate(cfg)


@router.patch("/configs/{config_id}", response_model=BureauConfigResponse)
async def update_bureau_config(
    config_id: uuid.UUID,
    data: BureauConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauConfigResponse:
    """Update a bureau configuration."""
    cfg = await _get_bureau_config(session, config_id, user)
    if not cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau config not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    await session.flush()
    return BureauConfigResponse.model_validate(cfg)


# --- Batches ---


@router.get("/batches", response_model=PaginatedResponse[BureauBatchResponse])
async def list_bureau_batches(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    bureau_config_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[BureauBatchResponse]:
    """List bureau batches."""
    count_q = select(func.count()).select_from(BureauBatch)
    if not user.is_master:
        count_q = count_q.where(BureauBatch.tenant_id == user.tenant_id)
    if bureau_config_id:
        count_q = count_q.where(BureauBatch.bureau_config_id == bureau_config_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(BureauBatch)
    if not user.is_master:
        q = q.where(BureauBatch.tenant_id == user.tenant_id)
    if bureau_config_id:
        q = q.where(BureauBatch.bureau_config_id == bureau_config_id)
    q = q.order_by(BureauBatch.reporting_period.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[BureauBatchResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/batches/{batch_id}", response_model=BureauBatchResponse)
async def get_bureau_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauBatchResponse:
    """Get a bureau batch by ID."""
    b = await _get_batch(session, batch_id, user)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau batch not found")
    return BureauBatchResponse.model_validate(b)


@router.post("/batches", response_model=BureauBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_bureau_batch(
    data: BureauBatchCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauBatchResponse:
    """Create a bureau batch and populate records from eligible accounts."""
    cfg = await _get_bureau_config(session, data.bureau_config_id, user)
    if not cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau config not found")

    as_of: date = data.reporting_period

    batch = BureauBatch(
        tenant_id=cfg.tenant_id,
        bureau_config_id=data.bureau_config_id,
        reporting_period=data.reporting_period,
        status=BureauBatchStatus.GENERATING,
        total_records=0,
        accepted_records=0,
        rejected_records=0,
        suppressed_records=0,
        file_name=data.file_name,
        file_hash=data.file_hash,
        filter_criteria=data.filter_criteria,
        errors=list(data.errors) if data.errors else [],
        generated_at=datetime.now(timezone.utc),
        submitted_at=data.submitted_at,
        response_received_at=data.response_received_at,
        generated_by_id=data.generated_by_id or user.user_id,
    )
    session.add(batch)
    await session.flush()

    aq = select(Account).where(Account.tenant_id == cfg.tenant_id)
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    accounts = list((await session.execute(aq)).scalars().all())

    suppressed = 0
    included = 0
    for acc in accounts:
        dq = select(func.count()).select_from(Dispute).where(
            Dispute.account_id == acc.id,
            Dispute.status.in_(_OPEN_DISPUTE),
        )
        has_open = ((await session.execute(dq)).scalar_one() or 0) > 0

        if cfg.suppress_during_dispute and has_open:
            rec = BureauRecord(
                tenant_id=cfg.tenant_id,
                batch_id=batch.id,
                account_id=acc.id,
                record_status=BureauRecordStatus.SUPPRESSED_DISPUTE,
                reported_balance=acc.total_balance,
                account_status_code="93",
                payment_rating=None,
                date_of_first_delinquency=acc.date_of_first_delinquency.date()
                if acc.date_of_first_delinquency
                else None,
                special_comment=None,
                raw_segment=None,
                suppression_reason="open_dispute",
                error_details=None,
            )
            session.add(rec)
            suppressed += 1
            continue

        ok, st, reason = _eligible_for_batch(acc, cfg, as_of)
        if not ok:
            rec = BureauRecord(
                tenant_id=cfg.tenant_id,
                batch_id=batch.id,
                account_id=acc.id,
                record_status=st or BureauRecordStatus.SUPPRESSED_BALANCE,
                reported_balance=acc.total_balance,
                account_status_code="93",
                payment_rating=None,
                date_of_first_delinquency=acc.date_of_first_delinquency.date()
                if acc.date_of_first_delinquency
                else None,
                special_comment=None,
                raw_segment=None,
                suppression_reason=reason,
                error_details=None,
            )
            session.add(rec)
            suppressed += 1
            continue

        rec = BureauRecord(
            tenant_id=cfg.tenant_id,
            batch_id=batch.id,
            account_id=acc.id,
            record_status=BureauRecordStatus.INCLUDED,
            reported_balance=acc.total_balance,
            account_status_code="11",
            payment_rating="0",
            date_of_first_delinquency=acc.date_of_first_delinquency.date()
            if acc.date_of_first_delinquency
            else None,
            special_comment=None,
            raw_segment=None,
            suppression_reason=None,
            error_details=None,
        )
        session.add(rec)
        included += 1

    batch.total_records = included + suppressed
    batch.suppressed_records = suppressed
    batch.accepted_records = included
    batch.status = BureauBatchStatus.GENERATED
    batch.generated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(batch)
    return BureauBatchResponse.model_validate(batch)


@router.patch("/batches/{batch_id}", response_model=BureauBatchResponse)
async def update_bureau_batch(
    batch_id: uuid.UUID,
    data: BureauBatchUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauBatchResponse:
    """Update a bureau batch."""
    b = await _get_batch(session, batch_id, user)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau batch not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    await session.flush()
    return BureauBatchResponse.model_validate(b)


# --- Records by batch ---


@router.get("/batches/{batch_id}/records", response_model=PaginatedResponse[BureauRecordResponse])
async def list_bureau_records_by_batch(
    batch_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[BureauRecordResponse]:
    """List bureau records for a batch."""
    b = await _get_batch(session, batch_id, user)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau batch not found")

    count_q = select(func.count()).select_from(BureauRecord).where(BureauRecord.batch_id == batch_id)
    if not user.is_master:
        count_q = count_q.where(BureauRecord.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(BureauRecord).where(BureauRecord.batch_id == batch_id)
    if not user.is_master:
        q = q.where(BureauRecord.tenant_id == user.tenant_id)
    q = q.order_by(BureauRecord.account_id).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[BureauRecordResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/batches/{batch_id}/records/{record_id}", response_model=BureauRecordResponse)
async def get_bureau_record(
    batch_id: uuid.UUID,
    record_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauRecordResponse:
    """Get a single bureau record."""
    q = select(BureauRecord).where(
        BureauRecord.id == record_id,
        BureauRecord.batch_id == batch_id,
    )
    if not user.is_master:
        q = q.where(BureauRecord.tenant_id == user.tenant_id)
    r = await session.execute(q)
    rec = r.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau record not found")
    return BureauRecordResponse.model_validate(rec)


@router.patch("/batches/{batch_id}/records/{record_id}", response_model=BureauRecordResponse)
async def update_bureau_record(
    batch_id: uuid.UUID,
    record_id: uuid.UUID,
    data: BureauRecordUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BureauRecordResponse:
    """Update a bureau record."""
    q = select(BureauRecord).where(
        BureauRecord.id == record_id,
        BureauRecord.batch_id == batch_id,
    )
    if not user.is_master:
        q = q.where(BureauRecord.tenant_id == user.tenant_id)
    r = await session.execute(q)
    rec = r.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bureau record not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rec, k, v)
    await session.flush()
    return BureauRecordResponse.model_validate(rec)
