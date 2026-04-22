'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight, Download, ArrowLeft } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

const fmtMoney = (v: number | string | null | undefined) =>
  v != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(v))
    : '—';

const fmtMoneyCents = (v: number | null | undefined) =>
  v != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v / 100)
    : '—';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

type ScheduledPayment = {
  payment_number: number;
  due_date: string | null;
  amount_due: number;
  amount_paid: number;
  is_paid: boolean;
  is_late: boolean;
  paid_date: string | null;
};

type ActualPayment = {
  id: string;
  amount_cents: number;
  method: string | null;
  status: string | null;
  received_at: string | null;
  processed_at: string | null;
};

type PlanRow = {
  plan_id: string;
  plan_type: string;
  plan_status: string;
  frequency: string;
  start_date: string;
  next_payment_date: string | null;
  total_amount: number;
  payment_amount: number;
  total_payments: number;
  payments_made: number;
  payments_remaining: number;
  amount_paid: number;
  balance_remaining: number;
  is_settlement: boolean;
  account: {
    id: string;
    account_reference: string;
    original_creditor: string;
    total_balance_cents: number;
    status: string;
  };
  scheduled_payments: ScheduledPayment[];
  actual_payments: ActualPayment[];
  account_history: {
    id: string;
    type: string;
    date: string | null;
    notes: string | null;
    tag: string;
    hist_type: string;
    status: string | null;
  }[];
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  defaulted: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  draft: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400',
  cancelled: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400',
  suspended: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
};

