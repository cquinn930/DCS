'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { ColumnDef } from '@tanstack/react-table';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { useApiList, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { StatusBadge } from '@/components/shared/status-badge';
import { cn } from '@/lib/utils';

const PERF = '/api/v1/performance';

type GoalGroupRow = {
  id: string;
  name: string;
  description: string | null;
  filter_criteria: Record<string, unknown>;
  is_active: boolean;
};

type CollectorGoalRow = {
  id: string;
  collector_id: string;
  goal_group_id: string | null;
  goal_type: string;
  period: string;
  target_amount: number;
  actual_amount: number;
  period_start: string;
  period_end: string;
};

type SnapshotRow = {
  id: string;
  collector_id: string;
  snapshot_date: string;
  calls_made: number;
  total_collected: number;
  accounts_worked: number;
  calls_connected: number;
};

type PerformanceSummary = {
  tenant_id: string;
  generated_at: string;
  distinct_collectors: number;
  snapshot_rows: number;
  total_collected_cents: number;
  total_calls_made: number;
  total_accounts_worked: number;
  goal_rows: number;
  goals_met_or_exceeded: number;
};

const GOAL_TYPES = [
  'collections',
  'contacts',
  'accounts_worked',
  'promises',
  'settlements',
  'payments_secured',
  'custom',
] as const;

const GOAL_PERIODS = [
  'daily',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
] as const;

const TABS = [
  { id: 'groups', label: 'Goal Groups' },
  { id: 'goals', label: 'Collector Goals' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'summary', label: 'Summary' },
] as const;

function fmtMoneyCents(cents: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);
}

function shortId(id: string) {
  return `${id.slice(0, 8)}…`;
}

