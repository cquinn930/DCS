'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
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
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { cn } from '@/lib/utils';

const DEFINITIONS = '/api/v1/tags/definitions';
const TAGS_BASE = '/api/v1/tags';

type TagDefinitionRow = {
  id: string;
  code: string;
  name: string;
  color: string | null;
  category: string;
  is_active: boolean;
  description?: string | null;
};

type TagAssignmentRow = {
  id: string;
  account_id: string;
  tag_definition_id: string;
  applied_at: string;
};

const COLOR_PRESETS = [
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
  '#f97316',
  '#22c55e',
  '#0ea5e9',
  '#64748b',
];

const CATEGORIES = [
  'status',
  'compliance',
  'financial',
  'legal',
  'operational',
  'client',
  'system',
  'custom',
] as const;

function swatch(color: string | null | undefined) {
  if (!color) return null;
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="inline-block h-4 w-4 rounded border border-border"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      <span className="font-mono text-xs">{color}</span>
    </span>
  );
}

export default function TagsPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [bulkTagId, setBulkTagId] = useState('');
  const [bulkAccountIds, setBulkAccountIds] = useState('');
  const [accountLookupId, setAccountLookupId] = useState('');

  const listParams = { page: pageIndex + 1, page_size: pageSize };
  const { data, total, isLoading, mutate } = useApiList<TagDefinitionRow>(
    DEFINITIONS,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<TagDefinitionRow>(DEFINITIONS, selectedId ?? undefined);

  const accountsKey =
    selectedId != null
      ? ([
          'tag-accounts',
          selectedId,
          user?.tenantId ?? '',
        ] as const)
      : null;
  const { data: accountsPage, mutate: mutateAccounts } = useSWR(
    accountsKey,
    async () => {
      const { data: body } = await apiClient.get<{
        items?: TagAssignmentRow[];
        total?: number;
      }>(`${TAGS_BASE}/definitions/${selectedId}/accounts?page=1&page_size=100`);
      return body;
    }
  );

  const accountTagsKey =
    accountLookupId.trim().length > 0
      ? ([
          'account-tags',
          accountLookupId.trim(),
        ] as const)
      : null;
  const { data: accountTagsPage, isLoading: accountTagsLoading } = useSWR(
    accountTagsKey,
    async () => {
      const { data: body } = await apiClient.get<{
        items?: TagAssignmentRow[];
      }>(`${TAGS_BASE}/accounts/${accountLookupId.trim()}/tags?page=1&page_size=50`);
      return body;
    }
  );

  const { trigger: createDef, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    TagDefinitionRow
  >('POST', DEFINITIONS);
  const { trigger: patchDef, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    TagDefinitionRow
  >('PATCH', DEFINITIONS);
  const { trigger: bulkApply, isMutating: applying } = useApiMutation<
    { tag_definition_id: string; account_ids: string[] },
    TagAssignmentRow[]
  >('POST', `${TAGS_BASE}/bulk-apply`);
  const { trigger: bulkRemove, isMutating: removing } = useApiMutation<
    { tag_definition_id: string; account_ids: string[] },
    { removed: number }
  >('POST', `${TAGS_BASE}/bulk-remove`);

  const [form, setForm] = useState({
    code: '',
    name: '',
    color: '#6366f1',
    category: 'custom',
    description: '',
    is_active: true,
  });

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<TagDefinitionRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'color',
      header: 'Color',
      cell: ({ getValue }) => swatch(String(getValue() ?? '')),
    },
    { accessorKey: 'category', header: 'Category' },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() ? 'active' : 'inactive'} />
      ),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      code: '',
      name: '',
      color: '#6366f1',
      category: 'custom',
      description: '',
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
      color: detail.color || '#6366f1',
      category: detail.category,
      description: detail.description ?? '',
      is_active: detail.is_active,
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const payload = {
      code: form.code,
      name: form.name,
      color: form.color,
      category: form.category,
      description: form.description || null,
      is_active: form.is_active,
    };
    if (!editMode) {
      await createDef(payload);
    } else if (selectedId) {
      await patchDef(payload, `/${selectedId}`);
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  function parseUuidList(raw: string): string[] {
    return raw
      .split(/[\s,;]+/g)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  async function handleBulkApply() {
    const account_ids = parseUuidList(bulkAccountIds);
    if (!bulkTagId.trim() || account_ids.length === 0) return;
    await bulkApply({
      tag_definition_id: bulkTagId.trim(),
      account_ids,
    });
    setBulkAccountIds('');
    await mutate();
    if (selectedId === bulkTagId.trim()) await mutateAccounts();
  }

  async function handleBulkRemove() {
    const account_ids = parseUuidList(bulkAccountIds);
    if (!bulkTagId.trim() || account_ids.length === 0) return;
    await bulkRemove({
      tag_definition_id: bulkTagId.trim(),
      account_ids,
    });
    setBulkAccountIds('');
    await mutate();
    if (selectedId === bulkTagId.trim()) await mutateAccounts();
  }

  const assignmentRows = accountsPage?.items ?? [];
  const assignmentColumns: ColumnDef<TagAssignmentRow>[] = [
    {
      accessorKey: 'account_id',
      header: 'Account ID',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue())}</span>
      ),
    },
    {
      accessorKey: 'applied_at',
      header: 'Applied',
      cell: ({ getValue }) =>
        new Date(String(getValue())).toLocaleString(undefined, {
          dateStyle: 'short',
          timeStyle: 'short',
        }),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tags"
        subtitle="Define tags, bulk apply to accounts, and inspect assignments"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New tag
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search tag definitions…"
      />

      <DataTable<TagDefinitionRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No tag definitions"
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
          title={detail?.name ?? 'Tag'}
          subtitle={detail ? `Code ${detail.code}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {detailLoading || !detail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Code">{detail.code}</FieldGroup>
                <FieldGroup label="Category">{detail.category}</FieldGroup>
                <FieldGroup label="Color">{swatch(detail.color)}</FieldGroup>
                <FieldGroup label="Active">
                  <StatusBadge status={detail.is_active ? 'active' : 'inactive'} />
                </FieldGroup>
                <FieldGroup label="Description">
                  {detail.description ?? '—'}
                </FieldGroup>
              </FieldGrid>

              <div className="mt-8 border-t border-border pt-6">
                <h3 className="text-sm font-semibold text-foreground">
                  Accounts with this tag
                </h3>
                <p className="mt-1 text-xs text-neutral-500">
                  GET /api/v1/tags/definitions/&#123;id&#125;/accounts
                </p>
                <div className="mt-4">
                  <DataTable<TagAssignmentRow>
                    columns={assignmentColumns}
                    data={assignmentRows}
                    isLoading={false}
                    emptyMessage="No active assignments"
                  />
                </div>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h3 className="text-base font-semibold text-foreground">
            Bulk operations
          </h3>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
            Apply or remove a tag for many accounts. Use one UUID per line or
            comma-separated.
          </p>
          <div className="mt-4 space-y-3">
            <label className="text-sm font-medium">Tag definition ID</label>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={bulkTagId}
              onChange={(e) => setBulkTagId(e.target.value)}
              placeholder="Tag UUID"
            />
            <label className="text-sm font-medium">Account IDs</label>
            <textarea
              className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={bulkAccountIds}
              onChange={(e) => setBulkAccountIds(e.target.value)}
              placeholder="Account UUIDs…"
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={applying}
                onClick={handleBulkApply}
                className={cn(
                  'rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50'
                )}
              >
                {applying ? 'Applying…' : 'Bulk apply'}
              </button>
              <button
                type="button"
                disabled={removing}
                onClick={handleBulkRemove}
                className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
              >
                {removing ? 'Removing…' : 'Bulk remove'}
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h3 className="text-base font-semibold text-foreground">
            Tags on account
          </h3>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
            Search by account ID to list active tag assignments.
          </p>
          <div className="mt-4 space-y-3">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={accountLookupId}
              onChange={(e) => setAccountLookupId(e.target.value)}
              placeholder="Account UUID"
            />
            {accountLookupId.trim() ? (
              accountTagsLoading ? (
                <p className="text-sm text-neutral-500">Loading…</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {(accountTagsPage?.items ?? []).length === 0 ? (
                    <li className="text-neutral-500">No tags on this account</li>
                  ) : (
                    (accountTagsPage?.items ?? []).map((a) => (
                      <li
                        key={a.id}
                        className="flex justify-between rounded-md border border-border px-3 py-2"
                      >
                        <span className="font-mono text-xs">
                          {a.tag_definition_id}
                        </span>
                        <span className="text-xs text-neutral-500">
                          {new Date(a.applied_at).toLocaleDateString()}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              )
            ) : (
              <p className="text-sm text-neutral-500">Enter an account ID.</p>
            )}
          </div>
        </div>
      </div>

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit tag' : 'Create tag definition'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Code" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              disabled={editMode}
            />
          </FormField>
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </FormField>
          <FormField label="Color">
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="color"
                className="h-10 w-14 cursor-pointer rounded border border-input bg-background p-1"
                value={form.color}
                onChange={(e) =>
                  setForm((f) => ({ ...f, color: e.target.value }))
                }
              />
              <select
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.color}
                onChange={(e) =>
                  setForm((f) => ({ ...f, color: e.target.value }))
                }
              >
                {COLOR_PRESETS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </FormField>
          <FormField label="Category">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.category}
              onChange={(e) =>
                setForm((f) => ({ ...f, category: e.target.value }))
              }
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Description">
            <textarea
              className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
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
    </div>
  );
}
