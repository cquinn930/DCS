'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Building2, Plus, Eye, Trash2, Edit } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/courts';

type CourtRow = { id: string; code: string; name: string; court_type: string | null; jurisdiction: string | null; state: string | null; city: string | null; phone: string | null; is_active: boolean; filing_fee_default: number | null; created_at: string };

const fmtMoney = (v: number | string | null) => v != null ? `$${Number(v).toFixed(2)}` : '—';

export default function CourtsPage() {
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [form, setForm] = useState({ code: '', name: '', court_type: '', jurisdiction: '', address_line1: '', city: '', state: '', zip_code: '', phone: '', fax: '', email: '', filing_fee_default: '', service_fee_default: '' });

  const { data, total, isLoading, mutate } = useApiList<CourtRow>(API, { page: pageIndex + 1, page_size: pageSize, search });
  const { data: detail } = useApiDetail<CourtRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: update } = useApiMutation('PATCH', API);
  const { trigger: remove } = useApiMutation('DELETE', API);

  const columns: ColumnDef<CourtRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'court_type', header: 'Type', cell: ({ row }) => row.original.court_type || '—' },
    { accessorKey: 'state', header: 'State', cell: ({ row }) => row.original.state || '—' },
    { accessorKey: 'city', header: 'City', cell: ({ row }) => row.original.city || '—' },
    { accessorKey: 'filing_fee_default', header: 'Filing Fee', cell: ({ row }) => fmtMoney(row.original.filing_fee_default) },
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

  const handleSave = async () => {
    const payload = { ...form, filing_fee_default: form.filing_fee_default ? parseFloat(form.filing_fee_default) : null, service_fee_default: form.service_fee_default ? parseFloat(form.service_fee_default) : null };
    if (editMode && selectedId) { await update(payload, `/${selectedId}`); } else { await create(payload); }
    setDrawerOpen(false);
    setEditMode(false);
    setForm({ code: '', name: '', court_type: '', jurisdiction: '', address_line1: '', city: '', state: '', zip_code: '', phone: '', fax: '', email: '', filing_fee_default: '', service_fee_default: '' });
    mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Court Management" subtitle="Manage courts, cost overrides, and representatives">
        <button onClick={() => { setEditMode(false); setDrawerOpen(true); }} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> Add Court</button>
      </PageHeader>

      <SearchBar value={search} onChange={setSearch} placeholder="Search courts..." />

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title={detail.name} onClose={() => setSelectedId(null)}>
          <FieldGroup label="Court Details">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Code</span><p className="text-sm">{detail.code}</p></div>
              <div><span className="text-xs text-gray-500">Type</span><p className="text-sm">{detail.court_type || '—'}</p></div>
              <div><span className="text-xs text-gray-500">Jurisdiction</span><p className="text-sm">{detail.jurisdiction || '—'}</p></div>
              <div><span className="text-xs text-gray-500">State</span><p className="text-sm">{detail.state || '—'}</p></div>
              <div><span className="text-xs text-gray-500">City</span><p className="text-sm">{detail.city || '—'}</p></div>
              <div><span className="text-xs text-gray-500">Phone</span><p className="text-sm">{detail.phone || '—'}</p></div>
              <div><span className="text-xs text-gray-500">Filing Fee</span><p className="text-sm">{fmtMoney(detail.filing_fee_default)}</p></div>
            </FieldGrid>
          </FieldGroup>
          <div className="flex gap-2 mt-4">
            <button onClick={() => { setEditMode(true); setForm({ code: detail.code, name: detail.name, court_type: detail.court_type || '', jurisdiction: detail.jurisdiction || '', address_line1: '', city: detail.city || '', state: detail.state || '', zip_code: '', phone: detail.phone || '', fax: '', email: '', filing_fee_default: detail.filing_fee_default?.toString() || '', service_fee_default: '' }); setDrawerOpen(true); }} className="px-3 py-1.5 text-sm bg-blue-50 text-blue-600 rounded hover:bg-blue-100">Edit</button>
          </div>
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={editMode ? 'Edit Court' : 'Add Court'} onSubmit={handleSave}>
        <FormField label="Code"><input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" disabled={editMode} /></FormField>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Type"><input value={form.court_type} onChange={e => setForm({ ...form, court_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="e.g., Circuit, District, Small Claims" /></FormField>
        <FormField label="Jurisdiction"><input value={form.jurisdiction} onChange={e => setForm({ ...form, jurisdiction: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="City"><input value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="State"><input value={form.state} onChange={e => setForm({ ...form, state: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Phone"><input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Filing Fee ($)"><input value={form.filing_fee_default} onChange={e => setForm({ ...form, filing_fee_default: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" type="number" step="0.01" /></FormField>
        <FormField label="Service Fee ($)"><input value={form.service_fee_default} onChange={e => setForm({ ...form, service_fee_default: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" type="number" step="0.01" /></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete Court" message="Are you sure you want to delete this court?" />
    </div>
  );
}
