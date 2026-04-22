'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Shield, Settings, Eye } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { StatusBadge } from '@/components/shared/status-badge';
import { useApiList, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/audit-trail';

type AccessLogRow = { id: string; account_id: string | null; user_id: string; action: string; resource_type: string | null; ip_address: string | null; created_at: string };
type LoginLogRow = { id: string; user_id: string; action: string; ip_address: string | null; success: boolean; failure_reason: string | null; created_at: string };
type AuditConfigRow = { id: string; name: string; track_views: boolean; track_edits: boolean; track_exports: boolean; retention_days: number; is_active: boolean; created_at: string };

const ACTION_MAP: Record<string, string> = {
  view: 'bg-blue-100 text-blue-700',
  edit: 'bg-yellow-100 text-yellow-700',
  create: 'bg-green-100 text-green-700',
  delete: 'bg-red-100 text-red-700',
  export: 'bg-purple-100 text-purple-700',
  login: 'bg-cyan-100 text-cyan-700',
  logout: 'bg-gray-100 text-gray-700',
};

export default function AuditTrailPage() {
  const [tab, setTab] = useState<'access' | 'login' | 'config'>('access');
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [configForm, setConfigForm] = useState({ name: '', track_views: true, track_edits: true, track_exports: true, track_prints: true, retention_days: 365 });

  const { data: accessLogs, total: accessTotal, isLoading: accessLoading } = useApiList<AccessLogRow>(`${API}/access-logs`, { page: pageIndex + 1, page_size: pageSize });
  const { data: loginLogs, total: loginTotal, isLoading: loginLoading } = useApiList<LoginLogRow>(`${API}/login-logs`, { page: pageIndex + 1, page_size: pageSize });
  const { data: configs, total: configTotal, isLoading: configLoading, mutate: mutateConfigs } = useApiList<AuditConfigRow>(`${API}/configs`, { page: pageIndex + 1, page_size: pageSize });
  const { trigger: createConfig } = useApiMutation('POST', `${API}/configs`);

  const accessColumns: ColumnDef<AccessLogRow>[] = [
    { accessorKey: 'action', header: 'Action', cell: ({ row }) => <StatusBadge status={row.original.action} colorMap={ACTION_MAP} /> },
    { accessorKey: 'resource_type', header: 'Resource', cell: ({ row }) => row.original.resource_type || '—' },
    { accessorKey: 'user_id', header: 'User', cell: ({ row }) => <span className="font-mono text-xs">{row.original.user_id.slice(0, 8)}...</span> },
    { accessorKey: 'account_id', header: 'Account', cell: ({ row }) => row.original.account_id ? <span className="font-mono text-xs">{row.original.account_id.slice(0, 8)}...</span> : '—' },
    { accessorKey: 'ip_address', header: 'IP', cell: ({ row }) => row.original.ip_address || '—' },
    { accessorKey: 'created_at', header: 'When', cell: ({ row }) => new Date(row.original.created_at).toLocaleString() },
  ];

  const loginColumns: ColumnDef<LoginLogRow>[] = [
    { accessorKey: 'action', header: 'Action', cell: ({ row }) => <StatusBadge status={row.original.action} colorMap={ACTION_MAP} /> },
    { accessorKey: 'user_id', header: 'User', cell: ({ row }) => <span className="font-mono text-xs">{row.original.user_id.slice(0, 8)}...</span> },
    { accessorKey: 'success', header: 'Success', cell: ({ row }) => row.original.success ? <span className="text-green-600">Yes</span> : <span className="text-red-600">No</span> },
    { accessorKey: 'failure_reason', header: 'Reason', cell: ({ row }) => row.original.failure_reason || '—' },
    { accessorKey: 'ip_address', header: 'IP', cell: ({ row }) => row.original.ip_address || '—' },
    { accessorKey: 'created_at', header: 'When', cell: ({ row }) => new Date(row.original.created_at).toLocaleString() },
  ];

  const configColumns: ColumnDef<AuditConfigRow>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'track_views', header: 'Views', cell: ({ row }) => row.original.track_views ? 'Yes' : 'No' },
    { accessorKey: 'track_edits', header: 'Edits', cell: ({ row }) => row.original.track_edits ? 'Yes' : 'No' },
    { accessorKey: 'track_exports', header: 'Exports', cell: ({ row }) => row.original.track_exports ? 'Yes' : 'No' },
    { accessorKey: 'retention_days', header: 'Retention (days)' },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Trail" subtitle="Account access logs, login history, and audit configuration">
        {tab === 'config' && (
          <button onClick={() => setConfigDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Settings className="h-4 w-4" /> New Config</button>
        )}
      </PageHeader>

      <div className="flex gap-2 border-b">
        {(['access', 'login', 'config'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setPageIndex(0); }} className={`px-4 py-2 text-sm font-medium border-b-2 capitalize ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'}`}>{t === 'access' ? 'Access Logs' : t === 'login' ? 'Login Logs' : 'Configuration'}</button>
        ))}
      </div>

      {tab === 'access' && <DataTable columns={accessColumns} data={accessLogs ?? []} isLoading={accessLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((accessTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}
      {tab === 'login' && <DataTable columns={loginColumns} data={loginLogs ?? []} isLoading={loginLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((loginTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}
      {tab === 'config' && <DataTable columns={configColumns} data={configs ?? []} isLoading={configLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((configTotal ?? 0) / pageSize)} onPageChange={setPageIndex} />}

      <FormDrawer open={configDrawerOpen} onClose={() => setConfigDrawerOpen(false)} title="New Audit Config" onSubmit={async () => { await createConfig(configForm); setConfigDrawerOpen(false); setConfigForm({ name: '', track_views: true, track_edits: true, track_exports: true, track_prints: true, retention_days: 365 }); mutateConfigs(); }}>
        <FormField label="Name"><input value={configForm.name} onChange={e => setConfigForm({ ...configForm, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Track Views"><label className="flex items-center gap-2"><input type="checkbox" checked={configForm.track_views} onChange={e => setConfigForm({ ...configForm, track_views: e.target.checked })} /> Enabled</label></FormField>
        <FormField label="Track Edits"><label className="flex items-center gap-2"><input type="checkbox" checked={configForm.track_edits} onChange={e => setConfigForm({ ...configForm, track_edits: e.target.checked })} /> Enabled</label></FormField>
        <FormField label="Track Exports"><label className="flex items-center gap-2"><input type="checkbox" checked={configForm.track_exports} onChange={e => setConfigForm({ ...configForm, track_exports: e.target.checked })} /> Enabled</label></FormField>
        <FormField label="Retention (days)"><input type="number" value={configForm.retention_days} onChange={e => setConfigForm({ ...configForm, retention_days: parseInt(e.target.value) || 365 })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
      </FormDrawer>
    </div>
  );
}
