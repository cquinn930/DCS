'use client';

import { useCallback, useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Plus } from 'lucide-react';
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
import { apiClient } from '@/lib/api';

const API_TEMPLATES = '/api/v1/documents/templates';
const API_GENERATIONS = '/api/v1/documents/generations';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type TemplateRow = {
  id: string;
  code: string;
  name: string;
  document_type: string;
  category?: string | null;
  is_active?: boolean;
};

type TemplateDetail = TemplateRow & {
  body_template?: string | null;
};

type GenerationRow = {
  id: string;
  template_id?: string;
  account_id?: string;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
};

export default function DocumentsPage() {
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const [form, setForm] = useState({
    code: '',
    name: '',
    document_type: 'letter',
    category: '',
    body_template: '',
    is_active: true,
  });

  const [genAccountOpen, setGenAccountOpen] = useState(false);
  const [genAccountId, setGenAccountId] = useState('');
  const [genSubmitting, setGenSubmitting] = useState(false);

  const [batchOpen, setBatchOpen] = useState(false);
  const [batchPayload, setBatchPayload] = useState(
    '{\n  "account_ids": []\n}'
  );
  const [batchSubmitting, setBatchSubmitting] = useState(false);

  const listParams = useMemo(
    () => ({ page: pageIndex + 1, page_size: pageSize }),
    [pageIndex, pageSize]
  );

  const { data, total, isLoading, mutate } = useApiList<TemplateRow>(
    API_TEMPLATES,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<TemplateDetail>(API_TEMPLATES, selectedId ?? undefined);

  const genListPath =
    selectedId != null
      ? `${API_GENERATIONS}?template_id=${encodeURIComponent(selectedId)}`
      : null;
  const {
    data: generations,
    isLoading: genLoading,
    mutate: mutateGenerations,
  } = useApiList<GenerationRow>(genListPath ?? null, {
    page: 1,
    page_size: 50,
  });

  const { trigger: createTpl, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    TemplateDetail
  >('POST', API_TEMPLATES);
  const { trigger: patchTpl, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    TemplateDetail
  >('PATCH', API_TEMPLATES);
  const { trigger: deleteTpl, isMutating: deleting } = useApiMutation(
    'DELETE',
    API_TEMPLATES
  );

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.document_type.toLowerCase().includes(q) ||
        (r.category ?? '').toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<TemplateRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'document_type', header: 'Type' },
    { accessorKey: 'category', header: 'Category', cell: ({ getValue }) => String(getValue() ?? '—') },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => (
        <StatusBadge status={row.original.is_active ? 'active' : 'closed'} />
      ),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      code: '',
      name: '',
      document_type: 'letter',
      category: '',
      body_template: '',
      is_active: true,
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      code: detail.code,
      name: detail.name,
      document_type: detail.document_type,
      category: detail.category ?? '',
      body_template: detail.body_template ?? '',
      is_active: detail.is_active ?? true,
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const body: Record<string, unknown> = {
      code: form.code.trim(),
      name: form.name.trim(),
      document_type: form.document_type.trim(),
      category: form.category.trim() || undefined,
      body_template: form.body_template,
      is_active: form.is_active,
    };
    if (!editMode) {
      await createTpl(body);
    } else if (selectedId) {
      await patchTpl(body, `/${selectedId}`);
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmDelete() {
    if (!selectedId) return;
    await deleteTpl(undefined, `/${selectedId}`);
    setDeleteOpen(false);
    setSelectedId(null);
    await mutate();
  }

  const generateForAccount = useCallback(async () => {
    if (!selectedId || !genAccountId.trim()) return;
    setGenSubmitting(true);
    try {
      await apiClient.post(
        `${API_TEMPLATES.replace(/\/$/, '')}/${selectedId}/generate-for-account`,
        { account_id: genAccountId.trim() }
      );
      setGenAccountOpen(false);
      setGenAccountId('');
      await mutateGenerations();
    } finally {
      setGenSubmitting(false);
    }
  }, [selectedId, genAccountId, mutateGenerations]);

  const batchGenerate = useCallback(async () => {
    if (!selectedId) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(batchPayload || '{}') as Record<string, unknown>;
    } catch {
      alert('Batch payload must be valid JSON');
      return;
    }
    setBatchSubmitting(true);
    try {
      await apiClient.post(
        `${API_TEMPLATES.replace(/\/$/, '')}/${selectedId}/batch-generate`,
        parsed
      );
      setBatchOpen(false);
      await mutateGenerations();
    } finally {
      setBatchSubmitting(false);
    }
  }, [selectedId, batchPayload, mutateGenerations]);

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Document templates"
        subtitle="Manage merge templates and generations"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New template
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search templates…"
      />

      <DataTable<TemplateRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No templates"
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
          title={d?.name ?? 'Template'}
          subtitle={d?.code}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setGenAccountOpen(true)}
                  className="inline-flex h-9 items-center rounded-md bg-primary-600 px-3 text-sm font-medium text-white hover:bg-primary-700"
                >
                  Generate for Account
                </button>
                <button
                  type="button"
                  onClick={() => setBatchOpen(true)}
                  className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm hover:bg-muted"
                >
                  Batch Generate
                </button>
              </div>

              <div className="mt-6">
                <FieldGrid cols={2}>
                  <FieldGroup label="Code">{d.code}</FieldGroup>
                  <FieldGroup label="Type">{d.document_type}</FieldGroup>
                  <FieldGroup label="Category">{d.category || '—'}</FieldGroup>
                  <FieldGroup label="Active">
                    <StatusBadge status={d.is_active ? 'active' : 'closed'} />
                  </FieldGroup>
                </FieldGrid>
              </div>

              <div className="mt-6">
                <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Template body
                </h3>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-xs text-foreground">
                  {d.body_template || '—'}
                </pre>
              </div>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Recent generations
                </h3>
                {genLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading…</p>
                ) : (
                  <div className="mt-3 overflow-hidden rounded-md border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">ID</th>
                          <th className="px-3 py-2 text-left font-medium">
                            Account
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Created
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(generations ?? []).length === 0 ? (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-3 py-6 text-center text-neutral-500"
                            >
                              No generations yet
                            </td>
                          </tr>
                        ) : (
                          (generations ?? []).map((g) => (
                            <tr key={g.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono text-xs">
                                {g.id}
                              </td>
                              <td className="px-3 py-2">
                                {String(g.account_id ?? '—')}
                              </td>
                              <td className="px-3 py-2">
                                {g.status ? (
                                  <StatusBadge status={String(g.status)} />
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof g.created_at === 'string'
                                    ? g.created_at
                                    : undefined
                                )}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit template' : 'New template'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Code" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.code}
              onChange={(e) =>
                setForm((f) => ({ ...f, code: e.target.value }))
              }
              disabled={editMode}
            />
          </FormField>
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.name}
              onChange={(e) =>
                setForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Document type" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.document_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, document_type: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Category">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.category}
              onChange={(e) =>
                setForm((f) => ({ ...f, category: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Body template" required>
            <textarea
              rows={16}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed"
              value={form.body_template}
              onChange={(e) =>
                setForm((f) => ({ ...f, body_template: e.target.value }))
              }
              placeholder="{{merge_fields}} — use your merge syntax here"
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) =>
                setForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <FormDrawer
        open={genAccountOpen}
        onClose={() => setGenAccountOpen(false)}
        title="Generate for account"
        onSubmit={generateForAccount}
        isSubmitting={genSubmitting}
        submitLabel="Generate"
      >
        <FormField label="Account ID" required>
          <input
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
            value={genAccountId}
            onChange={(e) => setGenAccountId(e.target.value)}
            placeholder="uuid"
          />
        </FormField>
      </FormDrawer>

      <FormDrawer
        open={batchOpen}
        onClose={() => setBatchOpen(false)}
        title="Batch generate"
        onSubmit={batchGenerate}
        isSubmitting={batchSubmitting}
        submitLabel="Run batch"
      >
        <p className="mb-3 text-sm text-neutral-600 dark:text-neutral-400">
          POST body as JSON. Typical shape includes{' '}
          <code className="rounded bg-muted px-1">account_ids</code> or filters
          your API accepts.
        </p>
        <FormField label="JSON payload" required>
          <textarea
            rows={12}
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
            value={batchPayload}
            onChange={(e) => setBatchPayload(e.target.value)}
          />
        </FormField>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete template?"
        message="This removes the template definition. Existing generated documents may remain."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
