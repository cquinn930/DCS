"""Dashboard analytics (live metrics, collector, management, queues)."""

import uuid
from datetime import date, datetime, time, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import (
    Account,
    AccountStatus,
    Case,
    CaseStatus,
    Dispute,
    DisputeStatus,
    Payment,
    PaymentStatus,
)
from dcs_api.models.litigation import LitigationCase, LitigationStatus
from dcs_api.models.performance import CollectorGoal, PerformanceSnapshot
from dcs_api.models.tenant import User
from dcs_api.models.trust import TrustAccount, TrustAccountStatus
from dcs_api.models.workflow import (
    ActivityEntry,
    ActivityStatus,
    QueueEntry,
    QueueEntryStatus,
    WorkQueue,
)
from dcs_api.schemas.dashboard import (
    CollectorDashboardResponse,
    LiveMetricsResponse,
    ManagementDashboardResponse,
    QueueStatsResponse,
)

router = APIRouter()


def _tenant_clause(model, user: CurrentUser):
    if user.is_master:
        return None
    return model.tenant_id == user.tenant_id


async def _require_user_in_scope(
    session: AsyncSession, collector_id: uuid.UUID, user: CurrentUser
) -> User:
    q = select(User).where(User.id == collector_id)
    if not user.is_master:
        q = q.where(User.tenant_id == user.tenant_id)
    u = (await session.execute(q)).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return u


@router.get("/live-metrics", response_model=LiveMetricsResponse)
async def get_live_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("dashboard:view"))],
) -> LiveMetricsResponse:
    """Real-time portfolio and operations counts."""
    tc = _tenant_clause(Account, user)
    open_statuses = [AccountStatus.ACTIVE, AccountStatus.HOLD, AccountStatus.LEGAL_HOLD]
    acc_q = select(
        func.count(Account.id),
        func.coalesce(func.sum(Account.total_balance), 0),
    ).where(Account.status.in_(open_statuses))
    if tc is not None:
        acc_q = acc_q.where(tc)
    active_q = select(func.count(Account.id)).where(Account.status == AccountStatus.ACTIVE)
    if tc is not None:
        active_q = active_q.where(tc)

    _, total_bal = (await session.execute(acc_q)).one()
    active_n = (await session.execute(active_q)).scalar_one()

    dclause = _tenant_clause(Dispute, user)
    disp_q = select(func.count(Dispute.id)).where(
        Dispute.status.in_([DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW])
    )
    if dclause is not None:
        disp_q = disp_q.where(dclause)

    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    pay_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.received_at >= start,
        Payment.received_at <= end,
    )
    if not user.is_master:
        pay_q = pay_q.join(Account, Account.id == Payment.account_id).where(
            Account.tenant_id == user.tenant_id
        )

    act_q = select(func.count(ActivityEntry.id)).where(
        ActivityEntry.status.in_([ActivityStatus.SCHEDULED, ActivityStatus.READY])
    )
    if not user.is_master:
        act_q = act_q.where(ActivityEntry.tenant_id == user.tenant_id)

    qe_q = select(func.count(QueueEntry.id)).where(
        QueueEntry.status == QueueEntryStatus.PENDING,
    )
    if not user.is_master:
        qe_q = qe_q.where(QueueEntry.tenant_id == user.tenant_id)

    open_disputes = (await session.execute(disp_q)).scalar_one()
    pay_today = (await session.execute(pay_q)).scalar_one()
    pending_act = (await session.execute(act_q)).scalar_one()
    q_pending = (await session.execute(qe_q)).scalar_one()

    return LiveMetricsResponse(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        generated_at=datetime.now(timezone.utc),
        active_accounts=int(active_n or 0),
        total_balance_cents=int(total_bal or 0),
        open_disputes=int(open_disputes or 0),
        payments_today_cents=int(pay_today or 0),
        pending_activities=int(pending_act or 0),
        queue_accounts_pending=int(q_pending or 0),
    )


