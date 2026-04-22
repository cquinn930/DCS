'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { ShieldAlert, Plus, Trash2, CheckCircle, Lock, Unlock } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/safeguards';

type LimitRow = { id: string; transaction_type: string; max_amount: number; requires_approval_above: number | null; applies_to_role: string | null; is_active: boolean; description: string | null };
type NoteRow = { id: string; account_id: string; note_text: string; must_acknowledge: boolean; acknowledged: boolean; acknowledged_by: string | null; is_active: boolean; created_at: string };
type HoldRow = { id: string; account_id: string; reason: string; hold_type: string; is_active: boolean; block_batch_processing: boolean; block_letters: boolean; expires_at: string | null; created_at: string };

const fmtMoney = (v: number | null) => v != null ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—';

export default function SafeguardsPage() {
  const [tab, setTab] = useState<'limits' | 'notes' | 'holds'>('limits');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [limitForm, setLimitForm] = useState({ transaction_type: '', max_amount: '', requires_approval_above: '', description: '' });
  const [noteForm, setNoteForm] = useState({ account_id: '', note_text: '', must_acknowledge: true });
  const [holdForm, setHoldForm] = useState({ account_id: '', reason: '', hold_type: 'general', block_batch_processing: true, block_letters: true, block_credit_reporting: true });

  const params = { page: pageIndex + 1, page_size: pageSize };
  const { data: limits, total: limTotal, isLoading: limLoading, mutate: mutateLimits } = useApiList<LimitRow>(`${API}/limits`, params);
  const { data: notes, total: noteTotal, isLoading: noteLoading, mutate: mutateNotes } = useApiList<NoteRow>(`${API}/notes`, params);
  const { data: holds, total: holdTotal, isLoading: holdLoading, mutate: mutateHolds } = useApiList<HoldRow>(`${API}/holds`, params);

  const { trigger: createLimit } = useApiMutation('POST', `${API}/limits`);
  const { trigger: deleteLimit } = useApiMutation('DELETE', `${API}/limits`);
  const { trigger: createNote } = useApiMutation('POST', `${API}/notes`);
  const { trigger: ackNote } = useApiMutation('POST', `${API}/notes`);
  const { trigger: createHold } = useApiMutation('POST', `${API}/holds`);
  const { trigger: releaseHold } = useApiMutation('POST', `${API}/holds`);

  const limitColumns: ColumnDef<LimitRow>[] = [
    { accessorKey: 'transaction_type', header: 'Type' },
    { accessorKey: 'max_amount', header: 'Max Amount', cell: ({ row }) => fmtMoney(row.original.max_amount) },
    { accessorKey: 'requires_approval_above', header: 'Approval Above', cell: ({ row }) => fmtMoney(row.original.requires_approval_above) },
    { accessorKey: 'applies_to_role', header: 'Role', cell: ({ row }) => row.original.applies_to_role || 'All' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { id: 'actions', header: '', cell: ({ row }) => <button onClick={() => { setSelectedId(row.original.id); setDeleteOpen(true); }} className="p-1 hover:bg-red-100 rounded text-red-600"><Trash2 className="h-4 w-4" /></button> },
  ];

  const noteColumns: ColumnDef<NoteRow>[] = [
    { accessorKey: 'account_id', header: 'Account', cell: ({ row }) => <span className="font-mono text-xs">{row.original.account_id.slice(0, 8)}...</span> },
    { accessorKey: 'note_text', header: 'Note', cell: ({ row }) => <span className="truncate max-w-xs block">{row.original.note_text}</span> },
    { accessorKey: 'must_acknowledge', header: 'Must Ack.', cell: ({ row }) => row.original.must_acknowledge ? 'Yes' : 'No' },
    { accessorKey: 'acknowledged', header: 'Ack.', cell: ({ row }) => row.original.acknowledged_by ? <span className="text-green-600">Yes</span> : <span className="text-gray-400">No</span> },
    {
      id: 'actions', header: '',
      cell: ({ row }) => !row.original.acknowledged_by ? (
        <button onClick={async () => { await ackNote(undefined, `/${row.original.id}/acknowledge`); mutateNotes(); }} className="p-1 hover:bg-green-100 rounded text-green-600"><CheckCircle className="h-4 w-4" /></button>
      ) : null,
    },
  ];

  const holdColumns: ColumnDef<HoldRow>[] = [
    { accessorKey: 'account_id', header: 'Account', cell: ({ row }) => <span className="font-mono text-xs">{row.original.account_id.slice(0, 8)}...</span> },
    { accessorKey: 'hold_type', header: 'Type' },
    { accessorKey: 'reason', header: 'Reason', cell: ({ row }) => <span className="truncate max-w-xs block">{row.original.reason}</span> },
    { accessorKey: 'block_batch_processing', header: 'Block Batch', cell: ({ row }) => row.original.block_batch_processing ? 'Yes' : 'No' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? <Lock className="h-4 w-4 text-red-500" /> : <Unlock className="h-4 w-4 text-green-500" /> },
    {
      id: 'actions', header: '',
      cell: ({ row }) => row.original.is_active ? (
        <button onClick={async () => { await releaseHold(undefined, `/${row.original.id}/release`); mutateHolds(); }} className="p-1 hover:bg-green-100 rounded text-green-600 text-xs">Release</button>
      ) : null,
    },
  ];

  const handleSubmit = async () => {
    if (tab === 'limits') {
      await createLimit({ ...limitForm, max_amount: parseFloat(limitForm.max_amount), requires_approval_above: limitForm.requires_approval_above ? parseFloat(limitForm.requires_approval_above) : null });
      mutateLimits();
    } else if (tab === 'notes') {
      await createNote(noteForm);
      mutateNotes();
    } else {
      await createHold(holdForm);
      mutateHolds();
    }
    setDrawerOpen(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Financial Safeguards" subtitle="Transaction limits, mandatory notes, and temporary holds">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> Add {tab === 'limits' ? 'Limit' : tab === 'notes' ? 'Note' : 'Hold'}</button>
      </PageHeader>

      <div className="flex gap-2 border-b">
        {(['limits', 'notes', 'holds'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 capitalize ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>{t === 'limits' ? 'Transaction Limits' : t === 'notes' ? 'Financial Notes' : 'Temporary Holds'}</button>
        ))}
      </div>

      {tab === 'limits' && <DataTable columns={limitColumns} data={limits ?? []} isLoading={limLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((limTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}
      {tab === 'notes' && <DataTable columns={noteColumns} data={notes ?? []} isLoading={noteLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((noteTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}
      {tab === 'holds' && <DataTable columns={holdColumns} data={holds ?? []} isLoading={holdLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((holdTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={`New ${tab === 'limits' ? 'Transaction Limit' : tab === 'notes' ? 'Financial Note' : 'Temporary Hold'}`} onSubmit={handleSubmit}>
        {tab === 'limits' && <>
          <FormField label="Transaction Type"><input value={limitForm.transaction_type} onChange={e => setLimitForm({ ...limitForm, transaction_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="e.g., payment, refund, adjustment" /></FormField>
          <FormField label="Max Amount ($)"><input type="number" step="0.01" value={limitForm.max_amount} onChange={e => setLimitForm({ ...limitForm, max_amount: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
          <FormField label="Requires Approval Above ($)"><input type="number" step="0.01" value={limitForm.requires_approval_above} onChange={e => setLimitForm({ ...limitForm, requires_approval_above: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
          <FormField label="Description"><input value={limitForm.description} onChange={e => setLimitForm({ ...limitForm, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        </>}
        {tab === 'notes' && <>
          <FormField label="Account ID"><input value={noteForm.account_id} onChange={e => setNoteForm({ ...noteForm, account_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
          <FormField label="Note"><textarea value={noteForm.note_text} onChange={e => setNoteForm({ ...noteForm, note_text: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={3} /></FormField>
          <FormField label="Must Acknowledge"><label className="flex items-center gap-2"><input type="checkbox" checked={noteForm.must_acknowledge} onChange={e => setNoteForm({ ...noteForm, must_acknowledge: e.target.checked })} /> Yes</label></FormField>
        </>}
        {tab === 'holds' && <>
          <FormField label="Account ID"><input value={holdForm.account_id} onChange={e => setHoldForm({ ...holdForm, account_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
          <FormField label="Reason"><textarea value={holdForm.reason} onChange={e => setHoldForm({ ...holdForm, reason: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={2} /></FormField>
          <FormField label="Hold Type"><select value={holdForm.hold_type} onChange={e => setHoldForm({ ...holdForm, hold_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="general">General</option><option value="legal">Legal</option><option value="dispute">Dispute</option><option value="bankruptcy">Bankruptcy</option><option value="deceased">Deceased</option></select></FormField>
          <FormField label="Block Batch Processing"><label className="flex items-center gap-2"><input type="checkbox" checked={holdForm.block_batch_processing} onChange={e => setHoldForm({ ...holdForm, block_batch_processing: e.target.checked })} /> Yes</label></FormField>
          <FormField label="Block Letters"><label className="flex items-center gap-2"><input type="checkbox" checked={holdForm.block_letters} onChange={e => setHoldForm({ ...holdForm, block_letters: e.target.checked })} /> Yes</label></FormField>
        </>}
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await deleteLimit(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutateLimits(); } }} title="Delete Limit" message="Are you sure?" />
    </div>
  );
}
