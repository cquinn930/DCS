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

const API = '/api/v1/disputes';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const REASONS = [
  'not_my_debt',
  'wrong_amount',
  'already_paid',
  'statute_expired',
  'identity_theft',
  'other',
] as const;

type DisputeRow = {
  id: string;
  account_id: string;
  reason: string;
  status: string;
  filed_at: string;
  response_due_date: string;
};

export default function DisputesPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
  };

  const { data, total, isLoading, mutate } = useApiList<DisputeRow>(
    API,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<DisputeRow & { description?: string | null }>(
      API,
      selectedId ?? undefined
    );

  const { trigger: createDispute, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: patchDispute, isMutating: patching } = useApiMutation(
    'PATCH',
    API
  );
  const { trigger: deleteDispute, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );

  const [form, setForm] = useState({
    account_id: '',
    dispute_type: 'other' as (typeof REASONS)[number],
    description: '',
  });

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  function isOverdue(due: string) {
    const t = new Date(due);
    t.setHours(0, 0, 0, 0);
    return t < today;
  }

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.id.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q) ||
      row.reason.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<DisputeRow>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
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
    { accessorKey: 'reason', header: 'Type' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'filed_at',
      header: 'Filed Date',
      cell: ({ getValue }) => fmtDate(String(getValue())),
    },
    {
      id: 'deadline',
      header: 'Response Deadline',
      cell: ({ row }) => {
        const due = row.original.response_due_date;
        const overdue = isOverdue(due);
        return (
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={
                overdue
                  ? 'font-medium text-error-600 dark:text-error-400'
                  : undefined
              }
            >
              {fmtDate(due)}
            </span>
            {overdue ? (
              <StatusBadge
                status="overdue"
                colorMap={{
                  overdue:
                    'bg-error-100 text-error-800 dark:bg-error-500/20 dark:text-error-300',
                }}
              />
            ) : null}
          </div>
        );
      },
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({ account_id: '', dispute_type: 'other', description: '' });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_id: detail.account_id,
      dispute_type: detail.reason as (typeof REASONS)[number],
      description: detail.description ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (!editMode) {
      await createDispute({
        account_id: form.account_id,
        reason: form.dispute_type,
        description: form.description || null,
      });
    } else if (selectedId) {
      await patchDispute(
        {
          resolution_notes: form.description || undefined,
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
    try {
      await deleteDispute(undefined, `/${selectedId}`);
      setDeleteOpen(false);
      setSelectedId(null);
      await mutate();
    } catch {
      /* may not exist */
    }
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Disputes"
        subtitle={
          user
            ? `Regulation F dispute tracking · ${user.email}`
            : 'Regulation F dispute tracking'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New dispute
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search disputes…"
      />

      <DataTable<DisputeRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No disputes found"
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
          title={`Dispute ${d?.id?.slice(0, 8) ?? ''}…`}
          subtitle={d ? `Account ${d.account_id}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Reason">{d.reason}</FieldGroup>
              <FieldGroup label="Status">
                <StatusBadge status={d.status} />
              </FieldGroup>
              <FieldGroup label="Filed">{fmtDate(d.filed_at)}</FieldGroup>
              <FieldGroup label="Response due">
                <span
                  className={
                    isOverdue(d.response_due_date)
                      ? 'text-error-600 dark:text-error-400'
                      : undefined
                  }
                >
                  {fmtDate(d.response_due_date)}
                </span>
              </FieldGroup>
              <FieldGroup label="Description">
                {(d as { description?: string }).description ?? '—'}
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit dispute' : 'New dispute'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save notes' : 'Create'}
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
          <FormField label="Dispute type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.dispute_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  dispute_type: e.target.value as (typeof REASONS)[number],
                }))
              }
              disabled={editMode}
            >
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Description">
            <textarea
              className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete dispute?"
        message="Deletion may not be supported by the API."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
