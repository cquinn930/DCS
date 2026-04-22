'use client';

import { useState } from 'react';
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
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/consumers';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

type ContactMethod = {
  id: string;
  contact_type: string;
  value: string;
  is_primary: boolean;
};

type ConsumerRow = {
  id: string;
  first_name: string;
  last_name: string;
  contact_methods: ContactMethod[];
  ssn_last_four?: string | null;
};

type ConsumerDetail = ConsumerRow & {
  date_of_birth?: string | null;
  language_preference?: string;
  timezone?: string;
};

function maskSsn(last?: string | null) {
  if (!last || last.length < 4) return '—';
  return `***-**-${last}`;
}

/** List API does not return structured address fields on contact methods. */
function listState(_cm: ContactMethod[]) {
  return '—';
}

export default function ConsumersPage() {
  const { user, hasPermission } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
    search: search.trim() || undefined,
  };

  const { data, total, isLoading, mutate } = useApiList<ConsumerRow>(
    API,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<ConsumerDetail>(API, selectedId ?? undefined);

  const { trigger: createConsumer, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: patchConsumer, isMutating: patching } = useApiMutation(
    'PATCH',
    API
  );
  const { trigger: deleteConsumer, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    ssn_last_four: '',
    address_line_1: '',
    address_line_2: '',
    city: '',
    state: '',
    postal_code: '',
    phone: '',
    email: '',
  });

  const rows = data ?? [];
  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<ConsumerRow>[] = [
    {
      id: 'name',
      header: 'Name',
      cell: ({ row }) =>
        `${row.original.first_name} ${row.original.last_name}`,
    },
    {
      id: 'email',
      header: 'Email',
      cell: ({ row }) => {
        const e = row.original.contact_methods?.find(
          (c) => c.contact_type === 'email'
        );
        return e?.value ?? '—';
      },
    },
    {
      id: 'phone',
      header: 'Phone',
      cell: ({ row }) => {
        const p = row.original.contact_methods?.find((c) =>
          c.contact_type.startsWith('phone')
        );
        return p?.value ?? '—';
      },
    },
    {
      id: 'state',
      header: 'State',
      cell: ({ row }) => listState(row.original.contact_methods ?? []),
    },
    {
      id: 'ssn',
      header: 'SSN Last 4',
      cell: ({ row }) => maskSsn(row.original.ssn_last_four),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      first_name: '',
      last_name: '',
      date_of_birth: '',
      ssn_last_four: '',
      address_line_1: '',
      address_line_2: '',
      city: '',
      state: '',
      postal_code: '',
      phone: '',
      email: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    const email = detail.contact_methods?.find(
      (c) => c.contact_type === 'email'
    );
    const phone = detail.contact_methods?.find((c) =>
      c.contact_type.startsWith('phone')
    );
    setForm({
      first_name: detail.first_name,
      last_name: detail.last_name,
      date_of_birth: detail.date_of_birth?.slice(0, 10) ?? '',
      ssn_last_four: detail.ssn_last_four ?? '',
      address_line_1: '',
      address_line_2: '',
      city: '',
      state: '',
      postal_code: '',
      phone: phone?.value ?? '',
      email: email?.value ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    const contact_methods = [
      ...(form.email
        ? [
            {
              contact_type: 'email',
              value: form.email,
              is_primary: true,
            },
          ]
        : []),
      ...(form.phone
        ? [
            {
              contact_type: 'phone_mobile',
              value: form.phone,
              is_primary: !form.email,
            },
          ]
        : []),
      ...(form.address_line_1
        ? [
            {
              contact_type: 'address_home',
              value: 'Primary',
              is_primary: !(form.email || form.phone),
              address_line_1: form.address_line_1,
              address_line_2: form.address_line_2 || undefined,
              city: form.city || undefined,
              state: form.state || undefined,
              postal_code: form.postal_code || undefined,
            },
          ]
        : []),
    ];

    if (!editMode) {
      await createConsumer({
        first_name: form.first_name,
        last_name: form.last_name,
        ssn_last_four: form.ssn_last_four || undefined,
        date_of_birth: form.date_of_birth
          ? new Date(form.date_of_birth).toISOString()
          : undefined,
        contact_methods,
      });
    } else if (selectedId) {
      await patchConsumer(
        {
          first_name: form.first_name,
          last_name: form.last_name,
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
    try {
      await deleteConsumer(undefined, `/${selectedId}`);
      setDeleteOpen(false);
      setSelectedId(null);
      await mutate();
    } catch {
      /* API may not support delete */
    }
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Consumers"
        subtitle={
          user
            ? `Consumers for your organization · ${user.email}`
            : 'Consumer records and contact methods'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            disabled={
              !user?.isOwner && !hasPermission('accounts:edit_contact')
            }
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700 disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            New consumer
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search name or external ID…"
      />

      <DataTable<ConsumerRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No consumers found"
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
          title={d ? `${d.first_name} ${d.last_name}` : 'Consumer'}
          subtitle={d ? `ID ${d.id}` : undefined}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Name">
                  {d.first_name} {d.last_name}
                </FieldGroup>
                <FieldGroup label="SSN (last 4)">
                  {maskSsn(d.ssn_last_four)}
                </FieldGroup>
                <FieldGroup label="Date of birth">
                  {fmtDate(d.date_of_birth ?? undefined)}
                </FieldGroup>
                <FieldGroup label="Language">{d.language_preference}</FieldGroup>
                <FieldGroup label="Timezone">{d.timezone}</FieldGroup>
              </FieldGrid>
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-foreground">
                  Contact methods
                </h3>
                <ul className="mt-2 divide-y divide-border rounded-md border border-border">
                  {(d.contact_methods ?? []).map((cm) => (
                    <li
                      key={cm.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                    >
                      <span className="font-medium capitalize">
                        {cm.contact_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-neutral-600 dark:text-neutral-400">
                        {cm.value}
                      </span>
                    </li>
                  ))}
                  {(!d.contact_methods || d.contact_methods.length === 0) && (
                    <li className="px-3 py-2 text-sm text-neutral-500">
                      No contact methods
                    </li>
                  )}
                </ul>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit consumer' : 'New consumer'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="First name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.first_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, first_name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Last name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.last_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, last_name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Date of birth">
            <input
              type="date"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.date_of_birth}
              onChange={(e) =>
                setForm((f) => ({ ...f, date_of_birth: e.target.value }))
              }
            />
          </FormField>
          <FormField label="SSN last four">
            <input
              maxLength={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.ssn_last_four}
              onChange={(e) =>
                setForm((f) => ({ ...f, ssn_last_four: e.target.value }))
              }
            />
          </FormField>
          {!editMode ? (
            <>
              <FormField label="Email">
                <input
                  type="email"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.email}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, email: e.target.value }))
                  }
                />
              </FormField>
              <FormField label="Phone">
                <input
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.phone}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, phone: e.target.value }))
                  }
                />
              </FormField>
              <FormField label="Address line 1">
                <input
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.address_line_1}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, address_line_1: e.target.value }))
                  }
                />
              </FormField>
              <FormField label="Address line 2">
                <input
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.address_line_2}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, address_line_2: e.target.value }))
                  }
                />
              </FormField>
              <FormField label="City">
                <input
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.city}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, city: e.target.value }))
                  }
                />
              </FormField>
              <FormField label="State">
                <input
                  maxLength={2}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.state}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      state: e.target.value.toUpperCase(),
                    }))
                  }
                />
              </FormField>
              <FormField label="Postal code">
                <input
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.postal_code}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, postal_code: e.target.value }))
                  }
                />
              </FormField>
            </>
          ) : null}
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete consumer?"
        message="Removes the consumer if supported by the API."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
