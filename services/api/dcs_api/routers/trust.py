"""Trust account, transactions, and bank reconciliation endpoints."""

import uuid
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.trust import (
    BankReconciliation,
    ReconciliationItem,
    ReconciliationMatchStatus,
    TrustAccount,
    TrustAccountType,
    TrustTransaction,
)
from dcs_api.schemas.trust import (
    BankReconciliationCreate,
    BankReconciliationResponse,
    BankReconciliationUpdate,
    ReconciliationItemCreate,
    ReconciliationItemResponse,
    ReconciliationItemUpdate,
    TrustAccountCreate,
    TrustAccountResponse,
    TrustAccountUpdate,
    TrustTransactionCreate,
    TrustTransactionResponse,
    TrustTransactionUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "trust:manage"


async def _get_trust_account(
    session: AsyncSession,
    account_id: uuid.UUID,
    user: CurrentUser,
) -> TrustAccount | None:
    q = select(TrustAccount).where(TrustAccount.id == account_id)
    if not user.is_master:
        q = q.where(TrustAccount.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


# --- Trust accounts ---


@router.get("/accounts", response_model=PaginatedResponse[TrustAccountResponse])
async def list_trust_accounts(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[TrustAccountResponse]:
    """List trust accounts in the tenant."""
    count_q = select(func.count()).select_from(TrustAccount)
    if not user.is_master:
        count_q = count_q.where(TrustAccount.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    base = select(TrustAccount)
    if not user.is_master:
        base = base.where(TrustAccount.tenant_id == user.tenant_id)
    offset = (page - 1) * page_size
    q = base.offset(offset).limit(page_size).order_by(TrustAccount.name)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[TrustAccountResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/accounts/{account_id}", response_model=TrustAccountResponse)
async def get_trust_account(
    account_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustAccountResponse:
    """Get a trust account by ID."""
    acc = await _get_trust_account(session, account_id, user)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")
    return TrustAccountResponse.model_validate(acc)


@router.post("/accounts", response_model=TrustAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_trust_account(
    data: TrustAccountCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustAccountResponse:
    """Create a trust account."""
    acc = TrustAccount(
        tenant_id=user.tenant_id,
        name=data.name,
        account_type=data.account_type,
        status=data.status,
        bank_name=data.bank_name,
        account_number_last4=data.account_number_last4,
        routing_number_last4=data.routing_number_last4,
        current_balance=data.current_balance,
        linked_account_id=data.linked_account_id,
        allow_overdraft=data.allow_overdraft,
        config=data.config,
    )
    session.add(acc)
    await session.flush()
    await session.refresh(acc)
    return TrustAccountResponse.model_validate(acc)


@router.patch("/accounts/{account_id}", response_model=TrustAccountResponse)
async def update_trust_account(
    account_id: uuid.UUID,
    data: TrustAccountUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustAccountResponse:
    """Update a trust account."""
    acc = await _get_trust_account(session, account_id, user)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(acc, k, v)
    await session.flush()
    return TrustAccountResponse.model_validate(acc)


# --- Trust transactions ---


@router.get("/transactions", response_model=PaginatedResponse[TrustTransactionResponse])
async def list_trust_transactions(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    trust_account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[TrustTransactionResponse]:
    """List trust transactions, optionally filtered by trust account."""
    count_q = select(func.count()).select_from(TrustTransaction)
    if not user.is_master:
        count_q = count_q.where(TrustTransaction.tenant_id == user.tenant_id)
    if trust_account_id:
        count_q = count_q.where(TrustTransaction.trust_account_id == trust_account_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(TrustTransaction)
    if not user.is_master:
        q = q.where(TrustTransaction.tenant_id == user.tenant_id)
    if trust_account_id:
        q = q.where(TrustTransaction.trust_account_id == trust_account_id)
    q = q.order_by(TrustTransaction.transaction_date.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[TrustTransactionResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/transactions/{transaction_id}", response_model=TrustTransactionResponse)
async def get_trust_transaction(
    transaction_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustTransactionResponse:
    """Get a trust transaction by ID."""
    q = select(TrustTransaction).where(TrustTransaction.id == transaction_id)
    if not user.is_master:
        q = q.where(TrustTransaction.tenant_id == user.tenant_id)
    r = await session.execute(q)
    tx = r.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TrustTransactionResponse.model_validate(tx)


def _validate_segregated_balance(trust_acc: TrustAccount, new_running_balance: int) -> None:
    if trust_acc.account_type == TrustAccountType.SEGREGATED_TRUST and not trust_acc.allow_overdraft:
        if new_running_balance < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Segregated trust account cannot have a negative balance",
            )


@router.post(
    "/transactions",
    response_model=TrustTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trust_transaction(
    data: TrustTransactionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustTransactionResponse:
    """Create a trust transaction and refresh trust account balance."""
    trust_acc = await _get_trust_account(session, data.trust_account_id, user)
    if not trust_acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")

    _validate_segregated_balance(trust_acc, data.running_balance)

    tx = TrustTransaction(
        tenant_id=trust_acc.tenant_id,
        trust_account_id=data.trust_account_id,
        transaction_type=data.transaction_type,
        amount=data.amount,
        running_balance=data.running_balance,
        reference_number=data.reference_number,
        check_number=data.check_number,
        payee=data.payee,
        memo=data.memo,
        account_id=data.account_id,
        payment_id=data.payment_id,
        linked_transaction_id=data.linked_transaction_id,
        transaction_date=data.transaction_date,
        posted_by_id=data.posted_by_id or user.user_id,
        is_reconciled=data.is_reconciled,
    )
    session.add(tx)
    trust_acc.current_balance = data.running_balance
    await session.flush()
    await session.refresh(tx)
    return TrustTransactionResponse.model_validate(tx)


@router.patch("/transactions/{transaction_id}", response_model=TrustTransactionResponse)
async def update_trust_transaction(
    transaction_id: uuid.UUID,
    data: TrustTransactionUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TrustTransactionResponse:
    """Update a trust transaction."""
    q = select(TrustTransaction).where(TrustTransaction.id == transaction_id)
    if not user.is_master:
        q = q.where(TrustTransaction.tenant_id == user.tenant_id)
    r = await session.execute(q)
    tx = r.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    trust_acc = await _get_trust_account(session, tx.trust_account_id, user)
    if not trust_acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tx, k, v)

    rb = tx.running_balance
    _validate_segregated_balance(trust_acc, rb)
    trust_acc.current_balance = rb
    await session.flush()
    return TrustTransactionResponse.model_validate(tx)


# --- Reconciliations ---


async def _get_reconciliation(
    session: AsyncSession, recon_id: uuid.UUID, user: CurrentUser
) -> BankReconciliation | None:
    q = select(BankReconciliation).where(BankReconciliation.id == recon_id)
    if not user.is_master:
        q = q.where(BankReconciliation.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("/reconciliations", response_model=PaginatedResponse[BankReconciliationResponse])
async def list_reconciliations(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    trust_account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[BankReconciliationResponse]:
    """List bank reconciliations."""
    count_q = select(func.count()).select_from(BankReconciliation)
    if not user.is_master:
        count_q = count_q.where(BankReconciliation.tenant_id == user.tenant_id)
    if trust_account_id:
        count_q = count_q.where(BankReconciliation.trust_account_id == trust_account_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(BankReconciliation)
    if not user.is_master:
        q = q.where(BankReconciliation.tenant_id == user.tenant_id)
    if trust_account_id:
        q = q.where(BankReconciliation.trust_account_id == trust_account_id)
    q = q.order_by(BankReconciliation.period_end.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[BankReconciliationResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/reconciliations/{reconciliation_id}", response_model=BankReconciliationResponse)
async def get_reconciliation(
    reconciliation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BankReconciliationResponse:
    """Get a bank reconciliation by ID."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found")
    return BankReconciliationResponse.model_validate(rec)


@router.post(
    "/reconciliations",
    response_model=BankReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reconciliation(
    data: BankReconciliationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BankReconciliationResponse:
    """Create a bank reconciliation."""
    ta = await _get_trust_account(session, data.trust_account_id, user)
    if not ta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")

    rec = BankReconciliation(
        tenant_id=ta.tenant_id,
        trust_account_id=data.trust_account_id,
        period_start=data.period_start,
        period_end=data.period_end,
        statement_balance=data.statement_balance,
        book_balance=data.book_balance,
        adjusted_balance=data.adjusted_balance,
        difference=data.difference,
        status=data.status,
        reconciled_by_id=data.reconciled_by_id,
        approved_by_id=data.approved_by_id,
        completed_at=data.completed_at,
        notes=data.notes,
        import_config=data.import_config,
    )
    session.add(rec)
    await session.flush()
    await session.refresh(rec)
    return BankReconciliationResponse.model_validate(rec)


@router.patch("/reconciliations/{reconciliation_id}", response_model=BankReconciliationResponse)
async def update_reconciliation(
    reconciliation_id: uuid.UUID,
    data: BankReconciliationUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BankReconciliationResponse:
    """Update a bank reconciliation."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rec, k, v)
    await session.flush()
    return BankReconciliationResponse.model_validate(rec)


class BankStatementImportRequest(BaseModel):
    """Parsed bank statement lines for import."""

    lines: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/reconciliations/{reconciliation_id}/import-bank-statement",
    response_model=BankReconciliationResponse,
)
async def import_bank_statement(
    reconciliation_id: uuid.UUID,
    body: BankStatementImportRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> BankReconciliationResponse:
    """Import bank statement lines as reconciliation items and store raw lines in import_config."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found")

    rec.import_config = {
        **rec.import_config,
        "imported_lines": body.lines,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    for line in body.lines:
        amt = line.get("statement_amount") or line.get("amount")
        stmt_date_raw = line.get("statement_date") or line.get("date")
        stmt_date: date | None = None
        if stmt_date_raw is not None:
            if isinstance(stmt_date_raw, date):
                stmt_date = stmt_date_raw
            elif isinstance(stmt_date_raw, datetime):
                stmt_date = stmt_date_raw.date()
            elif isinstance(stmt_date_raw, str):
                stmt_date = date.fromisoformat(stmt_date_raw[:10])
        item = ReconciliationItem(
            tenant_id=rec.tenant_id,
            reconciliation_id=rec.id,
            match_status=ReconciliationMatchStatus.UNMATCHED,
            statement_amount=int(amt) if amt is not None else None,
            statement_date=stmt_date,
            statement_reference=line.get("statement_reference") or line.get("reference"),
            statement_description=line.get("statement_description") or line.get("description"),
            book_transaction_id=None,
            book_amount=None,
            difference=0,
            notes=line.get("notes"),
        )
        session.add(item)
    await session.flush()
    await session.refresh(rec)
    return BankReconciliationResponse.model_validate(rec)


@router.post("/reconciliations/{reconciliation_id}/auto-match")
async def auto_match_reconciliation(
    reconciliation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> dict[str, Any]:
    """Match unmatched reconciliation items to trust transactions by amount (and date when present)."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found")

    iq = select(ReconciliationItem).where(
        ReconciliationItem.reconciliation_id == rec.id,
        ReconciliationItem.match_status == ReconciliationMatchStatus.UNMATCHED,
    )
    items = list((await session.execute(iq)).scalars().all())

    tq = select(TrustTransaction).where(TrustTransaction.trust_account_id == rec.trust_account_id)
    if not user.is_master:
        tq = tq.where(TrustTransaction.tenant_id == user.tenant_id)
    txs = list((await session.execute(tq)).scalars().all())
    used_tx: set[uuid.UUID] = set()

    matched = 0
    for item in items:
        if item.statement_amount is None or item.book_transaction_id:
            continue
        want = item.statement_amount
        pick: TrustTransaction | None = None
        for tx in txs:
            if tx.id in used_tx:
                continue
            if tx.amount == want or tx.amount == -want:
                pick = tx
                break
        if pick:
            item.book_transaction_id = pick.id
            item.book_amount = pick.amount
            item.match_status = ReconciliationMatchStatus.MATCHED
            item.difference = want - pick.amount
            used_tx.add(pick.id)
            matched += 1

    await session.flush()
    return {"reconciliation_id": str(reconciliation_id), "matched_items": matched}


# --- Reconciliation items ---


@router.get(
    "/reconciliations/{reconciliation_id}/items",
    response_model=PaginatedResponse[ReconciliationItemResponse],
)
async def list_reconciliation_items(
    reconciliation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[ReconciliationItemResponse]:
    """List line items for a reconciliation."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation not found")

    count_q = (
        select(func.count())
        .select_from(ReconciliationItem)
        .where(ReconciliationItem.reconciliation_id == reconciliation_id)
    )
    if not user.is_master:
        count_q = count_q.where(ReconciliationItem.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(ReconciliationItem).where(ReconciliationItem.reconciliation_id == reconciliation_id)
    if not user.is_master:
        q = q.where(ReconciliationItem.tenant_id == user.tenant_id)
    q = q.offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[ReconciliationItemResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get(
    "/reconciliations/{reconciliation_id}/items/{item_id}",
    response_model=ReconciliationItemResponse,
)
async def get_reconciliation_item(
    reconciliation_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ReconciliationItemResponse:
    """Get a single reconciliation item."""
    q = select(ReconciliationItem).where(
        ReconciliationItem.id == item_id,
        ReconciliationItem.reconciliation_id == reconciliation_id,
    )
    if not user.is_master:
        q = q.where(ReconciliationItem.tenant_id == user.tenant_id)
    r = await session.execute(q)
    item = r.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation item not found")
    return ReconciliationItemResponse.model_validate(item)


@router.post(
    "/reconciliations/{reconciliation_id}/items",
    response_model=ReconciliationItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reconciliation_item(
    reconciliation_id: uuid.UUID,
    data: ReconciliationItemCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ReconciliationItemResponse:
    """Create a reconciliation line item."""
    rec = await _get_reconciliation(session, reconciliation_id, user)
    if not rec or data.reconciliation_id != reconciliation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation not found or ID mismatch",
        )

    item = ReconciliationItem(
        tenant_id=rec.tenant_id,
        reconciliation_id=reconciliation_id,
        match_status=data.match_status,
        statement_amount=data.statement_amount,
        statement_date=data.statement_date,
        statement_reference=data.statement_reference,
        statement_description=data.statement_description,
        book_transaction_id=data.book_transaction_id,
        book_amount=data.book_amount,
        difference=data.difference,
        notes=data.notes,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return ReconciliationItemResponse.model_validate(item)


@router.patch(
    "/reconciliations/{reconciliation_id}/items/{item_id}",
    response_model=ReconciliationItemResponse,
)
async def update_reconciliation_item(
    reconciliation_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ReconciliationItemUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ReconciliationItemResponse:
    """Update a reconciliation line item."""
    q = select(ReconciliationItem).where(
        ReconciliationItem.id == item_id,
        ReconciliationItem.reconciliation_id == reconciliation_id,
    )
    if not user.is_master:
        q = q.where(ReconciliationItem.tenant_id == user.tenant_id)
    r = await session.execute(q)
    item = r.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation item not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await session.flush()
    return ReconciliationItemResponse.model_validate(item)
