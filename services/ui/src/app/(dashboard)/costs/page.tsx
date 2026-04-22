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
import { cn, formatCurrency, formatDate } from '@/lib/utils';

const API = '/api/v1/costs';
const TRUST_API = '/api/v1/trust/accounts';

type CostTab = 'entries' | 'disbursements' | 'billings';

type CostEntryRow = {
  id: string;
  account_id: string;
  cost_type: string;
  description: string | null;
  amount: number;
  status: string;
  incurred_date: string;
  trust_account_id: string | null;
};

type CostDisbRow = {
  id: string;
  cost_entry_id: string;
  amount: number;
  method: string;
  reference_number: string | null;
  disbursed_at: string;
  payee: string;
};

type BillingRow = {
  id: string;
  client_name: string;
  billing_period_start: string | null;
  billing_period_end: string | null;
  total_amount: number;
  status: string;
  created_at: string;
};

type TrustAccountMini = { id: string; name: string };

const COST_TYPES: { value: string; label: string }[] = [
  { value: 'court_filing', label: 'Court filing' },
  { value: 'service_of_process', label: 'Service of process' },
  { value: 'recording', label: 'Recording' },
  { value: 'skip_trace', label: 'Skip trace' },
  { value: 'credit_report', label: 'Credit report' },
  { value: 'garnishment', label: 'Garnishment' },
  { value: 'postage', label: 'Postage' },
  { value: 'document_prep', label: 'Document prep' },
  { value: 'travel', label: 'Travel' },
  { value: 'other', label: 'Other' },
];

const DISB_METHODS: { value: string; label: string }[] = [
  { value: 'check', label: 'Check' },
  { value: 'ach', label: 'ACH' },
  { value: 'wire', label: 'Wire' },
  { value: 'internal_transfer', label: 'Internal transfer' },
];

function tabButtonClass(active: boolean) {
  return cn(
    'rounded-md px-4 py-2 text-sm font-medium transition-colors',
    active
      ? 'bg-primary-100 text-primary-800 dark:bg-primary-900/40 dark:text-primary-300'
      : 'text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800'
  );
}

