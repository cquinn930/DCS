'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { cn } from '@/lib/utils';

const API_ACTIVITY = '/api/v1/workflow/activity-codes';
const API_CHAINS = '/api/v1/workflow/workflow-chains';
const API_QUEUES = '/api/v1/workflow/work-queues';

const ACTIVITY_CATEGORIES = [
  'LETTER',
  'CALL',
  'REVIEW',
  'LEGAL',
  'FINANCIAL',
  'COMPLIANCE',
  'SKIP_TRACE',
  'SYSTEM',
  'CUSTOM',
] as const;

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type TabId = 'activity' | 'chains' | 'queues';

type ActivityCodeRow = {
  id: string;
  code: string;
  name: string;
  category: string;
  default_priority: number;
  description?: string | null;
  is_active?: boolean;
  active?: boolean;
};

type WorkflowChainRow = {
  id: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
  steps_count?: number;
  step_count?: number;
};

type WorkflowStep = {
  id?: string;
  step_order: number;
  activity_code_id: string;
  delay_days?: number | null;
  condition?: string | null;
};

type WorkflowChainDetail = WorkflowChainRow & {
  steps?: WorkflowStep[];
};

type WorkQueueRow = {
  id: string;
  name: string;
  description?: string | null;
  priority: number;
  entry_count?: number;
  entries_count?: number;
  is_active?: boolean;
};

type WorkQueueDetail = WorkQueueRow & {
  filter_criteria?: Record<string, unknown> | null;
};

type QueueEntry = {
  id: string;
  account_id?: string;
  priority?: number;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
};

function tabButtonClass(active: boolean) {
  return cn(
    'rounded-md px-4 py-2 text-sm font-medium transition-colors',
    active
      ? 'bg-primary-600 text-white shadow-sm'
      : 'border border-border bg-background text-foreground hover:bg-muted'
  );
}

