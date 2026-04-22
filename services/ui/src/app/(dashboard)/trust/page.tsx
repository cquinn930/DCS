'use client';

import { useMemo, useState } from 'react';
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
import { cn } from '@/lib/utils';

const API = '/api/v1/trust';

const fmtMoney = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const fmtDateTime = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type TrustTab = 'accounts' | 'transactions' | 'reconciliations';

type TrustAccountRow = {
  id: string;
  name: string;
  account_number_last4: string;
  bank_name: string;
  account_type: string;
  current_balance: number;
  status: string;
};

type TrustTxRow = {
  id: string;
  trust_account_id: string;
  transaction_type: string;
  amount: number;
  reference_number: string | null;
  transaction_date: string;
  is_reconciled: boolean;
};

type ReconRow = {
  id: string;
  trust_account_id: string;
  period_end: string;
  period_start: string;
  status: string;
};

type ReconItemRow = {
  id: string;
  match_status: string;
  statement_amount: number | null;
  statement_date: string | null;
};

const ACCOUNT_TYPES: { value: string; label: string }[] = [
  { value: 'pooled_trust', label: 'Pooled trust' },
  { value: 'segregated_trust', label: 'Segregated trust' },
  { value: 'operating', label: 'Operating' },
  { value: 'collections_only', label: 'Collections only' },
];

const TX_TYPES: { value: string; label: string }[] = [
  { value: 'deposit', label: 'Deposit' },
  { value: 'disbursement', label: 'Disbursement' },
  { value: 'wire_in', label: 'Wire in' },
  { value: 'wire_out', label: 'Wire out' },
  { value: 'cost_transfer', label: 'Cost transfer' },
  { value: 'fee_transfer', label: 'Fee transfer' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'reversal', label: 'Reversal' },
  { value: 'check', label: 'Check' },
];

function tabButtonClass(active: boolean) {
  return cn(
    'rounded-md px-4 py-2 text-sm font-medium transition-colors',
    active
      ? 'bg-primary-100 text-primary-800 dark:bg-primary-900/40 dark:text-primary-300'
      : 'text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800'
  );
}

function ReconMatchedCount({ reconciliationId }: { reconciliationId: string }) {
  const { data, isLoading } = useApiList<ReconItemRow>(
    `${API}/reconciliations/${reconciliationId}/items`,
    { page: 1, page_size: 500 }
  );
  const n = useMemo(
    () =>
      (data ?? []).filter((i) => i.match_status?.toLowerCase() === 'matched').length,
    [data]
  );
  if (isLoading) return <span className="text-neutral-400">…</span>;
  return <span>{n}</span>;
}

function ReconUnmatchedCount({ reconciliationId }: { reconciliationId: string }) {
  const { data, isLoading } = useApiList<ReconItemRow>(
    `${API}/reconciliations/${reconciliationId}/items`,
    { page: 1, page_size: 500 }
  );
  const n = useMemo(
    () =>
      (data ?? []).filter((i) => i.match_status?.toLowerCase() === 'unmatched').length,
    [data]
  );
  if (isLoading) return <span className="text-neutral-400">…</span>;
  return <span>{n}</span>;
}

