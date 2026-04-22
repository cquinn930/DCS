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
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/masking/policies';

type MaskingPolicyRow = {
  id: string;
  entity_type: string;
  field_name: string;
  mask_type: string;
  exempt_roles: unknown[];
  is_active: boolean;
  description?: string | null;
};

const ENTITY_TYPES = ['consumer', 'account', 'payment'] as const;
const MASK_TYPES = [
  'full',
  'partial_last4',
  'partial_first2',
  'hash',
  'redact',
  'none',
] as const;

const ROLE_OPTIONS = [
  'admin',
  'owner',
  'collector',
  'manager',
  'auditor',
  'readonly',
];

export default function MaskingPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const listParams = { page: pageIndex + 1, page_size: pageSize };
  const { data, total, isLoading, mutate } =
    useApiList<MaskingPolicyRow>(API, listParams);
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<MaskingPolicyRow>(API, selectedId ?? undefined);

  const { trigger: createPol, isMutating: creating } = useApiMutation<
    Record<string, unknown>,
    MaskingPolicyRow
  >('POST', API);
  const { trigger: patchPol, isMutating: patching } = useApiMutation<
    Record<string, unknown>,
    MaskingPolicyRow
  >('PATCH', API);

  const [form, setForm] = useState({
    entity_type: 'consumer',
    field_name: 'ssn',
    mask_type: 'partial_last4',
    exempt_roles: [] as string[],
    is_active: true,
    description: '',
  });

  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        r.entity_type.toLowerCase().includes(q) ||
        r.field_name.toLowerCase().includes(q) ||
        r.mask_type.toLowerCase().includes(q)
    );
  }, [data, search]);

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<MaskingPolicyRow>[] = [
    { accessorKey: 'entity_type', header: 'Entity type' },
    { accessorKey: 'field_name', header: 'Field name' },
    { accessorKey: 'mask_type', header: 'Mask type' },
    {
      id: 'roles',
      header: 'Roles exempt',
      cell: ({ row }) => {
        const r = row.original.exempt_roles;
        if (Array.isArray(r) && r.length)
          return r.map((x) => String(x)).join(', ');
        return '—';
      },
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() ? 'active' : 'inactive'} />
      ),
    },
  ];

  function toggleRole(role: string) {
    setForm((f) => {
      const has = f.exempt_roles.includes(role);
      return {
        ...f,
        exempt_roles: has
          ? f.exempt_roles.filter((x) => x !== role)
          : [...f.exempt_roles, role],
      };
    });
  }

  function openCreate() {
    setEditMode(false);
    setForm({
      entity_type: 'consumer',
      field_name: 'ssn',
      mask_type: 'partial_last4',
      exempt_roles: [],
      is_active: true,
      description: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    const ex = Array.isArray(detail.exempt_roles)
      ? detail.exempt_roles.map((x) => String(x))
      : [];
    setForm({
      entity_type: detail.entity_type,
      field_name: detail.field_name,
      mask_type: detail.mask_type,
      exempt_roles: ex,
      is_active: detail.is_active,
      description: detail.description ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const payload = {
      entity_type: form.entity_type,
      field_name: form.field_name,
      mask_type: form.mask_type,
      exempt_roles: form.exempt_roles,
      is_active: form.is_active,
      description: form.description || null,
    };
    if (!editMode) {
      await createPol(payload);
    } else if (selectedId) {
      await patchPol(payload, `/${selectedId}`);
      await mutateDetail();
    }
    setDrawerOpen(false);
    await mutate();
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Data masking"
        subtitle={
          user
            ? `Field-level masking policies · ${user.email}`
            : 'Control how sensitive fields are shown by role'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New policy
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search policies…"
      />

      <DataTable<MaskingPolicyRow>
        columns={columns}
        data={filtered}
        isLoading={isLoading}
        emptyMessage="No masking policies"
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
          title={d ? `${d.entity_type}.${d.field_name}` : 'Policy'}
          subtitle={d?.mask_type}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Entity type">{d.entity_type}</FieldGroup>
              <FieldGroup label="Field name">{d.field_name}</FieldGroup>
              <FieldGroup label="Mask type">{d.mask_type}</FieldGroup>
              <FieldGroup label="Active">
                <StatusBadge status={d.is_active ? 'active' : 'inactive'} />
              </FieldGroup>
              <FieldGroup label="Roles exempt">
                {Array.isArray(d.exempt_roles) && d.exempt_roles.length
                  ? d.exempt_roles.map((x) => String(x)).join(', ')
                  : '—'}
              </FieldGroup>
              <FieldGroup label="Description">
                {d.description ?? '—'}
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit policy' : 'Create masking policy'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Entity type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.entity_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, entity_type: e.target.value }))
              }
            >
              {ENTITY_TYPES.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Field name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.field_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, field_name: e.target.value }))
              }
              placeholder="ssn, account_number, …"
            />
          </FormField>
          <FormField label="Mask type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.mask_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, mask_type: e.target.value }))
              }
            >
              {MASK_TYPES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Roles exempt (checkboxes)">
            <div className="flex flex-col gap-2 rounded-md border border-border p-3">
              {ROLE_OPTIONS.map((role) => (
                <label key={role} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.exempt_roles.includes(role)}
                    onChange={() => toggleRole(role)}
                  />
                  {role}
                </label>
              ))}
            </div>
          </FormField>
          <FormField label="Description">
            <textarea
              className="min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) =>
                setForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>
    </div>
  );
}
