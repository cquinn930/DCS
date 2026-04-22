#!/usr/bin/env python3
"""Reconcile payment_plans with real data from accounts.

Derives payments_made from time elapsed since plan start date,
capped by the balance difference. Handles accounts with multiple
plans by splitting credit across plans proportionally.

Key formulas:
  max_possible   = periods elapsed since start_date
  payments_made  = min(max_possible, ceil(balance_diff / pmt_amount))
  amount_paid    = payments_made * pmt_amount
  balance_remaining = account current balance
"""

import asyncio
import math
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import asyncpg

DB_URL = "postgresql://dcs:dcs@localhost:5432/dcs"

FREQ_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "semi_monthly": 15,
    "quarterly": 91,
    "lump_sum": 0,
}


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    tid = await pool.fetchval("SELECT id FROM tenants WHERE slug='flg'")
    if not tid:
        print("FLG tenant not found")
        return

    # Clear old scheduled_payments
    deleted = await pool.fetchval(
        "WITH d AS (DELETE FROM scheduled_payments WHERE tenant_id = $1 RETURNING 1) SELECT count(*) FROM d", tid
    )
    print(f"Cleared {deleted or 0} existing scheduled_payments")

    plans = await pool.fetch("""
        SELECT pp.id, pp.account_id, pp.payment_amount, pp.frequency,
               pp.start_date, pp.status,
               a.original_principal, a.current_principal, a.total_balance,
               a.date_placed
        FROM payment_plans pp
        JOIN accounts a ON a.id = pp.account_id
        WHERE pp.tenant_id = $1
        ORDER BY pp.account_id, pp.start_date DESC
    """, tid)

    print(f"Found {len(plans)} payment plans to reconcile")

    # Group plans by account so we can handle duplicates
    plans_by_account: dict[str, list] = defaultdict(list)
    for p in plans:
        plans_by_account[str(p["account_id"])].append(p)

    unique_accounts = len(plans_by_account)
    multi_plan_accounts = sum(1 for v in plans_by_account.values() if len(v) > 1)
    print(f"  {unique_accounts:,} unique accounts, {multi_plan_accounts:,} with multiple plans")

    updated = 0
    sched_created = 0
    stats = {"date_fixed": 0, "paid_off": 0, "partial": 0, "no_payments": 0}
    today = date.today()

    for aid_str, acct_plans in plans_by_account.items():
        # All plans on the same account share the same balance info
        first = acct_plans[0]
        orig_prin = Decimal(str(first["original_principal"] or 0)) / 100
        curr_bal = Decimal(str(first["total_balance"] or 0)) / 100
        total_paid_on_account = max(Decimal(0), orig_prin - curr_bal)

        # Track how much of total_paid has been attributed across plans
        remaining_to_attribute = total_paid_on_account

        for idx, plan in enumerate(acct_plans):
            plan_id = plan["id"]
            pmt_amount = Decimal(str(plan["payment_amount"]))
            freq = plan["frequency"]
            start_dt = plan["start_date"]

            # -- Fix bad start dates --
            # Any date in 2026+ is from the import's datetime.now() fallback
            migration_cutoff = date(2026, 1, 1)
            if start_dt and start_dt >= migration_cutoff:
                date_placed = plan["date_placed"]
                if date_placed:
                    dp = date_placed.date() if hasattr(date_placed, 'date') else date_placed
                    if dp < migration_cutoff:
                        start_dt = dp
                    else:
                        start_dt = date(2020, 1, 1)
                else:
                    start_dt = date(2020, 1, 1)
                await pool.execute(
                    "UPDATE payment_plans SET start_date = $2, next_payment_date = $2 WHERE id = $1",
                    plan_id, start_dt,
                )
                stats["date_fixed"] += 1

            total_amount = orig_prin if orig_prin > 0 else curr_bal
            if total_amount <= 0:
                total_amount = pmt_amount * 12
            if pmt_amount <= 0:
                continue

            total_payments = int(math.ceil(total_amount / pmt_amount))
            if total_payments <= 0:
                total_payments = 1

            # -- Time-based cap: how many periods have elapsed since start --
            freq_days = FREQ_DAYS.get(freq, 30)
            if freq_days == 0:
                freq_days = 30

            if isinstance(start_dt, date) and start_dt < today:
                days_elapsed = (today - start_dt).days
                max_by_time = max(0, days_elapsed // freq_days)
            else:
                max_by_time = 0

            # -- Calculate payments_made --
            if remaining_to_attribute > 0 and pmt_amount > 0 and max_by_time > 0:
                # How many payments could this plan account for?
                could_pay = min(
                    max_by_time,
                    int(remaining_to_attribute / pmt_amount),
                    total_payments,
                )
                payments_made = could_pay
                amount_paid = pmt_amount * payments_made
                remaining_to_attribute -= amount_paid
            else:
                payments_made = 0
                amount_paid = Decimal(0)

            balance_remaining = max(Decimal(0), total_amount - amount_paid)
            payments_remaining = max(0, total_payments - payments_made)

            if payments_made >= total_payments:
                stats["paid_off"] += 1
            elif payments_made > 0:
                stats["partial"] += 1
            else:
                stats["no_payments"] += 1

            await pool.execute("""
                UPDATE payment_plans
                SET total_amount = $2,
                    total_payments = $3,
                    payments_made = $4,
                    amount_paid = $5,
                    balance_remaining = $6,
                    payments_remaining = $7,
                    original_balance = $8
                WHERE id = $1
            """,
                plan_id,
                float(total_amount),
                total_payments,
                payments_made,
                float(amount_paid),
                float(balance_remaining),
                payments_remaining,
                float(total_amount),
            )
            updated += 1

            # -- Generate scheduled_payments --
            if isinstance(start_dt, date) and (payments_made > 0 or max_by_time > 0):
                rows_to_generate = min(total_payments, payments_made + 3)

                for i in range(rows_to_generate):
                    due = start_dt + timedelta(days=freq_days * i)
                    sp_id = uuid.uuid4()
                    is_paid = i < payments_made
                    paid_amt = pmt_amount if is_paid else Decimal(0)
                    paid_date_val = due if is_paid else None
                    is_late = not is_paid and due < today

                    await pool.execute("""
                        INSERT INTO scheduled_payments
                            (id, tenant_id, plan_id, payment_number, due_date,
                             amount_due, amount_paid, is_paid, paid_date, payment_id, is_late)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (id) DO NOTHING
                    """,
                        sp_id, tid, plan_id, i + 1, due,
                        float(pmt_amount), float(paid_amt),
                        is_paid, paid_date_val, None, is_late,
                    )
                    sched_created += 1

        if updated % 500 == 0 and updated > 0:
            print(f"  Reconciled {updated:,} plans...")

    print(f"\nDone!")
    print(f"  Plans reconciled:           {updated:,}")
    print(f"  Scheduled payments created: {sched_created:,}")
    print(f"  Dates fixed (were future):  {stats['date_fixed']:,}")
    print(f"  Fully paid off:             {stats['paid_off']:,}")
    print(f"  Partially paid:             {stats['partial']:,}")
    print(f"  No payments yet:            {stats['no_payments']:,}")

    # Show sample results
    samples = await pool.fetch("""
        SELECT pp.total_amount, pp.payment_amount, pp.payments_made,
               pp.amount_paid, pp.balance_remaining, pp.total_payments,
               pp.start_date, pp.frequency,
               a.account_reference, a.original_principal, a.total_balance
        FROM payment_plans pp
        JOIN accounts a ON a.id = pp.account_id
        WHERE pp.tenant_id = $1
        ORDER BY pp.payments_made DESC
        LIMIT 15
    """, tid)
    print(f"\nTop 15 plans by payments made:")
    print(f"  {'Ref':>10s}  {'Start':>10s}  {'Freq':>8s}  {'Orig Debt':>12s}  {'Curr Bal':>12s}  "
          f"{'Pmt Amt':>10s}  {'Made':>10s}  {'Paid':>12s}  {'Remain':>12s}")
    print("  " + "-" * 112)
    for s in samples:
        print(f"  {s['account_reference']:>10s}  "
              f"{s['start_date']}  "
              f"{s['frequency']:>8s}  "
              f"${Decimal(str(s['original_principal'])) / 100:>11,.2f}  "
              f"${Decimal(str(s['total_balance'])) / 100:>11,.2f}  "
              f"${s['payment_amount']:>9,.2f}  "
              f"{s['payments_made']:>4d}/{s['total_payments']:<4d}  "
              f"${s['amount_paid']:>11,.2f}  "
              f"${s['balance_remaining']:>11,.2f}")

    # Show a few multi-plan accounts for validation
    multi = await pool.fetch("""
        SELECT a.account_reference,
               count(*) as plan_count,
               sum(pp.payments_made) as total_made,
               sum(pp.amount_paid) as total_attributed,
               max(a.original_principal) as orig,
               max(a.total_balance) as bal
        FROM payment_plans pp
        JOIN accounts a ON a.id = pp.account_id
        WHERE pp.tenant_id = $1
        GROUP BY a.id, a.account_reference
        HAVING count(*) > 1
        ORDER BY count(*) DESC
        LIMIT 10
    """, tid)
    if multi:
        print(f"\nMulti-plan accounts (top 10):")
        print(f"  {'Ref':>10s}  {'Plans':>5s}  {'Total Made':>10s}  {'Attributed':>12s}  {'Balance Diff':>12s}")
        print("  " + "-" * 60)
        for m in multi:
            diff = (Decimal(str(m['orig'])) - Decimal(str(m['bal']))) / 100
            print(f"  {m['account_reference']:>10s}  "
                  f"{m['plan_count']:>5d}  "
                  f"{m['total_made']:>10d}  "
                  f"${float(m['total_attributed']):>11,.2f}  "
                  f"${diff:>11,.2f}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