export default function PerformancePage() {
  const { user } = useAuthStore();
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('groups');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [ggDrawer, setGgDrawer] = useState(false);
  const [cgDrawer, setCgDrawer] = useState(false);

  const [ggForm, setGgForm] = useState({
    name: '',
    description: '',
    period_type: 'monthly',
    is_active: true,
  });

  const [cgForm, setCgForm] = useState({
    collector_id: '',
    goal_group_id: '',
    goal_type: 'collections' as (typeof GOAL_TYPES)[number],
    period: 'monthly' as (typeof GOAL_PERIODS)[number],
    target_dollars: '',
    actual_dollars: '0',
    period_start: '',
    period_end: '',
    notes: '',
  });

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: groups, total: gTotal, isLoading: gLoading, mutate: mutG } =
    useApiList<GoalGroupRow>(`${PERF}/goal-groups`, listParams);
  const { data: goals, total: cgTotal, isLoading: cgLoading, mutate: mutCg } =
    useApiList<CollectorGoalRow>(`${PERF}/collector-goals`, listParams);
  const { data: snaps, total: sTotal, isLoading: sLoading } = useApiList<
    SnapshotRow
  >(`${PERF}/snapshots`, listParams);

  const token = useAuthStore((s) => s.accessToken);
  const { data: summary, isLoading: sumLoading } = useSWR(
    tab === 'summary' && token
      ? ([PERF + '/summary', token] as const)
      : null,
    async () => {
      const { data } = await apiClient.get<PerformanceSummary>(
        `${PERF}/summary`
      );
      return data;
    }
  );

  const { data: topGoals } = useApiList<CollectorGoalRow>(
    tab === 'summary' ? `${PERF}/collector-goals` : null,
    { page: 1, page_size: 10 }
  );

  const { trigger: createGg, isMutating: creatingGg } = useApiMutation<
    Record<string, unknown>,
    GoalGroupRow
  >('POST', `${PERF}/goal-groups`);
  const { trigger: createCg, isMutating: creatingCg } = useApiMutation<
    Record<string, unknown>,
    CollectorGoalRow
  >('POST', `${PERF}/collector-goals`);

  const filteredGroups = useMemo(() => {
    const rows = groups ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.description ?? '').toLowerCase().includes(q)
    );
  }, [groups, search]);

  const filteredGoals = useMemo(() => {
    const rows = goals ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.goal_type.toLowerCase().includes(q) ||
        r.collector_id.toLowerCase().includes(q)
    );
  }, [goals, search]);

  const filteredSnaps = useMemo(() => {
    const rows = snaps ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((r) => r.collector_id.toLowerCase().includes(q));
  }, [snaps, search]);

  const gPageCount = Math.max(1, Math.ceil((gTotal ?? 0) / pageSize));
  const cgPageCount = Math.max(1, Math.ceil((cgTotal ?? 0) / pageSize));
  const sPageCount = Math.max(1, Math.ceil((sTotal ?? 0) / pageSize));

  const groupColumns: ColumnDef<GoalGroupRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
    {
      id: 'period',
      header: 'Period type',
      cell: ({ row }) => {
        const fc = row.original.filter_criteria ?? {};
        const pt =
          typeof fc.period_type === 'string'
            ? fc.period_type
            : (fc as { period?: string }).period;
        return pt ?? '—';
      },
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() ? 'active' : 'inactive'} />
      ),
    },
  ];

  const goalColumns: ColumnDef<CollectorGoalRow>[] = [
    {
      accessorKey: 'collector_id',
      header: 'Collector',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{shortId(String(getValue()))}</span>
      ),
    },
    {
      accessorKey: 'goal_group_id',
      header: 'Goal group',
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return v ? (
          <span className="font-mono text-xs">{shortId(v)}</span>
        ) : (
          '—'
        );
      },
    },
    { accessorKey: 'goal_type', header: 'Metric' },
    {
      accessorKey: 'target_amount',
      header: 'Target',
      cell: ({ getValue }) => fmtMoneyCents(Number(getValue())),
    },
    {
      accessorKey: 'actual_amount',
      header: 'Actual',
      cell: ({ getValue }) => fmtMoneyCents(Number(getValue())),
    },
    {
      id: 'pct',
      header: '% Achievement',
      cell: ({ row }) => {
        const t = row.original.target_amount || 1;
        const a = row.original.actual_amount;
        const pct = Math.round((a / t) * 1000) / 10;
        return `${pct}%`;
      },
    },
    {
      id: 'period',
      header: 'Period',
      cell: ({ row }) =>
        `${row.original.period_start?.slice(0, 10)} → ${row.original.period_end?.slice(0, 10)}`,
    },
  ];

  const snapColumns: ColumnDef<SnapshotRow>[] = [
    {
      accessorKey: 'collector_id',
      header: 'Collector',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{shortId(String(getValue()))}</span>
      ),
    },
    {
      accessorKey: 'snapshot_date',
      header: 'Date',
      cell: ({ getValue }) => String(getValue()).slice(0, 10),
    },
    { accessorKey: 'calls_made', header: 'Calls' },
    {
      accessorKey: 'total_collected',
      header: 'Payments collected',
      cell: ({ getValue }) => fmtMoneyCents(Number(getValue())),
    },
    { accessorKey: 'accounts_worked', header: 'Accounts worked' },
    {
      accessorKey: 'calls_connected',
      header: 'Right party contacts',
      cell: ({ getValue }) => Number(getValue()).toLocaleString(),
    },
  ];

  async function submitGoalGroup() {
    await createGg({
      name: ggForm.name,
      description: ggForm.description || null,
      filter_criteria: { period_type: ggForm.period_type },
      is_active: ggForm.is_active,
    });
    setGgDrawer(false);
    setGgForm({
      name: '',
      description: '',
      period_type: 'monthly',
      is_active: true,
    });
    await mutG();
  }

  async function submitCollectorGoal() {
    const target_cents = Math.round(
      parseFloat(cgForm.target_dollars || '0') * 100
    );
    const actual_cents = Math.round(
      parseFloat(cgForm.actual_dollars || '0') * 100
    );
    await createCg({
      collector_id: cgForm.collector_id,
      goal_group_id: cgForm.goal_group_id.trim() || null,
      goal_type: cgForm.goal_type,
      period: cgForm.period,
      target_amount: target_cents,
      actual_amount: actual_cents,
      period_start: cgForm.period_start,
      period_end: cgForm.period_end,
      notes: cgForm.notes || null,
    });
    setCgDrawer(false);
    await mutCg();
  }

  const rankedGoals = useMemo(() => {
    const rows = [...(topGoals ?? [])];
    rows.sort((a, b) => {
      const ra = a.target_amount ? a.actual_amount / a.target_amount : 0;
      const rb = b.target_amount ? b.actual_amount / b.target_amount : 0;
      return rb - ra;
    });
    return rows.slice(0, 5);
  }, [topGoals]);

  const conversionPct =
    summary && summary.goal_rows > 0
      ? Math.round(
          (summary.goals_met_or_exceeded / summary.goal_rows) * 1000
        ) / 10
      : null;

  const avgCallsPerDay =
    summary && summary.snapshot_rows > 0
      ? summary.total_calls_made / summary.snapshot_rows
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Performance"
        subtitle={
          user
            ? `Goals, snapshots, and rollups · ${user.email}`
            : 'Collector performance and goals'
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id);
              setPageIndex(0);
            }}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              tab === t.id
                ? 'bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-300'
                : 'text-neutral-600 hover:bg-muted dark:text-neutral-400'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== 'summary' ? (
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Filter current tab…"
        />
      ) : null}

      {tab === 'groups' && (
        <>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setGgDrawer(true)}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New goal group
            </button>
          </div>
          <DataTable<GoalGroupRow>
            columns={groupColumns}
            data={filteredGroups}
            isLoading={gLoading}
            emptyMessage="No goal groups"
            pageCount={gPageCount}
            pageIndex={pageIndex}
            pageSize={pageSize}
            onPageChange={setPageIndex}
            onPageSizeChange={(s) => {
              setPageSize(s);
              setPageIndex(0);
            }}
          />
        </>
      )}

      {tab === 'goals' && (
        <>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setCgDrawer(true)}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New collector goal
            </button>
          </div>
          <DataTable<CollectorGoalRow>
            columns={goalColumns}
            data={filteredGoals}
            isLoading={cgLoading}
            emptyMessage="No collector goals"
            pageCount={cgPageCount}
            pageIndex={pageIndex}
            pageSize={pageSize}
            onPageChange={setPageIndex}
            onPageSizeChange={(s) => {
              setPageSize(s);
              setPageIndex(0);
            }}
          />
        </>
      )}

      {tab === 'snapshots' && (
        <DataTable<SnapshotRow>
          columns={snapColumns}
          data={filteredSnaps}
          isLoading={sLoading}
          emptyMessage="No snapshots"
          pageCount={sPageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      )}

      {tab === 'summary' && (
        <div className="space-y-6">
          {sumLoading || !summary ? (
            <p className="text-sm text-neutral-500">Loading summary…</p>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
                  <p className="text-xs font-medium uppercase text-neutral-500">
                    Total collected
                  </p>
                  <p className="mt-1 text-2xl font-semibold">
                    {fmtMoneyCents(summary.total_collected_cents)}
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
                  <p className="text-xs font-medium uppercase text-neutral-500">
                    Avg calls / snapshot row
                  </p>
                  <p className="mt-1 text-2xl font-semibold">
                    {avgCallsPerDay != null
                      ? avgCallsPerDay.toFixed(1)
                      : '—'}
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
                  <p className="text-xs font-medium uppercase text-neutral-500">
                    Goal conversion
                  </p>
                  <p className="mt-1 text-2xl font-semibold">
                    {conversionPct != null ? `${conversionPct}%` : '—'}
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Met or exceeded / total goals
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
                  <p className="text-xs font-medium uppercase text-neutral-500">
                    Accounts worked (sum)
                  </p>
                  <p className="mt-1 text-2xl font-semibold">
                    {summary.total_accounts_worked.toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
                <h3 className="text-base font-semibold">Top performers</h3>
                <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
                  Ranked by actual ÷ target on collector goals (sample).
                </p>
                <ul className="mt-4 divide-y divide-border">
                  {rankedGoals.length === 0 ? (
                    <li className="py-3 text-sm text-neutral-500">
                      No goals to rank yet
                    </li>
                  ) : (
                    rankedGoals.map((g, i) => (
                      <li
                        key={g.id}
                        className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
                      >
                        <span className="font-medium text-neutral-600">
                          #{i + 1}
                        </span>
                        <span className="font-mono text-xs">
                          {shortId(g.collector_id)}
                        </span>
                        <span>{g.goal_type}</span>
                        <span>
                          {g.target_amount
                            ? `${Math.round(
                                (g.actual_amount / g.target_amount) * 1000
                              ) / 10}%`
                            : '—'}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            </>
          )}
        </div>
      )}

      <FormDrawer
        open={ggDrawer}
        onClose={() => setGgDrawer(false)}
        title="Create goal group"
        onSubmit={submitGoalGroup}
        isSubmitting={creatingGg}
        submitLabel="Create"
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={ggForm.name}
              onChange={(e) =>
                setGgForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Description">
            <textarea
              className="min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={ggForm.description}
              onChange={(e) =>
                setGgForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Period type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={ggForm.period_type}
              onChange={(e) =>
                setGgForm((f) => ({ ...f, period_type: e.target.value }))
              }
            >
              {GOAL_PERIODS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ggForm.is_active}
              onChange={(e) =>
                setGgForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <FormDrawer
        open={cgDrawer}
        onClose={() => setCgDrawer(false)}
        title="Create collector goal"
        onSubmit={submitCollectorGoal}
        isSubmitting={creatingCg}
        submitLabel="Create"
      >
        <div className="flex flex-col gap-4">
          <FormField label="Collector ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={cgForm.collector_id}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, collector_id: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Goal group ID (optional)">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={cgForm.goal_group_id}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, goal_group_id: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Metric (goal type)">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.goal_type}
              onChange={(e) =>
                setCgForm((f) => ({
                  ...f,
                  goal_type: e.target.value as (typeof GOAL_TYPES)[number],
                }))
              }
            >
              {GOAL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Period">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.period}
              onChange={(e) =>
                setCgForm((f) => ({
                  ...f,
                  period: e.target.value as (typeof GOAL_PERIODS)[number],
                }))
              }
            >
              {GOAL_PERIODS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Target (USD)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.target_dollars}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, target_dollars: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Actual (USD)">
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.actual_dollars}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, actual_dollars: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Period start" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.period_start}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, period_start: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Period end" required>
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.period_end}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, period_end: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Notes">
            <textarea
              className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={cgForm.notes}
              onChange={(e) =>
                setCgForm((f) => ({ ...f, notes: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>
    </div>
  );
}
