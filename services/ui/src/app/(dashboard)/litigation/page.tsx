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

const API = '/api/v1/litigation';

const fmtMoney = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const LIT_STATUS = [
  'pending_filing',
  'filed',
  'served',
  'answer_received',
  'discovery',
  'trial_scheduled',
  'judgment_entered',
  'post_judgment',
  'satisfied',
  'dismissed',
  'appealed',
] as const;

type LitRow = {
  id: string;
  account_id: string;
  court_id: string;
  court_name: string;
  docket_number: string | null;
  status: string;
  principal_claimed: number;
  filed_date: string | null;
  trial_date: string | null;
};

export default function LitigationPage() {
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

  const { data, total, isLoading, mutate } = useApiList<LitRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<LitRow>(API, selectedId ?? undefined);

  const { trigger: createLit, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: patchLit, isMutating: patching } = useApiMutation(
    'PATCH',
    API
  );
  const { trigger: deleteLit, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );

  const [form, setForm] = useState({
    account_id: '',
    court_name: '',
    court_id: '',
    docket_number: '',
    case_type: 'special_civil',
    amount: '',
    status: 'pending_filing' as (typeof LIT_STATUS)[number],
  });

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (row.docket_number ?? '').toLowerCase().includes(q) ||
      row.court_name.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<LitRow>[] = [
    {
      accessorKey: 'docket_number',
      header: 'Docket',
      cell: ({ getValue, row }) =>
        (getValue() as string | null) ?? row.original.id.slice(0, 8),
    },
    {
      accessorKey: 'account_id',
      header: 'Account',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    { accessorKey: 'court_name', header: 'Court' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'principal_claimed',
      header: 'Amount',
      cell: ({ getValue }) => fmtMoney(Number(getValue())),
    },
    {
      accessorKey: 'filed_date',
      header: 'Filed',
      cell: ({ getValue }) => fmtDate((getValue() as string) ?? undefined),
    },
    {
      accessorKey: 'trial_date',
      header: 'Next Hearing',
      cell: ({ getValue }) => fmtDate((getValue() as string) ?? undefined),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      account_id: '',
      court_name: '',
      court_id: '',
      docket_number: '',
      case_type: 'special_civil',
      amount: '',
      status: 'pending_filing',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_id: detail.account_id,
      court_name: detail.court_name,
      court_id: detail.court_id,
      docket_number: detail.docket_number ?? '',
      case_type: 'special_civil',
      amount: String(detail.principal_claimed / 100),
      status: detail.status as (typeof LIT_STATUS)[number],
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const cents = Math.round(parseFloat(form.amount || '0') * 100);
    if (!editMode) {
      await createLit({
        account_id: form.account_id,
        court_id: form.court_id,
        court_name: form.court_name,
        court_type: form.case_type,
        docket_number: form.docket_number || null,
        status: form.status,
        principal_claimed: cents,
      });
    } else if (selectedId) {
      await patchLit(
        {
          court_id: form.court_id,
          court_name: form.court_name,
          docket_number: form.docket_number || null,
          principal_claimed: cents,
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
    await deleteLit(undefined, `/${selectedId}`);
    setDeleteOpen(false);
    setSelectedId(null);
    await mutate();
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Litigation"
        subtitle={
          user
            ? `Court cases and filings · ${user.email}`
            : 'Court cases and filings'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New litigation case
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search docket or court…"
      />

      <DataTable<LitRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No litigation cases found"
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
          title={d?.docket_number ?? `Case ${d?.id?.slice(0, 8)}`}
          subtitle={d?.court_name}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Account ID">{d.account_id}</FieldGroup>
              <FieldGroup label="Court">{d.court_name}</FieldGroup>
              <FieldGroup label="Status">
                <StatusBadge status={d.status} />
              </FieldGroup>
              <FieldGroup label="Amount claimed">
                {fmtMoney(d.principal_claimed)}
              </FieldGroup>
              <FieldGroup label="Filed">{fmtDate(d.filed_date ?? undefined)}</FieldGroup>
              <FieldGroup label="Next hearing">
                {fmtDate(d.trial_date ?? undefined)}
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit litigation case' : 'New litigation case'}
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
          <FormField label="Court name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.court_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, court_name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Court ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.court_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, court_id: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Docket number">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.docket_number}
              onChange={(e) =>
                setForm((f) => ({ ...f, docket_number: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Case type (court type)" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.case_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, case_type: e.target.value }))
              }
              disabled={editMode}
            >
              <option value="special_civil">special civil</option>
              <option value="superior">superior</option>
            </select>
          </FormField>
          <FormField label="Amount claimed (USD)" required>
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.amount}
              onChange={(e) =>
                setForm((f) => ({ ...f, amount: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Status">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.status}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  status: e.target.value as (typeof LIT_STATUS)[number],
                }))
              }
            >
              {LIT_STATUS.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete litigation case?"
        message="This removes the litigation record."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