export default function CostsPage() {
  const [tab, setTab] = useState<CostTab>('entries');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: trustAccounts } = useApiList<TrustAccountMini>(TRUST_API, {
    page: 1,
    page_size: 200,
  });

  const { data: entries, total: entTotal, isLoading: entLoading, mutate: mutEnt } =
    useApiList<CostEntryRow>(`${API}/entries`, listParams);
  const { data: disbs, total: disbTotal, isLoading: disbLoading, mutate: mutDisb } =
    useApiList<CostDisbRow>(`${API}/disbursements`, listParams);
  const { data: billings, total: billTotal, isLoading: billLoading, mutate: mutBill } =
    useApiList<BillingRow>(`${API}/billings`, listParams);

  const trustMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const t of trustAccounts ?? []) m[t.id] = t.name;
    return m;
  }, [trustAccounts]);

  const entryMap = useMemo(() => {
    const m: Record<string, CostEntryRow> = {};
    for (const e of entries ?? []) m[e.id] = e;
    return m;
  }, [entries]);

  const { data: entryDetail, isLoading: entryDetailLoading, mutate: mutEntryDetail } =
    useApiDetail<CostEntryRow>(`${API}/entries`, tab === 'entries' && selectedId ? selectedId : undefined);
  const { data: disbDetail, isLoading: disbDetailLoading, mutate: mutDisbDetail } =
    useApiDetail<CostDisbRow>(`${API}/disbursements`, tab === 'disbursements' && selectedId ? selectedId : undefined);
  const { data: billDetail, isLoading: billDetailLoading, mutate: mutBillDetail } =
    useApiDetail<BillingRow>(`${API}/billings`, tab === 'billings' && selectedId ? selectedId : undefined);

  const { trigger: createEntry, isMutating: creatingEntry } = useApiMutation('POST', `${API}/entries`);
  const { trigger: patchEntry, isMutating: patchingEntry } = useApiMutation('PATCH', `${API}/entries`);
  const { trigger: createDisb, isMutating: creatingDisb } = useApiMutation('POST', `${API}/disbursements`);
  const { trigger: patchDisb, isMutating: patchingDisb } = useApiMutation('PATCH', `${API}/disbursements`);
  const { trigger: createBill, isMutating: creatingBill } = useApiMutation('POST', `${API}/billings`);
  const { trigger: patchBill, isMutating: patchingBill } = useApiMutation('PATCH', `${API}/billings`);

  const [entryForm, setEntryForm] = useState({
    account_id: '',
    cost_type: 'court_filing',
    description: '',
    amount_dollars: '',
    trust_account_id: '',
  });

  const [disbForm, setDisbForm] = useState({
    cost_entry_id: '',
    amount_dollars: '',
    reference: '',
    method: 'check',
    payee: '',
    disbursed_at: '',
  });

  const [billForm, setBillForm] = useState({
    client_name: '',
    billing_period_start: '',
    billing_period_end: '',
    total_dollars: '',
  });

  const filteredEntries = (entries ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.description?.toLowerCase().includes(q) ||
      row.cost_type.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q)
    );
  });

  const filteredDisbs = (disbs ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    const ent = entryMap[row.cost_entry_id];
    return (
      row.payee.toLowerCase().includes(q) ||
      row.reference_number?.toLowerCase().includes(q) ||
      ent?.account_id.toLowerCase().includes(q)
    );
  });

  const filteredBills = (billings ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return row.client_name.toLowerCase().includes(q) || row.status.toLowerCase().includes(q);
  });

  const dataLoading =
    tab === 'entries' ? entLoading : tab === 'disbursements' ? disbLoading : billLoading;
  const total = tab === 'entries' ? entTotal : tab === 'disbursements' ? disbTotal : billTotal;
  const filtered =
    tab === 'entries' ? filteredEntries : tab === 'disbursements' ? filteredDisbs : filteredBills;

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const entryColumns: ColumnDef<CostEntryRow>[] = [
    {
      id: 'account',
      header: 'Account',
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.account_id}</span>
      ),
    },
    {
      accessorKey: 'cost_type',
      header: 'Type',
      cell: ({ getValue }) => <StatusBadge status={String(getValue()).replace(/_/g, ' ')} />,
    },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ getValue }) => {
        const v = getValue() as string | null;
        return v ? <span className="line-clamp-2 max-w-xs">{v}</span> : '—';
      },
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ getValue }) => formatCurrency(Number(getValue())),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'incurred_date',
      header: 'Date',
      cell: ({ getValue }) => formatDate(String(getValue())),
    },
  ];

  const disbColumns: ColumnDef<CostDisbRow>[] = [
    {
      id: 'entry',
      header: 'Cost entry',
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.cost_entry_id}</span>
      ),
    },
    {
      id: 'trust',
      header: 'Trust account',
      cell: ({ row }) => {
        const tid = entryMap[row.original.cost_entry_id]?.trust_account_id;
        return tid ? trustMap[tid] ?? tid : '—';
      },
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ getValue }) => formatCurrency(Number(getValue())),
    },
    {
      accessorKey: 'method',
      header: 'Method',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'disbursed_at',
      header: 'Date',
      cell: ({ getValue }) => formatDate(String(getValue())),
    },
  ];

  const billColumns: ColumnDef<BillingRow>[] = [
    { accessorKey: 'client_name', header: 'Client' },
    {
      id: 'period',
      header: 'Period',
      cell: ({ row }) => {
        const a = row.original.billing_period_start;
        const b = row.original.billing_period_end;
        if (!a && !b) return '—';
        return `${a ? formatDate(a) : '—'} – ${b ? formatDate(b) : '—'}`;
      },
    },
    {
      accessorKey: 'total_amount',
      header: 'Total amount',
      cell: ({ getValue }) => formatCurrency(Number(getValue())),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'created_at',
      header: 'Generated date',
      cell: ({ getValue }) => formatDate(String(getValue())),
    },
  ];

  function switchTab(next: CostTab) {
    setTab(next);
    setSelectedId(null);
    setPageIndex(0);
  }

  function openCreate() {
    setEditMode(false);
    if (tab === 'entries') {
      setEntryForm({
        account_id: '',
        cost_type: 'court_filing',
        description: '',
        amount_dollars: '',
        trust_account_id: '',
      });
    } else if (tab === 'disbursements') {
      setDisbForm({
        cost_entry_id: '',
        amount_dollars: '',
        reference: '',
        method: 'check',
        payee: '',
        disbursed_at: new Date().toISOString().slice(0, 16),
      });
    } else {
      setBillForm({
        client_name: '',
        billing_period_start: '',
        billing_period_end: '',
        total_dollars: '',
      });
    }
    setDrawerOpen(true);
  }

  function openEdit() {
    setEditMode(true);
    if (tab === 'entries' && entryDetail) {
      setEntryForm({
        account_id: entryDetail.account_id,
        cost_type: entryDetail.cost_type,
        description: entryDetail.description ?? '',
        amount_dollars: String(entryDetail.amount / 100),
        trust_account_id: entryDetail.trust_account_id ?? '',
      });
      setDrawerOpen(true);
    } else if (tab === 'disbursements' && disbDetail) {
      setDisbForm({
        cost_entry_id: disbDetail.cost_entry_id,
        amount_dollars: String(disbDetail.amount / 100),
        reference: disbDetail.reference_number ?? '',
        method: disbDetail.method,
        payee: disbDetail.payee,
        disbursed_at: disbDetail.disbursed_at.slice(0, 16),
      });
      setDrawerOpen(true);
    } else if (tab === 'billings' && billDetail) {
      setBillForm({
        client_name: billDetail.client_name,
        billing_period_start: billDetail.billing_period_start?.slice(0, 10) ?? '',
        billing_period_end: billDetail.billing_period_end?.slice(0, 10) ?? '',
        total_dollars: String(billDetail.total_amount / 100),
      });
      setDrawerOpen(true);
    }
  }

  async function submitDrawer() {
    if (tab === 'entries') {
      const cents = Math.round(parseFloat(entryForm.amount_dollars || '0') * 100);
      if (!editMode) {
        await createEntry({
          account_id: entryForm.account_id,
          cost_type: entryForm.cost_type,
          description: entryForm.description || null,
          amount: cents,
          incurred_date: new Date().toISOString(),
          trust_account_id: entryForm.trust_account_id || null,
        });
      } else if (selectedId) {
        await patchEntry(
          {
            cost_type: entryForm.cost_type,
            description: entryForm.description || null,
            amount: cents,
            trust_account_id: entryForm.trust_account_id || null,
          },
          `/${selectedId}`
        );
        await mutEntryDetail();
      }
      await mutEnt();
    } else if (tab === 'disbursements') {
      const cents = Math.round(parseFloat(disbForm.amount_dollars || '0') * 100);
      if (!editMode) {
        await createDisb({
          cost_entry_id: disbForm.cost_entry_id,
          amount: cents,
          method: disbForm.method,
          reference_number: disbForm.reference || null,
          payee: disbForm.payee,
          disbursed_at: new Date(disbForm.disbursed_at).toISOString(),
        });
      } else if (selectedId) {
        await patchDisb(
          {
            amount: cents,
            method: disbForm.method,
            reference_number: disbForm.reference || null,
            payee: disbForm.payee,
            disbursed_at: new Date(disbForm.disbursed_at).toISOString(),
          },
          `/${selectedId}`
        );
        await mutDisbDetail();
      }
      await mutDisb();
    } else {
      const cents = Math.round(parseFloat(billForm.total_dollars || '0') * 100);
      if (!editMode) {
        await createBill({
          client_name: billForm.client_name,
          billing_period_start: billForm.billing_period_start
            ? new Date(billForm.billing_period_start).toISOString()
            : null,
          billing_period_end: billForm.billing_period_end
            ? new Date(billForm.billing_period_end).toISOString()
            : null,
          total_amount: cents,
        });
      } else if (selectedId) {
        await patchBill(
          {
            client_name: billForm.client_name,
            billing_period_start: billForm.billing_period_start
              ? new Date(billForm.billing_period_start).toISOString()
              : null,
            billing_period_end: billForm.billing_period_end
              ? new Date(billForm.billing_period_end).toISOString()
              : null,
            total_amount: cents,
          },
          `/${selectedId}`
        );
        await mutBillDetail();
      }
      await mutBill();
    }
    setDrawerOpen(false);
  }

  const columns =
    tab === 'entries' ? entryColumns : tab === 'disbursements' ? disbColumns : billColumns;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Costs & billing"
        subtitle="Cost entries, disbursements, and client billings"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New{' '}
            {tab === 'entries' ? 'cost entry' : tab === 'disbursements' ? 'disbursement' : 'billing'}
          </button>
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button type="button" className={tabButtonClass(tab === 'entries')} onClick={() => switchTab('entries')}>
          Cost entries
        </button>
        <button
          type="button"
          className={tabButtonClass(tab === 'disbursements')}
          onClick={() => switchTab('disbursements')}
        >
          Disbursements
        </button>
        <button type="button" className={tabButtonClass(tab === 'billings')} onClick={() => switchTab('billings')}>
          Client billings
        </button>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder={
          tab === 'entries'
            ? 'Search cost entries…'
            : tab === 'disbursements'
              ? 'Search disbursements…'
              : 'Search billings…'
        }
      />

      <DataTable
        columns={columns as ColumnDef<(typeof filtered)[0]>[]}
        data={filtered}
        isLoading={dataLoading}
        emptyMessage="No rows found"
        onRowClick={(row) => setSelectedId((row as { id: string }).id)}
        pageCount={pageCount}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPageChange={setPageIndex}
        onPageSizeChange={(s) => {
          setPageSize(s);
          setPageIndex(0);
        }}
      />

      {selectedId && tab === 'entries' && (
        <DetailPanel
          title="Cost entry"
          subtitle={entryDetail?.description ?? undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {entryDetailLoading || !entryDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Account">
                <span className="font-mono text-xs">{entryDetail.account_id}</span>
              </FieldGroup>
              <FieldGroup label="Type">
                <StatusBadge status={entryDetail.cost_type.replace(/_/g, ' ')} />
              </FieldGroup>
              <FieldGroup label="Amount">{formatCurrency(entryDetail.amount)}</FieldGroup>
              <FieldGroup label="Status">
                <StatusBadge status={entryDetail.status} />
              </FieldGroup>
              <FieldGroup label="Trust account">
                {entryDetail.trust_account_id
                  ? trustMap[entryDetail.trust_account_id] ?? entryDetail.trust_account_id
                  : '—'}
              </FieldGroup>
              <FieldGroup label="Incurred">{formatDate(entryDetail.incurred_date)}</FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {selectedId && tab === 'disbursements' && (
        <DetailPanel
          title="Disbursement"
          subtitle={disbDetail?.payee}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {disbDetailLoading || !disbDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Cost entry">
                <span className="font-mono text-xs">{disbDetail.cost_entry_id}</span>
              </FieldGroup>
              <FieldGroup label="Trust account">
                {(() => {
                  const tid = entryMap[disbDetail.cost_entry_id]?.trust_account_id;
                  return tid ? trustMap[tid] ?? tid : '—';
                })()}
              </FieldGroup>
              <FieldGroup label="Amount">{formatCurrency(disbDetail.amount)}</FieldGroup>
              <FieldGroup label="Method">
                <StatusBadge status={disbDetail.method} />
              </FieldGroup>
              <FieldGroup label="Reference">{disbDetail.reference_number ?? '—'}</FieldGroup>
              <FieldGroup label="Date">{formatDate(disbDetail.disbursed_at)}</FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {selectedId && tab === 'billings' && (
        <DetailPanel
          title={billDetail?.client_name ?? 'Billing'}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {billDetailLoading || !billDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Total">{formatCurrency(billDetail.total_amount)}</FieldGroup>
              <FieldGroup label="Status">
                <StatusBadge status={billDetail.status} />
              </FieldGroup>
              <FieldGroup label="Period start">
                {billDetail.billing_period_start ? formatDate(billDetail.billing_period_start) : '—'}
              </FieldGroup>
              <FieldGroup label="Period end">
                {billDetail.billing_period_end ? formatDate(billDetail.billing_period_end) : '—'}
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={
          editMode
            ? tab === 'entries'
              ? 'Edit cost entry'
              : tab === 'disbursements'
                ? 'Edit disbursement'
                : 'Edit billing'
            : tab === 'entries'
              ? 'New cost entry'
              : tab === 'disbursements'
                ? 'New disbursement'
                : 'New billing'
        }
        onSubmit={submitDrawer}
        isSubmitting={
          tab === 'entries'
            ? creatingEntry || patchingEntry
            : tab === 'disbursements'
              ? creatingDisb || patchingDisb
              : creatingBill || patchingBill
        }
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        {tab === 'entries' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Account ID" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
                value={entryForm.account_id}
                onChange={(e) => setEntryForm((f) => ({ ...f, account_id: e.target.value }))}
                disabled={editMode}
              />
            </FormField>
            <FormField label="Cost type" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={entryForm.cost_type}
                onChange={(e) => setEntryForm((f) => ({ ...f, cost_type: e.target.value }))}
              >
                {COST_TYPES.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Description">
              <textarea
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                rows={2}
                value={entryForm.description}
                onChange={(e) => setEntryForm((f) => ({ ...f, description: e.target.value }))}
              />
            </FormField>
            <FormField label="Amount (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={entryForm.amount_dollars}
                onChange={(e) => setEntryForm((f) => ({ ...f, amount_dollars: e.target.value }))}
              />
            </FormField>
            <FormField label="Trust account (optional)">
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={entryForm.trust_account_id}
                onChange={(e) => setEntryForm((f) => ({ ...f, trust_account_id: e.target.value }))}
              >
                <option value="">None</option>
                {(trustAccounts ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </FormField>
          </div>
        ) : tab === 'disbursements' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Cost entry ID" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
                value={disbForm.cost_entry_id}
                onChange={(e) => setDisbForm((f) => ({ ...f, cost_entry_id: e.target.value }))}
                disabled={editMode}
              />
            </FormField>
            <p className="text-xs text-neutral-500">
              Link a trust account by setting it on the cost entry; disbursements validate against that trust balance.
            </p>
            <FormField label="Amount (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disbForm.amount_dollars}
                onChange={(e) => setDisbForm((f) => ({ ...f, amount_dollars: e.target.value }))}
              />
            </FormField>
            <FormField label="Method" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disbForm.method}
                onChange={(e) => setDisbForm((f) => ({ ...f, method: e.target.value }))}
              >
                {DISB_METHODS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Reference">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disbForm.reference}
                onChange={(e) => setDisbForm((f) => ({ ...f, reference: e.target.value }))}
              />
            </FormField>
            <FormField label="Payee" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disbForm.payee}
                onChange={(e) => setDisbForm((f) => ({ ...f, payee: e.target.value }))}
              />
            </FormField>
            <FormField label="Disbursed at" required>
              <input
                type="datetime-local"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disbForm.disbursed_at}
                onChange={(e) => setDisbForm((f) => ({ ...f, disbursed_at: e.target.value }))}
              />
            </FormField>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <FormField label="Client name" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={billForm.client_name}
                onChange={(e) => setBillForm((f) => ({ ...f, client_name: e.target.value }))}
              />
            </FormField>
            <FormField label="Billing period start">
              <input
                type="date"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={billForm.billing_period_start}
                onChange={(e) => setBillForm((f) => ({ ...f, billing_period_start: e.target.value }))}
              />
            </FormField>
            <FormField label="Billing period end">
              <input
                type="date"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={billForm.billing_period_end}
                onChange={(e) => setBillForm((f) => ({ ...f, billing_period_end: e.target.value }))}
              />
            </FormField>
            <FormField label="Total amount (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={billForm.total_dollars}
                onChange={(e) => setBillForm((f) => ({ ...f, total_dollars: e.target.value }))}
              />
            </FormField>
          </div>
        )}
      </FormDrawer>
    </div>
  );
}
