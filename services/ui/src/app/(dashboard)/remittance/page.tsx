'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { FileText, Plus, CheckCircle, Send, Eye } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiMutation } from '@/hooks/useApi';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/remittance';

type StatementRow = {
  id: string;
  statement_number: string;
  client_id: string;
  period_start: string;
  period_end: string;
  status: string;
  total_collected: number;
  total_fees: number;
  net_remittance: number;
  created_at: string;
};

const fmtMoney = (v: number) => `$${(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
const fmtDate = (d: string) => d ? new Date(d).toLocaleDateString() : '—';

const STATUS_MAP: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  pending_approval: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-blue-100 text-blue-700',
  finalized: 'bg-green-100 text-green-700',
  sent: 'bg-purple-100 text-purple-700',
  voided: 'bg-red-100 text-red-700',
};

export default function RemittancePage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ statement_number: '', client_id: '', period_start: '', period_end: '', notes: '' });

  const listParams = { page: pageIndex + 1, page_size: pageSize, search };
  const { data, total, isLoading, mutate } = useApiList<StatementRow>(API, listParams);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: update } = useApiMutation('PATCH', API);
  const { trigger: remove } = useApiMutation('DELETE', API);
  const { trigger: approve } = useApiMutation('POST', API);
  const { trigger: finalize } = useApiMutation('POST', API);

  const columns: ColumnDef<StatementRow>[] = [
    { accessorKey: 'statement_number', header: 'Statement #' },
    { accessorKey: 'period_start', header: 'Period Start', cell: ({ row }) => fmtDate(row.original.period_start) },
    { accessorKey: 'period_end', header: 'Period End', cell: ({ row }) => fmtDate(row.original.period_end) },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} colorMap={STATUS_MAP} /> },
    { accessorKey: 'total_collected', header: 'Collected', cell: ({ row }) => fmtMoney(row.original.total_collected) },
    { accessorKey: 'net_remittance', header: 'Net Remittance', cell: ({ row }) => fmtMoney(row.original.net_remittance) },
    { accessorKey: 'created_at', header: 'Created', cell: ({ row }) => fmtDate(row.original.created_at) },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <button onClick={() => setSelectedId(row.original.id)} className="p-1 hover:bg-gray-100 rounded" title="View"><Eye className="h-4 w-4" /></button>
          {row.original.status === 'draft' && (
            <button onClick={async () => { await approve(undefined, `/${row.original.id}/approve`); mutate(); }} className="p-1 hover:bg-blue-100 rounded text-blue-600" title="Approve"><CheckCircle className="h-4 w-4" /></button>
          )}
          {row.original.status === 'approved' && (
            <button onClick={async () => { await finalize(undefined, `/${row.original.id}/finalize`); mutate(); }} className="p-1 hover:bg-green-100 rounded text-green-600" title="Finalize"><Send className="h-4 w-4" /></button>
          )}
        </div>
      ),
    },
  ];

  const handleCreate = async () => {
    await create(form);
    setDrawerOpen(false);
    setForm({ statement_number: '', client_id: '', period_start: '', period_end: '', notes: '' });
    mutate();
  };

  const handleDelete = async () => {
    if (selectedId) {
      await remove(undefined, `/${selectedId}`);
      setSelectedId(null);
      setDeleteOpen(false);
      mutate();
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Client Remittance" subtitle="Generate and manage client remittance statements">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus className="h-4 w-4" /> New Statement
        </button>
      </PageHeader>

      <SearchBar value={search} onChange={setSearch} placeholder="Search statements..." />

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && (
        <DetailPanel title="Remittance Statement" onClose={() => setSelectedId(null)}>
          <FieldGroup label="Details">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">ID</span><p className="text-sm font-mono">{selectedId}</p></div>
            </FieldGrid>
          </FieldGroup>
          <div className="flex gap-2 mt-4">
            <button onClick={() => { setDeleteOpen(true); }} className="px-3 py-1.5 text-sm bg-red-50 text-red-600 rounded hover:bg-red-100">Delete</button>
          </div>
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Remittance Statement" onSubmit={handleCreate}>
        <FormField label="Statement Number"><input value={form.statement_number} onChange={e => setForm({ ...form, statement_number: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Client ID"><input value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Period Start"><input type="date" value={form.period_start} onChange={e => setForm({ ...form, period_start: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Period End"><input type="date" value={form.period_end} onChange={e => setForm({ ...form, period_end: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Notes"><textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={3} /></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={handleDelete} title="Delete Statement" message="Are you sure you want to delete this remittance statement?" />
    </div>
  );
}
