'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import {
  DetailPanel,
  FieldGrid,
  FieldGroup,
} from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';

const API_REQUESTS = '/api/v1/skip-trace/requests';
const API_RESULTS = '/api/v1/skip-trace/results';

const VENDORS = ['lexisnexis', 'tloxp', 'other'] as const;
const REQUEST_TYPES = ['individual', 'batch'] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type SkipTraceRequestRow = {
  id: string;
  account_id: string;
  consumer_name?: string | null;
  vendor: string;
  status: string;
  submitted_at?: string | null;
  results_count?: number;
  request_type?: string;
};

type SkipTraceRequestDetail = SkipTraceRequestRow & {
  notes?: string | null;
};

type SkipTraceResult = {
  id: string;
  request_id?: string;
  vendor?: string;
  status?: string;
  raw_payload?: unknown;
  created_at?: string;
  [key: string]: unknown;
};

export default function SkipTracePage() {
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [applyLoadingId, setApplyLoadingId] = useState<string | null>(null);

  const [form, setForm] = useState({
    account_id: '',
    vendor: 'lexisnexis' as (typeof VENDORS)[number],
    request_type: 'individual' as (typeof REQUEST_TYPES)[number],
    notes: '',
  });

  const listParams = useMemo(
    () => ({ page: pageIndex + 1, page_size: pageSize }),
    [pageIndex, pageSize]
  );

  const { data, total, isLoading, mutate } = useApiList<SkipTraceRequestRow>(
    API_REQUESTS,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<SkipTraceRequestDetail>(API_REQUESTS, selectedId ?? undefined);

  const resultsPath =
    selectedId != null
      ? `${API_REQUESTS.replace(/\/$/, '')}/${selectedId}/results`
      : null;
  const {
    data: results,
    isLoading: resultsLoading,
    mutate: mutateResults,
  } = useApiList<SkipTraceResult>(resultsPath, { page: 1, page_size: 200 });

  const { trigger: createReq, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    SkipTraceRequestDetail
  >('POST', API_REQUESTS);
  const { trigger: patchReq, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    SkipTraceRequestDetail
  >('PATCH', API_REQUESTS);
  const { trigger: deleteReq, isMutating: deleting } = useApiMutation(
    'DELETE',
    API_REQUESTS
  );

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.id.toLowerCase().includes(q) ||
        String(r.account_id).toLowerCase().includes(q) ||
        (r.consumer_name ?? '').toLowerCase().includes(q) ||
        r.vendor.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<SkipTraceRequestRow>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue())}</span>
      ),
    },
    {
      accessorKey: 'account_id',
      header: 'Account',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue())}</span>
      ),
    },
    {
      accessorKey: 'consumer_name',
      header: 'Consumer Name',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
    { accessorKey: 'vendor', header: 'Vendor' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue() ?? '')} />,
    },
    {
      accessorKey: 'submitted_at',
      header: 'Submitted',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
    {
      id: 'results_count',
      header: 'Results Count',
      cell: ({ row }) =>
        String(row.original.results_count ?? '—'),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      account_id: '',
      vendor: 'lexisnexis',
      request_type: 'individual',
      notes: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_id: detail.account_id,
      vendor: (detail.vendor as (typeof VENDORS)[number]) ?? 'other',
      request_type:
        (detail.request_type as (typeof REQUEST_TYPES)[number]) ?? 'individual',
      notes: detail.notes ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const body: Record<string, unknown> = {
      account_id: form.account_id.trim(),
      vendor: form.vendor,
      request_type: form.request_type,
      notes: form.notes.trim() || undefined,
    };
    if (!editMode) {
      await createReq(body);
    } else if (selectedId) {
      await patchReq(
        {
          vendor: form.vendor,
          request_type: form.request_type,
          notes: form.notes.trim() || undefined,
        },
        `/${selectedId}`
      );
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmDelete() {
    if (!selectedId) return;
    await deleteReq(undefined, `/${selectedId}`);
    setDeleteOpen(false);
    setSelectedId(null);
    await mutate();
  }

  async function submitToVendor() {
    if (!selectedId) return;
    setSubmitLoading(true);
    try {
      await apiClient.post(
        `${API_REQUESTS.replace(/\/$/, '')}/${selectedId}/submit`,
        {}
      );
      await mutateDetail();
      await mutateResults();
      await mutate();
    } finally {
      setSubmitLoading(false);
    }
  }

  async function applyResult(resultId: string) {
    setApplyLoadingId(resultId);
    try {
      await apiClient.post(
        `${API_RESULTS.replace(/\/$/, '')}/${resultId}/apply`,
        {}
      );
      await mutateResults();
      await mutateDetail();
      await mutate();
    } finally {
      setApplyLoadingId(null);
    }
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Skip trace"
        subtitle="Vendor skip-trace requests and results"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New request
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search requests…"
      />

      <DataTable<SkipTraceRequestRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No skip-trace requests"
        onRowClick={(row) => setSelectedId(row.id)}
        pageCount={pageCount}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPageChange={setPageIndex}
        onPageSizeChange={(s) => {
          setPageSize(s);
          setPageIndex(0);
        }}
      />

      {selectedId && (
        <DetailPanel
          title={d?.consumer_name || 'Skip-trace request'}
          subtitle={`${d?.vendor ?? ''} · ${d?.status ?? ''}`}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={submitLoading}
                  onClick={submitToVendor}
                  className="inline-flex h-9 items-center rounded-md bg-primary-600 px-3 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {submitLoading ? 'Submitting…' : 'Submit to Vendor'}
                </button>
              </div>
              <div className="mt-6">
                <FieldGrid cols={2}>
                  <FieldGroup label="Request ID">
                    <span className="font-mono text-xs">{d.id}</span>
                  </FieldGroup>
                  <FieldGroup label="Account">
                    <span className="font-mono text-xs">{d.account_id}</span>
                  </FieldGroup>
                  <FieldGroup label="Vendor">{d.vendor}</FieldGroup>
                  <FieldGroup label="Request type">
                    {d.request_type ?? '—'}
                  </FieldGroup>
                  <FieldGroup label="Status">
                    <StatusBadge status={d.status} />
                  </FieldGroup>
                  <FieldGroup label="Submitted">
                    {fmtDate(d.submitted_at ?? undefined)}
                  </FieldGroup>
                  <FieldGroup label="Results count">
                    {String(d.results_count ?? '—')}
                  </FieldGroup>
                  <FieldGroup label="Notes">{d.notes || '—'}</FieldGroup>
                </FieldGrid>
              </div>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Results
                </h3>
                {resultsLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading…</p>
                ) : (
                  <div className="mt-3 overflow-hidden rounded-md border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">ID</th>
                          <th className="px-3 py-2 text-left font-medium">
                            Vendor
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Created
                          </th>
                          <th className="px-3 py-2 text-right font-medium">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(results ?? []).length === 0 ? (
                          <tr>
                            <td
                              colSpan={5}
                              className="px-3 py-6 text-center text-neutral-500"
                            >
                              No results yet
                            </td>
                          </tr>
                        ) : (
                          (results ?? []).map((r) => (
                            <tr key={r.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono text-xs">
                                {r.id}
                              </td>
                              <td className="px-3 py-2">
                                {String(r.vendor ?? '—')}
                              </td>
                              <td className="px-3 py-2">
                                {r.status ? (
                                  <StatusBadge status={String(r.status)} />
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof r.created_at === 'string'
                                    ? r.created_at
                                    : undefined
                                )}
                              </td>
                              <td className="px-3 py-2 text-right">
                                <button
                                  type="button"
                                  disabled={applyLoadingId === r.id}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void applyResult(r.id);
                                  }}
                                  className="inline-flex h-8 items-center rounded-md border border-border bg-background px-2 text-xs font-medium hover:bg-muted disabled:opacity-50"
                                >
                                  {applyLoadingId === r.id
                                    ? 'Applying…'
                                    : 'Apply'}
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit request' : 'New skip-trace request'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Account ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
              value={form.account_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, account_id: e.target.value }))
              }
              disabled={editMode}
            />
          </FormField>
          <FormField label="Vendor" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.vendor}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  vendor: e.target.value as (typeof VENDORS)[number],
                }))
              }
            >
              {VENDORS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Request type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.request_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  request_type: e.target.value as (typeof REQUEST_TYPES)[number],
                }))
              }
            >
              {REQUEST_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Notes">
            <textarea
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.notes}
              onChange={(e) =>
                setForm((f) => ({ ...f, notes: e.target.value }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete skip-trace request?"
        message="This removes the request record. Confirm your retention policy before deleting."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
