'use client';

import { useEffect, useMemo, useState } from 'react';
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
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/tenants';

type TenantRow = {
  id: string;
  name: string;
  slug: string;
  status: string;
  business_model: string;
  default_jurisdiction: string;
  created_at?: string;
  retention_years?: number;
  settings?: Record<string, unknown>;
};

const BUSINESS_MODELS = [
  'subscription',
  'per_account',
  'contingency',
  'debt_buyer',
] as const;

export default function TenantsPage() {
  const isMaster = useAuthStore((s) => s.user?.isMaster);
  const masterFn = useAuthStore((s) => s.isMasterUser);
  const allowed = Boolean(isMaster) || masterFn();

  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [suspendOpen, setSuspendOpen] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };
  const { data, total, isLoading, mutate } = useApiList<TenantRow>(
    allowed ? API : null,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<TenantRow>(API, selectedId ?? undefined);

  const { trigger: createTenant, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    TenantRow
  >('POST', API);
  const { trigger: patchTenant, isMutating: suspending } = useApiMutation<
    Record<string, unknown>,
    TenantRow
  >('PATCH', API);

  const [form, setForm] = useState({
    name: '',
    slug: '',
    business_model: 'subscription' as (typeof BUSINESS_MODELS)[number],
    default_jurisdiction: 'NJ',
    retention_years: 7,
  });

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.slug.toLowerCase().includes(q) ||
        r.default_jurisdiction.toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<TenantRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'slug', header: 'Slug' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    { accessorKey: 'business_model', header: 'Business model' },
    { accessorKey: 'default_jurisdiction', header: 'Jurisdiction' },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ getValue }) => {
        const v = getValue() as string | undefined;
        return v ? new Date(v).toLocaleDateString() : '—';
      },
    },
  ];

  function openCreate() {
    setForm({
      name: '',
      slug: '',
      business_model: 'subscription',
      default_jurisdiction: 'NJ',
      retention_years: 7,
    });
    setDrawerOpen(true);
  }

  async function handleCreate() {
    await createTenant({
      name: form.name,
      slug: form.slug,
      business_model: form.business_model,
      default_jurisdiction: form.default_jurisdiction,
      retention_years: form.retention_years,
    });
    setDrawerOpen(false);
    await mutate();
  }

  async function confirmSuspend() {
    if (!selectedId) return;
    try {
      await patchTenant({ status: 'suspended' } as Record<string, unknown>, `/${selectedId}`);
      setSuspendOpen(false);
      await mutateDetail();
      await mutate();
    } catch {
      /* 422 if schema rejects status */
    }
  }

  const d = detail;

  if (!allowed) {
    return (
      <div className="space-y-6">
        <PageHeader title="Tenants" subtitle="Master account only" />
        <div className="rounded-lg border border-border bg-card p-8 text-center shadow-sm">
          <p className="text-lg font-medium text-foreground">Access denied</p>
          <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
            Only master users can view and manage all tenants.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenants"
        subtitle="Master directory — create and manage organizations"
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New tenant
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search tenants…"
      />

      <DataTable<TenantRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No tenants"
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
          title={d?.name ?? 'Tenant'}
          subtitle={d?.slug}
          onClose={() => setSelectedId(null)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="ID">
                  <span className="font-mono text-xs">{d.id}</span>
                </FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={d.status} />
                </FieldGroup>
                <FieldGroup label="Business model">{d.business_model}</FieldGroup>
                <FieldGroup label="Jurisdiction">
                  {d.default_jurisdiction}
                </FieldGroup>
                <FieldGroup label="Retention (years)">
                  {d.retention_years ?? '—'}
                </FieldGroup>
                <FieldGroup label="User count">—</FieldGroup>
              </FieldGrid>
              <div className="mt-6 border-t border-border pt-4">
                <p className="text-xs font-medium uppercase text-neutral-500">
                  Settings
                </p>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
                  {JSON.stringify(d.settings ?? {}, null, 2)}
                </pre>
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  disabled={d.status === 'suspended' || suspending}
                  onClick={() => setSuspendOpen(true)}
                  className="rounded-md border border-error-500/40 bg-error-50 px-4 py-2 text-sm font-medium text-error-800 hover:bg-error-50/80 disabled:opacity-50 dark:bg-error-500/10 dark:text-error-500"
                >
                  {suspending ? 'Updating…' : 'Suspend tenant'}
                </button>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Create tenant"
        onSubmit={handleCreate}
        isSubmitting={creating}
        submitLabel="Create"
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </FormField>
          <FormField label="Slug" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={form.slug}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''),
                }))
              }
              placeholder="lowercase-a-z-0-9"
            />
          </FormField>
          <FormField label="Business model">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.business_model}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  business_model: e.target.value as (typeof BUSINESS_MODELS)[number],
                }))
              }
            >
              {BUSINESS_MODELS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Default jurisdiction">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm uppercase"
              maxLength={2}
              value={form.default_jurisdiction}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  default_jurisdiction: e.target.value.toUpperCase(),
                }))
              }
            />
          </FormField>
          <FormField label="Retention years (min 7)">
            <input
              type="number"
              min={7}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.retention_years}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  retention_years: parseInt(e.target.value, 10) || 7,
                }))
              }
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={suspendOpen}
        onClose={() => setSuspendOpen(false)}
        onConfirm={confirmSuspend}
        title="Suspend tenant?"
        message="Sets tenant status to suspended if accepted by the API."
        confirmLabel={suspending ? 'Working…' : 'Suspend'}
        variant="danger"
      />
    </div>
  );
}
