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

const CONFIGS_API = '/api/v1/credit-bureau/configs';
const BATCHES_API = '/api/v1/credit-bureau/batches';

const BUREAUS = ['experian', 'equifax', 'transunion'] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type BureauConfigRow = {
  id: string;
  bureau: string;
  program_id?: string;
  status?: string;
  active?: boolean;
};

type BureauConfigDetail = BureauConfigRow & {
  subscriber_code?: string | null;
  portfolio_type?: string | null;
  contact_info?: unknown;
};

type BureauBatchRow = {
  id: string;
  bureau_config_id?: string;
  bureau_name?: string;
  status: string;
  record_count?: number;
  error_count?: number;
  generated_at?: string | null;
  reporting_period_start?: string;
  reporting_period_end?: string;
};

type BureauRecordRow = {
  id: string;
  account_id?: string;
  account_reference?: string;
  status_code?: string;
  amount?: number;
};

export default function CreditBureauPage() {
  const [tab, setTab] = useState<'configs' | 'batches'>('configs');
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [drawerEntity, setDrawerEntity] = useState<'config' | 'batch'>(
    'config'
  );

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: configs, total: cTotal, isLoading: cLoading, mutate: mc } =
    useApiList<BureauConfigRow>(CONFIGS_API, listParams);
  const { data: batches, total: bTotal, isLoading: bLoading, mutate: mb } =
    useApiList<BureauBatchRow>(BATCHES_API, listParams);

  const { data: cfgDetail, isLoading: cfgLoading, mutate: mutateCfg } =
    useApiDetail<BureauConfigDetail>(
      CONFIGS_API,
      selectedConfigId ?? undefined
    );
  const { data: batchDetail, isLoading: batchDetailLoading, mutate: mutateBatch } =
    useApiDetail<BureauBatchRow>(BATCHES_API, selectedBatchId ?? undefined);

  const recordsPath =
    selectedBatchId != null ? `${BATCHES_API}/${selectedBatchId}/records` : null;
  const { data: recordRows, isLoading: recordsLoading } =
    useApiList<BureauRecordRow>(recordsPath, { page: 1, page_size: 500 });

  const { trigger: createCfg, isMutating: creatingCfg } = useApiMutation(
    'POST',
    CONFIGS_API
  );
  const { trigger: patchCfg, isMutating: patchingCfg } = useApiMutation(
    'PATCH',
    CONFIGS_API
  );
  const { trigger: deleteCfg, isMutating: deletingCfg } = useApiMutation(
    'DELETE',
    CONFIGS_API
  );

  const { trigger: createBatch, isMutating: creatingBatch } = useApiMutation(
    'POST',
    BATCHES_API
  );
  const { trigger: deleteBatch, isMutating: deletingBatch } = useApiMutation(
    'DELETE',
    BATCHES_API
  );

  const [formConfig, setFormConfig] = useState({
    bureau: 'experian',
    program_id: '',
    subscriber_code: '',
    portfolio_type: '',
    contact_info: '{}',
  });
  const [formBatch, setFormBatch] = useState({
    bureau_config_id: '',
    reporting_period_start: '',
    reporting_period_end: '',
  });

  const configRows = configs ?? [];
  const batchRows = batches ?? [];
  const records = recordRows ?? [];

  const filteredConfigs = useMemo(() => {
    if (!search.trim()) return configRows;
    const q = search.toLowerCase();
    return configRows.filter(
      (r) =>
        r.bureau.toLowerCase().includes(q) ||
        String(r.program_id ?? '').toLowerCase().includes(q)
    );
  }, [configRows, search]);

  const filteredBatches = useMemo(() => {
    if (!search.trim()) return batchRows;
    const q = search.toLowerCase();
    return batchRows.filter(
      (r) =>
        (r.bureau_name ?? '').toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [batchRows, search]);

  const pageCount =
    tab === 'configs'
      ? Math.max(1, Math.ceil((cTotal ?? 0) / pageSize))
      : Math.max(1, Math.ceil((bTotal ?? 0) / pageSize));

  const configColumns: ColumnDef<BureauConfigRow>[] = [
    { accessorKey: 'bureau', header: 'Bureau' },
    { accessorKey: 'program_id', header: 'Program ID' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) =>
        getValue() ? (
          <StatusBadge status={String(getValue())} />
        ) : (
          <span>—</span>
        ),
    },
    {
      accessorKey: 'active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() === false ? 'inactive' : 'active'} />
      ),
    },
  ];

  const batchColumns: ColumnDef<BureauBatchRow>[] = [
    {
      accessorKey: 'bureau_name',
      header: 'Bureau Config',
      cell: ({ row }) =>
        row.original.bureau_name ?? row.original.bureau_config_id ?? '—',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    { accessorKey: 'record_count', header: 'Record Count' },
    { accessorKey: 'error_count', header: 'Errors' },
    {
      accessorKey: 'generated_at',
      header: 'Generated Date',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
  ];

  const recordColumns: ColumnDef<BureauRecordRow>[] = [
    {
      accessorKey: 'account_reference',
      header: 'Account',
      cell: ({ row }) =>
        row.original.account_reference ?? row.original.account_id ?? '—',
    },
    {
      accessorKey: 'status_code',
      header: 'Status Code',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ getValue }) => {
        const v = getValue();
        if (v == null || (typeof v !== 'number' && typeof v !== 'string'))
          return '—';
        const n = typeof v === 'number' ? v : parseFloat(v);
        if (Number.isNaN(n)) return '—';
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
        }).format(n);
      },
    },
  ];

  function openCreate(entity: 'config' | 'batch') {
    setDrawerEntity(entity);
    setEditMode(false);
    if (entity === 'config') {
      setFormConfig({
        bureau: 'experian',
        program_id: '',
        subscriber_code: '',
        portfolio_type: '',
        contact_info: '{}',
      });
    } else {
      setFormBatch({
        bureau_config_id: configRows[0]?.id ?? '',
        reporting_period_start: '',
        reporting_period_end: '',
      });
    }
    setDrawerOpen(true);
  }

  function openEditConfig() {
    if (!cfgDetail) return;
    setDrawerEntity('config');
    setEditMode(true);
    setFormConfig({
      bureau: cfgDetail.bureau,
      program_id: cfgDetail.program_id ?? '',
      subscriber_code: cfgDetail.subscriber_code ?? '',
      portfolio_type: cfgDetail.portfolio_type ?? '',
      contact_info: JSON.stringify(cfgDetail.contact_info ?? {}, null, 2),
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (drawerEntity === 'config') {
      let contact: unknown;
      try {
        contact = JSON.parse(formConfig.contact_info || '{}') as unknown;
      } catch {
        return;
      }
      const payload: Record<string, unknown> = {
        bureau: formConfig.bureau,
        program_id: formConfig.program_id || undefined,
        subscriber_code: formConfig.subscriber_code || undefined,
        portfolio_type: formConfig.portfolio_type || undefined,
        contact_info: contact,
      };
      if (!editMode) await createCfg(payload);
      else if (selectedConfigId)
        await patchCfg(payload, `/${selectedConfigId}`);
      await mc();
      if (selectedConfigId) await mutateCfg();
    } else {
      await createBatch({
        bureau_config_id: formBatch.bureau_config_id,
        reporting_period_start: formBatch.reporting_period_start
          ? new Date(formBatch.reporting_period_start).toISOString()
          : undefined,
        reporting_period_end: formBatch.reporting_period_end
          ? new Date(formBatch.reporting_period_end).toISOString()
          : undefined,
      });
      await mb();
    }
    setDrawerOpen(false);
  }

  async function confirmDelete() {
    try {
      if (tab === 'configs' && selectedConfigId) {
        await deleteCfg(undefined, `/${selectedConfigId}`);
        setSelectedConfigId(null);
        await mc();
      } else if (tab === 'batches' && selectedBatchId) {
        await deleteBatch(undefined, `/${selectedBatchId}`);
        setSelectedBatchId(null);
        await mb();
      }
    } catch {
      /* noop */
    }
    setDeleteOpen(false);
  }

  const isSubmitting =
    drawerEntity === 'config'
      ? creatingCfg || patchingCfg
      : creatingBatch;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Credit bureau"
        subtitle="Metro 2-style reporting configurations and batches"
        actions={
          <div className="flex gap-2">
            {tab === 'configs' ? (
              <button
                type="button"
                onClick={() => openCreate('config')}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              >
                <Plus className="h-4 w-4" />
                New config
              </button>
            ) : (
              <button
                type="button"
                onClick={() => openCreate('batch')}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              >
                <Plus className="h-4 w-4" />
                New batch
              </button>
            )}
          </div>
        }
      />

      <div className="flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => {
            setTab('configs');
            setSelectedBatchId(null);
            setPageIndex(0);
          }}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${
            tab === 'configs'
              ? 'border-primary-600 text-primary-700 dark:text-primary-400'
              : 'border-transparent text-neutral-600 hover:text-foreground'
          }`}
        >
          Configs
        </button>
        <button
          type="button"
          onClick={() => {
            setTab('batches');
            setSelectedConfigId(null);
            setPageIndex(0);
          }}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${
            tab === 'batches'
              ? 'border-primary-600 text-primary-700 dark:text-primary-400'
              : 'border-transparent text-neutral-600 hover:text-foreground'
          }`}
        >
          Batches
        </button>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder={tab === 'configs' ? 'Search configs…' : 'Search batches…'}
      />

      {tab === 'configs' ? (
        <DataTable<BureauConfigRow>
          columns={configColumns}
          data={filteredConfigs}
          isLoading={cLoading}
          emptyMessage="No bureau configs"
          onRowClick={(row) => setSelectedConfigId(row.id)}
          pageCount={pageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      ) : (
        <DataTable<BureauBatchRow>
          columns={batchColumns}
          data={filteredBatches}
          isLoading={bLoading}
          emptyMessage="No batches"
          onRowClick={(row) => setSelectedBatchId(row.id)}
          pageCount={pageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      )}

      {tab === 'configs' && selectedConfigId && (
        <DetailPanel
          title={cfgDetail?.bureau ?? 'Bureau config'}
          subtitle={cfgDetail?.program_id}
          onClose={() => setSelectedConfigId(null)}
          onEdit={openEditConfig}
          onDelete={() => setDeleteOpen(true)}
        >
          {cfgLoading || !cfgDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Bureau">{cfgDetail.bureau}</FieldGroup>
              <FieldGroup label="Program ID">{cfgDetail.program_id ?? '—'}</FieldGroup>
              <FieldGroup label="Subscriber code">
                {cfgDetail.subscriber_code ?? '—'}
              </FieldGroup>
              <FieldGroup label="Portfolio type">
                {cfgDetail.portfolio_type ?? '—'}
              </FieldGroup>
              <FieldGroup label="Status">
                {cfgDetail.status ? (
                  <StatusBadge status={cfgDetail.status} />
                ) : (
                  '—'
                )}
              </FieldGroup>
              <FieldGroup label="Active">
                <StatusBadge
                  status={cfgDetail.active === false ? 'inactive' : 'active'}
                />
              </FieldGroup>
              <div className="sm:col-span-2">
                <FieldGroup label="Contact info">
                  <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-2 text-xs dark:bg-neutral-900/50">
                    {JSON.stringify(cfgDetail.contact_info ?? {}, null, 2)}
                  </pre>
                </FieldGroup>
              </div>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {tab === 'batches' && selectedBatchId && (
        <DetailPanel
          title="Credit bureau batch"
          subtitle={
            batchDetail?.reporting_period_start && batchDetail?.reporting_period_end
              ? `${fmtDate(batchDetail.reporting_period_start)} – ${fmtDate(batchDetail.reporting_period_end)}`
              : undefined
          }
          onClose={() => setSelectedBatchId(null)}
          onDelete={() => setDeleteOpen(true)}
        >
          {batchDetailLoading || !batchDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Bureau config">
                  {batchDetail.bureau_name ?? batchDetail.bureau_config_id ?? '—'}
                </FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={batchDetail.status} />
                </FieldGroup>
                <FieldGroup label="Records">
                  {batchDetail.record_count ?? '—'}
                </FieldGroup>
                <FieldGroup label="Errors">{batchDetail.error_count ?? '—'}</FieldGroup>
                <FieldGroup label="Generated">{fmtDate(batchDetail.generated_at)}</FieldGroup>
              </FieldGrid>

              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">Records</h3>
                {recordsLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading records…</p>
                ) : (
                  <div className="mt-3">
                    <DataTable<BureauRecordRow>
                      columns={recordColumns}
                      data={records}
                      emptyMessage="No records in this batch"
                    />
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
        title={
          drawerEntity === 'config'
            ? editMode
              ? 'Edit bureau config'
              : 'New bureau config'
            : 'New batch'
        }
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        submitLabel={drawerEntity === 'config' ? (editMode ? 'Save' : 'Create') : 'Create batch'}
      >
        {drawerEntity === 'config' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Bureau" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formConfig.bureau}
                onChange={(e) =>
                  setFormConfig((f) => ({ ...f, bureau: e.target.value }))
                }
              >
                {BUREAUS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Program ID">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formConfig.program_id}
                onChange={(e) =>
                  setFormConfig((f) => ({ ...f, program_id: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Subscriber code">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formConfig.subscriber_code}
                onChange={(e) =>
                  setFormConfig((f) => ({
                    ...f,
                    subscriber_code: e.target.value,
                  }))
                }
              />
            </FormField>
            <FormField label="Portfolio type">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formConfig.portfolio_type}
                onChange={(e) =>
                  setFormConfig((f) => ({
                    ...f,
                    portfolio_type: e.target.value,
                  }))
                }
              />
            </FormField>
            <FormField label="Contact info (JSON)">
              <textarea
                rows={6}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                value={formConfig.contact_info}
                onChange={(e) =>
                  setFormConfig((f) => ({ ...f, contact_info: e.target.value }))
                }
              />
            </FormField>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <FormField label="Bureau config" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formBatch.bureau_config_id}
                onChange={(e) =>
                  setFormBatch((f) => ({
                    ...f,
                    bureau_config_id: e.target.value,
                  }))
                }
              >
                {configRows.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.bureau} · {c.program_id ?? c.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Reporting period start">
              <input
                type="datetime-local"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formBatch.reporting_period_start}
                onChange={(e) =>
                  setFormBatch((f) => ({
                    ...f,
                    reporting_period_start: e.target.value,
                  }))
                }
              />
            </FormField>
            <FormField label="Reporting period end">
              <input
                type="datetime-local"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formBatch.reporting_period_end}
                onChange={(e) =>
                  setFormBatch((f) => ({
                    ...f,
                    reporting_period_end: e.target.value,
                  }))
                }
              />
            </FormField>
          </div>
        )}
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete this item?"
        message="Confirm removal of this bureau configuration or batch."
        confirmLabel={
          deletingCfg || deletingBatch ? 'Deleting…' : 'Delete'
        }
        variant="danger"
      />
    </div>
  );
}
