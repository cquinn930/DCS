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
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

const API_RULES = '/api/v1/automation/event-rules';
const API_LOGS = '/api/v1/automation/event-logs';
const API_JOBS = '/api/v1/automation/scheduled-jobs';
const API_EXEC = '/api/v1/automation/job-executions';

type TabId = 'rules' | 'jobs';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

type EventRuleRow = {
  id: string;
  name: string;
  entity_type: string;
  event_type: string;
  is_active?: boolean;
  priority?: number;
};

type EventRuleDetail = EventRuleRow & {
  conditions?: Record<string, unknown> | null;
  actions?: Record<string, unknown> | null;
};

type EventLogRow = {
  id: string;
  rule_id?: string;
  status?: string;
  message?: string;
  created_at?: string;
  [key: string]: unknown;
};

type ScheduledJobRow = {
  id: string;
  name: string;
  job_type: string;
  schedule_expression: string;
  status: string;
  next_run?: string | null;
  last_run?: string | null;
};

type ScheduledJobDetail = ScheduledJobRow & {
  job_config?: Record<string, unknown> | null;
};

type JobExecutionRow = {
  id: string;
  job_id?: string;
  status?: string;
  started_at?: string;
  finished_at?: string;
  [key: string]: unknown;
};

function tabClass(active: boolean) {
  return cn(
    'rounded-md px-4 py-2 text-sm font-medium transition-colors',
    active
      ? 'bg-primary-600 text-white shadow-sm'
      : 'border border-border bg-background text-foreground hover:bg-muted'
  );
}

