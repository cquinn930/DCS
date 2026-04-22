'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Plus, Upload } from 'lucide-react';
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
import { useApiDetail, useApiList, useApiMutation, useApiUpload } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';

const TEMPLATES_API = '/api/v1/imports/templates';
const JOBS_API = '/api/v1/imports/jobs';

const FILE_FORMATS = ['csv', 'json', 'xlsx'] as const;

const TARGET_TABLES = [
  'accounts',
  'consumers',
  'payments',
  'disputes',
  'payments_allocations',
] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type ImportTemplateRow = {
  id: string;
  name: string;
  target_table: string;
  file_format: string;
  field_mappings?: unknown[] | null;
  active?: boolean;
};

type ImportTemplateDetail = ImportTemplateRow & {
  dedup_fields?: string[] | null;
  validation_rules?: unknown;
};

type ImportJobRow = {
  id: string;
  template_id?: string;
  template_name?: string;
  status: string;
  records_total?: number;
  records_processed?: number;
  error_count?: number;
  started_at?: string | null;
};

type ImportJobDetail = ImportJobRow & {
  errors?: unknown;
  error_details?: unknown;
  records_failed?: number;
};

export default function ImportsPage() {
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
  const [pasteData, setPasteData] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: templates, total: tTotal, isLoading: tLoading, mutate: mt } =
    useApiList<ImportTemplateRow>(TEMPLATES_API, listParams);
  const { data: jobs, total: jTotal, isLoading: jLoading, mutate: mj } =
    useApiList<ImportJobRow>(JOBS_API, listParams);

  const { data: tplDetail, isLoading: tplDetailLoading, mutate: mutateTpl } =
    useApiDetail<ImportTemplateDetail>(
      TEMPLATES_API,
      selectedTemplateId ?? undefined
    );
  const { data: jobDetail, isLoading: jobDetailLoading, mutate: mutateJob } =
    useApiDetail<ImportJobDetail>(JOBS_API, selectedJobId ?? undefined);

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
  const { upload, isUploading } = useApiUpload(TEMPLATES_API);
  const [runningImport, setRunningImport] = useState(false);

  const [form, setForm] = useState({
    name: '',
    target_table: 'accounts',
    file_format: 'csv',
    field_mappings: '[{"source":"col1","target":"id"}]',
    dedup_fields: '',
    validation_rules: '{}',
  });

  const templateRows = templates ?? [];
  const jobRows = jobs ?? [];

  const filteredTemplates = useMemo(() => {
    if (!search.trim()) return templateRows;
    const q = search.toLowerCase();
    return templateRows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.target_table.toLowerCase().includes(q)
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

  const templateColumns: ColumnDef<ImportTemplateRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'target_table', header: 'Target Table' },
    { accessorKey: 'file_format', header: 'File Format' },
    {
      accessorKey: 'field_mappings',
      header: 'Field Count',
      cell: ({ row }) => {
        const m = row.original.field_mappings;
        const n = Array.isArray(m) ? m.length : 0;
        return <span>{n}</span>;
      },
    },
    {
      accessorKey: 'active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() === false ? 'inactive' : 'active'} />
      ),
    },
  ];

  const jobColumns: ColumnDef<ImportJobRow>[] = [
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
    { accessorKey: 'records_total', header: 'Records Total' },
    { accessorKey: 'records_processed', header: 'Processed' },
    { accessorKey: 'error_count', header: 'Errors' },
    {
      accessorKey: 'started_at',
      header: 'Started',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
  ];

  function openCreateTemplate() {
    setEditMode(false);
    setForm({
      name: '',
      target_table: 'accounts',
      file_format: 'csv',
      field_mappings: '[{"source":"col1","target":"id"}]',
      dedup_fields: '',
      validation_rules: '{}',
    });
    setDrawerOpen(true);
  }

  function openEditTemplate() {
    if (!tplDetail) return;
    setEditMode(true);
    const dedup = Array.isArray(tplDetail.dedup_fields)
      ? tplDetail.dedup_fields.join(', ')
      : '';
    setForm({
      name: tplDetail.name,
      target_table: tplDetail.target_table,
      file_format: tplDetail.file_format,
      field_mappings: JSON.stringify(tplDetail.field_mappings ?? [], null, 2),
      dedup_fields: dedup,
      validation_rules: JSON.stringify(
        tplDetail.validation_rules ?? {},
        null,
        2
      ),
    });
    setDrawerOpen(true);
  }

  async function handleSubmitTemplate() {
    let mappings: unknown;
    let rules: unknown;
    try {
      mappings = JSON.parse(form.field_mappings) as unknown;
      rules = JSON.parse(form.validation_rules || '{}') as unknown;
    } catch {
      return;
    }
    const dedup = form.dedup_fields
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const payload: Record<string, unknown> = {
      name: form.name,
      target_table: form.target_table,
      file_format: form.file_format,
      field_mappings: mappings,
      dedup_fields: dedup,
      validation_rules: rules,
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

  async function confirmDeleteTemplate() {
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

  async function handleRunImport() {
    const tid = runTemplateId || selectedTemplateId;
    if (!tid) return;
    setRunningImport(true);
    try {
      if (file) {
        await upload(file, `/${tid}/run`);
      } else if (pasteData.trim()) {
        await apiClient.post(`${TEMPLATES_API}/${tid}/run`, {
          data: pasteData,
        });
      } else {
        await apiClient.post(`${TEMPLATES_API}/${tid}/run`, {});
      }
      setPasteData('');
      setFile(null);
      await mj();
      setTab('jobs');
    } finally {
      setRunningImport(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Imports"
        subtitle="Templates and file-based import jobs"
        actions={
          tab === 'templates' ? (
            <button
              type="button"
              onClick={openCreateTemplate}
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
        <DataTable<ImportTemplateRow>
          columns={templateColumns}
          data={filteredTemplates}
          isLoading={tLoading}
          emptyMessage="No import templates"
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
        <DataTable<ImportJobRow>
          columns={jobColumns}
          data={filteredJobs}
          isLoading={jLoading}
          emptyMessage="No import jobs"
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
          title={tplDetail?.name ?? 'Template'}
          subtitle={tplDetail?.target_table}
          onClose={() => setSelectedTemplateId(null)}
          onEdit={openEditTemplate}
          onDelete={() => setDeleteOpen(true)}
        >
          {tplDetailLoading || !tplDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Target table">{tplDetail.target_table}</FieldGroup>
                <FieldGroup label="File format">{tplDetail.file_format}</FieldGroup>
                <FieldGroup label="Active">
                  <StatusBadge
                    status={tplDetail.active === false ? 'inactive' : 'active'}
                  />
                </FieldGroup>
              </FieldGrid>
              <div className="mt-6 space-y-2">
                <h3 className="text-sm font-semibold">Run import</h3>
                <FormField label="Template">
                  <select
                    className="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={runTemplateId || selectedTemplateId}
                    onChange={(e) => setRunTemplateId(e.target.value)}
                  >
                    {templateRows.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </FormField>
                <FormField label="Upload file">
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-neutral-50 px-4 py-8 dark:bg-neutral-900/40">
                    <Upload className="mb-2 h-8 w-8 text-neutral-400" />
                    <span className="text-sm text-neutral-600">
                      {file ? file.name : 'Choose a file or use paste below'}
                    </span>
                    <input
                      type="file"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                </FormField>
                <FormField label="Or paste raw data">
                  <textarea
                    rows={6}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                    value={pasteData}
                    onChange={(e) => setPasteData(e.target.value)}
                    placeholder="CSV / JSON lines…"
                  />
                </FormField>
                <button
                  type="button"
                  disabled={runningImport || isUploading}
                  onClick={handleRunImport}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {isUploading || runningImport ? 'Starting…' : 'Run import'}
                </button>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      {tab === 'jobs' && selectedJobId && (
        <DetailPanel
          title={`Job ${selectedJobId.slice(0, 8)}…`}
          subtitle={jobDetail?.template_name}
          onClose={() => setSelectedJobId(null)}
        >
          {jobDetailLoading || !jobDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Status">
                  <StatusBadge status={jobDetail.status} />
                </FieldGroup>
                <FieldGroup label="Records total">
                  {jobDetail.records_total ?? '—'}
                </FieldGroup>
                <FieldGroup label="Processed">
                  {jobDetail.records_processed ?? '—'}
                </FieldGroup>
                <FieldGroup label="Errors">
                  {jobDetail.error_count ?? jobDetail.records_failed ?? '—'}
                </FieldGroup>
                <FieldGroup label="Started">
                  {fmtDate(jobDetail.started_at)}
                </FieldGroup>
              </FieldGrid>
              {(jobDetail.errors != null || jobDetail.error_details != null) && (
                <div className="mt-6">
                  <h3 className="text-sm font-semibold">Error details</h3>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-md border border-border bg-neutral-50 p-3 text-xs dark:bg-neutral-900/50">
                    {JSON.stringify(
                      jobDetail.error_details ?? jobDetail.errors,
                      null,
                      2
                    )}
                  </pre>
                </div>
              )}
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit template' : 'New import template'}
        onSubmit={handleSubmitTemplate}
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
          <FormField label="Target table" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.target_table}
              onChange={(e) =>
                setForm((f) => ({ ...f, target_table: e.target.value }))
              }
            >
              {TARGET_TABLES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="File format" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.file_format}
              onChange={(e) =>
                setForm((f) => ({ ...f, file_format: e.target.value }))
              }
            >
              {FILE_FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Field mappings (JSON array)">
            <textarea
              rows={8}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.field_mappings}
              onChange={(e) =>
                setForm((f) => ({ ...f, field_mappings: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Dedup fields (comma-separated)">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.dedup_fields}
              onChange={(e) =>
                setForm((f) => ({ ...f, dedup_fields: e.target.value }))
              }
              placeholder="external_id, account_id"
            />
          </FormField>
          <FormField label="Validation rules (JSON)">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.validation_rules}
              onChange={(e) =>
                setForm((f) => ({ ...f, validation_rules: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDeleteTemplate}
        title="Delete template?"
        message="Associated jobs may remain; this removes the template definition."
        confirmLabel={deletingTpl ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
