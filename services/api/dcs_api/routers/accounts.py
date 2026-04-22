"""Account management endpoints."""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, AccountStatus, DebtInstrument, Payment
from dcs_api.models.consumer import Consumer, ContactMethod
from dcs_api.models.workflow import ActivityEntry, ActivityPriority, ActivityStatus
from dcs_api.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

CLOSED_STATUSES = {
    AccountStatus.CLOSED,
    AccountStatus.PAID_IN_FULL,
    AccountStatus.SETTLED,
    AccountStatus.RECALLED,
    AccountStatus.STATUTE_BARRED,
}


@router.get("", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: AccountStatus | None = None,
    status_group: Literal["open", "closed"] | None = None,
    search: str | None = Query(None, max_length=200),
    consumer_id: uuid.UUID | None = None,
) -> PaginatedResponse[AccountResponse]:
    """List accounts in the tenant.

    status_group: "open" excludes closed/settled/PIF/recalled; "closed" shows only those.
    search: full-text search across reference, creditor, client account number.
    """
    query = select(Account).where(Account.tenant_id == user.tenant_id)

    if status_filter:
        query = query.where(Account.status == status_filter)
    elif status_group == "open":
        query = query.where(Account.status.notin_(CLOSED_STATUSES))
    elif status_group == "closed":
        query = query.where(Account.status.in_(CLOSED_STATUSES))

    if consumer_id:
        query = query.where(Account.consumer_id == consumer_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Account.account_reference.ilike(term),
                Account.original_creditor.ilike(term),
                Account.current_creditor.ilike(term),
                Account.client_account_number.ilike(term),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.options(selectinload(Account.debt_instrument)).offset(offset).limit(page_size)
    result = await session.execute(query)
    accounts = list(result.scalars().all())

    return PaginatedResponse(
        items=[AccountResponse.model_validate(a) for a in accounts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/export/csv")
async def export_accounts_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    status_filter: AccountStatus | None = None,
    status_group: Literal["open", "closed"] | None = None,
    search: str | None = Query(None, max_length=200),
) -> StreamingResponse:
    """Export accounts as CSV with the same filters as the list endpoint."""
    query = select(Account).where(Account.tenant_id == user.tenant_id)

    if status_filter:
        query = query.where(Account.status == status_filter)
    elif status_group == "open":
        query = query.where(Account.status.notin_(CLOSED_STATUSES))
    elif status_group == "closed":
        query = query.where(Account.status.in_(CLOSED_STATUSES))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Account.account_reference.ilike(term),
                Account.original_creditor.ilike(term),
                Account.current_creditor.ilike(term),
                Account.client_account_number.ilike(term),
            )
        )

    query = query.order_by(Account.account_reference)
    result = await session.execute(query)
    accounts = result.scalars().all()

    def fmt_money(cents: int | None) -> str:
        if cents is None:
            return "0.00"
        return f"{cents / 100:.2f}"

    def fmt_date(dt: datetime | None) -> str:
        if dt is None:
            return ""
        return dt.strftime("%m/%d/%Y")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Account Reference", "Original Creditor", "Current Creditor",
        "Client Account #", "Status", "Debt Type", "Jurisdiction",
        "Original Principal", "Current Principal", "Current Interest",
        "Current Fees", "Total Balance",
        "Date Placed", "Date of Service", "Date of First Delinquency",
        "Legal Hold", "Legal Hold Reason",
    ])

    for a in accounts:
        writer.writerow([
            a.account_reference,
            a.original_creditor,
            a.current_creditor or "",
            a.client_account_number or "",
            a.status.value if a.status else "",
            a.debt_type.value if a.debt_type else "",
            a.jurisdiction or "",
            fmt_money(a.original_principal),
            fmt_money(a.current_principal),
            fmt_money(a.current_interest),
            fmt_money(a.current_fees),
            fmt_money(a.total_balance),
            fmt_date(a.date_placed),
            fmt_date(a.date_of_service),
            fmt_date(a.date_of_first_delinquency),
            "Yes" if a.legal_hold else "No",
            a.legal_hold_reason or "",
        ])

    buf.seek(0)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"accounts-{status_group or 'all'}-{today}.csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{account_id}")