export default function AutomationPage() {
  const [activeTab, setActiveTab] = useState<TabId>('rules');

  /* Event rules */
  const [erSearch, setErSearch] = useState('');
  const [erPage, setErPage] = useState(0);
  const [erPageSize, setErPageSize] = useState(20);
  const [erSelected, setErSelected] = useState<string | null>(null);
  const [erDrawer, setErDrawer] = useState(false);
  const [erEdit, setErEdit] = useState(false);
  const [erDelete, setErDelete] = useState(false);
  const [erForm, setErForm] = useState({
    name: '',
    entity_type: '',
    event_type: '',
    conditions: '{}',
    actions: '{}',
    priority: '100',
    is_active: true,
  });

  const erParams = useMemo(
    () => ({ page: erPage + 1, page_size: erPageSize }),
    [erPage, erPageSize]
  );
  const {
    data: erData,
    total: erTotal,
    isLoading: erLoading,
    mutate: erMutate,
  } = useApiList<EventRuleRow>(API_RULES, erParams);
  const {
    data: erDetail,
    isLoading: erDetailLoading,
    mutate: erDetailMutate,
  } = useApiDetail<EventRuleDetail>(API_RULES, erSelected ?? undefined);

  const logsPath =
    erSelected != null
      ? `${API_LOGS}?rule_id=${encodeURIComponent(erSelected)}`
      : null;
  const { data: eventLogs, isLoading: logsLoading } = useApiList<EventLogRow>(
    logsPath,
    { page: 1, page_size: 100 }
  );

  const { trigger: erCreate, isMutating: erCreating } = useApiMutation<
    Record<string, unknown>,
    EventRuleDetail
  >('POST', API_RULES);
  const { trigger: erPatch, isMutating: erPatching } = useApiMutation<
    Record<string, unknown>,
    EventRuleDetail
  >('PATCH', API_RULES);
  const { trigger: erDel, isMutating: erDeleting } = useApiMutation(
    'DELETE',
    API_RULES
  );

  /* Scheduled jobs */
  const [sjSearch, setSjSearch] = useState('');
  const [sjPage, setSjPage] = useState(0);
  const [sjPageSize, setSjPageSize] = useState(20);
  const [sjSelected, setSjSelected] = useState<string | null>(null);
  const [sjDrawer, setSjDrawer] = useState(false);
  const [sjEdit, setSjEdit] = useState(false);
  const [sjDelete, setSjDelete] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [sjForm, setSjForm] = useState({
    name: '',
    job_type: '',
    schedule_expression: '0 * * * *',
    job_config: '{}',
    status: 'active',
  });

  const sjParams = useMemo(
    () => ({ page: sjPage + 1, page_size: sjPageSize }),
    [sjPage, sjPageSize]
  );
  const {
    data: sjData,
    total: sjTotal,
    isLoading: sjLoading,
    mutate: sjMutate,
  } = useApiList<ScheduledJobRow>(API_JOBS, sjParams);
  const {
    data: sjDetail,
    isLoading: sjDetailLoading,
    mutate: sjDetailMutate,
  } = useApiDetail<ScheduledJobDetail>(API_JOBS, sjSelected ?? undefined);

  const execPath =
    sjSelected != null
      ? `${API_EXEC}?job_id=${encodeURIComponent(sjSelected)}`
      : null;
  const {
    data: executions,
    isLoading: execLoading,
    mutate: execMutate,
  } = useApiList<JobExecutionRow>(execPath, { page: 1, page_size: 100 });

  const { trigger: sjCreate, isMutating: sjCreating } = useApiMutation<
    Record<string, unknown>,
    ScheduledJobDetail
  >('POST', API_JOBS);
  const { trigger: sjPatch, isMutating: sjPatching } = useApiMutation<
    Record<string, unknown>,
    ScheduledJobDetail
  >('PATCH', API_JOBS);
  const { trigger: sjDel, isMutating: sjDeleting } = useApiMutation(
    'DELETE',
    API_JOBS
  );

  useEffect(() => {
    setErSelected(null);
    setSjSelected(null);
  }, [activeTab]);

  const erFiltered = useMemo(() => {
    const rows = erData ?? [];
    if (!erSearch.trim()) return rows;
    const q = erSearch.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.entity_type.toLowerCase().includes(q) ||
        r.event_type.toLowerCase().includes(q)
    );
  }, [erData, erSearch]);

  const sjFiltered = useMemo(() => {
    const rows = sjData ?? [];
    if (!sjSearch.trim()) return rows;
    const q = sjSearch.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.job_type.toLowerCase().includes(q) ||
        r.schedule_expression.toLowerCase().includes(q)
    );
  }, [sjData, sjSearch]);

  const erPageCount = Math.max(1, Math.ceil((erTotal ?? 0) / erPageSize));
  const sjPageCount = Math.max(1, Math.ceil((sjTotal ?? 0) / sjPageSize));

  const erColumns: ColumnDef<EventRuleRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'entity_type', header: 'Entity Type' },
    { accessorKey: 'event_type', header: 'Event Type' },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => (
        <StatusBadge status={row.original.is_active ? 'active' : 'closed'} />
      ),
    },
    {
      accessorKey: 'priority',
      header: 'Priority',
      cell: ({ getValue }) => String(getValue() ?? '—'),
    },
  ];

  const sjColumns: ColumnDef<ScheduledJobRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'job_type', header: 'Job Type' },
    {
      accessorKey: 'schedule_expression',
      header: 'Schedule',
      cell: ({ getValue }) => (
        <code className="text-xs">{String(getValue() ?? '—')}</code>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ getValue }) => <StatusBadge status={String(getValue() ?? '')} />,
    },
    {
      accessorKey: 'next_run',
      header: 'Next Run',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
    {
      accessorKey: 'last_run',
      header: 'Last Run',
      cell: ({ getValue }) => fmtDate(String(getValue() ?? '')),
    },
  ];

  function parseJson(raw: string, label: string) {
    try {
      return JSON.parse(raw || '{}') as Record<string, unknown>;
    } catch {
      throw new Error(`${label} must be valid JSON`);
    }
  }

  function openErCreate() {
    setErEdit(false);
    setErForm({
      name: '',
      entity_type: '',
      event_type: '',
      conditions: '{}',
      actions: '{}',
      priority: '100',
      is_active: true,
    });
    setErDrawer(true);
  }

  function openErEdit() {
    if (!erDetail) return;
    setErEdit(true);
    setErForm({
      name: erDetail.name,
      entity_type: erDetail.entity_type,
      event_type: erDetail.event_type,
      conditions: JSON.stringify(erDetail.conditions ?? {}, null, 2),
      actions: JSON.stringify(erDetail.actions ?? {}, null, 2),
      priority: String(erDetail.priority ?? 100),
      is_active: erDetail.is_active ?? true,
    });
    setErDrawer(true);
  }

  async function submitEr() {
    let conditions: Record<string, unknown>;
    let actions: Record<string, unknown>;
    try {
      conditions = parseJson(erForm.conditions, 'Conditions');
      actions = parseJson(erForm.actions, 'Actions');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Invalid JSON');
      return;
    }
    const body = {
      name: erForm.name.trim(),
      entity_type: erForm.entity_type.trim(),
      event_type: erForm.event_type.trim(),
      conditions,
      actions,
      priority: parseInt(erForm.priority, 10) || 0,
      is_active: erForm.is_active,
    };
    if (!erEdit) {
      await erCreate(body);
    } else if (erSelected) {
      await erPatch(body, `/${erSelected}`);
      await erDetailMutate();
    }
    setErDrawer(false);
    await erMutate();
  }

  async function confirmErDelete() {
    if (!erSelected) return;
    await erDel(undefined, `/${erSelected}`);
    setErDelete(false);
    setErSelected(null);
    await erMutate();
  }

  function openSjCreate() {
    setSjEdit(false);
    setSjForm({
      name: '',
      job_type: '',
      schedule_expression: '0 * * * *',
      job_config: '{}',
      status: 'active',
    });
    setSjDrawer(true);
  }

  function openSjEdit() {
    if (!sjDetail) return;
    setSjEdit(true);
    setSjForm({
      name: sjDetail.name,
      job_type: sjDetail.job_type,
      schedule_expression: sjDetail.schedule_expression,
      job_config: JSON.stringify(sjDetail.job_config ?? {}, null, 2),
      status: sjDetail.status,
    });
    setSjDrawer(true);
  }

  async function submitSj() {
    let job_config: Record<string, unknown>;
    try {
      job_config = parseJson(sjForm.job_config, 'Job config');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Invalid JSON');
      return;
    }
    const body = {
      name: sjForm.name.trim(),
      job_type: sjForm.job_type.trim(),
      schedule_expression: sjForm.schedule_expression.trim(),
      job_config,
      status: sjForm.status.trim(),
    };
    if (!sjEdit) {
      await sjCreate(body);
    } else if (sjSelected) {
      await sjPatch(body, `/${sjSelected}`);
      await sjDetailMutate();
    }
    setSjDrawer(false);
    await sjMutate();
  }

  async function confirmSjDelete() {
    if (!sjSelected) return;
    await sjDel(undefined, `/${sjSelected}`);
    setSjDelete(false);
    setSjSelected(null);
    await sjMutate();
  }

  async function runNow() {
    if (!sjSelected) return;
    setRunLoading(true);
    try {
      await apiClient.post(
        `${API_JOBS.replace(/\/$/, '')}/${sjSelected}/trigger`,
        {}
      );
      await sjDetailMutate();
      await execMutate();
    } finally {
      setRunLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automation"
        subtitle="Event rules and scheduled jobs"
        actions={
          activeTab === 'rules' ? (
            <button
              type="button"
              onClick={openErCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New event rule
            </button>
          ) : (
            <button
              type="button"
              onClick={openSjCreate}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              New scheduled job
            </button>
          )
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button
          type="button"
          className={tabClass(activeTab === 'rules')}
          onClick={() => setActiveTab('rules')}
        >
          Event Rules
        </button>
        <button
          type="button"
          className={tabClass(activeTab === 'jobs')}
          onClick={() => setActiveTab('jobs')}
        >
          Scheduled Jobs
        </button>
      </div>

      {activeTab === 'rules' && (
        <>
          <SearchBar
            value={erSearch}
            onChange={setErSearch}
            placeholder="Search event rules…"
          />
          <DataTable<EventRuleRow>
            columns={erColumns}
            data={erFiltered}
            isLoading={erLoading}
            emptyMessage="No event rules"
            onRowClick={(row) => setErSelected(row.id)}
            pageCount={erPageCount}
            pageIndex={erPage}
            pageSize={erPageSize}
            onPageChange={setErPage}
            onPageSizeChange={(s) => {
              setErPageSize(s);
              setErPage(0);
            }}
          />
        </>
      )}

      {activeTab === 'jobs' && (
        <>
          <SearchBar
            value={sjSearch}
            onChange={setSjSearch}
            placeholder="Search scheduled jobs…"
          />
          <DataTable<ScheduledJobRow>
            columns={sjColumns}
            data={sjFiltered}
            isLoading={sjLoading}
            emptyMessage="No scheduled jobs"
            onRowClick={(row) => setSjSelected(row.id)}
            pageCount={sjPageCount}
            pageIndex={sjPage}
            pageSize={sjPageSize}
            onPageChange={setSjPage}
            onPageSizeChange={(s) => {
              setSjPageSize(s);
              setSjPage(0);
            }}
          />
        </>
      )}

      {activeTab === 'rules' && erSelected && (
        <DetailPanel
          title={erDetail?.name ?? 'Event rule'}
          subtitle={`${erDetail?.entity_type ?? ''} · ${erDetail?.event_type ?? ''}`}
          onClose={() => setErSelected(null)}
          onEdit={openErEdit}
          onDelete={() => setErDelete(true)}
        >
          {erDetailLoading || !erDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <FieldGrid cols={2}>
                <FieldGroup label="Entity type">{erDetail.entity_type}</FieldGroup>
                <FieldGroup label="Event type">{erDetail.event_type}</FieldGroup>
                <FieldGroup label="Priority">
                  {String(erDetail.priority ?? '—')}
                </FieldGroup>
                <FieldGroup label="Active">
                  <StatusBadge
                    status={erDetail.is_active ? 'active' : 'closed'}
                  />
                </FieldGroup>
              </FieldGrid>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div>
                  <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                    Conditions (JSON)
                  </h3>
                  <pre className="mt-2 max-h-40 overflow-auto rounded-md border border-border bg-muted/30 p-2 font-mono text-xs">
                    {JSON.stringify(erDetail.conditions ?? {}, null, 2)}
                  </pre>
                </div>
                <div>
                  <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                    Actions (JSON)
                  </h3>
                  <pre className="mt-2 max-h-40 overflow-auto rounded-md border border-border bg-muted/30 p-2 font-mono text-xs">
                    {JSON.stringify(erDetail.actions ?? {}, null, 2)}
                  </pre>
                </div>
              </div>
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Event logs
                </h3>
                {logsLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading…</p>
                ) : (
                  <div className="mt-3 overflow-hidden rounded-md border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">ID</th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Message
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Created
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(eventLogs ?? []).length === 0 ? (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-3 py-6 text-center text-neutral-500"
                            >
                              No logs
                            </td>
                          </tr>
                        ) : (
                          (eventLogs ?? []).map((log) => (
                            <tr key={log.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono text-xs">
                                {log.id}
                              </td>
                              <td className="px-3 py-2">
                                {log.status ? (
                                  <StatusBadge status={String(log.status)} />
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {String(log.message ?? '—')}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof log.created_at === 'string'
                                    ? log.created_at
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

      {activeTab === 'jobs' && sjSelected && (
        <DetailPanel
          title={sjDetail?.name ?? 'Scheduled job'}
          subtitle={sjDetail?.job_type}
          onClose={() => setSjSelected(null)}
          onEdit={openSjEdit}
          onDelete={() => setSjDelete(true)}
        >
          {sjDetailLoading || !sjDetail ? (
            <p className="text-sm text-neutral-500">Loading…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={runLoading}
                  onClick={runNow}
                  className="inline-flex h-9 items-center rounded-md bg-primary-600 px-3 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {runLoading ? 'Running…' : 'Run Now'}
                </button>
              </div>
              <div className="mt-6">
                <FieldGrid cols={2}>
                  <FieldGroup label="Schedule (cron)">
                    <code className="text-xs">{sjDetail.schedule_expression}</code>
                  </FieldGroup>
                  <FieldGroup label="Status">
                    <StatusBadge status={sjDetail.status} />
                  </FieldGroup>
                  <FieldGroup label="Next run">
                    {fmtDate(sjDetail.next_run ?? undefined)}
                  </FieldGroup>
                  <FieldGroup label="Last run">
                    {fmtDate(sjDetail.last_run ?? undefined)}
                  </FieldGroup>
                </FieldGrid>
              </div>
              <div className="mt-6">
                <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Job config
                </h3>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
                  {JSON.stringify(sjDetail.job_config ?? {}, null, 2)}
                </pre>
              </div>
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-foreground">
                  Executions
                </h3>
                {execLoading ? (
                  <p className="mt-2 text-sm text-neutral-500">Loading…</p>
                ) : (
                  <div className="mt-3 overflow-hidden rounded-md border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-neutral-50 dark:bg-neutral-900/40">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">ID</th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Started
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Finished
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(executions ?? []).length === 0 ? (
                          <tr>
                            <td
                              colSpan={4}
                              className="px-3 py-6 text-center text-neutral-500"
                            >
                              No executions
                            </td>
                          </tr>
                        ) : (
                          (executions ?? []).map((ex) => (
                            <tr key={ex.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono text-xs">
                                {ex.id}
                              </td>
                              <td className="px-3 py-2">
                                {ex.status ? (
                                  <StatusBadge status={String(ex.status)} />
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof ex.started_at === 'string'
                                    ? ex.started_at
                                    : undefined
                                )}
                              </td>
                              <td className="px-3 py-2">
                                {fmtDate(
                                  typeof ex.finished_at === 'string'
                                    ? ex.finished_at
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
        open={erDrawer}
        onClose={() => setErDrawer(false)}
        title={erEdit ? 'Edit event rule' : 'New event rule'}
        onSubmit={submitEr}
        isSubmitting={erCreating || erPatching}
        submitLabel={erEdit ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={erForm.name}
              onChange={(e) =>
                setErForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Entity type" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={erForm.entity_type}
              onChange={(e) =>
                setErForm((f) => ({ ...f, entity_type: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Event type" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={erForm.event_type}
              onChange={(e) =>
                setErForm((f) => ({ ...f, event_type: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Conditions (JSON)" required>
            <textarea
              rows={6}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={erForm.conditions}
              onChange={(e) =>
                setErForm((f) => ({ ...f, conditions: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Actions (JSON)" required>
            <textarea
              rows={6}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={erForm.actions}
              onChange={(e) =>
                setErForm((f) => ({ ...f, actions: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Priority" required>
            <input
              type="number"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={erForm.priority}
              onChange={(e) =>
                setErForm((f) => ({ ...f, priority: e.target.value }))
              }
            />
          </FormField>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={erForm.is_active}
              onChange={(e) =>
                setErForm((f) => ({ ...f, is_active: e.target.checked }))
              }
            />
            Active
          </label>
        </div>
      </FormDrawer>

      <FormDrawer
        open={sjDrawer}
        onClose={() => setSjDrawer(false)}
        title={sjEdit ? 'Edit scheduled job' : 'New scheduled job'}
        onSubmit={submitSj}
        isSubmitting={sjCreating || sjPatching}
        submitLabel={sjEdit ? 'Save' : 'Create'}
      >
        <div className="flex flex-col gap-4">
          <FormField label="Name" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={sjForm.name}
              onChange={(e) =>
                setSjForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Job type" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={sjForm.job_type}
              onChange={(e) =>
                setSjForm((f) => ({ ...f, job_type: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Schedule (cron expression)" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm"
              value={sjForm.schedule_expression}
              onChange={(e) =>
                setSjForm((f) => ({
                  ...f,
                  schedule_expression: e.target.value,
                }))
              }
            />
          </FormField>
          <FormField label="Job config (JSON)" required>
            <textarea
              rows={8}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={sjForm.job_config}
              onChange={(e) =>
                setSjForm((f) => ({ ...f, job_config: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Status" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={sjForm.status}
              onChange={(e) =>
                setSjForm((f) => ({ ...f, status: e.target.value }))
              }
              placeholder="active, paused, …"
            />
          </FormField>
        </div>
      </FormDrawer>

      <ConfirmDialog
        open={erDelete}
        onClose={() => setErDelete(false)}
        onConfirm={confirmErDelete}
        title="Delete event rule?"
        message="This action cannot be undone."
        confirmLabel={erDeleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
      <ConfirmDialog
        open={sjDelete}
        onClose={() => setSjDelete(false)}
        onConfirm={confirmSjDelete}
        title="Delete scheduled job?"
        message="This action cannot be undone."
        confirmLabel={sjDeleting ? 'Deleting…' : 'Delete'}
        variant="danger"
      />
    </div>
  );
}
