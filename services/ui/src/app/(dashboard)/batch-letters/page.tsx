'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Mail, Plus, Eye, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/batch-letters';

type ConfigRow = { id: string; name: string; description: string | null; is_active: boolean; rules: { id: string; action_code: string; document_template_name: string | null }[]; created_at: string };

export default function BatchLettersPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', is_active: true });

  const { data, total, isLoading, mutate } = useApiList<ConfigRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { data: detail } = useApiDetail<ConfigRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: remove } = useApiMutation('DELETE', API);

  const columns: ColumnDef<ConfigRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'description', header: 'Description', cell: ({ row }) => row.original.description || '—' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { accessorKey: 'rules', header: 'Rules', cell: ({ row }) => row.original.rules?.length ?? 0 },
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

  return (
    <div className="space-y-6">
      <PageHeader title="Batch Letters" subtitle="Configure batch letter generation by action code">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New Config</button>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title={detail.name} onClose={() => setSelectedId(null)}>
          <FieldGroup label="Configuration">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Name</span><p className="text-sm">{detail.name}</p></div>
              <div><span className="text-xs text-gray-500">Active</span><p className="text-sm">{detail.is_active ? 'Yes' : 'No'}</p></div>
              <div><span className="text-xs text-gray-500">Description</span><p className="text-sm">{detail.description || '—'}</p></div>
            </FieldGrid>
          </FieldGroup>
          {detail.rules?.length > 0 && (
            <FieldGroup label={`Rules (${detail.rules.length})`}>
              <div className="space-y-2">
                {detail.rules.map((r, i) => (
                  <div key={r.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded text-sm">
                    <span className="font-mono font-semibold">{r.action_code}</span>
                    <span className="text-gray-400">→</span>
                    <span>{r.document_template_name || 'No template'}</span>
                  </div>
                ))}
              </div>
            </FieldGroup>
          )}
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Batch Letter Config" onSubmit={async () => { await create(form); setDrawerOpen(false); setForm({ name: '', description: '', is_active: true }); mutate(); }}>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Description"><textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={2} /></FormField>
        <FormField label="Active"><label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> Enabled</label></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete Config" message="Are you sure you want to delete this batch letter configuration?" />
    </div>
  );
}