async def get_account(
    account_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> dict:
    """Get account by ID with full detail including debtor/consumer info."""
    query = (
        select(Account)
        .where(Account.id == account_id, Account.tenant_id == user.tenant_id)
        .options(
            selectinload(Account.debt_instrument),
            selectinload(Account.consumer).selectinload(Consumer.contact_methods),
        )
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    resp = AccountResponse.model_validate(account).model_dump()

    consumer = account.consumer
    if consumer:
        contacts = consumer.contact_methods or []
        phones = [
            {"type": c.contact_type.value, "value": c.value, "is_primary": c.is_primary}
            for c in contacts if "phone" in c.contact_type.value
        ]
        emails = [
            {"value": c.value, "is_primary": c.is_primary}
            for c in contacts if c.contact_type.value == "email"
        ]
        addresses = [
            {
                "type": c.contact_type.value,
                "line1": c.address_line_1, "line2": c.address_line_2,
                "city": c.city, "state": c.state, "zip": c.postal_code,
                "is_primary": c.is_primary,
            }
            for c in contacts if "address" in c.contact_type.value
        ]
        resp["debtor"] = {
            "id": str(consumer.id),
            "first_name": consumer.first_name,
            "last_name": consumer.last_name,
            "middle_name": consumer.middle_name,
            "suffix": consumer.suffix,
            "ssn_last_four": consumer.ssn_last_four,
            "date_of_birth": consumer.date_of_birth.isoformat() if consumer.date_of_birth else None,
            "is_deceased": consumer.is_deceased,
            "is_represented": consumer.is_represented,
            "attorney_name": consumer.attorney_name,
            "attorney_contact": consumer.attorney_contact,
            "phones": phones,
            "emails": emails,
            "addresses": addresses,
        }
    else:
        resp["debtor"] = None

    return resp


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> AccountResponse:
    """Create a new account."""
    # Calculate total balance
    total_balance = data.current_principal + data.current_interest + data.current_fees

    account = Account(
        tenant_id=user.tenant_id,
        consumer_id=data.consumer_id,
        account_reference=data.account_reference,
        original_creditor=data.original_creditor,
        current_creditor=data.current_creditor,
        client_account_number=data.client_account_number,
        debt_type=data.debt_type,
        jurisdiction=data.jurisdiction,
        original_principal=data.original_principal,
        current_principal=data.current_principal,
        current_interest=data.current_interest,
        current_fees=data.current_fees,
        total_balance=total_balance,
        date_of_service=data.date_of_service,
        date_of_first_delinquency=data.date_of_first_delinquency,
        date_placed=data.date_placed,
        extra_data=data.extra_data,
    )
    session.add(account)
    await session.flush()

    # Add debt instrument if provided
    if data.debt_instrument:
        instrument = DebtInstrument(
            tenant_id=user.tenant_id,
            account_id=account.id,
            instrument_type=data.debt_instrument.instrument_type,
            interest_rate=data.debt_instrument.interest_rate,
            interest_type=data.debt_instrument.interest_type,
            contract_date=data.debt_instrument.contract_date,
            terms=data.debt_instrument.terms,
        )
        session.add(instrument)

    await session.flush()
    await session.refresh(account)

    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_BALANCES_FEES))],
) -> AccountResponse:
    """Update account.

    Note: Accounts under legal hold have restricted modifications.
    Balance changes require elevated permissions.
    """
    query = (
        select(Account)
        .where(Account.id == account_id, Account.tenant_id == user.tenant_id)
        .options(selectinload(Account.debt_instrument))
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Check legal hold
    if account.legal_hold:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is under legal hold - modifications restricted",
        )

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    # Recalculate total balance
    account.total_balance = account.current_principal + account.current_interest + account.current_fees

    await session.flush()
    return AccountResponse.model_validate(account)


