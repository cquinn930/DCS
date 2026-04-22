'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { ClipboardCheck, Plus, Eye, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/reviews';

type TemplateRow = { id: string; name: string; category: string | null; is_active: boolean; require_all_items: boolean; items: { id: string; label: string; sort_order: number }[]; created_at: string };
type ReviewRow = { id: string; account_id: string; template_id: string; reviewer_id: string; status: string; started_at: string | null; completed_at: string | null; overall_result: string | null; created_at: string };

const STATUS_MAP: Record<string, string> = {
  not_started: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
};

export default function ReviewsPage() {
  const [tab, setTab] = useState<'templates' | 'reviews'>('templates');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', description: '', category: '', require_all_items: true });
  const [reviewForm, setReviewForm] = useState({ account_id: '', template_id: '' });
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);

  const { data: templates, total: tmplTotal, isLoading: tmplLoading, mutate: mutateTmpl } = useApiList<TemplateRow>(`${API}/templates`, { page: pageIndex + 1, page_size: pageSize });
  const { data: reviews, total: revTotal, isLoading: revLoading, mutate: mutateRevs } = useApiList<ReviewRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { trigger: createTmpl } = useApiMutation('POST', `${API}/templates`);
  const { trigger: deleteTmpl } = useApiMutation('DELETE', `${API}/templates`);
  const { trigger: createReview } = useApiMutation('POST', API);

  const tmplColumns: ColumnDef<TemplateRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'category', header: 'Category', cell: ({ row }) => row.original.category || '—' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { accessorKey: 'items', header: 'Items', cell: ({ row }) => row.original.items?.length ?? 0 },
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

  const reviewColumns: ColumnDef<ReviewRow>[] = [
    { accessorKey: 'account_id', header: 'Account', cell: ({ row }) => <span className="font-mono text-xs">{row.original.account_id.slice(0, 8)}...</span> },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} colorMap={STATUS_MAP} /> },
    { accessorKey: 'overall_result', header: 'Result', cell: ({ row }) => row.original.overall_result || '—' },
    { accessorKey: 'started_at', header: 'Started', cell: ({ row }) => row.original.started_at ? new Date(row.original.started_at).toLocaleDateString() : '—' },
    { accessorKey: 'completed_at', header: 'Completed', cell: ({ row }) => row.original.completed_at ? new Date(row.original.completed_at).toLocaleDateString() : '—' },
    { id: 'actions', header: '', cell: ({ row }) => <button onClick={() => setSelectedId(row.original.id)} className="p-1 hover:bg-gray-100 rounded"><Eye className="h-4 w-4" /></button> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Legal Reviews" subtitle="Attorney review checklists and compliance verification">
        <div className="flex gap-2">
          <button onClick={() => setReviewDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"><ClipboardCheck className="h-4 w-4" /> Start Review</button>
          <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New Template</button>
        </div>
      </PageHeader>

      <div className="flex gap-2 border-b">
        <button onClick={() => { setTab('templates'); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'templates' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>Templates</button>
        <button onClick={() => { setTab('reviews'); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'reviews' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>Reviews</button>
      </div>

      {tab === 'templates' ? (
        <DataTable columns={tmplColumns} data={templates ?? []} isLoading={tmplLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((tmplTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />
      ) : (
        <DataTable columns={reviewColumns} data={reviews ?? []} isLoading={revLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((revTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Review Template" onSubmit={async () => { await createTmpl(form); setDrawerOpen(false); setForm({ name: '', description: '', category: '', require_all_items: true }); mutateTmpl(); }}>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Description"><textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={2} /></FormField>
        <FormField label="Category"><input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="e.g., Pre-Suit, Compliance" /></FormField>
        <FormField label="Require All Items"><label className="flex items-center gap-2"><input type="checkbox" checked={form.require_all_items} onChange={e => setForm({ ...form, require_all_items: e.target.checked })} /> Yes</label></FormField>
      </FormDrawer>

      <FormDrawer open={reviewDrawerOpen} onClose={() => setReviewDrawerOpen(false)} title="Start Account Review" onSubmit={async () => { await createReview(reviewForm); setReviewDrawerOpen(false); setReviewForm({ account_id: '', template_id: '' }); mutateRevs(); }}>
        <FormField label="Account ID"><input value={reviewForm.account_id} onChange={e => setReviewForm({ ...reviewForm, account_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
        <FormField label="Template ID"><input value={reviewForm.template_id} onChange={e => setReviewForm({ ...reviewForm, template_id: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" /></FormField>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await deleteTmpl(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutateTmpl(); } }} title="Delete Template" message="Are you sure you want to delete this review template?" />
    </div>
  );
}