@router.get("/collector/{collector_id}", response_model=CollectorDashboardResponse)
async def get_collector_dashboard(
    collector_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("dashboard:view"))],
) -> CollectorDashboardResponse:
    """Collector workspace: queue, goals, and recent activity."""
    await _require_user_in_scope(session, collector_id, user)

    tc = _tenant_clause(Case, user)
    assigned_q = select(func.count(Case.id)).where(
        Case.assigned_to_id == collector_id,
        Case.status != CaseStatus.CLOSED,
    )
    if tc is not None:
        assigned_q = assigned_q.where(tc)
    assigned_n = (await session.execute(assigned_q)).scalar_one()

    qe_tc = _tenant_clause(QueueEntry, user)
    depth_q = select(func.count(QueueEntry.id)).where(
        QueueEntry.assigned_to_id == collector_id,
        QueueEntry.status.in_(
            [
                QueueEntryStatus.PENDING,
                QueueEntryStatus.ASSIGNED,
                QueueEntryStatus.IN_PROGRESS,
            ]
        ),
    )
    if qe_tc is not None:
        depth_q = depth_q.where(qe_tc)
    depth_n = (await session.execute(depth_q)).scalar_one()

    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    due_q = select(func.count(ActivityEntry.id)).where(
        ActivityEntry.assigned_to_id == collector_id,
        ActivityEntry.scheduled_date >= start,
        ActivityEntry.scheduled_date <= end,
        ActivityEntry.status.in_([ActivityStatus.SCHEDULED, ActivityStatus.READY, ActivityStatus.IN_PROGRESS]),
    )
    if not user.is_master:
        due_q = due_q.where(ActivityEntry.tenant_id == user.tenant_id)
    due_n = (await session.execute(due_q)).scalar_one()

    pay_join = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Account, Account.id == Payment.account_id)
        .join(Case, Case.account_id == Account.id)
        .where(
            Case.assigned_to_id == collector_id,
            Payment.status == PaymentStatus.COMPLETED,
            Payment.received_at >= start,
            Payment.received_at <= end,
        )
    )
    if not user.is_master:
        pay_join = pay_join.where(Account.tenant_id == user.tenant_id)
    pay_sum = (await session.execute(pay_join)).scalar_one()

    calls_q = select(func.coalesce(func.sum(PerformanceSnapshot.calls_made), 0)).where(
        PerformanceSnapshot.collector_id == collector_id,
        PerformanceSnapshot.snapshot_date == today,
    )
    if not user.is_master:
        calls_q = calls_q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    calls_today = (await session.execute(calls_q)).scalar_one()

    goals_q = select(CollectorGoal).where(CollectorGoal.collector_id == collector_id)
    if not user.is_master:
        goals_q = goals_q.where(CollectorGoal.tenant_id == user.tenant_id)
    goals_q = goals_q.where(
        CollectorGoal.period_start <= today,
        CollectorGoal.period_end >= today,
    )
    goals = list((await session.execute(goals_q)).scalars().all())
    progress: float | None = None
    if goals:
        ratios = [min(g.actual_amount / g.target_amount, 1.0) if g.target_amount else 0.0 for g in goals]
        progress = round(sum(ratios) / len(ratios) * 100.0, 2)

    extra: dict[str, Any] = {
        "total_assigned_accounts_reported": int(assigned_n or 0),
        "snapshot_calls_today": int(calls_today or 0),
    }

    return CollectorDashboardResponse(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        collector_id=collector_id,
        generated_at=datetime.now(timezone.utc),
        assigned_accounts=int(assigned_n or 0),
        queue_depth=int(depth_n or 0),
        activities_due_today=int(due_n or 0),
        payments_secured_cents=int(pay_sum or 0),
        calls_today=int(calls_today or 0),
        goal_progress_pct=progress,
        extra=extra,
    )


