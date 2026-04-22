'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { formatCurrency } from '@/lib/utils';

const API = '/api/v1/waterfalls';

type WaterfallRow = {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
};

type WaterfallRuleRow = {
  id: string;
  waterfall_id: string;
  bucket: string;
  phase: string;
  priority: number;
  max_percentage: number | null;
  max_amount: number | null;
};

type TestAllocationResult = {
  amount_cents: number;
  phase_filter: string | null;
  allocations: Record<string, number>;
  remainder_cents: number;
};

const BUCKETS = [
  'principal',
  'interest',
  'fees',
  'costs',
  'attorney_fees',
  'statutory_fees',
  'excess',
] as const;

const PHASES = [
  { value: 'default', label: 'Default' },
  { value: 'pre_suit', label: 'Pre-suit' },
  { value: 'post_suit', label: 'Post-suit' },
  { value: 'pre_judgment', label: 'Pre-judgment' },
  { value: 'post_judgment', label: 'Post-judgment' },
];

function RulesCountCell({ waterfallId }: { waterfallId: string }) {
  const { total, isLoading } = useApiList<unknown>(`${API}/${waterfallId}/rules`, {
    page: 1,
    page_size: 1,
  });
  if (isLoading) return <span className="text-neutral-400">…</span>;
  return <span>{total}</span>;
}

