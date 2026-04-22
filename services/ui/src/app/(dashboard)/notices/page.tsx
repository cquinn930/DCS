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
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiDetail, useApiList, useApiMutation } from '@/hooks/useApi';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/notices';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const NOTICE_TYPES = [
  'initial_communication',
  'validation_notice',
  'dispute_acknowledgement',
  'payment_confirmation',
  'settlement_offer',
  'post_judgment_disclosure',
  'cease_communication',
] as const;

type NoticeRow = {
  id: string;
  account_id: string;
  notice_type: string;
  status: string;
  sent_at: string | null;
  scheduled_at: string | null;
};

export default function NoticesPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);

  const listParams = {
    page: pageIndex + 1,
    page_size: pageSize,
  };

  const { data, total, isLoading, mutate } = useApiList<NoticeRow>(
    API,
    listParams
  );
  const { data: detail, isLoading: detailLoading, mutate: mutateDetail } =
    useApiDetail<
      NoticeRow & {
        template_id?: string;
        template_version?: string;
        channel?: string;
        recipient?: string;
      }
    >(API, selectedId ?? undefined);

  const { trigger: createNotice, isMutating: creating } = useApiMutation(
    'POST',
    API
  );
  const { trigger: patchNotice, isMutating: patching } = useApiMutation(
    'PATCH',
    API
  );
  const { trigger: deleteNotice, isMutating: deleting } = useApiMutation(
    'DELETE',
    API
  );
  const { trigger: sendNotice, isMutating: sending } = useApiMutation(
    'POST',
    API
  );

  const [form, setForm] = useState({
    account_id: '',
    notice_type: 'validation_notice' as (typeof NOTICE_TYPES)[number],
    content: '',
    channel: 'mail',
    recipient: '',
  });

  const rows = (data ?? []).filter((row) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      row.id.toLowerCase().includes(q) ||
      row.account_id.toLowerCase().includes(q) ||
      row.notice_type.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.max(1, Math.ceil((total ?? 0) / pageSize));

  const columns: ColumnDef<NoticeRow>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    {
      accessorKey: 'account_id',
      header: 'Account',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{String(getValue()).slice(0, 8)}…</span>
      ),
    },
    { accessorKey: 'notice_type', header: 'Type' },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue())} />,
    },
    {
      accessorKey: 'sent_at',
      header: 'Sent Date',
      cell: ({ getValue }) => fmtDate((getValue() as string) ?? undefined),
    },
    {
      accessorKey: 'scheduled_at',
      header: 'Due Date',
      cell: ({ getValue }) => fmtDate((getValue() as string) ?? undefined),
    },
  ];

  function openCreate() {
    setEditMode(false);
    setForm({
      account_id: '',
      notice_type: 'validation_notice',
      content: '',
      channel: 'mail',
      recipient: '',
    });
    setDrawerOpen(true);
  }

  function openEdit() {
    if (!detail) return;
    setEditMode(true);
    setForm({
      account_id: detail.account_id,
      notice_type: detail.notice_type as (typeof NOTICE_TYPES)[number],
      content: '',
      channel: detail.channel ?? 'mail',
      recipient: detail.recipient ?? '',
    });
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (!editMode) {
      await createNotice({
        account_id: form.account_id,
        notice_type: form.notice_type,
        template_id: 'MANUAL',
        template_version: '1',
        channel: form.channel,
        recipient: form.recipient || form.content.slice(0, 500) || 'Pending',
        content_hash: form.content
          ? btoa(unescape(encodeURIComponent(form.content))).slice(0, 64)
          : null,
      });
    } else if (selectedId) {
      await patchNotice(
        {
          notice_type: form.notice_type,
          channel: form.channel,
          recipient: form.recipient,
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
    await deleteNotice(undefined, `/${selectedId}`);
    setDeleteOpen(false);
    setSelectedId(null);
    await mutate();
  }

  async function confirmSend() {
    if (!selectedId) return;
    await sendNotice(undefined, `/${selectedId}/send`);
    setSendOpen(false);
    await mutateDetail();
    await mutate();
  }

  const d = detail;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notices"
        subtitle={
          user
            ? `Regulatory and operational notices · ${user.email}`
            : 'Regulatory and operational notices'
        }
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus className="h-4 w-4" />
            New notice
          </button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search notices…"
      />

      <DataTable<NoticeRow>
        columns={columns}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No notices found"
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
          title={`Notice ${d?.id?.slice(0, 8) ?? ''}…`}
          subtitle={d?.notice_type.replace(/_/g, ' ')}
          onClose={() => setSelectedId(null)}
          onEdit={openEdit}
          onDelete={() => setDeleteOpen(true)}
        >
          {detailLoading || !d ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Account ID">{d.account_id}</FieldGroup>
                <FieldGroup label="Type">{d.notice_type}</FieldGroup>
                <FieldGroup label="Status">
                  <StatusBadge status={d.status} />
                </FieldGroup>
                <FieldGroup label="Sent">{fmtDate(d.sent_at ?? undefined)}</FieldGroup>
                <FieldGroup label="Scheduled / due">
                  {fmtDate(d.scheduled_at ?? undefined)}
                </FieldGroup>
                <FieldGroup label="Recipient">
                  {(d as { recipient?: string }).recipient ?? '—'}
                </FieldGroup>
              </FieldGrid>
              {d.status === 'pending' || d.status === 'failed' ? (
                <div className="mt-4 border-t border-border pt-4">
                  <button
                    type="button"
                    onClick={() => setSendOpen(true)}
                    className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
                  >
                    Send notice
                  </button>
                </div>
              ) : null}
            </>
          )}
        </DetailPanel>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editMode ? 'Edit notice' : 'New notice'}
        onSubmit={handleSubmit}
        isSubmitting={creating || patching}
        submitLabel={editMode ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Account ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={form.account_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, account_id: e.target.value }))
              }
              disabled={editMode}
            />
          </FormField>
          <FormField label="Notice type" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.notice_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  notice_type: e.target.value as (typeof NOTICE_TYPES)[number],
                }))
              }
            >
              {NOTICE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Channel" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.channel}
              onChange={(e) =>
                setForm((f) => ({ ...f, channel: e.target.value }))
              }
            >
              <option value="mail">mail</option>
              <option value="email">email</option>
              <option value="sms">sms</option>
            </select>
          </FormField>
          <FormField label="Recipient" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.recipient}
              onChange={(e) =>
                setForm((f) => ({ ...f, recipient: e.target.value }))
              }
              placeholder="Name / address line"
            />
          </FormField>
          <FormField label="Content">
            <textarea
              className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.content}
              onChange={(e) =>
                setForm((f) => ({ ...f, content: e.target.value }))
              }
              placeholder="Notice body (hashed for audit)"
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={confirmDelete}
        title="Delete notice?"
        message="This removes the notice record."
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />

      <ConfirmDialog
        open={sendOpen}
        onClose={() => setSendOpen(false)}
        onConfirm={confirmSend}
        title="Send this notice?"
        message="Marks the notice as sent and sets the sent timestamp."
        confirmLabel={sending ? 'Sending…' : 'Send'}
        variant="info"
      />
    </div>
  );
}