@router.get("/management", response_model=ManagementDashboardResponse)
async def get_management_dashboard(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("dashboard:manage"))],
) -> ManagementDashboardResponse:
    """Agency-level KPIs (management)."""
    acct_tc = _tenant_clause(Account, user)
    port_q = select(func.coalesce(func.sum(Account.total_balance), 0))
    if acct_tc is not None:
        port_q = port_q.where(acct_tc)
    portfolio = (await session.execute(port_q)).scalar_one()

    coll_q = select(func.count(func.distinct(Case.assigned_to_id))).where(
        Case.assigned_to_id.isnot(None),
        Case.status != CaseStatus.CLOSED,
    )
    if not user.is_master:
        coll_q = coll_q.where(Case.tenant_id == user.tenant_id)
    active_coll = (await session.execute(coll_q)).scalar_one()

    lit_q = select(func.count(LitigationCase.id)).where(
        LitigationCase.status.not_in([LitigationStatus.SATISFIED, LitigationStatus.DISMISSED])
    )
    if not user.is_master:
        lit_q = lit_q.where(LitigationCase.tenant_id == user.tenant_id)
    lit_open = (await session.execute(lit_q)).scalar_one()

    trust_q = select(func.coalesce(func.sum(TrustAccount.current_balance), 0)).where(
        TrustAccount.status == TrustAccountStatus.ACTIVE,
    )
    if not user.is_master:
        trust_q = trust_q.where(TrustAccount.tenant_id == user.tenant_id)
    trust_bal = (await session.execute(trust_q)).scalar_one()

    month_start = date.today().replace(day=1)
    m_start = datetime.combine(month_start, time.min, tzinfo=timezone.utc)
    mtd_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.received_at >= m_start,
    )
    if not user.is_master:
        mtd_q = mtd_q.join(Account, Account.id == Payment.account_id).where(
            Account.tenant_id == user.tenant_id
        )
    mtd = (await session.execute(mtd_q)).scalar_one()

    acc_n_q = select(func.count(Account.id))
    if acct_tc is not None:
        acc_n_q = acc_n_q.where(acct_tc)
    acc_total = (await session.execute(acc_n_q)).scalar_one() or 1
    disp_open_q = select(func.count(Dispute.id)).where(
        Dispute.status.in_([DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW])
    )
    if not user.is_master:
        disp_open_q = disp_open_q.where(Dispute.tenant_id == user.tenant_id)
    disp_open = (await session.execute(disp_open_q)).scalar_one()
    dispute_rate = round((disp_open / acc_total) * 100.0, 2) if acc_total else None

    comp_q = (
        select(Case.assigned_to_id, func.count(Case.id))
        .where(
            Case.assigned_to_id.isnot(None),
            Case.status != CaseStatus.CLOSED,
        )
        .group_by(Case.assigned_to_id)
    )
    if not user.is_master:
        comp_q = comp_q.where(Case.tenant_id == user.tenant_id)
    comp_rows = (await session.execute(comp_q)).all()
    collector_comparison = [
        {"collector_id": str(r[0]), "open_cases": int(r[1])} for r in comp_rows[:50]
    ]

    client_q = (
        select(Account.original_creditor, func.count(Account.id), func.sum(Account.total_balance))
        .group_by(Account.original_creditor)
    )
    if acct_tc is not None:
        client_q = client_q.where(acct_tc)
    client_q = client_q.order_by(func.sum(Account.total_balance).desc()).limit(10)
    client_rows = (await session.execute(client_q)).all()
    top_clients = [
        {"client": r[0], "accounts": int(r[1]), "balance_cents": int(r[2] or 0)}
        for r in client_rows
    ]

    extra: dict[str, Any] = {
        "collector_comparison": collector_comparison,
        "top_clients": top_clients,
    }

    return ManagementDashboardResponse(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        generated_at=datetime.now(timezone.utc),
        total_portfolio_cents=int(portfolio or 0),
        active_collectors=int(active_coll or 0),
        litigation_cases_open=int(lit_open or 0),
        trust_balance_cents=int(trust_bal or 0),
        month_to_date_collected_cents=int(mtd or 0),
        dispute_rate_pct=dispute_rate,
        extra=extra,
    )


@router.get("/queue-stats", response_model=list[QueueStatsResponse])
async def get_queue_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("dashboard:view"))],
) -> list[QueueStatsResponse]:
    """Per-queue volume and aging (all queues in scope)."""
    wq_q = select(WorkQueue)
    if not user.is_master:
        wq_q = wq_q.where(WorkQueue.tenant_id == user.tenant_id)
    queues = list((await session.execute(wq_q)).scalars().all())
    now = datetime.now(timezone.utc)
    out: list[QueueStatsResponse] = []
    for wq in queues:
        base = select(QueueEntry).where(QueueEntry.queue_id == wq.id)
        if not user.is_master:
            base = base.where(QueueEntry.tenant_id == user.tenant_id)
        entries = list((await session.execute(base)).scalars().all())
        pending = sum(1 for e in entries if e.status == QueueEntryStatus.PENDING)
        inprog = sum(
            1
            for e in entries
            if e.status in (QueueEntryStatus.ASSIGNED, QueueEntryStatus.IN_PROGRESS)
        )
        completed_today = sum(
            1
            for e in entries
            if e.status == QueueEntryStatus.COMPLETED
            and e.completed_at
            and e.completed_at.date() == now.date()
        )
        ages_hours: list[float] = []
        oldest: datetime | None = None
        sla_breaches = 0
        for e in entries:
            if e.status in (
                QueueEntryStatus.PENDING,
                QueueEntryStatus.ASSIGNED,
                QueueEntryStatus.IN_PROGRESS,
            ):
                age_h = (now - e.entered_at).total_seconds() / 3600.0
                ages_hours.append(age_h)
                oldest = e.entered_at if oldest is None or e.entered_at < oldest else oldest
                if wq.sla_hours is not None and age_h > wq.sla_hours:
                    sla_breaches += 1
        avg_age = round(sum(ages_hours) / len(ages_hours), 2) if ages_hours else None

        out.append(
            QueueStatsResponse(
                id=uuid.uuid4(),
                tenant_id=wq.tenant_id,
                queue_id=wq.id,
                generated_at=now,
                pending_count=pending,
                in_progress_count=inprog,
                completed_today=completed_today,
                avg_age_hours=avg_age,
                sla_breaches=sla_breaches,
                oldest_entry_at=oldest,
            )
        )
    return out
