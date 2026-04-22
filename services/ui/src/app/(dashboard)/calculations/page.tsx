'use client';

import { useMemo, useState } from 'react';
import { Calculator, Info } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { FormField } from '@/components/shared/form-drawer';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { formatCurrency, formatDate } from '@/lib/utils';

const API = '/api/v1/calculations';

type InterestResult = {
  principal: number;
  annual_rate: string;
  interest_type: string;
  start_date: string;
  end_date: string;
  days: number;
  interest_amount: number;
  total_amount: number;
  daily_rate: string;
  formula: string;
  steps: { description?: string; formula?: string; values?: string; result?: string }[];
};

type AllocationResult = {
  payment_amount: number;
  allocations: Record<string, number>;
  remaining_balances: Record<string, number>;
  overpayment: number;
};

type PostJudgmentResult = {
  judgment_amount: number;
  judgment_date: string;
  calculation_date: string;
  days_accrued: number;
  total_interest: number;
  current_balance: number;
  rates_applied: { year?: number; rate?: number; days?: number; interest?: number }[];
  is_above_threshold: boolean;
};

type HistoryRow = {
  id: string;
  calculation_type: string;
  requested_at?: string;
  inputs?: Record<string, unknown>;
  engine_version?: string;
};

type AccountBalances = {
  id: string;
  current_principal: number;
  current_interest: number;
  current_fees: number;
};

