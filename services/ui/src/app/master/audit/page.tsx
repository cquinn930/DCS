'use client';

import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Eye,
  History,
  LogOut,
  Pencil,
  ShieldCheck,
} from 'lucide-react';
import { apiClient } from '@/lib/api';

type AuditEntry = {
  id: string;
  occurred_at: string;
  event: string;
  master_email: string | null;
  target_tenant_slug: string | null;
  mode: string | null;
  reason: string | null;
  impersonation_id: string | null;
  ip_address: string | null;
};

const EVENT_LABEL: Record<string, { label: string; tone: string; icon: React.ComponentType<{ className?: string }> }> = {
  'impersonation.start': {
    label: 'Entered tenant',
    tone: 'text-amber-600',
    icon: ShieldCheck,
  },
  'impersonation.end': {
    label: 'Exited tenant',
    tone: 'text-neutral-500',
    icon: LogOut,
  },
  'master.login': {
    label: 'Master sign-in',
    tone: 'text-primary-600',
    icon: ShieldCheck,
  },
};

export default function MasterAuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantFilter, setTenantFilter] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const path = tenantFilter
          ? `/api/v1/master/audit?tenant_slug=${encodeURIComponent(tenantFilter)}`
          : '/api/v1/master/audit';
        const resp = await apiClient.get<AuditEntry[]>(path);
        if (!cancelled) {
          setEntries(resp.data);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || 'Failed to load audit log');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tenantFilter]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <History className="h-6 w-6 text-primary-600" />
          Master audit log
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Every master sign-in and impersonation event. Most recent first.
        </p>
      </header>

      <div className="flex gap-2">
        <input
          type="text"
          value={tenantFilter}
          onChange={(e) => setTenantFilter(e.target.value)}
          placeholder="Filter by tenant slug (e.g. flg)"
          className="rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 px-3 py-1.5 text-sm w-64"
        />
        {tenantFilter && (
          <button
            onClick={() => setTenantFilter('')}
            className="text-sm text-neutral-500 hover:text-neutral-700"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-error-200 bg-error-50 dark:bg-error-900/20 p-4 flex gap-2 text-error-700 dark:text-error-300 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-neutral-500">No audit entries yet.</p>
      ) : (
        <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 dark:bg-neutral-950 text-left text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-2">When</th>
                <th className="px-4 py-2">Event</th>
                <th className="px-4 py-2">Master</th>
                <th className="px-4 py-2">Tenant</th>
                <th className="px-4 py-2">Mode</th>
                <th className="px-4 py-2">Reason</th>
                <th className="px-4 py-2">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {entries.map((e) => {
                const meta =
                  EVENT_LABEL[e.event] ||
                  { label: e.event, tone: 'text-neutral-500', icon: History };
                const ModeIcon = e.mode === 'write' ? Pencil : Eye;
                return (
                  <tr key={e.id}>
                    <td className="px-4 py-3 text-xs text-neutral-500 tabular-nums whitespace-nowrap">
                      {new Date(e.occurred_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 ${meta.tone}`}>
                        <meta.icon className="h-3.5 w-3.5" />
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">{e.master_email || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">{e.target_tenant_slug || '—'}</td>
                    <td className="px-4 py-3">
                      {e.mode ? (
                        <span className="inline-flex items-center gap-1 text-xs">
                          <ModeIcon className="h-3 w-3" />
                          {e.mode}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-neutral-600 dark:text-neutral-400 max-w-md truncate" title={e.reason || ''}>
                      {e.reason || '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-neutral-500 font-mono">{e.ip_address || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
