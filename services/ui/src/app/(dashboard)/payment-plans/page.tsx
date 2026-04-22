'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import Link from 'next/link';
import { CreditCard, Plus, Eye, Trash2, Play, Calendar, FileText } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/payment-plans';

type PlanRow = { id: string; account_id: string; plan_type: string; status: string; total_amount: number; payment_amount: number; frequency: string; total_payments: number; payments_made: number; balance_remaining: number; start_date: string; next_payment_date: string | null; is_settlement: boolean; created_at: string };

const fmtMoney = (v: number) => `$${(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString() : '—';

const STATUS_MAP: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  completed: 'bg-blue-100 text-blue-700',
  defaulted: 'bg-red-100 text-red-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
  suspended: 'bg-orange-100 text-orange-700',
};

export default function PaymentPlansPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ account_id: '', plan_type: 'standard', total_amount: '', payment_amount: '', frequency: 'monthly', total_payments: '', start_date: '', is_settlement: false, settlement_amount: '' });

  const { data, total, isLoading, mutate } = useApiList<PlanRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { data: detail } = useApiDetail<PlanRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: remove } = useApiMutation('DELETE', API);
  const { trigger: activate } = useApiMutation('POST', API);

  const columns: ColumnDef<PlanRow>[] = [
    { accessorKey: 'account_id', header: 'Account', cell: ({ row }) => <span className="font-mono text-xs">{row.original.account_id.slice(0, 8)}...</span> },
    { accessorKey: 'plan_type', header: 'Type', cell: ({ row }) => <span className="capitalize">{row.original.plan_type}</span> },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} colorMap={STATUS_MAP} /> },
    { accessorKey: 'total_amount', header: 'Total', cell: ({ row }) => fmtMoney(row.original.total_amount) },
    { accessorKey: 'payment_amount', header: 'Payment', cell: ({ row }) => fmtMoney(row.original.payment_amount) },
    { accessorKey: 'frequency', header: 'Frequency', cell: ({ row }) => <span className="capitalize">{row.original.frequency.replace('_', ' ')}</span> },
    { accessorKey: 'payments_made', header: 'Progress', cell: ({ row }) => `${row.original.payments_made}/${row.original.total_payments}` },
    { accessorKey: 'balance_remaining', header: 'Remaining', cell: ({ row }) => fmtMoney(row.original.balance_remaining) },
    { accessorKey: 'next_payment_date', header: 'Next Due', cell: ({ row }) => fmtDate(row.original.next_payment_date) },
    {
      id: 'actions', header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <button onClick={() => setSelectedId(row.original.id)} className="p-1 hover:bg-gray-100 rounded"><Eye className="h-4 w-4" /></button>
          {row.original.status === 'draft' && (
            <button onClick={async () => { await activate(undefined, `/${row.original.id}/activate`); mutate(); }} className="p-1 hover:bg-green-100 rounded text-green-600" title="Activate"><Play className="h-4 w-4" /></button>
          )}
          <button onClick={() => { setSelectedId(row.original.id); setDeleteOpen(true); }} className="p-1 hover:bg-red-100 rounded text-red-600"><Trash2 className="h-4 w-4" /></button>
        </div>
      ),
    },
  ];

  const handleCreate = async () => {
    await create({ ...form, total_amount: parseFloat(form.total_amount), payment_amount: parseFloat(form.payment_amount), total_payments: parseInt(form.total_payments), settlement_amount: form.settlement_amount ? parseFloat(form.settlement_amount) : null });
    setDrawerOpen(false);
    setForm({ account_id: '', plan_type: 'standard', total_amount: '', payment_amount: '', frequency: 'monthly', total_payments: '', start_date: '', is_settlement: false, settlement_amount: '' });
    mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Payment Plans" subtitle="Manage payment arrangements, settlements, and amortization schedules">
        <div className="flex items-center gap-3">
          <Link href="/payment-plans/report" className="flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted"><FileText className="h-4 w-4" /> Agreement Report</Link>
          <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New Plan</button>
        </div>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title="Payment Plan" onClose={() => setSelectedId(null)}>
          <FieldGroup label="Plan Details">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Type</span><p className="text-sm capitalize">{detail.plan_type}</p></div>
              <div><span className="text-xs text-gray-500">Status</span><p className="text-sm"><StatusBadge status={detail.status} colorMap={STATUS_MAP} /></p></div>
              <div><span className="text-xs text-gray-500">Total Amount</span><p className="text-sm">{fmtMoney(detail.total_amount)}</p></div>
              <div><span className="text-xs text-gray-500">Payment Amount</span><p className="text-sm">{fmtMoney(detail.payment_amount)}</p></div>
              <div><span className="text-xs text-gray-500">Frequency</span><p className="text-sm capitalize">{detail.frequency.replace('_', ' ')}</p></div>
              <div><span className="text-xs text-gray-500">Progress</span><p className="text-sm">{detail.payments_made}/{detail.total_payments} payments</p></div>
              <div><span className="text-xs text-gray-500">Balance</span><p className="text-sm">{fmtMoney(detail.balance_remaining)}</p></div>
              <div><span className="text-xs text-gray-500">Start Date</span><p className="text-sm">{fmtDate(detail.start_date)}</p></div>
              <div><span className="text-xs text-gray-500">Next Payment</span><p className="text-sm">{fmtDate(detail.next_payment_date)}</p></div>
              {detail.is_settlement && <div><span className="text-xs text-gray-500">Settlement</span><p className="text-sm font-semibold text-green-600">Yes</p></div>}
            </FieldGrid>
          </FieldGroup>
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Payment Plan" onSubmit={handleCreate}>
        <FormField label="Account ID"><input value={form.account_id} onChange={e => setForm({ ...form, account_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
        <FormField label="Plan Type"><select value={form.plan_type} onChange={e => setForm({ ...form, plan_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="standard">Standard</option><option value="settlement">Settlement</option><option value="hardship">Hardship</option><option value="stipulated">Stipulated</option></select></FormField>
        <FormField label="Total Amount ($)"><input type="number" step="0.01" value={form.total_amount} onChange={e => setForm({ ...form, total_amount: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Payment Amount ($)"><input type="number" step="0.01" value={form.payment_amount} onChange={e => setForm({ ...form, payment_amount: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Frequency"><select value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="weekly">Weekly</option><option value="biweekly">Biweekly</option><option value="monthly">Monthly</option><option value="semi_monthly">Semi-monthly</option><option value="quarterly">Quarterly</option><option value="lump_sum">Lump Sum</option></select></FormField>
        <FormField label="Total Payments"><input type="number" value={form.total_payments} onChange={e => setForm({ ...form, total_payments: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Start Date"><input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Settlement"><label className="flex items-center gap-2"><input type="checkbox" checked={form.is_settlement} onChange={e => setForm({ ...form, is_settlement: e.target.checked })} /> This is a settlement</label></FormField>
        {form.is_settlement && <FormField label="Settlement Amount ($)"><input type="number" step="0.01" value={form.settlement_amount} onChange={e => setForm({ ...form, settlement_amount: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>}
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete Plan" message="Are you sure you want to delete this payment plan?" />
    </div>
  );
}
