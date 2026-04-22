'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { FileCheck, Eye, CheckCircle, XCircle, Send } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { StatusBadge } from '@/components/shared/status-badge';
import { useApiList, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/doc-drafts';

type DraftRow = { id: string; tenant_id: string; status: string; created_at: string };

const STATUS_MAP: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  pending_review: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  generated: 'bg-blue-100 text-blue-700',
};

export default function DocDraftsPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('');

  const { data, total, isLoading, mutate } = useApiList<DraftRow>(API, { page: pageIndex + 1, page_size: pageSize, ...(statusFilter ? { status: statusFilter } : {}) });
  const { trigger: submitReview } = useApiMutation('POST', API);
  const { trigger: approve } = useApiMutation('POST', API);
  const { trigger: reject } = useApiMutation('POST', API);

  const columns: ColumnDef<DraftRow>[] = [
    { accessorKey: 'id', header: 'Document ID', cell: ({ row }) => <span className="font-mono text-xs">{row.original.id.slice(0, 12)}...</span> },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} colorMap={STATUS_MAP} /> },
    { accessorKey: 'created_at', header: 'Created', cell: ({ row }) => new Date(row.original.created_at).toLocaleString() },
    {
      id: 'actions', header: 'Actions',
      cell: ({ row }) => (
        <div className="flex gap-1">
          {row.original.status === 'draft' && (
            <button onClick={async () => { await submitReview(undefined, `/${row.original.id}/submit-for-review`); mutate(); }} className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100"><Send className="h-3 w-3" /> Submit</button>
          )}
          {row.original.status === 'pending_review' && (
            <>
              <button onClick={async () => { await approve(undefined, `/${row.original.id}/approve`); mutate(); }} className="flex items-center gap-1 px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100"><CheckCircle className="h-3 w-3" /> Approve</button>
              <button onClick={async () => { await reject(undefined, `/${row.original.id}/reject`); mutate(); }} className="flex items-center gap-1 px-2 py-1 text-xs bg-red-50 text-red-600 rounded hover:bg-red-100"><XCircle className="h-3 w-3" /> Reject</button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Document Drafts" subtitle="Review and approve document drafts before finalization">
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPageIndex(0); }} className="rounded-lg border px-3 py-2 text-sm">
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="pending_review">Pending Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />
    </div>
  );
}
