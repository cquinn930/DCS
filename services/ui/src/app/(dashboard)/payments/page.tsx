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

const API = '/api/v1/payments';

const fmtMoney = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const METHODS = [
  'card',
  'ach',
  'echeck',
  'wire',
  'check',
  'cash',
  'other',
] as const;

type PaymentRow = {
  id: string;
  account_id: string;
  amount: number;
  method: string;
  status: string;
  received_at: string;
  processor_reference?: string | null;
};

export default function PaymentsPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [reverseOpen, setReverseOpen] = useState(false);

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
  };

  const { data, total, isLoading, mutate } = useApiList<PaymentRow>(
    API,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<PaymentRow>(API, selectedId ?? undefined);

  const { trigger: createPayment, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: reversePayment, isMutating: reversing } = useApiMutation(
    'POST',
    API
  );

  const [form, setForm] = useState({
    account_id: '',
    amount: '',
    payment_method: 'ach' as (typeof METHODS)[number],
    processor_reference: '',
  });

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.id.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q) ||
      row.status.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<PaymentRow>[] = [
    {
      accessorKey: 'id',
      header: 'Reference',
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
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ getValue }) => fmtMoney(Number(getValue())),
    },
    { accessorKey: 'method', header: 'Method' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'received_at',
      header: 'Date',
      cell: ({ getValue }) => fmtDate(String(getValue())),
    },
  ];

  function openCreate() {
    setForm({
      account_id: '',
      amount: '',
      payment_method: 'ach',
      processor_reference: '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const cents = Math.round(parseFloat(form.amount || '0') * 100);
    await createPayment({
      account_id: form.account_id,
      amount: cents,
      method: form.payment_method,
      source: 'portal',
      processor_token: form.processor_reference || undefined,
    });
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmReverse() {
    if (!selectedId) return;
    await reversePayment(undefined, `/${selectedId}/reverse`);
    setReverseOpen(false);
    await mutateDetail();
    await mutate();
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payments"
        subtitle={
          user
            ? `Payment history and reversals · ${user.email}`
            : 'Payment history and reversals'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            Record payment
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search payments…"
      />

      <DataTable<PaymentRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No payments found"
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
          title={`Payment ${d?.id?.slice(0, 8) ?? ''}…`}
          subtitle={d ? fmtDate(d.received_at) : undefined}
          onClose={() => setSelectedId(null)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Account ID">{d.account_id}</FieldGroup>
                <FieldGroup label="Amount">{fmtMoney(d.amount)}</FieldGroup>
                <FieldGroup label="Method">{d.method}</FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={d.status} />
                </FieldGroup>
                <FieldGroup label="Processor ref">
                  {d.processor_reference ?? '—'}
                </FieldGroup>
                <FieldGroup label="Received">{fmtDate(d.received_at)}</FieldGroup>
              </FieldGrid>
              {d.status !== 'reversed' ? (
                <div className="mt-4 border-t border-border pt-4">
                  <button
                    type="button"
                    onClick={() => setReverseOpen(true)}
                    className="rounded-md border border-error-500/40 bg-error-50 px-3 py-2 text-sm font-medium text-error-800 hover:bg-error-100 dark:bg-error-500/10 dark:text-error-400"
                  >
                    Reverse payment
                  </button>
                </div>
              ) : null}
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Record payment"
        onSubmit={handleSubmit}
        isSubmitting={creating}
        submitLabel="Submit"
      >
        <div className="flex flex-col gap-4">
          <FormField label="Account ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={form.account_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, account_id: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Amount (USD)" required>
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
          <FormField label="Payment method" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.payment_method}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  payment_method: e.target.value as (typeof METHODS)[number],
                }))
              }
            >
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Processor reference">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.processor_reference}
              onChange={(e) =>
                setForm((f) => ({ ...f, processor_reference: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={reverseOpen}
        onClose={() => setReverseOpen(false)}
        onConfirm={confirmReverse}
        title="Reverse this payment?"
        message="This reverses allocations and restores balances. Continue?"
        confirmLabel={reversing ? 'Reversing…' : 'Reverse'}
        variant="danger"
      />
    </div>
  );
}