export default function WaterfallsPage() {
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };
  const { data, total, isLoading, mutate } = useApiList<WaterfallRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<WaterfallRow & { is_default?: boolean; jurisdiction?: string | null }>(
      API,
      selectedId ?? undefined
    );
  const { data: rules, isLoading: rulesLoading, mutate: mutateRules } = useApiList<WaterfallRuleRow>(
    selectedId ? `${API}/${selectedId}/rules` : null,
    { page: 1, page_size: 200 }
  );

  const { trigger: createWf, isMutating: creating } = useApiMutation('POST', API);
  const { trigger: patchWf, isMutating: patching } = useApiMutation('PATCH', API);
  const { trigger: createRule, isMutating: creatingRule } = useApiMutation('POST', API);
  const { trigger: testAlloc, isMutating: testing } = useApiMutation<
    { amount_cents: number; phase?: string | null },
    TestAllocationResult
  >('POST', API);

  const [form, setForm] = useState({
    name: '',
    description: '',
    is_default: false,
  });

  const [ruleForm, setRuleForm] = useState({
    bucket: 'principal',
    phase: 'default',
    priority: '0',
    max_percentage: '',
    fixed_amount_dollars: '',
  });

  const [testAmount, setTestAmount] = useState('');
  const [testPhase, setTestPhase] = useState<string>('');
  const [testResult, setTestResult] = useState<TestAllocationResult | null>(null);

  const filtered = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.name.toLowerCase().includes(q) ||
      (row.description?.toLowerCase().includes(q) ?? false)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const sortedRules = useMemo(
    () => [...(rules ?? [])].sort((a, b) => a.priority - b.priority),
    [rules]
  );

  const columns: ColumnDef<WaterfallRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return v ? <span className="line-clamp-2">{v}</span> : '—';
      },
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ getValue }) =>
        getValue() ? <StatusBadge status="active" /> : <StatusBadge status="closed" />,
    },
    {
      id: 'rules_count',
      header: 'Rules count',
      cell: ({ row }) => <RulesCountCell waterfallId={row.original.id} />,
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({ name: '', description: '', is_default: false });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      name: detail.name,
      description: detail.description ?? '',
      is_default: !!detail.is_default,
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (!editMode) {
      await createWf({
        name: form.name,
        description: form.description || null,
        is_default: form.is_default,
      });
    } else if (selectedId) {
      await patchWf(
        {
          name: form.name,
          description: form.description || null,
          is_default: form.is_default,
        },
        `/${selectedId}`
      );
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  async function handleAddRule() {
    if (!selectedId) return;
    const maxPct = ruleForm.max_percentage.trim()
      ? Math.min(100, Math.max(0, parseInt(ruleForm.max_percentage, 10)))
      : null;
    const maxAmt = ruleForm.fixed_amount_dollars.trim()
      ? Math.round(parseFloat(ruleForm.fixed_amount_dollars) * 100)
      : null;
    await createRule(
      {
        waterfall_id: selectedId,
        bucket: ruleForm.bucket,
        phase: ruleForm.phase,
        priority: parseInt(ruleForm.priority, 10) || 0,
        max_percentage: maxPct,
        max_amount: maxAmt,
        conditions: {},
      },
      `/${selectedId}/rules`
    );
    setRuleForm({
      bucket: 'principal',
      phase: 'default',
      priority: '0',
      max_percentage: '',
      fixed_amount_dollars: '',
    });
    await mutateRules();
    await mutate();
  }

  async function runTestAllocation() {
    if (!selectedId) return;
    const cents = Math.round(parseFloat(testAmount || '0') * 100);
    if (cents <= 0) return;
    const body: { amount_cents: number; phase?: string | null } = { amount_cents: cents };
    if (testPhase) body.phase = testPhase;
    const res = await testAlloc(body, `/${selectedId}/test-allocation`);
    setTestResult(res);
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payment waterfalls"
        subtitle="Allocation rules and allocation testing"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New waterfall
          </button>
        }
      />

      <SearchBar value={search} onChange={setSearch} placeholder="Search waterfalls…" />

      <DataTable<WaterfallRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No waterfalls found"
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
          title={d?.name ?? 'Waterfall'}
          subtitle={d?.description ?? undefined}
          onClose={() => {
            setSelectedId(null);
            setTestResult(null);
          }}
          onEdit={openEdit}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Active">
                  {d.is_active ? <StatusBadge status="active" /> : <StatusBadge status="closed" />}
                </FieldGroup>
                <FieldGroup label="Default">{d.is_default ? 'Yes' : 'No'}</FieldGroup>
              </FieldGrid>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">Rules (by priority)</h3>
                {rulesLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading rules…</p>
                ) : (
                  <div className="mt-2 overflow-x-auto rounded-md border border-border">
                    <table className="w-full min-w-[640px] text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Priority
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Phase
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Bucket
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            % cap
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Fixed amount
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedRules.map((r) => (
                          <tr key={r.id} className="border-t border-border">
                            <td className="px-3 py-2 font-mono">{r.priority}</td>
                            <td className="px-3 py-2">
                              <StatusBadge status={r.phase.replace(/_/g, ' ')} />
                            </td>
                            <td className="px-3 py-2">
                              <StatusBadge status={r.bucket.replace(/_/g, ' ')} />
                            </td>
                            <td className="px-3 py-2">
                              {r.max_percentage != null ? `${r.max_percentage}%` : '—'}
                            </td>
                            <td className="px-3 py-2">
                              {r.max_amount != null ? formatCurrency(r.max_amount) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="mt-8 rounded-lg border border-border bg-neutral-50/50 p-4 dark:bg-neutral-900/30">
                <h3 className="text-sm font-semibold text-foreground">Add rule</h3>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Bucket</span>
                    <select
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={ruleForm.bucket}
                      onChange={(e) => setRuleForm((f) => ({ ...f, bucket: e.target.value }))}
                    >
                      {BUCKETS.map((b) => (
                        <option key={b} value={b}>
                          {b.replace(/_/g, ' ')}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Phase</span>
                    <select
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={ruleForm.phase}
                      onChange={(e) => setRuleForm((f) => ({ ...f, phase: e.target.value }))}
                    >
                      {PHASES.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Priority</span>
                    <input
                      type="number"
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={ruleForm.priority}
                      onChange={(e) => setRuleForm((f) => ({ ...f, priority: e.target.value }))}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Max % (optional)</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={ruleForm.max_percentage}
                      onChange={(e) => setRuleForm((f) => ({ ...f, max_percentage: e.target.value }))}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Fixed amount USD (optional)</span>
                    <input
                      type="number"
                      step="0.01"
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={ruleForm.fixed_amount_dollars}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, fixed_amount_dollars: e.target.value }))
                      }
                    />
                  </label>
                </div>
                <button
                  type="button"
                  disabled={creatingRule}
                  onClick={handleAddRule}
                  className="mt-4 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {creatingRule ? 'Adding…' : 'Add rule'}
                </button>
              </div>

              <div className="mt-8 rounded-lg border border-dashed border-primary-300 bg-primary-50/30 p-4 dark:border-primary-700 dark:bg-primary-950/20">
                <h3 className="text-sm font-semibold text-foreground">Test allocation</h3>
                <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
                  Simulate how a payment is split across buckets for this waterfall.
                </p>
                <div className="mt-4 flex flex-wrap items-end gap-3">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Amount (USD)</span>
                    <input
                      type="number"
                      step="0.01"
                      className="w-40 rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={testAmount}
                      onChange={(e) => setTestAmount(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium">Phase filter (optional)</span>
                    <select
                      className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={testPhase}
                      onChange={(e) => setTestPhase(e.target.value)}
                    >
                      <option value="">All phases</option>
                      {PHASES.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    disabled={testing}
                    onClick={runTestAllocation}
                    className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium shadow-sm hover:bg-muted disabled:opacity-50"
                  >
                    {testing ? 'Running…' : 'Run test'}
                  </button>
                </div>
                {testResult ? (
                  <div className="mt-4 space-y-2 rounded-md border border-border bg-background p-3 text-sm">
                    <p>
                      <span className="text-neutral-500">Input:</span>{' '}
                      {formatCurrency(testResult.amount_cents)} (remainder{' '}
                      {formatCurrency(testResult.remainder_cents)})
                    </p>
                    <ul className="space-y-1 font-mono text-xs">
                      {Object.entries(testResult.allocations).map(([k, v]) => (
                        <li key={k}>
                          {k}: {formatCurrency(v)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit waterfall' : 'New waterfall'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </FormField>
          <FormField label="Description">
            <textarea
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              rows={3}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
            />
            Default waterfall for new accounts
          </label>
        </div>
      </FormDrawer>
    </div>
  );
}