export default function WorkflowPage() {
  const [activeTab, setActiveTab] = useState<TabId>('activity');

  /* Activity codes */
  const [acSearch, setAcSearch] = useState('');
  const [acPage, setAcPage] = useState(0);
  const [acPageSize, setAcPageSize] = useState(20);
  const [acSelected, setAcSelected] = useState<string | null>(null);
  const [acDrawer, setAcDrawer] = useState(false);
  const [acEdit, setAcEdit] = useState(false);
  const [acDelete, setAcDelete] = useState(false);
  const [acForm, setAcForm] = useState({
    code: '',
    name: '',
    category: 'LETTER' as (typeof ACTIVITY_CATEGORIES)[number],
    default_priority: '50',
    description: '',
    is_active: true,
  });

  const acParams = useMemo(
    () => ({ page: acPage + 1, page_size: acPageSize }),
    [acPage, acPageSize]
  );
  const {
    data: acData,
    total: acTotal,
    isLoading: acLoading,
    mutate: acMutate,
  } = useApiList<ActivityCodeRow>(API_ACTIVITY, acParams);
  const {
    data: acDetail,
    isLoading: acDetailLoading,
    mutate: acDetailMutate,
  } = useApiDetail<ActivityCodeRow>(API_ACTIVITY, acSelected ?? undefined);

  const { trigger: acCreate, isMutating: acCreating } = useApiMutation<
    Record<string, unknown>,
    ActivityCodeRow
  >('POST', API_ACTIVITY);
  const { trigger: acPatch, isMutating: acPatching } = useApiMutation<
    Record<string, unknown>,
    ActivityCodeRow
  >('PATCH', API_ACTIVITY);
  const { trigger: acDel, isMutating: acDeleting } = useApiMutation(
    'DELETE',
    API_ACTIVITY
  );

  /* Workflow chains */
  const [wcSearch, setWcSearch] = useState('');
  const [wcPage, setWcPage] = useState(0);
  const [wcPageSize, setWcPageSize] = useState(20);
  const [wcSelected, setWcSelected] = useState<string | null>(null);
  const [wcDrawer, setWcDrawer] = useState(false);
  const [wcEdit, setWcEdit] = useState(false);
  const [wcDelete, setWcDelete] = useState(false);
  const [wcForm, setWcForm] = useState({
    name: '',
    description: '',
    is_active: true,
  });

  const wcParams = useMemo(
    () => ({ page: wcPage + 1, page_size: wcPageSize }),
    [wcPage, wcPageSize]
  );
  const {
    data: wcData,
    total: wcTotal,
    isLoading: wcLoading,
    mutate: wcMutate,
  } = useApiList<WorkflowChainRow>(API_CHAINS, wcParams);
  const {
    data: wcDetail,
    isLoading: wcDetailLoading,
    mutate: wcDetailMutate,
  } = useApiDetail<WorkflowChainDetail>(API_CHAINS, wcSelected ?? undefined);

  const { trigger: wcCreate, isMutating: wcCreating } = useApiMutation<
    Record<string, unknown>,
    WorkflowChainDetail
  >('POST', API_CHAINS);
  const { trigger: wcPatch, isMutating: wcPatching } = useApiMutation<
    Record<string, unknown>,
    WorkflowChainDetail
  >('PATCH', API_CHAINS);
  const { trigger: wcDel, isMutating: wcDeleting } = useApiMutation(
    'DELETE',
    API_CHAINS
  );

  /* Work queues */
  const [wqSearch, setWqSearch] = useState('');
  const [wqPage, setWqPage] = useState(0);
  const [wqPageSize, setWqPageSize] = useState(20);
  const [wqSelected, setWqSelected] = useState<string | null>(null);
  const [wqDrawer, setWqDrawer] = useState(false);
  const [wqEdit, setWqEdit] = useState(false);
  const [wqDelete, setWqDelete] = useState(false);
  const [wqForm, setWqForm] = useState({
    name: '',
    description: '',
    priority: '100',
    filter_criteria: '{}',
    is_active: true,
  });
  const [nextPreview, setNextPreview] = useState<unknown>(null);
  const [nextLoading, setNextLoading] = useState(false);

  const wqParams = useMemo(
    () => ({ page: wqPage + 1, page_size: wqPageSize }),
    [wqPage, wqPageSize]
  );
  const {
    data: wqData,
    total: wqTotal,
    isLoading: wqLoading,
    mutate: wqMutate,
  } = useApiList<WorkQueueRow>(API_QUEUES, wqParams);
  const {
    data: wqDetail,
    isLoading: wqDetailLoading,
    mutate: wqDetailMutate,
  } = useApiDetail<WorkQueueDetail>(API_QUEUES, wqSelected ?? undefined);

  const entriesPath =
    wqSelected != null
      ? `${API_QUEUES.replace(/\/$/, '')}/${wqSelected}/entries`
      : null;
  const {
    data: wqEntries,
    isLoading: wqEntriesLoading,
    mutate: wqEntriesMutate,
  } = useApiList<QueueEntry>(entriesPath, { page: 1, page_size: 100 });

  const { trigger: wqCreate, isMutating: wqCreating } = useApiMutation<
    Record<string, unknown>,
    WorkQueueDetail
  >('POST', API_QUEUES);
  const { trigger: wqPatch, isMutating: wqPatching } = useApiMutation<
    Record<string, unknown>,
    WorkQueueDetail
  >('PATCH', API_QUEUES);
  const { trigger: wqDel, isMutating: wqDeleting } = useApiMutation(
    'DELETE',
    API_QUEUES
  );

  useEffect(() => {
    setAcSelected(null);
    setWcSelected(null);
    setWqSelected(null);
    setNextPreview(null);
  }, [activeTab]);

  const acFiltered = useMemo(() => {
    const rows = acData ?? [];
    if (!acSearch.trim()) return rows;
    const q = acSearch.toLowerCase();
    return rows.filter(
      (r) =>
        r.code.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q)
    );
  }, [acData, acSearch]);

  const wcFiltered = useMemo(() => {
    const rows = wcData ?? [];
    if (!wcSearch.trim()) return rows;
    const q = wcSearch.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.description ?? '').toLowerCase().includes(q)
    );
  }, [wcData, wcSearch]);

  const wqFiltered = useMemo(() => {
    const rows = wqData ?? [];
    if (!wqSearch.trim()) return rows;
    const q = wqSearch.toLowerCase();
    return rows.filter((r) => r.name.toLowerCase().includes(q));
  }, [wqData, wqSearch]);

  const acPageCount = Math.max(1, Math.ceil((acTotal ?? 0) / acPageSize));
  const wcPageCount = Math.max(1, Math.ceil((wcTotal ?? 0) / wcPageSize));
  const wqPageCount = Math.max(1, Math.ceil((wqTotal ?? 0) / wqPageSize));

  const acColumns: ColumnDef<ActivityCodeRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'category', header: 'Category' },
    {
      accessorKey: 'default_priority',
      header: 'Default Priority',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => {
        const v = row.original.is_active ?? row.original.active ?? true;
        return <StatusBadge status={v ? 'active' : 'closed'} />;
      },
    },
  ];

  const wcColumns: ColumnDef<WorkflowChainRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ getValue }) => {
        const t = String(getValue() ?? '');
        return (
          <span className="line-clamp-2 max-w-xs" title={t}>
            {t || '—'}
          </span>
        );
      },
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => (
        <StatusBadge status={row.original.is_active ? 'active' : 'closed'} />
      ),
    },
    {
      id: 'steps',
      header: 'Steps Count',
      cell: ({ row }) => {
        const n =
          row.original.steps_count ??
          row.original.step_count ??
          '—';
        return String(n);
      },
    },
  ];

  const wqColumns: ColumnDef<WorkQueueRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    {
      accessorKey: 'priority',
      header: 'Priority',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
    {
      id: 'entries',
      header: 'Entry Count',
      cell: ({ row }) =>
        String(
          row.original.entry_count ??
            row.original.entries_count ??
            '—'
        ),
    },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => (
        <StatusBadge status={row.original.is_active ? 'active' : 'closed'} />
      ),
    },
  ];

  function openAcCreate() {
    setAcEdit(false);
    setAcForm({
      code: '',
      name: '',
      category: 'LETTER',
      default_priority: '50',
      description: '',
      is_active: true,
    });
    setAcDrawer(true);
  }

  function openAcEdit() {
    if (!acDetail) return;
    setAcEdit(true);
    setAcForm({
      code: acDetail.code,
      name: acDetail.name,
      category: (acDetail.category as (typeof ACTIVITY_CATEGORIES)[number]) ?? 'CUSTOM',
      default_priority: String(acDetail.default_priority ?? 0),
      description: acDetail.description ?? '',
      is_active: acDetail.is_active ?? acDetail.active ?? true,
    });
    setAcDrawer(true);
  }

  async function submitAc() {
    const body = {
      code: acForm.code.trim(),
      name: acForm.name.trim(),
      category: acForm.category,
      default_priority: parseInt(acForm.default_priority, 10) || 0,
      description: acForm.description.trim() || undefined,
      is_active: acForm.is_active,
    };
    if (!acEdit) {
      await acCreate(body);
    } else if (acSelected) {
      await acPatch(body, `/${acSelected}`);
      await acDetailMutate();
    }
    setAcDrawer(false);
    await acMutate();
  }

  async function confirmAcDelete() {
    if (!acSelected) return;
    await acDel(undefined, `/${acSelected}`);
    setAcDelete(false);
    setAcSelected(null);
    await acMutate();
  }

  function openWcCreate() {
    setWcEdit(false);
    setWcForm({ name: '', description: '', is_active: true });
    setWcDrawer(true);
  }

  function openWcEdit() {
    if (!wcDetail) return;
    setWcEdit(true);
    setWcForm({
      name: wcDetail.name,
      description: wcDetail.description ?? '',
      is_active: wcDetail.is_active ?? true,
    });
    setWcDrawer(true);
  }

  async function submitWc() {
    const body = {
      name: wcForm.name.trim(),
      description: wcForm.description.trim() || undefined,
      is_active: wcForm.is_active,
    };
    if (!wcEdit) {
      await wcCreate(body);
    } else if (wcSelected) {
      await wcPatch(body, `/${wcSelected}`);
      await wcDetailMutate();
    }
    setWcDrawer(false);
    await wcMutate();
  }

  async function confirmWcDelete() {
    if (!wcSelected) return;
    await wcDel(undefined, `/${wcSelected}`);
    setWcDelete(false);
    setWcSelected(null);
    await wcMutate();
  }

  function openWqCreate() {
    setWqEdit(false);
    setWqForm({
      name: '',
      description: '',
      priority: '100',
      filter_criteria: '{}',
      is_active: true,
    });
    setWqDrawer(true);
  }

  function openWqEdit() {
    if (!wqDetail) return;
    setWqEdit(true);
    setWqForm({
      name: wqDetail.name,
      description: wqDetail.description ?? '',
      priority: String(wqDetail.priority ?? 0),
      filter_criteria: wqDetail.filter_criteria
        ? JSON.stringify(wqDetail.filter_criteria, null, 2)
        : '{}',
      is_active: wqDetail.is_active ?? true,
    });
    setWqDrawer(true);
  }

  const parseJsonField = useCallback((raw: string, label: string) => {
    try {
      return JSON.parse(raw || '{}') as Record<string, unknown>;
    } catch {
      throw new Error(`${label} must be valid JSON`);
    }
  }, []);

  async function submitWq() {
    let filter: Record<string, unknown>;
    try {
      filter = parseJsonField(wqForm.filter_criteria, 'Filter criteria');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Invalid JSON');
      return;
    }
    const body = {
      name: wqForm.name.trim(),
      description: wqForm.description.trim() || undefined,
      priority: parseInt(wqForm.priority, 10) || 0,
      filter_criteria: filter,
      is_active: wqForm.is_active,
    };
    if (!wqEdit) {
      await wqCreate(body);
    } else if (wqSelected) {
      await wqPatch(body, `/${wqSelected}`);
      await wqDetailMutate();
    }
    setWqDrawer(false);
    await wqMutate();
  }

  async function confirmWqDelete() {
    if (!wqSelected) return;
    await wqDel(undefined, `/${wqSelected}`);
    setWqDelete(false);
    setWqSelected(null);
    await wqMutate();
  }

  const fetchNextItem = useCallback(async () => {
    if (!wqSelected) return;
    setNextLoading(true);
    setNextPreview(null);
    try {
      const { data } = await apiClient.get<unknown>(
        `${API_QUEUES.replace(/\/$/, '')}/${wqSelected}/next`
      );
      setNextPreview(data);
      await wqEntriesMutate();
    } finally {
      setNextLoading(false);
    }
  }, [wqSelected, wqEntriesMutate]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workflow"
        subtitle="Activity codes, workflow chains, and work queues"
        actions={
          activeTab === 'activity' ? (
            <button
              type="button"
              onClick={openAcCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New activity code
            </button>
          ) : activeTab === 'chains' ? (
            <button
              type="button"
              onClick={openWcCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New workflow chain
            </button>
          ) : (
            <button
              type="button"
              onClick={openWqCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New work queue
            </button>
          )
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button
          type="button"
          className={tabButtonClass(activeTab === 'activity')}
          onClick={() => setActiveTab('activity')}
        >
          Activity Codes
        </button>
        <button
          type="button"
          className={tabButtonClass(activeTab === 'chains')}
          onClick={() => setActiveTab('chains')}
        >
          Workflow Chains
        </button>
        <button
          type="button"
          className={tabButtonClass(activeTab === 'queues')}
          onClick={() => setActiveTab('queues')}
        >
          Work Queues
        </button>
      </div>

      {activeTab === 'activity' && (
        <>
          <SearchBar
            value={acSearch}
            onChange={setAcSearch}
            placeholder="Search activity codes…"
          />
          <DataTable<ActivityCodeRow>
            columns={acColumns}
            data={acFiltered}
            isLoading={acLoading}
            emptyMessage="No activity codes"
            onRowClick={(row) => setAcSelected(row.id)}
            pageCount={acPageCount}
            pageIndex={acPage}
            pageSize={acPageSize}
            onPageChange={setAcPage}
            onPageSizeChange={(s) => {
              setAcPageSize(s);
              setAcPage(0);
            }}
          />
        </>
      )}

      {activeTab === 'chains' && (
        <>
          <SearchBar
            value={wcSearch}
            onChange={setWcSearch}
            placeholder="Search workflow chains…"
          />
          <DataTable<WorkflowChainRow>
            columns={wcColumns}
            data={wcFiltered}
            isLoading={wcLoading}
            emptyMessage="No workflow chains"
            onRowClick={(row) => setWcSelected(row.id)}
            pageCount={wcPageCount}
            pageIndex={wcPage}
            pageSize={wcPageSize}
            onPageChange={setWcPage}
            onPageSizeChange={(s) => {
              setWcPageSize(s);
              setWcPage(0);
            }}
          />
        </>
      )}

      {activeTab === 'queues' && (
        <>
          <SearchBar
            value={wqSearch}
            onChange={setWqSearch}
            placeholder="Search work queues…"
          />
          <DataTable<WorkQueueRow>
            columns={wqColumns}
            data={wqFiltered}
            isLoading={wqLoading}
            emptyMessage="No work queues"
            onRowClick={(row) => setWqSelected(row.id)}
            pageCount={wqPageCount}
            pageIndex={wqPage}
            pageSize={wqPageSize}
            onPageChange={setWqPage}
            onPageSizeChange={(s) => {
              setWqPageSize(s);
              setWqPage(0);
            }}
          />
        </>
      )}

      {activeTab === 'activity' && acSelected && (
        <DetailPanel
          title={acDetail?.code ?? 'Activity code'}
          subtitle={acDetail?.name}
          onClose={() => setAcSelected(null)}
          onEdit={openAcEdit}
          onDelete={() => setAcDelete(true)}
        >
          {acDetailLoading || !acDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <FieldGrid cols={2}>
              <FieldGroup label="Code">{acDetail.code}</FieldGroup>
              <FieldGroup label="Name">{acDetail.name}</FieldGroup>
              <FieldGroup label="Category">{acDetail.category}</FieldGroup>
              <FieldGroup label="Default priority">
                {String(acDetail.default_priority)}
              </FieldGroup>
              <FieldGroup label="Active">
                <StatusBadge
                  status={
                    acDetail.is_active ?? acDetail.active ? 'active' : 'closed'
                  }
                />
              </FieldGroup>
              <FieldGroup label="Description">
                {acDetail.description || '—'}
              </FieldGroup>
            </FieldGrid>
          )}
        </DetailPanel>
      )}

      {activeTab === 'chains' && wcSelected && (
        <DetailPanel
          title={wcDetail?.name ?? 'Workflow chain'}
          subtitle="Steps define execution order"
          onClose={() => setWcSelected(null)}
          onEdit={openWcEdit}
          onDelete={() => setWcDelete(true)}
        >
          {wcDetailLoading || !wcDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Name">{wcDetail.name}</FieldGroup>
                <FieldGroup label="Active">
                  <StatusBadge
                    status={wcDetail.is_active ? 'active' : 'closed'}
                  />
                </FieldGroup>
                <FieldGroup label="Description">
                  {wcDetail.description || '—'}
                </FieldGroup>
              </FieldGrid>
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Steps
                </h3>
                <div className="mt-3 overflow-hidden rounded-md border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">Order</th>
                        <th className="px-3 py-2 text-left font-medium">
                          Activity code ID
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Delay (days)
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Condition
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(wcDetail.steps ?? []).length === 0 ? (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-3 py-6 text-center text-neutral-500"
                          >
                            No steps on this chain
                          </td>
                        </tr>
                      ) : (
                        (wcDetail.steps ?? []).map((s, i) => (
                          <tr
                            key={s.id ?? `${s.step_order}-${i}`}
                            className="border-t border-border"
                          >
                            <td className="px-3 py-2">{s.step_order}</td>
                            <td className="px-3 py-2 font-mono text-xs">
                              {s.activity_code_id}
                            </td>
                            <td className="px-3 py-2">{s.delay_days ?? '—'}</td>
                            <td className="px-3 py-2">
                              {s.condition || '—'}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </DetailPanel>
      )}

      {activeTab === 'queues' && wqSelected && (
        <DetailPanel
          title={wqDetail?.name ?? 'Work queue'}
          subtitle={`Priority ${wqDetail?.priority ?? '—'}`}
          onClose={() => {
            setWqSelected(null);
            setNextPreview(null);
          }}
          onEdit={openWqEdit}
          onDelete={() => setWqDelete(true)}
        >
          {wqDetailLoading || !wqDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={nextLoading}
                  onClick={fetchNextItem}
                  className="inline-flex h-9 items-center rounded-md bg-primary-600 px-3 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {nextLoading ? 'Loading…' : 'Next Item'}
                </button>
              </div>
              {nextPreview != null && (
                <pre className="mt-4 max-h-48 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
                  {JSON.stringify(nextPreview, null, 2)}
                </pre>
              )}
              <div className="mt-6">
                <FieldGrid cols={2}>
                  <FieldGroup label="Description">
                    {wqDetail.description || '—'}
                  </FieldGroup>
                  <FieldGroup label="Active">
                    <StatusBadge
                      status={wqDetail.is_active ? 'active' : 'closed'}
                    />
                  </FieldGroup>
                </FieldGrid>
              </div>
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Entries
                </h3>
                {wqEntriesLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading entries…</p>
                ) : (
                  <div className="mt-3 overflow-hidden rounded-md border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">ID</th>
                          <th className="px-3 py-2 text-left font-medium">
                            Account
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Created
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(wqEntries ?? []).length === 0 ? (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-3 py-6 text-center text-neutral-500"
                            >
                              No entries
                            </td>
                          </tr>
                        ) : (
                          (wqEntries ?? []).map((e) => (
                            <tr key={e.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono text-xs">
                                {e.id}
                              </td>
                              <td className="px-3 py-2">
                                {String(e.account_id ?? '—')}
                              </td>
                              <td className="px-3 py-2">
                                {e.status ? (
                                  <StatusBadge status={String(e.status)} />
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof e.created_at === 'string'
                                    ? e.created_at
                                    : undefined
                                )}
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
        open={acDrawer}
        onClose={() => setAcDrawer(false)}
        title={acEdit ? 'Edit activity code' : 'New activity code'}
        onSubmit={submitAc}
        isSubmitting={acCreating || acPatching}
        submitLabel={acEdit ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Code" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={acForm.code}
              onChange={(e) =>
                setAcForm((f) => ({ ...f, code: e.target.value }))
              }
              disabled={acEdit}
            />
          </FormField>
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={acForm.name}
              onChange={(e) =>
                setAcForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Category" required>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={acForm.category}
              onChange={(e) =>
                setAcForm((f) => ({
                  ...f,
                  category: e.target.value as (typeof ACTIVITY_CATEGORIES)[number],
                }))
              }
            >
              {ACTIVITY_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Default priority" required>
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={acForm.default_priority}
              onChange={(e) =>
                setAcForm((f) => ({ ...f, default_priority: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Description">
            <textarea
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={acForm.description}
              onChange={(e) =>
                setAcForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={acForm.is_active}
              onChange={(e) =>
                setAcForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <FormDrawer
        open={wcDrawer}
        onClose={() => setWcDrawer(false)}
        title={wcEdit ? 'Edit workflow chain' : 'New workflow chain'}
        onSubmit={submitWc}
        isSubmitting={wcCreating || wcPatching}
        submitLabel={wcEdit ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={wcForm.name}
              onChange={(e) =>
                setWcForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Description">
            <textarea
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={wcForm.description}
              onChange={(e) =>
                setWcForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={wcForm.is_active}
              onChange={(e) =>
                setWcForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <FormDrawer
        open={wqDrawer}
        onClose={() => setWqDrawer(false)}
        title={wqEdit ? 'Edit work queue' : 'New work queue'}
        onSubmit={submitWq}
        isSubmitting={wqCreating || wqPatching}
        submitLabel={wqEdit ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={wqForm.name}
              onChange={(e) =>
                setWqForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Description">
            <textarea
              rows={2}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={wqForm.description}
              onChange={(e) =>
                setWqForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Priority" required>
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={wqForm.priority}
              onChange={(e) =>
                setWqForm((f) => ({ ...f, priority: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Filter criteria (JSON)" required>
            <textarea
              rows={6}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={wqForm.filter_criteria}
              onChange={(e) =>
                setWqForm((f) => ({ ...f, filter_criteria: e.target.value }))
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={wqForm.is_active}
              onChange={(e) =>
                setWqForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={acDelete}
        onClose={() => setAcDelete(false)}
        onConfirm={confirmAcDelete}
        title="Delete activity code?"
        message="This action cannot be undone."
        confirmLabel={acDeleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
      <ConfirmDialog
        open={wcDelete}
        onClose={() => setWcDelete(false)}
        onConfirm={confirmWcDelete}
        title="Delete workflow chain?"
        message="This action cannot be undone."
        confirmLabel={wcDeleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
      <ConfirmDialog
        open={wqDelete}
        onClose={() => setWqDelete(false)}
        onConfirm={confirmWqDelete}
        title="Delete work queue?"
        message="This action cannot be undone."
        confirmLabel={wqDeleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
