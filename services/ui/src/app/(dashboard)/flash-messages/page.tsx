'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Bell, Plus, Eye, Trash2, CheckCircle } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/flash-messages';

type TemplateRow = { id: string; name: string; message_text: string; priority: string; scope: string; is_active: boolean; auto_apply: boolean; created_at: string };
type AlertRow = { id: string; account_id: string; message_text: string; priority: string; is_active: boolean; acknowledged: boolean; created_at: string };

const PRIORITY_MAP: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

export default function FlashMessagesPage() {
  const [tab, setTab] = useState<'templates' | 'alerts'>('templates');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', message_text: '', priority: 'medium', scope: 'account', condition_script: '', require_acknowledgment: false });

  const tmplParams = { page: pageIndex + 1, page_size: pageSize };
  const { data: templates, total: tmplTotal, isLoading: tmplLoading, mutate: mutateTmpl } = useApiList<TemplateRow>(`${API}/templates`, tmplParams);
  const { data: alerts, total: alertTotal, isLoading: alertLoading, mutate: mutateAlerts } = useApiList<AlertRow>(API, { ...tmplParams, active_only: true });
  const { trigger: createTmpl } = useApiMutation('POST', `${API}/templates`);
  const { trigger: deleteTmpl } = useApiMutation('DELETE', `${API}/templates`);
  const { trigger: ackAlert } = useApiMutation('POST', API);

  const tmplColumns: ColumnDef<TemplateRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'priority', header: 'Priority', cell: ({ row }) => <StatusBadge status={row.original.priority} colorMap={PRIORITY_MAP} /> },
    { accessorKey: 'scope', header: 'Scope' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { accessorKey: 'auto_apply', header: 'Auto', cell: ({ row }) => row.original.auto_apply ? 'Yes' : 'No' },
    {
      id: 'actions', header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <button onClick={() => setSelectedId(row.original.id)} className="p-1 hover:bg-gray-100 rounded"><Eye className="h-4 w-4" /></button>
          <button onClick={() => { setSelectedId(row.original.id); setDeleteOpen(true); }} className="p-1 hover:bg-red-100 rounded text-red-600"><Trash2 className="h-4 w-4" /></button>
        </div>
      ),
    },
  ];

  const alertColumns: ColumnDef<AlertRow>[] = [
    { accessorKey: 'message_text', header: 'Message', cell: ({ row }) => <span className="truncate max-w-xs block">{row.original.message_text}</span> },
    { accessorKey: 'priority', header: 'Priority', cell: ({ row }) => <StatusBadge status={row.original.priority} colorMap={PRIORITY_MAP} /> },
    { accessorKey: 'acknowledged', header: 'Acknowledged', cell: ({ row }) => row.original.acknowledged ? 'Yes' : 'No' },
    {
      id: 'actions', header: '',
      cell: ({ row }) => !row.original.acknowledged ? (
        <button onClick={async () => { await ackAlert(undefined, `/${row.original.id}/acknowledge`); mutateAlerts(); }} className="p-1 hover:bg-green-100 rounded text-green-600" title="Acknowledge"><CheckCircle className="h-4 w-4" /></button>
      ) : null,
    },
  ];

  const handleCreateTmpl = async () => {
    await createTmpl(form);
    setDrawerOpen(false);
    setForm({ name: '', message_text: '', priority: 'medium', scope: 'account', condition_script: '', require_acknowledgment: false });
    mutateTmpl();
  };

  const handleDelete = async () => {
    if (selectedId) { await deleteTmpl(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutateTmpl(); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Flash Messages & Alerts" subtitle="Condition-triggered account alerts and notification templates">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New Template</button>
      </PageHeader>

      <div className="flex gap-2 border-b">
        <button onClick={() => { setTab('templates'); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'templates' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>Templates</button>
        <button onClick={() => { setTab('alerts'); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'alerts' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>Active Alerts</button>
      </div>

      {tab === 'templates' ? (
        <DataTable columns={tmplColumns} data={templates ?? []} isLoading={tmplLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((tmplTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />
      ) : (
        <DataTable columns={alertColumns} data={alerts ?? []} isLoading={alertLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((alertTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Flash Message Template" onSubmit={handleCreateTmpl}>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Message"><textarea value={form.message_text} onChange={e => setForm({ ...form, message_text: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={3} /></FormField>
        <FormField label="Priority"><select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></FormField>
        <FormField label="Scope"><select value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="account">Account</option><option value="consumer">Consumer</option><option value="client">Client</option></select></FormField>
        <FormField label="Condition Script"><textarea value={form.condition_script} onChange={e => setForm({ ...form, condition_script: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" rows={4} placeholder="Optional DCS Script condition..." /></FormField>
        <FormField label="Require Acknowledgment"><label className="flex items-center gap-2"><input type="checkbox" checked={form.require_acknowledgment} onChange={e => setForm({ ...form, require_acknowledgment: e.target.checked })} /> Yes</label></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={handleDelete} title="Delete Template" message="Are you sure you want to delete this flash message template?" />
    </div>
  );
}
