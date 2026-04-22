'use client';

import { useState } from 'react';
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
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/cases';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const CASE_STATUSES = [
  'new',
  'in_progress',
  'on_hold',
  'escalated',
  'resolved',
  'closed',
] as const;

type CaseRow = {
  id: string;
  account_id: string;
  assigned_to_id: string | null;
  status: string;
  created_at: string;
  notes?: string | null;
};

export default function CasesPage() {
  const { user, hasPermission } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<string>('in_progress');
  const [assignUserId, setAssignUserId] = useState('');

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
  };

  const { data, total, isLoading, mutate } = useApiList<CaseRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<CaseRow>(API, selectedId ?? undefined);

  const { trigger: createCase, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: patchCase, isMutating: patching } = useApiMutation(
    'PATCH',
    API
  );
  const { trigger: deleteCase, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );
  const { trigger: bulkStatusUpdate, isMutating: bulkMutating } =
    useApiMutation('POST', API);
  const { trigger: assignCollector, isMutating: assignMutating } =
    useApiMutation('POST', API);

  const [form, setForm] = useState({
    account_id: '',
    description: '',
    status: 'new' as (typeof CASE_STATUSES)[number],
  });

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.id.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q) ||
      (row.notes ?? '').toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<CaseRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          aria-label="Select all on page"
          checked={
            rows.length > 0 && rows.every((r) => selectedIds.has(r.id))
          }
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedIds(new Set(rows.map((r) => r.id)));
            } else {
              setSelectedIds(new Set());
            }
          }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.has(row.original.id)}
          onChange={(e) => {
            const next = new Set(selectedIds);
            if (e.target.checked) next.add(row.original.id);
            else next.delete(row.original.id);
            setSelectedIds(next);
          }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
    {
      accessorKey: 'id',
      header: 'Case #',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    {
      accessorKey: 'account_id',
      header: 'Account',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    {
      accessorKey: 'assigned_to_id',
      header: 'Assigned To',
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return v ? (
          <span className="font-mono text-xs">{v.slice(0, 8)}…</span>
        ) : (
          '—'
        );
      },
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ getValue }) => fmtDate(String(getValue())),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({ account_id: '', description: '', status: 'new' });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_id: detail.account_id,
      description: detail.notes ?? '',
      status: detail.status as (typeof CASE_STATUSES)[number],
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (!editMode) {
      await createCase({
        account_id: form.account_id,
        notes: form.description || null,
        status: form.status,
      });
    } else if (selectedId) {
      await patchCase(
        {
          notes: form.description || null,
          status: form.status,
        },
        `/${selectedId}`
      );
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmDelete() {
    if (!selectedId) return;
    await deleteCase(undefined, `/${selectedId}`);
    setDeleteOpen(false);
    setSelectedId(null);
    await mutate();
  }

  async function runBulkStatus() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    await bulkStatusUpdate(
      { case_ids: ids, status: bulkStatus },
      '/bulk-status'
    );
    setBulkOpen(false);
    setSelectedIds(new Set());
    await mutate();
  }

  async function runAssign() {
    if (!selectedId || !assignUserId.trim()) return;
    await assignCollector(
      { assigned_to_id: assignUserId.trim() },
      `/${selectedId}/assign`
    );
    setAssignOpen(false);
    setAssignUserId('');
    await mutateDetail();
    await mutate();
  }

  const d = detail;
  const canManage =
    Boolean(user?.isOwner) || hasPermission('cases:manage');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cases"
        subtitle={
          user
            ? `Collection case workflow · ${user.email}`
            : 'Collection case workflow'
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!canManage}
              onClick={() => setBulkOpen(true)}
              className="inline-flex h-10 items-center rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-40"
            >
              Bulk status update
            </button>
            <button
              type="button"
              disabled={!canManage}
              onClick={openCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
            >
              <Plus className="h-4 w-4" />
              New case
            </button>
          </div>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Filter current page…"
      />

      <DataTable<CaseRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No cases found"
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
          title={`Case ${d?.id?.slice(0, 8) ?? ''}…`}
          subtitle={d ? `Account ${d.account_id}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Case ID">{d.id}</FieldGroup>
                <FieldGroup label="Account ID">{d.account_id}</FieldGroup>
                <FieldGroup label="Assigned to">
                  {d.assigned_to_id ?? '—'}
                </FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={d.status} />
                </FieldGroup>
                <FieldGroup label="Created">{fmtDate(d.created_at)}</FieldGroup>
                <FieldGroup label="Notes">{d.notes ?? '—'}</FieldGroup>
              </FieldGrid>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  disabled={!canManage}
                  onClick={() => setAssignOpen(true)}
                  className="rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
                >
                  Assign collector
                </button>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit case' : 'New case'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Account ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={form.account_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, account_id: e.target.value }))
              }
              disabled={editMode}
            />
          </FormField>
          <FormField label="Description">
            <textarea
              className="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Status" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.status}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  status: e.target.value as (typeof CASE_STATUSES)[number],
                }))
              }
            >
              {CASE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      </FormDrawer>

      <FormDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign collector"
        onSubmit={runAssign}
        isSubmitting={assignMutating}
        submitLabel="Assign"
      >
        <FormField label="User ID (collector)" required>
          <input
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
            value={assignUserId}
            onChange={(e) => setAssignUserId(e.target.value)}
            placeholder="UUID"
          />
        </FormField>
      </FormDrawer>

      <FormDrawer
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title="Bulk status update"
        onSubmit={runBulkStatus}
        isSubmitting={bulkMutating}
        submitLabel="Update selected"
      >
        <p className="mb-3 text-sm text-neutral-600 dark:text-neutral-400">
          {selectedIds.size} case(s) selected.
        </p>
        <FormField label="New status" required>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={bulkStatus}
            onChange={(e) => setBulkStatus(e.target.value)}
          >
            {CASE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </FormField>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete case?"
        message="This permanently deletes the case record."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