function HistoryRow({ h }: { h: PlanRow['account_history'][number] }) {
  const [open, setOpen] = useState(false);
  const lines = (h.notes || '').split('\n');
  const desc = lines.find((l) => l.startsWith('DESCRIPT='))?.replace('DESCRIPT=', '') || lines[0] || '';
  const noteLines = lines.filter((l) => l.startsWith('NOTES='));
  const noteText = noteLines.map((l) => l.replace('NOTES=', '').replace(/^"|"$/g, '')).join(' ').trim();
  const fullText = lines
    .filter((l) => !l.startsWith('OP=') && !l.startsWith('CODE=') && !l.startsWith('ASSOC=') && !l.startsWith('ACTTIME=') && !l.startsWith('ACTALARM='))
    .map((l) => {
      if (l.startsWith('DESCRIPT=')) return l.replace('DESCRIPT=', '');
      if (l.startsWith('NOTES=')) return l.replace('NOTES=', '').replace(/^"|"$/g, '');
      if (l.startsWith('ACTDATE=')) return 'Date: ' + l.replace('ACTDATE=', '');
      return l;
    })
    .filter(Boolean)
    .join('\n');

  return (
    <>
      <tr
        className="hover:bg-neutral-50 dark:hover:bg-neutral-700/50 cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <td className="px-3 py-1.5 tabular-nums whitespace-nowrap">{fmtDate(h.date)}</td>
        <td className="px-3 py-1.5">
          <span className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium',
            h.hist_type === 'N' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
            h.hist_type === 'S' ? 'bg-neutral-100 text-neutral-600' :
            'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
          )}>
            {h.hist_type === 'N' ? 'Note' : h.hist_type === 'A' ? 'Activity' : h.hist_type === 'S' ? 'System' : h.hist_type || 'Entry'}
          </span>
        </td>
        <td className="px-3 py-1.5 max-w-xs">
          <p className={cn(
            'text-neutral-800 dark:text-neutral-200 font-medium',
            !open && 'truncate'
          )}>{desc}</p>
          {!open && noteText && <p className="text-neutral-500 truncate mt-0.5">{noteText}</p>}
        </td>
      </tr>
      {open && (
        <tr className="bg-neutral-50/80 dark:bg-neutral-700/30">
          <td colSpan={3} className="px-4 py-3">
            <pre className="text-xs text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap font-sans leading-relaxed">
              {fullText}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

export default function PaymentAgreementReport() {
  const [data, setData] = useState<PlanRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const pageSize = 50;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(pageSize),
        });
        if (statusFilter) params.set('plan_status', statusFilter);
        const res = await apiClient.get<any>(
          `/api/v1/payment-plans/report/agreements-with-payments?${params}`
        );
        if (!cancelled) {
          const d = res.data as any;
          setData(d.items ?? []);
          setTotal(d.total ?? 0);
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Failed to load report');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [page, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function toggleExpand(planId: string) {
    setExpandedId((prev) => (prev === planId ? null : planId));
  }

  async function exportCsv() {
    const rows: string[] = [];
    rows.push([
      'Account Ref', 'Creditor', 'Account Balance', 'Plan Type', 'Plan Status',
      'Frequency', 'Start Date', 'Next Payment', 'Total Amount', 'Payment Amount',
      'Total Payments', 'Payments Made', 'Remaining Pmts', 'Amount Paid', 'Balance Remaining',
    ].join(','));
    for (const r of data) {
      rows.push([
        `"${r.account.account_reference}"`,
        `"${r.account.original_creditor}"`,
        (r.account.total_balance_cents / 100).toFixed(2),
        r.plan_type, r.plan_status, r.frequency,
        r.start_date || '', r.next_payment_date || '',
        r.total_amount.toFixed(2), r.payment_amount.toFixed(2),
        r.total_payments, r.payments_made, r.payments_remaining,
        r.amount_paid.toFixed(2), r.balance_remaining.toFixed(2),
      ].join(','));
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payment-agreement-report-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payment Agreement Report"
        subtitle={`Accounts with payment plans and their payment history · ${total.toLocaleString()} plans`}
        actions={
          <div className="flex items-center gap-3">
            <Link
              href="/payment-plans"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-medium hover:bg-muted"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
            <button
              type="button"
              onClick={exportCsv}
              disabled={data.length === 0}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </button>
          </div>
        }
      />

      {/* Filter bar */}
      <div className="flex items-center gap-4">
        <label className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Plan Status:
        </label>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="defaulted">Defaulted</option>
          <option value="draft">Draft</option>
          <option value="suspended">Suspended</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {error && (
        <div className="rounded-lg border border-error-200 bg-error-50 dark:bg-error-900/20 p-4 text-sm text-error-700 dark:text-error-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : data.length === 0 ? (
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-12 text-center text-neutral-500">
          No payment agreements found.
        </div>
      ) : (
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
                <th className="w-8 px-3 py-3" />
                <th className="px-3 py-3 text-left font-medium text-neutral-500">Account</th>
                <th className="px-3 py-3 text-left font-medium text-neutral-500">Creditor</th>
                <th className="px-3 py-3 text-right font-medium text-neutral-500">Acct Balance</th>
                <th className="px-3 py-3 text-left font-medium text-neutral-500">Status</th>
                <th className="px-3 py-3 text-left font-medium text-neutral-500">Freq</th>
                <th className="px-3 py-3 text-left font-medium text-neutral-500">Start Date</th>
                <th className="px-3 py-3 text-right font-medium text-neutral-500">Plan Total</th>
                <th className="px-3 py-3 text-right font-medium text-neutral-500">Pmt Amt</th>
                <th className="px-3 py-3 text-center font-medium text-neutral-500">Made/Total</th>
                <th className="px-3 py-3 text-right font-medium text-neutral-500">Paid</th>
                <th className="px-3 py-3 text-right font-medium text-neutral-500">Remaining</th>
                <th className="px-3 py-3 text-center font-medium text-neutral-500">Progress</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
              {data.map((row) => {
                const isOpen = expandedId === row.plan_id;
                return (
                  <PlanRowBlock key={row.plan_id} row={row} isOpen={isOpen} onToggle={() => toggleExpand(row.plan_id)} />
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-neutral-500">
            Page {page} of {totalPages} · {total.toLocaleString()} total
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="h-9 rounded-md border border-border px-3 text-sm disabled:opacity-40 hover:bg-muted"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="h-9 rounded-md border border-border px-3 text-sm disabled:opacity-40 hover:bg-muted"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanRowBlock({ row, isOpen, onToggle }: { row: PlanRow; isOpen: boolean; onToggle: () => void }) {
  const pctPaid = row.total_amount > 0
    ? Math.min(100, Math.round((row.amount_paid / row.total_amount) * 100))
    : 0;

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors"
        onClick={onToggle}
      >
        <td className="px-3 py-3 text-neutral-400">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </td>
        <td className="px-3 py-3 font-medium text-neutral-900 dark:text-white">
          <Link href={`/accounts/${row.account.id}`} className="hover:text-primary-600 hover:underline" onClick={(e) => e.stopPropagation()}>
            {row.account.account_reference}
          </Link>
        </td>
        <td className="px-3 py-3 text-neutral-600 dark:text-neutral-400 truncate max-w-[180px]">
          {row.account.original_creditor}
        </td>
        <td className="px-3 py-3 text-right tabular-nums font-medium">
          {fmtMoneyCents(row.account.total_balance_cents)}
        </td>
        <td className="px-3 py-3">
          <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_COLORS[row.plan_status] ?? STATUS_COLORS.draft)}>
            {row.plan_status}
          </span>
        </td>
        <td className="px-3 py-3 capitalize text-neutral-600 dark:text-neutral-400">{row.frequency?.replace(/_/g, ' ')}</td>
        <td className="px-3 py-3 tabular-nums text-neutral-600 dark:text-neutral-400">{fmtDate(row.start_date)}</td>
        <td className="px-3 py-3 text-right tabular-nums">{fmtMoney(row.total_amount)}</td>
        <td className="px-3 py-3 text-right tabular-nums">{fmtMoney(row.payment_amount)}</td>
        <td className="px-3 py-3 text-center tabular-nums">
          {row.payments_made}/{row.total_payments}
        </td>
        <td className="px-3 py-3 text-right tabular-nums text-green-700 dark:text-green-400 font-medium">{fmtMoney(row.amount_paid)}</td>
        <td className="px-3 py-3 text-right tabular-nums">{fmtMoney(row.balance_remaining)}</td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 min-w-[60px]">
              <div
                className={cn(
                  'h-2 rounded-full transition-all',
                  pctPaid >= 100 ? 'bg-green-500' : pctPaid >= 50 ? 'bg-blue-500' : 'bg-amber-500'
                )}
                style={{ width: `${pctPaid}%` }}
              />
            </div>
            <span className="text-xs tabular-nums text-neutral-500 w-8 text-right">{pctPaid}%</span>
          </div>
        </td>
      </tr>

      {isOpen && (
        <tr>
          <td colSpan={13} className="bg-neutral-50 dark:bg-neutral-850 px-6 py-4">
            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-3">
                <p className="text-xs text-neutral-500 uppercase font-medium">Start Date</p>
                <p className="mt-1 text-sm font-semibold">{fmtDate(row.start_date)}</p>
              </div>
              <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-3">
                <p className="text-xs text-neutral-500 uppercase font-medium">Next Payment</p>
                <p className="mt-1 text-sm font-semibold">{fmtDate(row.next_payment_date)}</p>
              </div>
              <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-3">
                <p className="text-xs text-neutral-500 uppercase font-medium">Total Paid</p>
                <p className="mt-1 text-sm font-semibold text-green-700 dark:text-green-400">{fmtMoney(row.amount_paid)}</p>
              </div>
              <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-3">
                <p className="text-xs text-neutral-500 uppercase font-medium">Balance Remaining</p>
                <p className="mt-1 text-sm font-semibold">{fmtMoney(row.balance_remaining)}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Scheduled payments */}
              <div>
                <h4 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
                  Scheduled Payments ({row.scheduled_payments.length})
                </h4>
                {row.scheduled_payments.length > 0 ? (
                  <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 overflow-hidden max-h-[300px] overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0">
                        <tr className="bg-neutral-100 dark:bg-neutral-700">
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">#</th>
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">Due Date</th>
                          <th className="px-3 py-2 text-right font-medium text-neutral-500">Due</th>
                          <th className="px-3 py-2 text-right font-medium text-neutral-500">Paid</th>
                          <th className="px-3 py-2 text-center font-medium text-neutral-500">Status</th>
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">Paid Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                        {row.scheduled_payments.map((sp) => (
                          <tr key={sp.payment_number} className={cn(sp.is_late && !sp.is_paid && 'bg-red-50 dark:bg-red-900/10')}>
                            <td className="px-3 py-1.5 tabular-nums">{sp.payment_number}</td>
                            <td className="px-3 py-1.5 tabular-nums">{fmtDate(sp.due_date)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtMoney(sp.amount_due)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtMoney(sp.amount_paid)}</td>
                            <td className="px-3 py-1.5 text-center">
                              {sp.is_paid ? (
                                <span className="text-green-600 font-medium">Paid</span>
                              ) : sp.is_late ? (
                                <span className="text-red-600 font-medium">Late</span>
                              ) : (
                                <span className="text-neutral-400">Pending</span>
                              )}
                            </td>
                            <td className="px-3 py-1.5 tabular-nums">{sp.is_paid ? fmtDate(sp.paid_date) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-neutral-400 italic">No scheduled payments generated yet.</p>
                )}
              </div>

              {/* Account History */}
              <div>
                <h4 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
                  Account History ({(row.account_history || []).length + row.actual_payments.length})
                </h4>
                {(row.actual_payments.length > 0 || (row.account_history || []).length > 0) ? (
                  <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 overflow-hidden max-h-[400px] overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0">
                        <tr className="bg-neutral-100 dark:bg-neutral-700">
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">Date</th>
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">Type</th>
                          <th className="px-3 py-2 text-left font-medium text-neutral-500">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700">
                        {row.actual_payments.map((p) => (
                          <tr key={p.id}>
                            <td className="px-3 py-1.5 tabular-nums whitespace-nowrap">{fmtDate(p.received_at)}</td>
                            <td className="px-3 py-1.5">
                              <span className="rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-2 py-0.5 text-xs font-medium">Payment</span>
                            </td>
                            <td className="px-3 py-1.5">
                              {fmtMoneyCents(p.amount_cents)} via {p.method?.replace(/_/g, ' ') ?? 'unknown'}
                            </td>
                          </tr>
                        ))}
                        {(row.account_history || []).map((h: any) => (
                          <HistoryRow key={h.id} h={h} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-neutral-400 italic">
                    No history found for this account.
                  </p>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