export default function CalculationsPage() {
  const { data: history, isLoading: historyLoading } = useApiList<HistoryRow>(`${API}/history`, {
    page: 1,
    page_size: 50,
  });

  const [siPrincipal, setSiPrincipal] = useState('10000');
  const [siRate, setSiRate] = useState('5.5');
  const [siStart, setSiStart] = useState(() => new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10));
  const [siEnd, setSiEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const [siCompound, setSiCompound] = useState(false);
  const [siResult, setSiResult] = useState<InterestResult | null>(null);

  const [paPayment, setPaPayment] = useState('500');
  const [paAccountId, setPaAccountId] = useState('');
  const [paPrincipal, setPaPrincipal] = useState('500000');
  const [paInterest, setPaInterest] = useState('12000');
  const [paFees, setPaFees] = useState('3500');
  const [paResult, setPaResult] = useState<AllocationResult | null>(null);

  const { data: accountForAlloc } = useApiDetail<AccountBalances>(
    '/api/v1/accounts',
    paAccountId.trim() ? paAccountId.trim() : undefined
  );

  const [pjAmount, setPjAmount] = useState('100000');
  const [pjJudgmentDate, setPjJudgmentDate] = useState('2024-01-15');
  const [pjCalcDate, setPjCalcDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [pjJurisdiction, setPjJurisdiction] = useState('NJ');
  const [pjResult, setPjResult] = useState<PostJudgmentResult | null>(null);

  const { trigger: postSimple, isMutating: siMut } = useApiMutation<Record<string, unknown>, InterestResult>(
    'POST',
    API
  );
  const { trigger: postAlloc, isMutating: paMut } = useApiMutation<Record<string, unknown>, AllocationResult>(
    'POST',
    API
  );
  const { trigger: postPj, isMutating: pjMut } = useApiMutation<Record<string, unknown>, PostJudgmentResult>(
    'POST',
    API
  );

  const balancesFromAccount = useMemo(() => {
    if (!paAccountId.trim() || !accountForAlloc) return null;
    return {
      principal: accountForAlloc.current_principal,
      interest: accountForAlloc.current_interest,
      fees: accountForAlloc.current_fees,
    };
  }, [paAccountId, accountForAlloc]);

  async function runSimpleInterest() {
    const principalCents = Math.round(parseFloat(siPrincipal || '0') * 100);
    const body = {
      principal: principalCents,
      annual_rate: parseFloat(siRate || '0'),
      start_date: siStart,
      end_date: siEnd,
      interest_type: siCompound ? 'compound_daily' : 'simple',
      rounding_rule: 'final_step',
    };
    const res = await postSimple(body, '/simple-interest');
    setSiResult(res);
  }

  async function runPaymentAllocation() {
    const paymentCents = Math.round(parseFloat(paPayment || '0') * 100);
    const p =
      balancesFromAccount?.principal ?? Math.round(parseFloat(paPrincipal || '0'));
    const i = balancesFromAccount?.interest ?? Math.round(parseFloat(paInterest || '0'));
    const f = balancesFromAccount?.fees ?? Math.round(parseFloat(paFees || '0'));
    const body = {
      payment_amount: paymentCents,
      current_principal: p,
      current_interest: i,
      current_fees: f,
      allocation_order: ['interest', 'principal', 'fees'],
    };
    const res = await postAlloc(body, '/payment-allocation');
    setPaResult(res);
  }

  async function runPostJudgment() {
    const judgmentCents = Math.round(parseFloat(pjAmount || '0') * 100);
    const body = {
      judgment_amount: judgmentCents,
      judgment_date: pjJudgmentDate,
      calculation_date: pjCalcDate,
      jurisdiction: pjJurisdiction,
    };
    const res = await postPj(body, '/post-judgment-interest');
    setPjResult(res);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Calculations"
        subtitle="Interest, payment allocation, and post-judgment interest (live API)"
      />

      <div className="rounded-lg border border-primary-200 bg-primary-50/80 p-4 dark:border-primary-800 dark:bg-primary-950/30">
        <div className="flex gap-3">
          <Info className="h-5 w-5 shrink-0 text-primary-600 dark:text-primary-400" aria-hidden />
          <p className="text-sm text-primary-900 dark:text-primary-200">
            <strong>Non-legal guidance:</strong> Results are for operational review. Verify before use in legal
            proceedings. Simple interest requests are persisted for audit history where applicable.
          </p>
        </div>
      </div>

      {/* Section 1 */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Simple interest calculator</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          POST <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/v1/calculations/simple-interest</code>
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <FormField label="Principal (USD)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={siPrincipal}
              onChange={(e) => setSiPrincipal(e.target.value)}
            />
          </FormField>
          <FormField label="Annual rate (%)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={siRate}
              onChange={(e) => setSiRate(e.target.value)}
            />
          </FormField>
          <FormField label="Start date" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={siStart}
              onChange={(e) => setSiStart(e.target.value)}
            />
          </FormField>
          <FormField label="End date" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={siEnd}
              onChange={(e) => setSiEnd(e.target.value)}
            />
          </FormField>
          <div className="flex items-end pb-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={siCompound}
                onChange={(e) => setSiCompound(e.target.checked)}
              />
              Compound (daily)
            </label>
          </div>
        </div>
        <button
          type="button"
          disabled={siMut}
          onClick={runSimpleInterest}
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          <Calculator className="h-4 w-4" aria-hidden />
          {siMut ? 'Calculating…' : 'Calculate'}
        </button>
        {siResult ? (
          <div className="mt-6 space-y-4 rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs uppercase text-neutral-500">Days</p>
                <p className="font-semibold">{siResult.days}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Interest</p>
                <p className="font-semibold">{formatCurrency(siResult.interest_amount)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Total</p>
                <p className="font-semibold text-primary-700 dark:text-primary-300">
                  {formatCurrency(siResult.total_amount)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Daily rate</p>
                <p className="font-mono text-xs">{String(siResult.daily_rate)}</p>
              </div>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400">{siResult.formula}</p>
            <ul className="space-y-2">
              {(siResult.steps ?? []).map((s, i) => (
                <li key={i} className="rounded-md bg-background p-2 font-mono text-xs">
                  {s.description && <span className="text-neutral-500">{s.description}: </span>}
                  {s.result ?? s.values}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      {/* Section 2 */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Payment allocation</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          POST{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/v1/calculations/payment-allocation</code>
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <FormField label="Payment amount (USD)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={paPayment}
              onChange={(e) => setPaPayment(e.target.value)}
            />
          </FormField>
          <FormField label="Account ID (loads balances)">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
              placeholder="Optional UUID"
              value={paAccountId}
              onChange={(e) => setPaAccountId(e.target.value)}
            />
          </FormField>
        </div>
        {balancesFromAccount ? (
          <p className="mt-2 text-xs text-neutral-500">
            Using live balances from account: principal {formatCurrency(balancesFromAccount.principal)}, interest{' '}
            {formatCurrency(balancesFromAccount.interest)}, fees {formatCurrency(balancesFromAccount.fees)}.
          </p>
        ) : (
          <p className="mt-4 text-sm font-medium text-foreground">Manual balances (cents)</p>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <FormField label="Principal (cents)">
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={!!balancesFromAccount}
              value={paPrincipal}
              onChange={(e) => setPaPrincipal(e.target.value)}
            />
          </FormField>
          <FormField label="Interest (cents)">
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={!!balancesFromAccount}
              value={paInterest}
              onChange={(e) => setPaInterest(e.target.value)}
            />
          </FormField>
          <FormField label="Fees (cents)">
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={!!balancesFromAccount}
              value={paFees}
              onChange={(e) => setPaFees(e.target.value)}
            />
          </FormField>
        </div>
        <button
          type="button"
          disabled={paMut}
          onClick={runPaymentAllocation}
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          <Calculator className="h-4 w-4" aria-hidden />
          {paMut ? 'Allocating…' : 'Allocate payment'}
        </button>
        {paResult ? (
          <div className="mt-6 space-y-3 rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <p>
              <span className="text-neutral-500">Overpayment:</span>{' '}
              {formatCurrency(paResult.overpayment)}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(paResult.allocations).map(([k, v]) => (
                <div key={k} className="flex justify-between rounded-md bg-background px-3 py-2 font-mono text-xs">
                  <span>{k}</span>
                  <span>{formatCurrency(v)}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-neutral-500">Remaining balances (after allocation)</p>
            <div className="grid gap-2 font-mono text-xs">
              {Object.entries(paResult.remaining_balances).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span>{k}</span>
                  <span>{formatCurrency(v)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {/* Section 3 */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Post-judgment interest</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          POST{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/v1/calculations/post-judgment-interest</code>
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <FormField label="Judgment amount (USD)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={pjAmount}
              onChange={(e) => setPjAmount(e.target.value)}
            />
          </FormField>
          <FormField label="Judgment date" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={pjJudgmentDate}
              onChange={(e) => setPjJudgmentDate(e.target.value)}
            />
          </FormField>
          <FormField label="Calculation date" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={pjCalcDate}
              onChange={(e) => setPjCalcDate(e.target.value)}
            />
          </FormField>
          <FormField label="Jurisdiction">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={pjJurisdiction}
              onChange={(e) => setPjJurisdiction(e.target.value)}
              maxLength={2}
            />
          </FormField>
        </div>
        <button
          type="button"
          disabled={pjMut}
          onClick={runPostJudgment}
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          <Calculator className="h-4 w-4" aria-hidden />
          {pjMut ? 'Calculating…' : 'Calculate'}
        </button>
        {pjResult ? (
          <div className="mt-6 space-y-4 rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs uppercase text-neutral-500">Days accrued</p>
                <p className="font-semibold">{pjResult.days_accrued}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Total interest</p>
                <p className="font-semibold">{formatCurrency(pjResult.total_interest)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Current balance</p>
                <p className="font-semibold text-primary-700 dark:text-primary-300">
                  {formatCurrency(pjResult.current_balance)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase text-neutral-500">Above threshold</p>
                <p className="font-semibold">{pjResult.is_above_threshold ? 'Yes' : 'No'}</p>
              </div>
            </div>
            <p className="text-xs text-neutral-600">
              Rate schedule (jurisdiction-specific breakdown). Effective annual rates vary by year; see{' '}
              <code className="rounded bg-muted px-1">rates_applied</code> from the API.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-xs">
                <thead>
                  <tr className="border-b border-border text-left text-neutral-500">
                    <th className="py-2 pr-2">Year</th>
                    <th className="py-2 pr-2">Rate %</th>
                    <th className="py-2 pr-2">Days</th>
                    <th className="py-2">Interest</th>
                  </tr>
                </thead>
                <tbody>
                  {(pjResult.rates_applied ?? []).map((r, i) => (
                    <tr key={i} className="border-b border-border/60">
                      <td className="py-2 font-mono">{r.year ?? '—'}</td>
                      <td className="py-2 font-mono">{r.rate ?? '—'}</td>
                      <td className="py-2 font-mono">{r.days ?? '—'}</td>
                      <td className="py-2 font-mono">
                        {r.interest != null ? formatCurrency(r.interest) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>

      {/* History */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Calculation history</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">GET /api/v1/calculations/history</p>
        {historyLoading ? (
          <p className="mt-4 text-sm text-neutral-500">Loading…</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-semibold uppercase text-neutral-500">
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Requested</th>
                  <th className="py-2">Engine</th>
                </tr>
              </thead>
              <tbody>
                {(history ?? []).map((h) => (
                  <tr key={h.id} className="border-b border-border/70">
                    <td className="py-2 pr-3">
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-mono">
                        {h.calculation_type}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-neutral-600 dark:text-neutral-400">
                      {h.requested_at ? formatDate(h.requested_at) : '—'}
                    </td>
                    <td className="py-2 font-mono text-xs text-neutral-500">{h.engine_version ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!history?.length ? (
              <p className="mt-4 text-sm text-neutral-500">No history entries yet.</p>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
