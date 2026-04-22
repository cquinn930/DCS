'use client';

import { useEffect, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import {
  DetailPanel,
  FieldGrid,
  FieldGroup,
} from '@/components/shared/detail-panel';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/judgments';

const fmtMoney = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

type JudgmentRow = {
  id: string;
  litigation_case_id: string;
  judgment_amount: number;
  post_judgment_rate: number | string;
  judgment_date: string;
  rate_source?: string;
};

type AccrualRow = {
  accrual_date?: string;
  accrued_amount?: number;
  cumulative_amount?: number;
  annual_rate?: number | string;
};

export default function JudgmentsPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [accruals, setAccruals] = useState<AccrualRow[]>([]);
  const [accrualsLoading, setAccrualsLoading] = useState(false);
  const [calcDate, setCalcDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [calcResult, setCalcResult] = useState<Record<
    string,
    unknown
  > | null>(null);

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
  };

  const { data, total, isLoading, mutate } = useApiList<JudgmentRow>(
    API,
    listParams
  );
  const { data: detail, isLoading: detailLoading } = useApiDetail<
    JudgmentRow & {
      calculated_interest?: number;
      current_balance?: number;
    }
  >(API, selectedId ?? undefined);

  const { trigger: calcInterest, isMutating: calcMutating } = useApiMutation(
    'POST',
    API
  );

  useEffect(() => {
    if (!selectedId) {
      setAccruals([]);
      setCalcResult(null);
      return;
    }
    let cancelled = false;
    setAccrualsLoading(true);
    apiClient
      .get<AccrualRow[]>(`${API}/${selectedId}/accruals`)
      .then((res) => {
        if (!cancelled) setAccruals(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        if (!cancelled) setAccruals([]);
      })
      .finally(() => {
        if (!cancelled) setAccrualsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.id.toLowerCase().includes(q) ||
      row.litigation_case_id.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<JudgmentRow>[] = [
    {
      accessorKey: 'id',
      header: 'Judgment #',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    {
      accessorKey: 'litigation_case_id',
      header: 'Account',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    {
      accessorKey: 'judgment_amount',
      header: 'Amount',
      cell: ({ getValue }) => fmtMoney(Number(getValue())),
    },
    {
      accessorKey: 'post_judgment_rate',
      header: 'Interest Rate',
      cell: ({ getValue }) => {
        const v = getValue();
        return typeof v === 'number' ? `${v}%` : String(v);
      },
    },
    {
      accessorKey: 'rate_source',
      header: 'Court',
      cell: ({ row }) => row.original.rate_source ?? '—',
    },
    {
      accessorKey: 'judgment_date',
      header: 'Entry Date',
      cell: ({ getValue }) => fmtDate(String(getValue())),
    },
  ];

  async function runCalculateInterest() {
    if (!selectedId || !calcDate) return;
    const res = await calcInterest(
      undefined,
      `/${selectedId}/calculate-interest?calculation_date=${encodeURIComponent(calcDate)}`
    );
    setCalcResult(res as Record<string, unknown>);
    await mutate();
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Judgments"
        subtitle={
          user
            ? `Post-judgment balances · ${user.email}`
            : 'Judgments and post-judgment interest'
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search judgments…"
      />

      <DataTable<JudgmentRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No judgments found"
        onRowClick={(row) => setSelectedId(row.id)}
        pageCount={pageCount}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPageChange={setPageIndex}
        onPageSizeChange={(s) => {
          setPageSize(s);
          setPageIndex(0);
        }}
      />

      {selectedId && (
        <DetailPanel
          title={`Judgment ${d?.id?.slice(0, 8) ?? ''}…`}
          subtitle={
            d?.current_balance != null
              ? `Current balance ${fmtMoney(d.current_balance)}`
              : undefined
          }
          onClose={() => setSelectedId(null)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Litigation case ID">
                  {d.litigation_case_id}
                </FieldGroup>
                <FieldGroup label="Judgment amount">
                  {fmtMoney(d.judgment_amount)}
                </FieldGroup>
                <FieldGroup label="Interest rate">
                  {typeof d.post_judgment_rate === 'number'
                    ? `${d.post_judgment_rate}%`
                    : String(d.post_judgment_rate)}
                </FieldGroup>
                <FieldGroup label="Entry date">
                  {fmtDate(d.judgment_date)}
                </FieldGroup>
                {'calculated_interest' in d && d.calculated_interest != null ? (
                  <FieldGroup label="Calculated interest (snapshot)">
                    {fmtMoney(Number(d.calculated_interest))}
                  </FieldGroup>
                ) : null}
              </FieldGrid>

              <div className="mt-6 border-t border-border pt-4">
                <h3 className="text-sm font-semibold">Accruals</h3>
                {accrualsLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading accruals…</p>
                ) : accruals.length === 0 ? (
                  <p className="mt-2 text-sm text-neutral-500">
                    No accrual rows returned.
                  </p>
                ) : (
                  <div className="mt-2 max-h-56 overflow-auto rounded-md border border-border">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-border bg-neutral-50 dark:bg-neutral-900/50">
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Accrued</th>
                          <th className="px-3 py-2">Cumulative</th>
                        </tr>
                      </thead>
                      <tbody>
                        {accruals.map((a, i) => (
                          <tr key={i} className="border-b border-border last:border-0">
                            <td className="px-3 py-2">
                              {fmtDate(a.accrual_date as string | undefined)}
                            </td>
                            <td className="px-3 py-2">
                              {fmtMoney(Number(a.accrued_amount ?? 0))}
                            </td>
                            <td className="px-3 py-2">
                              {fmtMoney(Number(a.cumulative_amount ?? 0))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="mt-6 flex flex-wrap items-end gap-3 border-t border-border pt-4">
                <div>
                  <label className="text-xs font-medium uppercase text-neutral-500">
                    Calculation date
                  </label>
                  <input
                    type="date"
                    className="mt-1 block rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={calcDate}
                    onChange={(e) => setCalcDate(e.target.value)}
                  />
                </div>
                <button
                  type="button"
                  onClick={runCalculateInterest}
                  disabled={calcMutating}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {calcMutating ? 'Calculating…' : 'Calculate interest'}
                </button>
              </div>

              {calcResult ? (
                <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-neutral-50 p-3 text-xs dark:bg-neutral-900/50">
                  {JSON.stringify(calcResult, null, 2)}
                </pre>
              ) : null}
            </>
          )}
        </DetailPanel>
      )}
    </div>
  );
}
