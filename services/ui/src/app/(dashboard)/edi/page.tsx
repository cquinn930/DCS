'use client';

import { useMemo, useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Cog, Plus } from 'lucide-react';
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

const FORMATS_API = '/api/v1/edi/formats';
const PARTNERS_API = '/api/v1/edi/partners';
const BATCHES_API = '/api/v1/edi/batches';

const DIRECTIONS = ['inbound', 'outbound'] as const;
const PROTOCOLS = ['sftp', 'api', 'email'] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type EdiFormatRow = {
  id: string;
  code: string;
  name: string;
  direction: string;
  format_type: string;
  active?: boolean;
};

type EdiPartnerRow = {
  id: string;
  name: string;
  code: string;
  format_id?: string;
  format_name?: string;
  protocol: string;
  active?: boolean;
};

type EdiBatchRow = {
  id: string;
  partner_id?: string;
  partner_name?: string;
  direction: string;
  status: string;
  record_count?: number;
  created_at?: string;
};

export default function EdiPage() {
  const [tab, setTab] = useState<'formats' | 'partners' | 'batches'>(
    'formats'
  );
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedFormatId, setSelectedFormatId] = useState<string | null>(null);
  const [selectedPartnerId, setSelectedPartnerId] = useState<string | null>(
    null
  );
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [drawerKind, setDrawerKind] = useState<'format' | 'partner' | 'batch'>(
    'format'
  );

  const listParams = { page: pageIndex + 1, page_size: pageSize };

  const { data: formats, total: fTotal, isLoading: fLoading, mutate: mf } =
    useApiList<EdiFormatRow>(FORMATS_API, listParams);
  const { data: partners, total: pTotal, isLoading: pLoading, mutate: mp } =
    useApiList<EdiPartnerRow>(PARTNERS_API, listParams);
  const { data: batches, total: bTotal, isLoading: bLoading, mutate: mb } =
    useApiList<EdiBatchRow>(BATCHES_API, listParams);

  const { data: fmtDetail, isLoading: fmtLoading, mutate: mutateFmt } =
    useApiDetail<EdiFormatRow & { field_definitions?: unknown; delimiter?: string }>(
      FORMATS_API,
      selectedFormatId ?? undefined
    );
  const { data: ptnDetail, isLoading: ptnLoading, mutate: mutatePtn } =
    useApiDetail<
      EdiPartnerRow & { connection_config?: unknown }
    >(PARTNERS_API, selectedPartnerId ?? undefined);
  const { data: batchDetail, isLoading: batchLoading, mutate: mutateBatch } =
    useApiDetail<EdiBatchRow & { data?: unknown }>(
      BATCHES_API,
      selectedBatchId ?? undefined
    );

  const { trigger: createFormat, isMutating: creatingF } = useApiMutation(
    'POST',
    FORMATS_API
  );
  const { trigger: patchFormat, isMutating: patchingF } = useApiMutation(
    'PATCH',
    FORMATS_API
  );
  const { trigger: deleteFormat, isMutating: deletingF } = useApiMutation(
    'DELETE',
    FORMATS_API
  );

  const { trigger: createPartner, isMutating: creatingP } = useApiMutation(
    'POST',
    PARTNERS_API
  );
  const { trigger: patchPartner, isMutating: patchingP } = useApiMutation(
    'PATCH',
    PARTNERS_API
  );
  const { trigger: deletePartner, isMutating: deletingP } = useApiMutation(
    'DELETE',
    PARTNERS_API
  );

  const { trigger: createBatch, isMutating: creatingB } = useApiMutation(
    'POST',
    BATCHES_API
  );
  const { trigger: deleteBatch, isMutating: deletingB } = useApiMutation(
    'DELETE',
    BATCHES_API
  );
  const { trigger: processBatch, isMutating: processing } = useApiMutation(
    'POST',
    BATCHES_API
  );

  const [formFormat, setFormFormat] = useState({
    code: '',
    name: '',
    direction: 'inbound',
    format_type: 'fixed',
    field_definitions: '[]',
    delimiter: ',',
  });
  const [formPartner, setFormPartner] = useState({
    name: '',
    code: '',
    format_id: '',
    protocol: 'sftp',
    connection_config: '{}',
  });
  const [formBatch, setFormBatch] = useState({
    partner_id: '',
    direction: 'inbound',
    data: '{}',
  });

  const formatRows = formats ?? [];
  const partnerRows = partners ?? [];
  const batchRows = batches ?? [];

  const filteredFormats = useMemo(() => {
    if (!search.trim()) return formatRows;
    const q = search.toLowerCase();
    return formatRows.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.direction.toLowerCase().includes(q)
    );
  }, [formatRows, search]);

  const filteredPartners = useMemo(() => {
    if (!search.trim()) return partnerRows;
    const q = search.toLowerCase();
    return partnerRows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.code.toLowerCase().includes(q)
    );
  }, [partnerRows, search]);

  const filteredBatches = useMemo(() => {
    if (!search.trim()) return batchRows;
    const q = search.toLowerCase();
    return batchRows.filter(
      (r) =>
        (r.partner_name ?? '').toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [batchRows, search]);

  const pageCount =
    tab === 'formats'
      ? Math.max(1, Math.ceil((fTotal ?? 0) / pageSize))
      : tab === 'partners'
        ? Math.max(1, Math.ceil((pTotal ?? 0) / pageSize))
        : Math.max(1, Math.ceil((bTotal ?? 0) / pageSize));

  const formatColumns: ColumnDef<EdiFormatRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'direction', header: 'Direction' },
    { accessorKey: 'format_type', header: 'Format Type' },
    {
      accessorKey: 'active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() === false ? 'inactive' : 'active'} />
      ),
    },
  ];

  const partnerColumns: ColumnDef<EdiPartnerRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'code', header: 'Code' },
    {
      accessorKey: 'format_name',
      header: 'Format',
      cell: ({ row }) => row.original.format_name ?? row.original.format_id ?? '—',
    },
    { accessorKey: 'protocol', header: 'Protocol' },
    {
      accessorKey: 'active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() === false ? 'inactive' : 'active'} />
      ),
    },
  ];

  const batchColumns: ColumnDef<EdiBatchRow>[] = [
    {
      accessorKey: 'partner_name',
      header: 'Partner',
      cell: ({ row }) => row.original.partner_name ?? row.original.partner_id ?? '—',
    },
    { accessorKey: 'direction', header: 'Direction' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    { accessorKey: 'record_count', header: 'Record Count' },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
  ];

  function openCreate(kind: 'format' | 'partner' | 'batch') {
    setDrawerKind(kind);
    setEditMode(false);
    if (kind === 'format') {
      setFormFormat({
        code: '',
        name: '',
        direction: 'inbound',
        format_type: 'fixed',
        field_definitions: '[]',
        delimiter: ',',
      });
    } else if (kind === 'partner') {
      setFormPartner({
        name: '',
        code: '',
        format_id: formatRows[0]?.id ?? '',
        protocol: 'sftp',
        connection_config: '{}',
      });
    } else {
      setFormBatch({
        partner_id: partnerRows[0]?.id ?? '',
        direction: 'inbound',
        data: '{}',
      });
    }
    setDrawerOpen(true);
  }

  function openEdit(kind: 'format' | 'partner') {
    setDrawerKind(kind);
    if (kind === 'format' && fmtDetail) {
      setEditMode(true);
      setFormFormat({
        code: fmtDetail.code,
        name: fmtDetail.name,
        direction: fmtDetail.direction,
        format_type: fmtDetail.format_type,
        field_definitions: JSON.stringify(
          fmtDetail.field_definitions ?? [],
          null,
          2
        ),
        delimiter: fmtDetail.delimiter ?? ',',
      });
      setDrawerOpen(true);
    } else if (kind === 'partner' && ptnDetail) {
      setEditMode(true);
      setFormPartner({
        name: ptnDetail.name,
        code: ptnDetail.code,
        format_id: ptnDetail.format_id ?? '',
        protocol: ptnDetail.protocol,
        connection_config: JSON.stringify(
          ptnDetail.connection_config ?? {},
          null,
          2
        ),
      });
      setDrawerOpen(true);
    }
  }

  async function handleSubmit() {
    if (drawerKind === 'format') {
      let defs: unknown;
      try {
        defs = JSON.parse(formFormat.field_definitions || '[]') as unknown;
      } catch {
        return;
      }
      const payload: Record<string, unknown> = {
        code: formFormat.code,
        name: formFormat.name,
        direction: formFormat.direction,
        format_type: formFormat.format_type,
        field_definitions: defs,
        delimiter: formFormat.delimiter || undefined,
      };
      if (!editMode) await createFormat(payload);
      else if (selectedFormatId)
        await patchFormat(payload, `/${selectedFormatId}`);
      await mf();
      if (selectedFormatId) await mutateFmt();
    } else if (drawerKind === 'partner') {
      let cfg: unknown;
      try {
        cfg = JSON.parse(formPartner.connection_config || '{}') as unknown;
      } catch {
        return;
      }
      const payload: Record<string, unknown> = {
        name: formPartner.name,
        code: formPartner.code,
        format_id: formPartner.format_id,
        protocol: formPartner.protocol,
        connection_config: cfg,
      };
      if (!editMode) await createPartner(payload);
      else if (selectedPartnerId)
        await patchPartner(payload, `/${selectedPartnerId}`);
      await mp();
      if (selectedPartnerId) await mutatePtn();
    } else {
      let dataParsed: unknown;
      try {
        dataParsed = JSON.parse(formBatch.data || '{}') as unknown;
      } catch {
        return;
      }
      await createBatch({
        partner_id: formBatch.partner_id,
        direction: formBatch.direction,
        data: dataParsed,
      });
      await mb();
    }
    setDrawerOpen(false);
  }

  async function confirmDelete() {
    try {
      if (tab === 'formats' && selectedFormatId) {
        await deleteFormat(undefined, `/${selectedFormatId}`);
        setSelectedFormatId(null);
        await mf();
      } else if (tab === 'partners' && selectedPartnerId) {
        await deletePartner(undefined, `/${selectedPartnerId}`);
        setSelectedPartnerId(null);
        await mp();
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

  async function handleProcessBatch() {
    if (!selectedBatchId) return;
    await processBatch(undefined, `/${selectedBatchId}/process`);
    await mutateBatch();
    await mb();
  }

  const isSubmitting =
    creatingF ||
    patchingF ||
    creatingP ||
    patchingP ||
    creatingB;

  return (
    <div className="space-y-6">
      <PageHeader
        title="EDI"
        subtitle="Exchange formats, trading partners, and batches"
        actions={
          <div className="flex flex-wrap gap-2">
            {tab === 'formats' ? (
              <button
                type="button"
                onClick={() => openCreate('format')}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              >
                <Plus className="h-4 w-4" />
                New format
              </button>
            ) : null}
            {tab === 'partners' ? (
              <button
                type="button"
                onClick={() => openCreate('partner')}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              >
                <Plus className="h-4 w-4" />
                New partner
              </button>
            ) : null}
            {tab === 'batches' ? (
              <button
                type="button"
                onClick={() => openCreate('batch')}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              >
                <Plus className="h-4 w-4" />
                New batch
              </button>
            ) : null}
          </div>
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border">
        {(['formats', 'partners', 'batches'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t);
              setSelectedFormatId(null);
              setSelectedPartnerId(null);
              setSelectedBatchId(null);
              setPageIndex(0);
            }}
            className={`border-b-2 px-3 py-2 text-sm font-medium capitalize ${
              tab === t
                ? 'border-primary-600 text-primary-700 dark:text-primary-400'
                : 'border-transparent text-neutral-600 hover:text-foreground'
            }`}
          >
            {t === 'formats' ? 'Formats' : t === 'partners' ? 'Partners' : 'Batches'}
          </button>
        ))}
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder={`Search ${tab}…`}
      />

      {tab === 'formats' ? (
        <DataTable<EdiFormatRow>
          columns={formatColumns}
          data={filteredFormats}
          isLoading={fLoading}
          emptyMessage="No EDI formats"
          onRowClick={(row) => {
            setSelectedFormatId(row.id);
            setDrawerKind('format');
          }}
          pageCount={pageCount}
          pageIndex={pageIndex}
          pageSize={pageSize}
          onPageChange={setPageIndex}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setPageIndex(0);
          }}
        />
      ) : tab === 'partners' ? (
        <DataTable<EdiPartnerRow>
          columns={partnerColumns}
          data={filteredPartners}
          isLoading={pLoading}
          emptyMessage="No partners"
          onRowClick={(row) => {
            setSelectedPartnerId(row.id);
            setDrawerKind('partner');
          }}
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
        <DataTable<EdiBatchRow>
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

      {tab === 'formats' && selectedFormatId && (
        <DetailPanel
          title={fmtDetail?.name ?? 'Format'}
          subtitle={fmtDetail?.code}
          onClose={() => setSelectedFormatId(null)}
          onEdit={() => openEdit('format')}
          onDelete={() => setDeleteOpen(true)}
        >
          {fmtLoading || !fmtDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Direction">{fmtDetail.direction}</FieldGroup>
              <FieldGroup label="Format type">{fmtDetail.format_type}</FieldGroup>
              <FieldGroup label="Delimiter">{fmtDetail.delimiter ?? '—'}</FieldGroup>
              <FieldGroup label="Active">
                <StatusBadge
                  status={fmtDetail.active === false ? 'inactive' : 'active'}
                />
              </FieldGroup>
              <div className="sm:col-span-2">
                <FieldGroup label="Field definitions">
                  <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-2 text-xs dark:bg-neutral-900/50">
                    {JSON.stringify(fmtDetail.field_definitions ?? [], null, 2)}
                  </pre>
                </FieldGroup>
              </div>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {tab === 'partners' && selectedPartnerId && (
        <DetailPanel
          title={ptnDetail?.name ?? 'Partner'}
          subtitle={ptnDetail?.code}
          onClose={() => setSelectedPartnerId(null)}
          onEdit={() => openEdit('partner')}
          onDelete={() => setDeleteOpen(true)}
        >
          {ptnLoading || !ptnDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Protocol">{ptnDetail.protocol}</FieldGroup>
              <FieldGroup label="Format ID">{ptnDetail.format_id ?? '—'}</FieldGroup>
              <FieldGroup label="Active">
                <StatusBadge
                  status={ptnDetail.active === false ? 'inactive' : 'active'}
                />
              </FieldGroup>
              <div className="sm:col-span-2">
                <FieldGroup label="Connection config">
                  <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-2 text-xs dark:bg-neutral-900/50">
                    {JSON.stringify(ptnDetail.connection_config ?? {}, null, 2)}
                  </pre>
                </FieldGroup>
              </div>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {tab === 'batches' && selectedBatchId && (
        <DetailPanel
          title="EDI batch"
          subtitle={batchDetail?.partner_name ?? batchDetail?.partner_id}
          onClose={() => setSelectedBatchId(null)}
          onDelete={() => setDeleteOpen(true)}
        >
          {batchLoading || !batchDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Direction">{batchDetail.direction}</FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={batchDetail.status} />
                </FieldGroup>
                <FieldGroup label="Record count">
                  {batchDetail.record_count ?? '—'}
                </FieldGroup>
                <FieldGroup label="Created">{fmtDate(batchDetail.created_at)}</FieldGroup>
              </FieldGrid>
              {batchDetail.data != null && (
                <pre className="mt-4 max-h-48 overflow-auto rounded-md border border-border bg-neutral-50 p-3 text-xs dark:bg-neutral-900/50">
                  {JSON.stringify(batchDetail.data, null, 2)}
                </pre>
              )}
              <div className="mt-6 border-t border-border pt-4">
                <button
                  type="button"
                  disabled={processing}
                  onClick={handleProcessBatch}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  <Cog className="h-4 w-4" />
                  {processing ? 'Processing…' : 'Process'}
                </button>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={
          drawerKind === 'format'
            ? editMode
              ? 'Edit format'
              : 'New exchange format'
            : drawerKind === 'partner'
              ? editMode
                ? 'Edit partner'
                : 'New partner'
              : 'New batch'
        }
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        submitLabel={
          drawerKind === 'batch' ? 'Create batch' : editMode ? 'Save' : 'Create'
        }
      >
        {drawerKind === 'format' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Code" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                value={formFormat.code}
                onChange={(e) =>
                  setFormFormat((f) => ({ ...f, code: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Name" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formFormat.name}
                onChange={(e) =>
                  setFormFormat((f) => ({ ...f, name: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Direction" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formFormat.direction}
                onChange={(e) =>
                  setFormFormat((f) => ({ ...f, direction: e.target.value }))
                }
              >
                {DIRECTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Format type" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formFormat.format_type}
                onChange={(e) =>
                  setFormFormat((f) => ({ ...f, format_type: e.target.value }))
                }
                placeholder="x12, fixed, delimited…"
              />
            </FormField>
            <FormField label="Field definitions (JSON)">
              <textarea
                rows={10}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                value={formFormat.field_definitions}
                onChange={(e) =>
                  setFormFormat((f) => ({
                    ...f,
                    field_definitions: e.target.value,
                  }))
                }
              />
            </FormField>
            <FormField label="Delimiter">
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formFormat.delimiter}
                onChange={(e) =>
                  setFormFormat((f) => ({ ...f, delimiter: e.target.value }))
                }
              />
            </FormField>
          </div>
        ) : drawerKind === 'partner' ? (
          <div className="flex flex-col gap-4">
            <FormField label="Name" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formPartner.name}
                onChange={(e) =>
                  setFormPartner((f) => ({ ...f, name: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Code" required>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                value={formPartner.code}
                onChange={(e) =>
                  setFormPartner((f) => ({ ...f, code: e.target.value }))
                }
              />
            </FormField>
            <FormField label="Format" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formPartner.format_id}
                onChange={(e) =>
                  setFormPartner((f) => ({ ...f, format_id: e.target.value }))
                }
              >
                {formatRows.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.code} — {f.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Protocol" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formPartner.protocol}
                onChange={(e) =>
                  setFormPartner((f) => ({ ...f, protocol: e.target.value }))
                }
              >
                {PROTOCOLS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Connection config (JSON)">
              <textarea
                rows={8}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                value={formPartner.connection_config}
                onChange={(e) =>
                  setFormPartner((f) => ({
                    ...f,
                    connection_config: e.target.value,
                  }))
                }
              />
            </FormField>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <FormField label="Partner" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formBatch.partner_id}
                onChange={(e) =>
                  setFormBatch((f) => ({ ...f, partner_id: e.target.value }))
                }
              >
                {partnerRows.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Direction" required>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={formBatch.direction}
                onChange={(e) =>
                  setFormBatch((f) => ({ ...f, direction: e.target.value }))
                }
              >
                {DIRECTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="Data (JSON)">
              <textarea
                rows={12}
                className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                value={formBatch.data}
                onChange={(e) =>
                  setFormBatch((f) => ({ ...f, data: e.target.value }))
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
        title="Delete this record?"
        message="This action may not be reversible depending on API rules."
        confirmLabel={
          deletingF || deletingP || deletingB ? 'Deleting…' : 'Delete'
        }
        variant="danger"
      />
    </div>
  );
}
