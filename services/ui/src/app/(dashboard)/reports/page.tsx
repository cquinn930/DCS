'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Play, Plus } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import {
  DetailPanel,
  FieldGrid,
  FieldGroup,
} from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/reports';

const SOURCE_TABLES = [
  'accounts',
  'consumers',
  'payments',
  'disputes',
  'notices',
  'judgments',
  'cases',
  'litigation',
] as const;

const OUTPUT_FORMATS = ['csv', 'json', 'pdf'] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

const execStatusColors: Record<string, string> = {
  queued: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500',
  running:
    'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  completed:
    'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  failed: 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500',
};

type ReportRow = {
  id: string;
  name: string;
  source_table: string;
  output_format: string;
  created_at?: string;
  last_run_at?: string | null;
};

type ReportDetail = ReportRow & {
  description?: string | null;
  columns?: unknown;
  filters?: unknown;
  group_by?: string | null;
  sort_by?: string | null;
};

type ReportExecution = {
  id: string;
  status: string;
  created_at?: string;
  completed_at?: string | null;
  download_url?: string | null;
  output_url?: string | null;
  error_message?: string | null;
};

export default function ReportsPage() {
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data, total, isLoading, mutate } = useApiList<ReportRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<ReportDetail>(API, selectedId ?? undefined);

  const execPath =
    selectedId != null ? `${API}/${selectedId}/executions` : null;
  const { data: execList, isLoading: execLoading, mutate: mutateExec } =
    useApiList<ReportExecution>(execPath, { page: 1, page_size: 100 });

  const { trigger: createReport, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    ReportDetail
  >('POST', API);
  const { trigger: patchReport, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    ReportDetail
  >('PATCH', API);
  const { trigger: deleteReport, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );
  const { trigger: runReport, isMutating: running } = useApiMutation(
    'POST',
    API
  );

  const [form, setForm] = useState({
    name: '',
    description: '',
    source_table: 'accounts',
    output_format: 'csv',
    columns: '[]',
    filters: '{}',
    group_by: '',
    sort_by: '',
  });

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.source_table.toLowerCase().includes(q) ||
        r.output_format.toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<ReportRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'source_table', header: 'Source Table' },
    { accessorKey: 'output_format', header: 'Output Format' },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
    {
      accessorKey: 'last_run_at',
      header: 'Last Run',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
  ];

  function stringifyJson(value: unknown, fallback: string) {
    if (value === undefined || value === null) return fallback;
    try {
      return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    } catch {
      return fallback;
    }
  }

  function openCreate() {
    setEditMode(false);
    setForm({
      name: '',
      description: '',
      source_table: 'accounts',
      output_format: 'csv',
      columns: '[]',
      filters: '{}',
      group_by: '',
      sort_by: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      name: detail.name,
      description: detail.description ?? '',
      source_table: detail.source_table,
      output_format: detail.output_format,
      columns: stringifyJson(detail.columns, '[]'),
      filters: stringifyJson(detail.filters, '{}'),
      group_by: detail.group_by ?? '',
      sort_by: detail.sort_by ?? '',
    });
    setDrawerOpen(true);
  }

  function parseJsonField(raw: string, label: string): unknown {
    const t = raw.trim();
    if (!t) return label === 'columns' ? [] : {};
    return JSON.parse(t) as unknown;
  }

  async function handleSubmit() {
    let columnsParsed: unknown;
    let filtersParsed: unknown;
    try {
      columnsParsed = parseJsonField(form.columns, 'columns');
      filtersParsed = parseJsonField(form.filters, 'filters');
    } catch {
      return;
    }
    const payload: Record<string, unknown> = {
      name: form.name,
      description: form.description || undefined,
      source_table: form.source_table,
      output_format: form.output_format,
      columns: columnsParsed,
      filters: filtersParsed,
      group_by: form.group_by || undefined,
      sort_by: form.sort_by || undefined,
    };
    if (!editMode) {
      await createReport(payload);
    } else if (selectedId) {
      await patchReport(payload, `/${selectedId}`);
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmDelete() {
    if (!selectedId) return;
    try {
      await deleteReport(undefined, `/${selectedId}`);
      setDeleteOpen(false);
      setSelectedId(null);
      await mutate();
    } catch {
      /* surfaced by client */
    }
  }

  async function handleRunReport() {
    if (!selectedId) return;
    await runReport(undefined, `/${selectedId}/run`);
    await mutateDetail();
    await mutateExec();
    await mutate();
  }

  const d = detail;
  const executions = execList ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        subtitle="Define scheduled and on-demand data exports"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New report
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search reports…"
      />

      <DataTable<ReportRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No reports found"
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
          title={d?.name ?? 'Report'}
          subtitle={d?.source_table ? `Table · ${d.source_table}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Name">{d.name}</FieldGroup>
                <FieldGroup label="Output format">{d.output_format}</FieldGroup>
                <FieldGroup label="Source table">{d.source_table}</FieldGroup>
                <FieldGroup label="Created">{fmtDate(d.created_at)}</FieldGroup>
                <FieldGroup label="Last run">{fmtDate(d.last_run_at)}</FieldGroup>
                {d.description ? (
                  <FieldGroup label="Description">
                    <span className="whitespace-pre-wrap">{d.description}</span>
                  </FieldGroup>
                ) : null}
              </FieldGrid>

              <div className="mt-6 space-y-2">
                <h3 className="text-sm font-semibold text-foreground">Configuration</h3>
                <pre className="max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-3 text-xs dark:bg-neutral-900/50">
                  {stringifyJson(
                    {
                      columns: d.columns,
                      filters: d.filters,
                      group_by: d.group_by,
                      sort_by: d.sort_by,
                    },
                    '{}'
                  )}
                </pre>
              </div>

              <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  disabled={running}
                  onClick={handleRunReport}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700 disabled:opacity-50"
                >
                  <Play className="h-4 w-4" />
                  {running ? 'Running…' : 'Run report'}
                </button>
              </div>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Recent executions
                </h3>
                {execLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading…</p>
                ) : executions.length === 0 ? (
                  <p className="mt-2 text-sm text-neutral-500">No executions yet.</p>
                ) : (
                  <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
                    {executions.map((ex) => (
                      <li
                        key={ex.id}
                        className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge
                            status={ex.status}
                            colorMap={execStatusColors}
                          />
                          <span className="text-neutral-600 dark:text-neutral-400">
                            {fmtDate(ex.created_at)}
                            {ex.completed_at
                              ? ` → ${fmtDate(ex.completed_at)}`
                              : ''}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {ex.download_url || ex.output_url ? (
                            <a
                              href={(ex.download_url ?? ex.output_url) as string}
                              className="text-primary-600 hover:underline dark:text-primary-400"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Download
                            </a>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit report' : 'New report'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save changes' : 'Create'}
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
              rows={2}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Source table" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.source_table}
              onChange={(e) =>
                setForm((f) => ({ ...f, source_table: e.target.value }))
              }
            >
              {SOURCE_TABLES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Output format" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.output_format}
              onChange={(e) =>
                setForm((f) => ({ ...f, output_format: e.target.value }))
              }
            >
              {OUTPUT_FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Columns (JSON array)">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.columns}
              onChange={(e) =>
                setForm((f) => ({ ...f, columns: e.target.value }))
              }
              placeholder='["id","name"]'
            />
          </FormField>
          <FormField label="Filters (JSON object)">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.filters}
              onChange={(e) =>
                setForm((f) => ({ ...f, filters: e.target.value }))
              }
              placeholder='{"status":"open"}'
            />
          </FormField>
          <FormField label="Group by">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.group_by}
              onChange={(e) =>
                setForm((f) => ({ ...f, group_by: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Sort by">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.sort_by}
              onChange={(e) =>
                setForm((f) => ({ ...f, sort_by: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete report?"
        message="This report definition will be removed."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
