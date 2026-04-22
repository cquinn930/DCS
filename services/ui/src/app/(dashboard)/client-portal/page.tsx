'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Globe, Plus, Eye, Trash2, Edit } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/client-portal';

type PortalUserRow = { id: string; client_id: string; email: string; name: string; access_level: string; is_active: boolean; last_login: string | null; created_at: string };

const ACCESS_MAP: Record<string, string> = {
  view_only: 'bg-gray-100 text-gray-700',
  standard: 'bg-blue-100 text-blue-700',
  full: 'bg-green-100 text-green-700',
  custom: 'bg-purple-100 text-purple-700',
};

export default function ClientPortalPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ client_id: '', email: '', name: '', password: '', access_level: 'view_only' });

  const { data, total, isLoading, mutate } = useApiList<PortalUserRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { data: detail } = useApiDetail<PortalUserRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: remove } = useApiMutation('DELETE', API);

  const columns: ColumnDef<PortalUserRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'email', header: 'Email' },
    { accessorKey: 'access_level', header: 'Access', cell: ({ row }) => <StatusBadge status={row.original.access_level} colorMap={ACCESS_MAP} /> },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { accessorKey: 'last_login', header: 'Last Login', cell: ({ row }) => row.original.last_login ? new Date(row.original.last_login).toLocaleString() : 'Never' },
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
      <PageHeader title="Client Portal" subtitle="Manage client-facing portal access and permissions">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> Add Portal User</button>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title={detail.name} onClose={() => setSelectedId(null)}>
          <FieldGroup label="Portal User">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Name</span><p className="text-sm">{detail.name}</p></div>
              <div><span className="text-xs text-gray-500">Email</span><p className="text-sm">{detail.email}</p></div>
              <div><span className="text-xs text-gray-500">Access Level</span><p className="text-sm"><StatusBadge status={detail.access_level} colorMap={ACCESS_MAP} /></p></div>
              <div><span className="text-xs text-gray-500">Active</span><p className="text-sm">{detail.is_active ? 'Yes' : 'No'}</p></div>
              <div><span className="text-xs text-gray-500">Last Login</span><p className="text-sm">{detail.last_login ? new Date(detail.last_login).toLocaleString() : 'Never'}</p></div>
            </FieldGrid>
          </FieldGroup>
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Add Portal User" onSubmit={async () => { await create(form); setDrawerOpen(false); setForm({ client_id: '', email: '', name: '', password: '', access_level: 'view_only' }); mutate(); }}>
        <FormField label="Client ID"><input value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Email"><input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Password"><input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Access Level"><select value={form.access_level} onChange={e => setForm({ ...form, access_level: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="view_only">View Only</option><option value="standard">Standard</option><option value="full">Full</option><option value="custom">Custom</option></select></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete Portal User" message="This will revoke their access. Continue?" />
    </div>
  );
}
