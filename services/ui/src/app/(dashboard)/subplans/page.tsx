'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { GitBranch, Plus, Eye, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/subplans';

type SubPlanRow = { id: string; name: string; description: string | null; category: string | null; is_active: boolean; version: number; steps: { id: string; name: string; step_type: string; sort_order: number }[]; created_at: string };

export default function SubPlansPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', category: '', is_active: true });

  const { data, total, isLoading, mutate } = useApiList<SubPlanRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { data: detail } = useApiDetail<SubPlanRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: remove } = useApiMutation('DELETE', API);

  const columns: ColumnDef<SubPlanRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'category', header: 'Category', cell: ({ row }) => row.original.category || '—' },
    { accessorKey: 'version', header: 'Version' },
    { accessorKey: 'steps', header: 'Steps', cell: ({ row }) => row.original.steps?.length ?? 0 },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
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
      <PageHeader title="SubPlans" subtitle="Reusable workflow fragments for insertion into workflow chains">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New SubPlan</button>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title={detail.name} onClose={() => setSelectedId(null)}>
          <FieldGroup label="SubPlan Details">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Category</span><p className="text-sm">{detail.category || '—'}</p></div>
              <div><span className="text-xs text-gray-500">Version</span><p className="text-sm">{detail.version}</p></div>
              <div><span className="text-xs text-gray-500">Active</span><p className="text-sm">{detail.is_active ? 'Yes' : 'No'}</p></div>
            </FieldGrid>
          </FieldGroup>
          {detail.steps?.length > 0 && (
            <FieldGroup label={`Steps (${detail.steps.length})`}>
              <div className="space-y-2">
                {detail.steps.sort((a, b) => a.sort_order - b.sort_order).map(s => (
                  <div key={s.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded text-sm">
                    <span className="text-xs text-gray-400 w-6">{s.sort_order + 1}.</span>
                    <span className="font-medium">{s.name}</span>
                    <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded">{s.step_type}</span>
                  </div>
                ))}
              </div>
            </FieldGroup>
          )}
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New SubPlan" onSubmit={async () => { await create(form); setDrawerOpen(false); setForm({ name: '', description: '', category: '', is_active: true }); mutate(); }}>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Description"><textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={2} /></FormField>
        <FormField label="Category"><input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="e.g., Pre-Collect, Legal, Settlement" /></FormField>
        <FormField label="Active"><label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> Enabled</label></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete SubPlan" message="Are you sure you want to delete this SubPlan and all its steps?" />
    </div>
  );
}