@router.post("/{account_id}/legal-hold")
async def apply_legal_hold(
    account_id: uuid.UUID,
    reason: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_DISPUTES))],
) -> dict:
    """Apply legal hold to an account.

    Non-legal guidance: Legal hold prevents modifications and deletion.
    Required for disputes, litigation, bankruptcy, and regulatory inquiries.
    """
    query = select(Account).where(
        Account.id == account_id, Account.tenant_id == user.tenant_id
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    account.legal_hold = True
    account.legal_hold_reason = reason
    account.legal_hold_date = datetime.now(timezone.utc)
    account.status = AccountStatus.LEGAL_HOLD

    await session.flush()
    return {"message": "Legal hold applied", "account_id": str(account_id)}


@router.delete("/{account_id}/legal-hold")
async def release_legal_hold(
    account_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.APPROVE_LITIGATION_FILINGS))],
) -> dict:
    """Release legal hold from an account.

    Non-legal guidance: Releasing legal hold requires elevated permissions.
    Verify all underlying conditions (disputes, litigation) are resolved.
    """
    query = select(Account).where(
        Account.id == account_id, Account.tenant_id == user.tenant_id
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    account.legal_hold = False
    account.legal_hold_reason = None
    account.legal_hold_date = None
    account.status = AccountStatus.ACTIVE

    await session.flush()
    return {"message": "Legal hold released", "account_id": str(account_id)}


@router.get("/{account_id}/history")
async def get_account_history(
    account_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, max_length=200),
    entry_type: Literal["all", "activity", "payment"] | None = Query(None),
) -> dict:
    """Get combined history for an account: activity entries + payments.

    search: case-insensitive text search across notes, method, source, status, tag.
    entry_type: filter to only activities or only payments.
    """
    acct_q = select(Account).where(
        Account.id == account_id, Account.tenant_id == user.tenant_id
    )
    if not (await session.execute(acct_q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Unfiltered totals (for badge counts)
    act_count_total = (await session.execute(
        select(func.count()).select_from(
            select(ActivityEntry.id)
            .where(ActivityEntry.account_id == account_id, ActivityEntry.tenant_id == user.tenant_id)
            .subquery()
        )
    )).scalar() or 0

    pay_count_total = (await session.execute(
        select(func.count()).select_from(
            select(Payment.id)
            .where(Payment.account_id == account_id, Payment.tenant_id == user.tenant_id)
            .subquery()
        )
    )).scalar() or 0

    history: list[dict] = []
    search_lower = search.strip().lower() if search and search.strip() else None
    include_activities = entry_type in (None, "all", "activity")
    include_payments = entry_type in (None, "all", "payment")

    if include_activities:
        act_q = (
            select(ActivityEntry)
            .where(ActivityEntry.account_id == account_id, ActivityEntry.tenant_id == user.tenant_id)
            .order_by(ActivityEntry.scheduled_date.desc())
        )
        if search_lower:
            act_q = act_q.where(
                or_(
                    ActivityEntry.notes.ilike(f"%{search_lower}%"),
                    func.cast(ActivityEntry.result, String).ilike(f"%{search_lower}%"),
                )
            )
        act_result = await session.execute(act_q)
        for a in act_result.scalars().all():
            dt = a.scheduled_date or a.created_at
            result_data = a.result or {}
            tag = result_data.get("tag", "") if isinstance(result_data, dict) else ""
            hist_type = result_data.get("type", "") if isinstance(result_data, dict) else ""
            history.append({
                "type": "activity",
                "id": str(a.id),
                "date": dt.isoformat() if dt else "",
                "status": a.status.value if a.status else None,
                "notes": a.notes,
                "result": result_data,
                "priority": a.priority.value if a.priority else None,
                "tag": tag,
                "hist_type": hist_type,
            })

    if include_payments:
        pay_q = (
            select(Payment)
            .where(Payment.account_id == account_id, Payment.tenant_id == user.tenant_id)
            .order_by(Payment.received_at.desc())
        )
        if search_lower:
            pay_q = pay_q.where(
                or_(
                    func.cast(Payment.method, String).ilike(f"%{search_lower}%"),
                    Payment.source.ilike(f"%{search_lower}%"),
                    func.cast(Payment.status, String).ilike(f"%{search_lower}%"),
                )
            )
        pay_result = await session.execute(pay_q)
        for p in pay_result.scalars().all():
            dt = p.received_at or p.created_at
            history.append({
                "type": "payment",
                "id": str(p.id),
                "date": dt.isoformat() if dt else "",
                "amount_cents": p.amount,
                "method": p.method.value if p.method else None,
                "status": p.status.value if p.status else None,
                "source": p.source,
            })

    history.sort(key=lambda x: x.get("date", ""), reverse=True)
    total = len(history)
    offset = (page - 1) * page_size
    page_items = history[offset:offset + page_size]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "activity_count": act_count_total,
        "payment_count": pay_count_total,
    }


@router.post("/{account_id}/notes")
async def add_account_note(
    account_id: uuid.UUID,
    body: dict,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> dict:
    """Add a note/history entry to an account without requiring an activity code."""
    acct_q = select(Account).where(
        Account.id == account_id, Account.tenant_id == user.tenant_id
    )
    if not (await session.execute(acct_q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    notes = body.get("notes", "").strip()
    if not notes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notes cannot be empty")

    now = datetime.now(timezone.utc)
    entry = ActivityEntry(
        tenant_id=user.tenant_id,
        account_id=account_id,
        activity_code_id=None,
        assigned_to_id=user.id if hasattr(user, 'id') else user.user_id,
        status=ActivityStatus.COMPLETED,
        priority=ActivityPriority.NORMAL,
        scheduled_date=now,
        started_at=now,
        completed_at=now,
        notes=notes,
        result={"type": "manual_note", "added_by": str(user.user_id)},
    )
    session.add(entry)
    await session.flush()

    return {
        "id": str(entry.id),
        "message": "Note added",
        "date": now.isoformat(),
    }
