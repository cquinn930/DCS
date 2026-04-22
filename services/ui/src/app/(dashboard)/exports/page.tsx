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

const TEMPLATES_API = '/api/v1/exports/templates';
const JOBS_API = '/api/v1/exports/jobs';

const SOURCE_TABLES = [
  'accounts',
  'consumers',
  'payments',
  'disputes',
  'notices',
  'judgments',
] as const;

const OUTPUT_FORMATS = ['csv', 'json', 'xlsx', 'pdf'] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type ExportTemplateRow = {
  id: string;
  name: string;
  source_table: string;
  output_format: string;
  active?: boolean;
};

type ExportTemplateDetail = ExportTemplateRow & {
  columns?: unknown;
  filters?: unknown;
  sort_order?: string | null;
};

type ExportJobRow = {
  id: string;
  template_id?: string;
  template_name?: string;
  status: string;
  record_count?: number;
  output_format?: string;
  started_at?: string | null;
  completed_at?: string | null;
};

export default function ExportsPage() {
  const [tab, setTab] = useState<'templates' | 'jobs'>('templates');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null
  );
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [runTemplateId, setRunTemplateId] = useState('');

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: templates, total: tTotal, isLoading: tLoading, mutate: mt } =
    useApiList<ExportTemplateRow>(TEMPLATES_API, listParams);
  const { data: jobs, total: jTotal, isLoading: jLoading, mutate: mj } =
    useApiList<ExportJobRow>(JOBS_API, listParams);

  const { data: tplDetail, isLoading: tplDetailLoading, mutate: mutateTpl } =
    useApiDetail<ExportTemplateDetail>(
      TEMPLATES_API,
      selectedTemplateId ?? undefined
    );
  const { data: jobDetail, isLoading: jobDetailLoading } = useApiDetail<
    ExportJobRow & { error_message?: string | null }
  >(JOBS_API, selectedJobId ?? undefined);

  const { trigger: createTpl, isMutating: creatingTpl } = useApiMutation(
    'POST',
    TEMPLATES_API
  );
  const { trigger: patchTpl, isMutating: patchingTpl } = useApiMutation(
    'PATCH',
    TEMPLATES_API
  );
  const { trigger: deleteTpl, isMutating: deletingTpl } = useApiMutation(
    'DELETE',
    TEMPLATES_API
  );
  const { trigger: runExport, isMutating: running } = useApiMutation(
    'POST',
    TEMPLATES_API
  );

  const [form, setForm] = useState({
    name: '',
    source_table: 'accounts',
    output_format: 'csv',
    columns: '[]',
    filters: '{}',
    sort_order: '',
  });

  const templateRows = templates ?? [];
  const jobRows = jobs ?? [];

  const filteredTemplates = useMemo(() => {
    if (!search.trim()) return templateRows;
    const q = search.toLowerCase();
    return templateRows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.source_table.toLowerCase().includes(q)
    );
  }, [templateRows, search]);

  const filteredJobs = useMemo(() => {
    if (!search.trim()) return jobRows;
    const q = search.toLowerCase();
    return jobRows.filter(
      (r) =>
        (r.template_name ?? '').toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [jobRows, search]);

  const pageCount =
    tab === 'templates'
      ? Math.max(1, Math.ceil((tTotal ?? 0) / pageSize))
      : Math.max(1, Math.ceil((jTotal ?? 0) / pageSize));

  const templateColumns: ColumnDef<ExportTemplateRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'source_table', header: 'Source Table' },
    { accessorKey: 'output_format', header: 'Output Format' },
    {
      accessorKey: 'active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() === false ? 'inactive' : 'active'} />
      ),
    },
  ];

  const jobColumns: ColumnDef<ExportJobRow>[] = [
    {
      accessorKey: 'template_name',
      header: 'Template',
      cell: ({ row }) => row.original.template_name ?? row.original.template_id ?? '—',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    { accessorKey: 'record_count', header: 'Record Count' },
    { accessorKey: 'output_format', header: 'Format' },
    {
      accessorKey: 'started_at',
      header: 'Started',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
    {
      accessorKey: 'completed_at',
      header: 'Completed',
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
      source_table: 'accounts',
      output_format: 'csv',
      columns: '[]',
      filters: '{}',
      sort_order: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!tplDetail) return;
    setEditMode(true);
    setForm({
      name: tplDetail.name,
      source_table: tplDetail.source_table,
      output_format: tplDetail.output_format,
      columns: stringifyJson(tplDetail.columns, '[]'),
      filters: stringifyJson(tplDetail.filters, '{}'),
      sort_order: tplDetail.sort_order ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    let columnsParsed: unknown;
    let filtersParsed: unknown;
    try {
      columnsParsed = JSON.parse(form.columns || '[]') as unknown;
      filtersParsed = JSON.parse(form.filters || '{}') as unknown;
    } catch {
      return;
    }
    const payload: Record<string, unknown> = {
      name: form.name,
      source_table: form.source_table,
      output_format: form.output_format,
      columns: columnsParsed,
      filters: filtersParsed,
      sort_order: form.sort_order || undefined,
    };
    if (!editMode) {
      await createTpl(payload);
    } else if (selectedTemplateId) {
      await patchTpl(payload, `/${selectedTemplateId}`);
      await mutateTpl();
    }
    setDrawerOpen(false);
    await mt();
  }

  async function confirmDelete() {
    if (!selectedTemplateId) return;
    try {
      await deleteTpl(undefined, `/${selectedTemplateId}`);
      setDeleteOpen(false);
      setSelectedTemplateId(null);
      await mt();
    } catch {
      /* noop */
    }
  }

  async function handleRun() {
    const tid = runTemplateId || selectedTemplateId;
    if (!tid) return;
    await runExport(undefined, `/${tid}/run`);
    await mj();
    setTab('jobs');
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Exports"
        subtitle="Bulk export templates and job history"
        actions={
          tab === 'templates' ? (
            <button
              type="button"
              onClick={openCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New template
            </button>
          ) : null
        }
      />

      <div className="flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => {
            setTab('templates');
            setSelectedJobId(null);
            setPageIndex(0);
          }}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${
            tab === 'templates'
              ? 'border-primary-600 text-primary-700 dark:text-primary-400'
              : 'border-transparent text-neutral-600 hover:text-foreground'
          }`}
        >
          Templates
        </button>
        <button
          type="button"
          onClick={() => {
            setTab('jobs');
            setSelectedTemplateId(null);
            setPageIndex(0);
          }}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${
            tab === 'jobs'
              ? 'border-primary-600 text-primary-700 dark:text-primary-400'
              : 'border-transparent text-neutral-600 hover:text-foreground'
          }`}
        >
          Jobs
        </button>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder={
          tab === 'templates' ? 'Search templates…' : 'Search jobs…'
        }
      />

      {tab === 'templates' ? (
        <DataTable<ExportTemplateRow>
          columns={templateColumns}
          data={filteredTemplates}
          isLoading={tLoading}
          emptyMessage="No export templates"
          onRowClick={(row) => setSelectedTemplateId(row.id)}
          pageCount={pageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      ) : (
        <DataTable<ExportJobRow>
          columns={jobColumns}
          data={filteredJobs}
          isLoading={jLoading}
          emptyMessage="No export jobs"
          onRowClick={(row) => setSelectedJobId(row.id)}
          pageCount={pageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      )}

      {tab === 'templates' && selectedTemplateId && (
        <DetailPanel
          title={tplDetail?.name ?? 'Export template'}
          subtitle={tplDetail?.source_table}
          onClose={() => setSelectedTemplateId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {tplDetailLoading || !tplDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Source table">{tplDetail.source_table}</FieldGroup>
                <FieldGroup label="Output format">{tplDetail.output_format}</FieldGroup>
                <FieldGroup label="Active">
                  <StatusBadge
                    status={tplDetail.active === false ? 'inactive' : 'active'}
                  />
                </FieldGroup>
              </FieldGrid>
              <pre className="mt-6 max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-3 text-xs dark:bg-neutral-900/50">
                {stringifyJson(
                  {
                    columns: tplDetail.columns,
                    filters: tplDetail.filters,
                    sort_order: tplDetail.sort_order,
                  },
                  '{}'
                )}
              </pre>
              <div className="mt-6 flex flex-wrap items-end gap-3 border-t border-border pt-4">
                <div className="min-w-[200px] flex-1">
                  <label className="text-xs font-medium uppercase text-neutral-500">
                    Run template
                  </label>
                  <select
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={runTemplateId || selectedTemplateId}
                    onChange={(e) => setRunTemplateId(e.target.value)}
                  >
                    {templateRows.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  disabled={running}
                  onClick={handleRun}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  <Play className="h-4 w-4" />
                  {running ? 'Starting…' : 'Run export'}
                </button>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      {tab === 'jobs' && selectedJobId && (
        <DetailPanel
          title={`Export job`}
          subtitle={jobDetail?.template_name ?? jobDetail?.template_id}
          onClose={() => setSelectedJobId(null)}
        >
          {jobDetailLoading || !jobDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Status">
                <StatusBadge status={jobDetail.status} />
              </FieldGroup>
              <FieldGroup label="Records">{jobDetail.record_count ?? '—'}</FieldGroup>
              <FieldGroup label="Format">{jobDetail.output_format ?? '—'}</FieldGroup>
              <FieldGroup label="Started">{fmtDate(jobDetail.started_at)}</FieldGroup>
              <FieldGroup label="Completed">
                {fmtDate(jobDetail.completed_at)}
              </FieldGroup>
              {'error_message' in jobDetail && jobDetail.error_message ? (
                <FieldGroup label="Error">
                  <span className="text-error-600">{jobDetail.error_message}</span>
                </FieldGroup>
              ) : null}
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit export template' : 'New export template'}
        onSubmit={handleSubmit}
        isSubmitting={creatingTpl || patchingTpl}
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
          <FormField label="Columns (JSON)">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.columns}
              onChange={(e) =>
                setForm((f) => ({ ...f, columns: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Filters (JSON)">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.filters}
              onChange={(e) =>
                setForm((f) => ({ ...f, filters: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Sort order">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.sort_order}
              onChange={(e) =>
                setForm((f) => ({ ...f, sort_order: e.target.value }))
              }
              placeholder="created_at desc"
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete export template?"
        message="Scheduled or historical jobs may still reference this template."
        confirmLabel={deletingTpl ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
