'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ColumnDef } from '@tanstack/react-table';
import { Plus, Download } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
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
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/accounts';

const fmtMoney = (v: number | string | null) =>
  v != null
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
      }).format(Number(v) / 100)
    : '—';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

type AccountRow = {
  id: string;
  account_reference: string;
  consumer_id: string;
  original_creditor: string;
  total_balance: number;
  status: string;
  jurisdiction: string;
  date_placed: string;
  legal_hold?: boolean;
};

type AccountDetail = AccountRow & {
  original_principal: number;
  current_principal: number;
  current_interest: number;
  current_fees: number;
  legal_hold: boolean;
  legal_hold_reason?: string | null;
  debt_type?: string;
};

const JURISDICTIONS = ['NJ', 'NY', 'PA', 'DE'] as const;

type TabKey = 'open' | 'closed';

export default function AccountsPage() {
  const router = useRouter();
  const { user, hasPermission } = useAuthStore();
  const [tab, setTab] = useState<TabKey>('open');
  const [search, setSearch] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [legalReason, setLegalReason] = useState('');

  const listParams: Record<string, unknown> = {
    page: pageIndex + 1,
    page_size: pageSize,
    status_group: tab,
  };
  if (searchSubmitted.trim()) {
    listParams.search = searchSubmitted.trim();
  }

  const { data, total, isLoading, mutate } = useApiList<AccountRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<AccountDetail>(API, selectedId ?? undefined);

  const { trigger: createAccount, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    AccountDetail
  >('POST', API);
  const { trigger: patchAccount, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    AccountDetail
  >('PATCH', API);
  const { trigger: deleteAccount, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );
  const { trigger: postLegalHold, isMutating: holding } = useApiMutation(
    'POST',
    API
  );
  const { trigger: deleteLegalHold, isMutating: releasing } = useApiMutation(
    'DELETE',
    API
  );

  const [form, setForm] = useState({
    account_reference: '',
    consumer_id: '',
    original_creditor: '',
    original_balance: '',
    jurisdiction: 'NJ',
    date_placed: '',
    current_creditor: '',
    current_principal: '',
    current_interest: '',
    current_fees: '',
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const switchTab = useCallback((t: TabKey) => {
    setTab(t);
    setPageIndex(0);
    setSelectedId(null);
  }, []);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setSearchSubmitted(search);
      setPageIndex(0);
    },
    [search]
  );

  const clearSearch = useCallback(() => {
    setSearch('');
    setSearchSubmitted('');
    setPageIndex(0);
  }, []);

  const [exporting, setExporting] = useState(false);

  const exportCsv = useCallback(async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams({ status_group: tab });
      if (searchSubmitted.trim()) params.set('search', searchSubmitted.trim());

      const token = typeof window !== 'undefined'
        ? JSON.parse(localStorage.getItem('dcs-auth') || '{}')?.state?.accessToken
        : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiBase}/api/v1/accounts/export/csv?${params}`, { headers });
      if (!res.ok) throw new Error('Export failed');

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `accounts-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  }, [tab, searchSubmitted]);

  const columns: ColumnDef<AccountRow>[] = [
    { accessorKey: 'account_reference', header: 'Reference' },
    {
      accessorKey: 'consumer_id',
      header: 'Consumer',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    { accessorKey: 'original_creditor', header: 'Creditor' },
    {
      accessorKey: 'total_balance',
      header: 'Balance',
      cell: ({ getValue }) => (
        <span className="font-medium tabular-nums">{fmtMoney(getValue() as number)}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    { accessorKey: 'jurisdiction', header: 'Jur.' },
    {
      accessorKey: 'date_placed',
      header: 'Date Placed',
      cell: ({ getValue }) => fmtDate(String(getValue())),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      account_reference: '',
      consumer_id: '',
      original_creditor: '',
      original_balance: '',
      jurisdiction: 'NJ',
      date_placed: '',
      current_creditor: '',
      current_principal: '',
      current_interest: '',
      current_fees: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_reference: detail.account_reference,
      consumer_id: detail.consumer_id,
      original_creditor: detail.original_creditor,
      original_balance: String(detail.original_principal / 100),
      jurisdiction: detail.jurisdiction,
      date_placed: detail.date_placed?.slice(0, 10) ?? '',
      current_creditor: detail.original_creditor,
      current_principal: String(detail.current_principal / 100),
      current_interest: String(detail.current_interest / 100),
      current_fees: String(detail.current_fees / 100),
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const cents = Math.round(parseFloat(form.original_balance || '0') * 100);
    if (!editMode) {
      await createAccount({
        consumer_id: form.consumer_id,
        account_reference: form.account_reference,
        original_creditor: form.original_creditor,
        jurisdiction: form.jurisdiction,
        original_principal: cents,
        current_principal: cents,
        current_interest: 0,
        current_fees: 0,
        date_placed: new Date(form.date_placed).toISOString(),
      });
    } else if (selectedId) {
      await patchAccount(
        {
          current_creditor: form.current_creditor || undefined,
          current_principal: Math.round(
            parseFloat(form.current_principal || '0') * 100
          ),
          current_interest: Math.round(
            parseFloat(form.current_interest || '0') * 100
          ),
          current_fees: Math.round(parseFloat(form.current_fees || '0') * 100),
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
      await deleteAccount(undefined, `/${selectedId}`);
      setDeleteOpen(false);
      setSelectedId(null);
      await mutate();
    } catch {
      /* surface via network layer */
    }
  }

  async function toggleLegalHold() {
    if (!selectedId || !detail) return;
    if (!detail.legal_hold) {
      const reason = legalReason.trim() || 'Manual hold';
      await postLegalHold(undefined, `/${selectedId}/legal-hold?reason=${encodeURIComponent(reason)}`);
    } else {
      await deleteLegalHold(undefined, `/${selectedId}/legal-hold`);
    }
    setLegalReason('');
    await mutateDetail();
    await mutate();
  }

  const d = detail;
  const tabs: { key: TabKey; label: string }[] = [
    { key: 'open', label: 'Open Accounts' },
    { key: 'closed', label: 'Closed Accounts' },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        subtitle={
          user
            ? `Manage debt accounts · ${user.email}`
            : 'Manage debt accounts and balances'
        }
        actions={
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={exportCsv}
              disabled={exporting}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium shadow-sm hover:bg-muted disabled:opacity-40"
            >
              <Download className="h-4 w-4" />
              {exporting ? 'Exporting…' : 'Export CSV'}
            </button>
            <button
              type="button"
              onClick={openCreate}
              disabled={
                !user?.isOwner && !hasPermission('accounts:edit_contact')
              }
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700 disabled:opacity-40"
            >
              <Plus className="h-4 w-4" />
              New account
            </button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex items-center gap-6 border-b border-neutral-200 dark:border-neutral-700">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => switchTab(t.key)}
            className={cn(
              'relative pb-3 text-sm font-medium transition-colors',
              tab === t.key
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300'
            )}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-primary-600 dark:bg-primary-400" />
            )}
          </button>
        ))}

        {/* Inline search for this page */}
        <form onSubmit={handleSearch} className="ml-auto flex items-center gap-2 pb-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search accounts…"
            className="h-9 w-64 rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="submit"
            className="h-9 rounded-md bg-primary-600 px-3 text-sm font-medium text-white hover:bg-primary-700"
          >
            Search
          </button>
          {searchSubmitted && (
            <button
              type="button"
              onClick={clearSearch}
              className="h-9 rounded-md border border-border px-3 text-sm font-medium text-neutral-600 hover:bg-muted dark:text-neutral-300"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {searchSubmitted && (
        <p className="text-sm text-neutral-500">
          Showing results for <span className="font-medium text-foreground">&ldquo;{searchSubmitted}&rdquo;</span>
          {' '}in {tab} accounts · {total.toLocaleString()} found
        </p>
      )}

      <DataTable<AccountRow>
        columns={columns}
        data={data ?? []}
        isLoading={isLoading}
        emptyMessage={
          searchSubmitted
            ? `No ${tab} accounts match "${searchSubmitted}"`
            : `No ${tab} accounts found`
        }
        onRowClick={(row) => router.push(`/accounts/${row.id}`)}
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
          title={d?.account_reference ?? 'Account'}
          subtitle={d ? `Consumer ${d.consumer_id}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Reference">
                  {d.account_reference}
                </FieldGroup>
                <FieldGroup label="Consumer ID">
                  <span className="font-mono text-xs">{d.consumer_id}</span>
                </FieldGroup>
                <FieldGroup label="Original creditor">
                  {d.original_creditor}
                </FieldGroup>
                <FieldGroup label="Jurisdiction">{d.jurisdiction}</FieldGroup>
                <FieldGroup label="Balance">{fmtMoney(d.total_balance)}</FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={d.status} />
                </FieldGroup>
                <FieldGroup label="Original principal">{fmtMoney(d.original_principal)}</FieldGroup>
                <FieldGroup label="Current principal">{fmtMoney(d.current_principal)}</FieldGroup>
                <FieldGroup label="Interest">{fmtMoney(d.current_interest)}</FieldGroup>
                <FieldGroup label="Fees/Costs">{fmtMoney(d.current_fees)}</FieldGroup>
                <FieldGroup label="Date placed">{fmtDate(d.date_placed)}</FieldGroup>
                <FieldGroup label="Legal hold">
                  {d.legal_hold ? 'Yes' : 'No'}
                  {d.legal_hold_reason ? ` — ${d.legal_hold_reason}` : ''}
                </FieldGroup>
              </FieldGrid>

              <div className="mt-6 flex flex-wrap items-end gap-3 border-t border-border pt-4">
                {!d.legal_hold ? (
                  <>
                    <div className="min-w-[200px] flex-1">
                      <label className="text-xs font-medium uppercase text-neutral-500">
                        Reason (apply hold)
                      </label>
                      <input
                        className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={legalReason}
                        onChange={(e) => setLegalReason(e.target.value)}
                        placeholder="Reason for legal hold"
                      />
                    </div>
                    <button
                      type="button"
                      disabled={holding}
                      onClick={toggleLegalHold}
                      className={cn(
                        'rounded-md bg-warning-600 px-4 py-2 text-sm font-medium text-white hover:bg-warning-700 disabled:opacity-50'
                      )}
                    >
                      {holding ? 'Applying…' : 'Apply legal hold'}
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    disabled={releasing}
                    onClick={toggleLegalHold}
                    className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
                  >
                    {releasing ? 'Releasing…' : 'Release legal hold'}
                  </button>
                )}
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit account' : 'New account'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save changes' : 'Create'}
      >
        {!editMode ? (
          <div className="flex flex-col gap-4">
            <FormField label="Account reference" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.account_reference}
                onChange={(e) =>
                  setForm((f) => ({ ...f, account_reference: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Consumer ID" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                value={form.consumer_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, consumer_id: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Original creditor" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.original_creditor}
                onChange={(e) =>
                  setForm((f) => ({ ...f, original_creditor: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Original balance (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.original_balance}
                onChange={(e) =>
                  setForm((f) => ({ ...f, original_balance: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Jurisdiction" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.jurisdiction}
                onChange={(e) =>
                  setForm((f) => ({ ...f, jurisdiction: e.target.value }))
                }
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j} value={j}>
                    {j}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Date placed" required>
              <input
                type="date"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.date_placed}
                onChange={(e) =>
                  setForm((f) => ({ ...f, date_placed: e.target.value }))
                }
              />
            </FormField>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <FormField label="Current creditor">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.current_creditor}
                onChange={(e) =>
                  setForm((f) => ({ ...f, current_creditor: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Current principal (USD)">
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.current_principal}
                onChange={(e) =>
                  setForm((f) => ({ ...f, current_principal: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Current interest (USD)">
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.current_interest}
                onChange={(e) =>
                  setForm((f) => ({ ...f, current_interest: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Current fees (USD)">
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.current_fees}
                onChange={(e) =>
                  setForm((f) => ({ ...f, current_fees: e.target.value }))
                }
              />
            </FormField>
          </div>
        )}
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete account?"
        message="This may fail if the API does not support account deletion."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