export default function TrustPage() {
  const [tab, setTab] = useState<TrustTab>('accounts');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: accounts, total: acctTotal, isLoading: acctLoading, mutate: mutAcct } =
    useApiList<TrustAccountRow>(`${API}/accounts`, listParams);
  const { data: txs, total: txTotal, isLoading: txLoading, mutate: mutTx } =
    useApiList<TrustTxRow>(`${API}/transactions`, listParams);
  const { data: recons, total: reconTotal, isLoading: reconLoading, mutate: mutRecon } =
    useApiList<ReconRow>(`${API}/reconciliations`, listParams);

  const accountMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const a of accounts ?? []) m[a.id] = a.name;
    return m;
  }, [accounts]);

  const { data: acctDetail, isLoading: acctDetailLoading, mutate: mutAcctDetail } =
    useApiDetail<TrustAccountRow & { routing_number_last4?: string | null; config?: Record<string, unknown> }>(
      `${API}/accounts`,
      tab === 'accounts' && selectedId ? selectedId : undefined
    );
  const { data: txDetail, isLoading: txDetailLoading, mutate: mutTxDetail } =
    useApiDetail<TrustTxRow & { memo?: string | null; running_balance?: number }>(
      `${API}/transactions`,
      tab === 'transactions' && selectedId ? selectedId : undefined
    );
  const { data: reconDetail, isLoading: reconDetailLoading, mutate: mutReconDetail } =
    useApiDetail<ReconRow & { statement_balance: number; book_balance: number }>(
      `${API}/reconciliations`,
      tab === 'reconciliations' && selectedId ? selectedId : undefined
    );

  const { data: reconItems, isLoading: itemsLoading, mutate: mutItems } = useApiList<ReconItemRow>(
    tab === 'reconciliations' && selectedId
      ? `${API}/reconciliations/${selectedId}/items`
      : null,
    { page: 1, page_size: 500 }
  );

  const { trigger: createAcct, isMutating: creatingAcct } = useApiMutation('POST', `${API}/accounts`);
  const { trigger: patchAcct, isMutating: patchingAcct } = useApiMutation('PATCH', `${API}/accounts`);
  const { trigger: createTx, isMutating: creatingTx } = useApiMutation('POST', `${API}/transactions`);
  const { trigger: patchTx, isMutating: patchingTx } = useApiMutation('PATCH', `${API}/transactions`);
  const { trigger: createRecon, isMutating: creatingRecon } = useApiMutation('POST', `${API}/reconciliations`);
  const { trigger: patchRecon, isMutating: patchingRecon } = useApiMutation('PATCH', `${API}/reconciliations`);
  const { trigger: importStatement, isMutating: importing } = useApiMutation(
    'POST',
    `${API}/reconciliations`
  );
  const { trigger: autoMatch, isMutating: matching } = useApiMutation('POST', `${API}/reconciliations`);

  const [acctForm, setAcctForm] = useState({
    name: '',
    account_number_last4: '',
    bank_name: '',
    account_type: 'pooled_trust',
    description: '',
  });

  const [txForm, setTxForm] = useState({
    trust_account_id: '',
    transaction_type: 'deposit',
    amount_dollars: '',
    reference_number: '',
    memo: '',
    transaction_date: '',
  });

  const [reconForm, setReconForm] = useState({
    trust_account_id: '',
    statement_date: '',
    statement_balance_dollars: '',
  });

  const [importJson, setImportJson] = useState('[]');

  const filteredAccounts = (accounts ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.name.toLowerCase().includes(q) ||
      row.bank_name.toLowerCase().includes(q) ||
      row.account_number_last4.includes(q)
    );
  });

  const filteredTxs = (txs ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (row.reference_number?.toLowerCase().includes(q) ?? false) ||
      accountMap[row.trust_account_id]?.toLowerCase().includes(q) ||
      row.transaction_type.toLowerCase().includes(q)
    );
  });

  const filteredRecons = (recons ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      accountMap[row.trust_account_id]?.toLowerCase().includes(q) ||
      row.status.toLowerCase().includes(q)
    );
  });

  const dataLoading =
    tab === 'accounts' ? acctLoading : tab === 'transactions' ? txLoading : reconLoading;
  const total =
    tab === 'accounts' ? acctTotal : tab === 'transactions' ? txTotal : reconTotal;
  const filtered =
    tab === 'accounts' ? filteredAccounts : tab === 'transactions' ? filteredTxs : filteredRecons;

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const acctColumns: ColumnDef<TrustAccountRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'account_number_last4',
      header: 'Account number',
      cell: ({ getValue }) => (
        <span className="font-mono">••••{String(getValue())}</span>
      ),
    },
    { accessorKey: 'bank_name', header: 'Bank' },
    {
      accessorKey: 'account_type',
      header: 'Type',
      cell: ({ getValue }) => <StatusBadge status={String(getValue()).replace(/_/g, ' ')} />,
    },
    {
      accessorKey: 'current_balance',
      header: 'Balance',
      cell: ({ getValue }) => fmtMoney(Number(getValue())),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
  ];

  const txColumns: ColumnDef<TrustTxRow>[] = [
    {
      accessorKey: 'reference_number',
      header: 'Reference',
      cell: ({ getValue }) => getValue() ?? '—',
    },
    {
      id: 'trust_name',
      header: 'Trust account',
      cell: ({ row }) => accountMap[row.original.trust_account_id] ?? row.original.trust_account_id,
    },
    {
      accessorKey: 'transaction_type',
      header: 'Type',
      cell: ({ getValue }) => <StatusBadge status={String(getValue()).replace(/_/g, ' ')} />,
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ getValue }) => fmtMoney(Number(getValue())),
    },
    {
      accessorKey: 'transaction_date',
      header: 'Date',
      cell: ({ getValue }) => fmtDateTime(String(getValue())),
    },
    {
      accessorKey: 'is_reconciled',
      header: 'Status',
      cell: ({ getValue }) =>
        getValue() ? <StatusBadge status="matched" /> : <StatusBadge status="pending" />,
    },
  ];

  const reconColumns: ColumnDef<ReconRow>[] = [
    {
      id: 'trust',
      header: 'Trust account',
      cell: ({ row }) => accountMap[row.original.trust_account_id] ?? row.original.trust_account_id,
    },
    {
      accessorKey: 'period_end',
      header: 'Statement date',
      cell: ({ row }) => fmtDate(row.original.period_end),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      id: 'matched',
      header: 'Matched count',
      cell: ({ row }) => <ReconMatchedCount reconciliationId={row.original.id} />,
    },
    {
      id: 'unmatched',
      header: 'Unmatched count',
      cell: ({ row }) => <ReconUnmatchedCount reconciliationId={row.original.id} />,
    },
  ];

  function switchTab(next: TrustTab) {
    setTab(next);
    setSelectedId(null);
    setPageIndex(0);
  }

  function openCreate() {
    setEditMode(false);
    if (tab === 'accounts') {
      setAcctForm({
        name: '',
        account_number_last4: '',
        bank_name: '',
        account_type: 'pooled_trust',
        description: '',
      });
    } else if (tab === 'transactions') {
      setTxForm({
        trust_account_id: '',
        transaction_type: 'deposit',
        amount_dollars: '',
        reference_number: '',
        memo: '',
        transaction_date: new Date().toISOString().slice(0, 16),
      });
    } else {
      setReconForm({
        trust_account_id: '',
        statement_date: new Date().toISOString().slice(0, 10),
        statement_balance_dollars: '',
      });
    }
    setDrawerOpen(true);
  }

  function openEdit() {
    setEditMode(true);
    if (tab === 'accounts' && acctDetail) {
      setAcctForm({
        name: acctDetail.name,
        account_number_last4: acctDetail.account_number_last4,
        bank_name: acctDetail.bank_name,
        account_type: acctDetail.account_type,
        description: String((acctDetail.config as { description?: string })?.description ?? ''),
      });
      setDrawerOpen(true);
    } else if (tab === 'transactions' && txDetail) {
      setTxForm({
        trust_account_id: txDetail.trust_account_id,
        transaction_type: txDetail.transaction_type,
        amount_dollars: String(Math.abs(txDetail.amount) / 100),
        reference_number: txDetail.reference_number ?? '',
        memo: (txDetail as { memo?: string }).memo ?? '',
        transaction_date: txDetail.transaction_date.slice(0, 16),
      });
      setDrawerOpen(true);
    } else if (tab === 'reconciliations' && reconDetail) {
      setReconForm({
        trust_account_id: reconDetail.trust_account_id,
        statement_date: reconDetail.period_end.slice(0, 10),
        statement_balance_dollars: String(reconDetail.statement_balance / 100),
      });
      setDrawerOpen(true);
    }
  }

  async function submitDrawer() {
    if (tab === 'accounts') {
      const last4 = acctForm.account_number_last4.replace(/\D/g, '').slice(-4);
      if (last4.length !== 4) throw new Error('Account number must include 4 digits');
      const config = acctForm.description
        ? { ...((acctDetail?.config as object) ?? {}), description: acctForm.description }
        : acctDetail?.config;
      if (!editMode) {
        await createAcct({
          name: acctForm.name,
          bank_name: acctForm.bank_name,
          account_type: acctForm.account_type,
          account_number_last4: last4,
          current_balance: 0,
          config: config ?? {},
        });
      } else if (selectedId) {
        await patchAcct(
          {
            name: acctForm.name,
            bank_name: acctForm.bank_name,
            account_type: acctForm.account_type,
            account_number_last4: last4,
            config,
          },
          `/${selectedId}`
        );
        await mutAcctDetail();
      }
      await mutAcct();
    } else if (tab === 'transactions') {
      const amtCents = Math.round(parseFloat(txForm.amount_dollars || '0') * 100);
      const inflow = ['deposit', 'wire_in'].includes(txForm.transaction_type);
      const signed = inflow ? Math.abs(amtCents) : -Math.abs(amtCents);
      const ta = accounts?.find((a) => a.id === txForm.trust_account_id);
      const current = ta?.current_balance ?? 0;
      const running = current + signed;
      if (!editMode) {
        await createTx({
          trust_account_id: txForm.trust_account_id,
          transaction_type: txForm.transaction_type,
          amount: signed,
          running_balance: running,
          reference_number: txForm.reference_number || null,
          memo: txForm.memo || null,
          transaction_date: new Date(txForm.transaction_date).toISOString(),
          is_reconciled: false,
        });
      } else if (selectedId) {
        await patchTx(
          {
            transaction_type: txForm.transaction_type,
            amount: signed,
            reference_number: txForm.reference_number || null,
            memo: txForm.memo || null,
            transaction_date: new Date(txForm.transaction_date).toISOString(),
          },
          `/${selectedId}`
        );
        await mutTxDetail();
      }
      await mutTx();
    } else {
      const stmtCents = Math.round(parseFloat(reconForm.statement_balance_dollars || '0') * 100);
      const d = reconForm.statement_date;
      const ta = accounts?.find((a) => a.id === reconForm.trust_account_id);
      const book = ta?.current_balance ?? 0;
      if (!editMode) {
        await createRecon({
          trust_account_id: reconForm.trust_account_id,
          period_start: d,
          period_end: d,
          statement_balance: stmtCents,
          book_balance: book,
          difference: stmtCents - book,
        });
      } else if (selectedId) {
        await patchRecon(
          {
            period_start: d,
            period_end: d,
            statement_balance: stmtCents,
            book_balance: book,
            difference: stmtCents - book,
          },
          `/${selectedId}`
        );
        await mutReconDetail();
      }
      await mutRecon();
    }
    setDrawerOpen(false);
  }

  async function handleImport() {
    if (!selectedId) return;
    let lines: unknown[];
    try {
      lines = JSON.parse(importJson);
    } catch {
      return;
    }
    await importStatement({ lines }, `/${selectedId}/import-bank-statement`);
    await mutReconDetail();
    await mutItems();
    await mutRecon();
  }

  async function handleAutoMatch() {
    if (!selectedId) return;
    await autoMatch(undefined, `/${selectedId}/auto-match`);
    await mutItems();
    await mutReconDetail();
    await mutRecon();
  }

  const columns =
    tab === 'accounts' ? acctColumns : tab === 'transactions' ? txColumns : reconColumns;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Trust"
        subtitle="Trust accounts, transactions, and bank reconciliation"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New {tab === 'accounts' ? 'account' : tab === 'transactions' ? 'transaction' : 'reconciliation'}
          </button>
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button type="button" className={tabButtonClass(tab === 'accounts')} onClick={() => switchTab('accounts')}>
          Trust accounts
        </button>
        <button type="button" className={tabButtonClass(tab === 'transactions')} onClick={() => switchTab('transactions')}>
          Transactions
        </button>
        <button type="button" className={tabButtonClass(tab === 'reconciliations')} onClick={() => switchTab('reconciliations')}>
          Reconciliation
        </button>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder={
          tab === 'accounts'
            ? 'Search accounts…'
            : tab === 'transactions'
              ? 'Search transactions…'
              : 'Search reconciliations…'
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

      {selectedId && tab === 'accounts' && (
        <DetailPanel
          title={acctDetail?.name ?? 'Trust account'}
          subtitle={acctDetail ? `••••${acctDetail.account_number_last4}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {acctDetailLoading || !acctDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Bank">{acctDetail.bank_name}</FieldGroup>
              <FieldGroup label="Type">
                <StatusBadge status={acctDetail.account_type.replace(/_/g, ' ')} />
              </FieldGroup>
              <FieldGroup label="Balance">{fmtMoney(acctDetail.current_balance)}</FieldGroup>
              <FieldGroup label="Status">
                <StatusBadge status={acctDetail.status} />
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {selectedId && tab === 'transactions' && (
        <DetailPanel
          title={txDetail?.reference_number ?? 'Transaction'}
          subtitle={txDetail ? accountMap[txDetail.trust_account_id] : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {txDetailLoading || !txDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Type">
                <StatusBadge status={txDetail.transaction_type.replace(/_/g, ' ')} />
              </FieldGroup>
              <FieldGroup label="Amount">{fmtMoney(txDetail.amount)}</FieldGroup>
              <FieldGroup label="Date">{fmtDateTime(txDetail.transaction_date)}</FieldGroup>
              <FieldGroup label="Memo">{(txDetail as { memo?: string | null }).memo ?? '—'}</FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {selectedId && tab === 'reconciliations' && (
        <DetailPanel
          title="Reconciliation"
          subtitle={reconDetail ? fmtDate(reconDetail.period_end) : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {reconDetailLoading || !reconDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Trust account">
                  {accountMap[reconDetail.trust_account_id] ?? reconDetail.trust_account_id}
                </FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={reconDetail.status} />
                </FieldGroup>
                <FieldGroup label="Statement balance">{fmtMoney(reconDetail.statement_balance)}</FieldGroup>
                <FieldGroup label="Book balance">{fmtMoney(reconDetail.book_balance)}</FieldGroup>
              </FieldGrid>

              <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  disabled={matching}
                  onClick={handleAutoMatch}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {matching ? 'Matching…' : 'Auto match'}
                </button>
              </div>

              <div className="mt-6">
                <h3 className="text-sm font-semibold text-foreground">Import bank statement</h3>
                <p className="mt-1 text-xs text-neutral-500">
                  POST body: array of line objects (JSON). Example: statement_amount, statement_date, reference.
                </p>
                <textarea
                  className="mt-2 w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                  value={importJson}
                  onChange={(e) => setImportJson(e.target.value)}
                />
                <button
                  type="button"
                  disabled={importing}
                  onClick={handleImport}
                  className="mt-2 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
                >
                  {importing ? 'Importing…' : 'Import bank statement'}
                </button>
              </div>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">Items</h3>
                {itemsLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading items…</p>
                ) : (
                  <div className="mt-2 overflow-x-auto rounded-md border border-border">
                    <table className="w-full min-w-[480px] text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Match
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Amount
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-neutral-500">
                            Date
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(reconItems ?? []).map((it) => (
                          <tr key={it.id} className="border-t border-border">
                            <td className="px-3 py-2">
                              <StatusBadge status={it.match_status} />
                            </td>
                            <td className="px-3 py-2 font-mono">
                              {it.statement_amount != null ? fmtMoney(it.statement_amount) : '—'}
                            </td>
                            <td className="px-3 py-2">{it.statement_date ? fmtDate(it.statement_date) : '—'}</td>
                          </tr>
                        ))}
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
        title={
          editMode
            ? tab === 'accounts'
              ? 'Edit trust account'
              : tab === 'transactions'
                ? 'Edit transaction'
                : 'Edit reconciliation'
            : tab === 'accounts'
              ? 'New trust account'
              : tab === 'transactions'
                ? 'New transaction'
                : 'New reconciliation'
        }
        onSubmit={submitDrawer}
        isSubmitting={
          tab === 'accounts'
            ? creatingAcct || patchingAcct
            : tab === 'transactions'
              ? creatingTx || patchingTx
              : creatingRecon || patchingRecon
        }
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        {tab === 'accounts' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Name" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={acctForm.name}
                onChange={(e) => setAcctForm((f) => ({ ...f, name: e.target.value }))}
              />
            </FormField>
            <FormField label="Account number (last 4 digits)" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                value={acctForm.account_number_last4}
                onChange={(e) => setAcctForm((f) => ({ ...f, account_number_last4: e.target.value }))}
                maxLength={4}
              />
            </FormField>
            <FormField label="Bank name" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={acctForm.bank_name}
                onChange={(e) => setAcctForm((f) => ({ ...f, bank_name: e.target.value }))}
              />
            </FormField>
            <FormField label="Account type" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={acctForm.account_type}
                onChange={(e) => setAcctForm((f) => ({ ...f, account_type: e.target.value }))}
              >
                {ACCOUNT_TYPES.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Description (stored in config)">
              <textarea
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                rows={3}
                value={acctForm.description}
                onChange={(e) => setAcctForm((f) => ({ ...f, description: e.target.value }))}
              />
            </FormField>
          </div>
        ) : tab === 'transactions' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Trust account" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={txForm.trust_account_id}
                onChange={(e) => setTxForm((f) => ({ ...f, trust_account_id: e.target.value }))}
              >
                <option value="">Select…</option>
                {(accounts ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Transaction type" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={txForm.transaction_type}
                onChange={(e) => setTxForm((f) => ({ ...f, transaction_type: e.target.value }))}
              >
                {TX_TYPES.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Amount (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={txForm.amount_dollars}
                onChange={(e) => setTxForm((f) => ({ ...f, amount_dollars: e.target.value }))}
              />
            </FormField>
            <FormField label="Reference number">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={txForm.reference_number}
                onChange={(e) => setTxForm((f) => ({ ...f, reference_number: e.target.value }))}
              />
            </FormField>
            <FormField label="Description (memo)">
              <textarea
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                rows={2}
                value={txForm.memo}
                onChange={(e) => setTxForm((f) => ({ ...f, memo: e.target.value }))}
              />
            </FormField>
            <FormField label="Transaction date" required>
              <input
                type="datetime-local"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={txForm.transaction_date}
                onChange={(e) => setTxForm((f) => ({ ...f, transaction_date: e.target.value }))}
              />
            </FormField>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <FormField label="Trust account" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={reconForm.trust_account_id}
                onChange={(e) => setReconForm((f) => ({ ...f, trust_account_id: e.target.value }))}
              >
                <option value="">Select…</option>
                {(accounts ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Statement date" required>
              <input
                type="date"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={reconForm.statement_date}
                onChange={(e) => setReconForm((f) => ({ ...f, statement_date: e.target.value }))}
              />
            </FormField>
            <FormField label="Statement balance (USD)" required>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={reconForm.statement_balance_dollars}
                onChange={(e) =>
                  setReconForm((f) => ({ ...f, statement_balance_dollars: e.target.value }))
                }
              />
            </FormField>
          </div>
        )}
      </FormDrawer>
    </div>
  );
}
