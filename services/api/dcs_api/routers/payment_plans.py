"""Payment plan API routes."""
import uuid as _uuid
from typing import Annotated, Any
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Payment, PaymentStatus
from dcs_api.models.workflow import ActivityEntry
from dcs_api.models.payment_plans import PaymentPlan, PlanStatus, ScheduledPayment, PaymentFrequency
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.payment_plans import (
    PaymentPlanCreate,
    PaymentPlanResponse,
    PaymentPlanUpdate,
    ScheduledPaymentResponse,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


def _frequency_days(freq: str) -> int:
    mapping = {"weekly": 7, "biweekly": 14, "monthly": 30, "semi_monthly": 15, "quarterly": 90, "lump_sum": 0}
    return mapping.get(freq, 30)


@router.get("", response_model=PaginatedResponse[PaymentPlanResponse])
async def list_plans(
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    q = select(PaymentPlan).where(PaymentPlan.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(PaymentPlan.account_id == account_id)
    if status_filter:
        q = q.where(PaymentPlan.status == status_filter)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(PaymentPlan.created_at.desc()))
    items = [PaymentPlanResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/report/agreements-with-payments")
async def payment_agreement_report(
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="plan_status"),
) -> dict[str, Any]:
    """Report: accounts with payment agreements and their payment history."""
    plan_q = (
        select(PaymentPlan)
        .where(PaymentPlan.tenant_id == user.tenant_id)
        .options(selectinload(PaymentPlan.scheduled_payments))
    )
    if status_filter:
        plan_q = plan_q.where(PaymentPlan.status == status_filter)
    plan_q = plan_q.order_by(PaymentPlan.start_date.desc())

    count_q = select(func.count()).select_from(
        select(PaymentPlan.id).where(PaymentPlan.tenant_id == user.tenant_id).subquery()
    )
    if status_filter:
        count_q = select(func.count()).select_from(
            select(PaymentPlan.id)
            .where(PaymentPlan.tenant_id == user.tenant_id, PaymentPlan.status == status_filter)
            .subquery()
        )
    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    result = await session.execute(plan_q.offset(offset).limit(page_size))
    plans = list(result.scalars().all())

    account_ids = list({p.account_id for p in plans})
    accounts_map: dict[str, Account] = {}
    if account_ids:
        acc_result = await session.execute(
            select(Account).where(Account.id.in_(account_ids))
        )
        for a in acc_result.scalars().all():
            accounts_map[str(a.id)] = a

    # Pull actual payments from payments table
    payments_map: dict[str, list[dict]] = {}
    if account_ids:
        pay_result = await session.execute(
            select(Payment)
            .where(Payment.account_id.in_(account_ids), Payment.tenant_id == user.tenant_id)
            .order_by(Payment.received_at.desc())
        )
        for p in pay_result.scalars().all():
            aid = str(p.account_id)
            if aid not in payments_map:
                payments_map[aid] = []
            payments_map[aid].append({
                "id": str(p.id),
                "type": "payment",
                "amount_cents": p.amount,
                "method": p.method.value if p.method else None,
                "status": p.status.value if p.status else None,
                "date": p.received_at.isoformat() if p.received_at else None,
                "notes": None,
            })

    # Also pull activity_entries as account history (limited to 20 most recent per account)
    history_map: dict[str, list[dict]] = {}
    if account_ids:
        ae_result = await session.execute(
            select(ActivityEntry)
            .where(
                ActivityEntry.account_id.in_(account_ids),
                ActivityEntry.tenant_id == user.tenant_id,
            )
            .order_by(ActivityEntry.scheduled_date.desc())
            .limit(page_size * 20)
        )
        for ae in ae_result.scalars().all():
            aid = str(ae.account_id)
            if aid not in history_map:
                history_map[aid] = []
            if len(history_map[aid]) >= 20:
                continue
            result_data = ae.result or {}
            tag = result_data.get("tag", "") if isinstance(result_data, dict) else ""
            hist_type = result_data.get("type", "") if isinstance(result_data, dict) else ""
            history_map[aid].append({
                "id": str(ae.id),
                "type": "activity",
                "date": ae.scheduled_date.isoformat() if ae.scheduled_date else (ae.created_at.isoformat() if ae.created_at else None),
                "notes": ae.notes,
                "tag": tag,
                "hist_type": hist_type,
                "status": ae.status.value if ae.status else None,
            })

    items_out = []
    for plan in plans:
        aid = str(plan.account_id)
        acct = accounts_map.get(aid)
        sorted_sp = sorted(
            (plan.scheduled_payments or []),
            key=lambda sp: sp.payment_number,
            reverse=True,
        )
        scheduled = [
            {
                "payment_number": sp.payment_number,
                "due_date": sp.due_date.isoformat() if sp.due_date else None,
                "amount_due": float(sp.amount_due),
                "amount_paid": float(sp.amount_paid),
                "is_paid": sp.is_paid,
                "is_late": sp.is_late,
                "paid_date": sp.paid_date.isoformat() if sp.paid_date else None,
            }
            for sp in sorted_sp
        ]
        items_out.append({
            "plan_id": str(plan.id),
            "plan_type": plan.plan_type.value if plan.plan_type else None,
            "plan_status": plan.status.value if plan.status else None,
            "frequency": plan.frequency.value if plan.frequency else None,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "next_payment_date": plan.next_payment_date.isoformat() if plan.next_payment_date else None,
            "total_amount": float(plan.total_amount),
            "payment_amount": float(plan.payment_amount),
            "total_payments": plan.total_payments,
            "payments_made": plan.payments_made,
            "payments_remaining": plan.payments_remaining,
            "amount_paid": float(plan.amount_paid),
            "balance_remaining": float(plan.balance_remaining),
            "is_settlement": plan.is_settlement,
            "account": {
                "id": aid,
                "account_reference": acct.account_reference if acct else "—",
                "original_creditor": acct.original_creditor if acct else "—",
                "total_balance_cents": acct.total_balance if acct else 0,
                "status": acct.status.value if acct and acct.status else "—",
            },
            "scheduled_payments": scheduled,
            "actual_payments": payments_map.get(aid, []),
            "account_history": history_map.get(aid, []),
        })

    return {
        "items": items_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{plan_id}", response_model=PaymentPlanResponse)
async def get_plan(
    plan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == user.tenant_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Payment plan not found")
    return PaymentPlanResponse.model_validate(plan)


@router.post("", response_model=PaymentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PaymentPlanCreate,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    plan = PaymentPlan(
        **body.model_dump(),
        tenant_id=user.tenant_id,
        payments_remaining=body.total_payments,
        balance_remaining=body.total_amount,
        next_payment_date=body.start_date,
    )
    session.add(plan)
    await session.flush()

    freq_days = _frequency_days(body.frequency)
    for i in range(body.total_payments):
        due = body.start_date + timedelta(days=freq_days * i) if freq_days > 0 else body.start_date
        sp = ScheduledPayment(
            plan_id=plan.id,
            payment_number=i + 1,
            due_date=due,
            amount_due=body.payment_amount,
            tenant_id=user.tenant_id,
        )
        session.add(sp)
    await session.flush()
    await session.refresh(plan)
    return PaymentPlanResponse.model_validate(plan)


@router.patch("/{plan_id}", response_model=PaymentPlanResponse)
async def update_plan(
    plan_id: str,
    body: PaymentPlanUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == user.tenant_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Payment plan not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    await session.flush()
    await session.refresh(plan)
    return PaymentPlanResponse.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == user.tenant_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Payment plan not found")
    await session.delete(plan)
    await session.flush()


@router.get("/{plan_id}/schedule", response_model=list[ScheduledPaymentResponse])
async def get_schedule(
    plan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ScheduledPayment).where(ScheduledPayment.plan_id == plan_id, ScheduledPayment.tenant_id == user.tenant_id)
        .order_by(ScheduledPayment.payment_number)
    )
    return [ScheduledPaymentResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/{plan_id}/activate", response_model=PaymentPlanResponse)
async def activate_plan(
    plan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("payment_plans:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(PaymentPlan).where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == user.tenant_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Payment plan not found")
    plan.status = PlanStatus.ACTIVE
    plan.approved_by = user.id
    plan.approved_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(plan)
    return PaymentPlanResponse.model_validate(plan)


