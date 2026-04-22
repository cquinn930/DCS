'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  Building2,
  ChevronRight,
  Eye,
  Pencil,
  ShieldAlert,
  X,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

type Tenant = {
  id: string;
  slug: string;
  name: string;
  status: string;
  business_model: string;
  default_jurisdiction: string;
  user_count: number;
  last_user_login: string | null;
  auto_approve_master_access: boolean;
  created_at: string;
};

const statusBadge: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  suspended: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  locked_down: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  deactivated: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400',
};

export default function MasterTenantsPage() {
  const router = useRouter();
  const enterTenant = useAuthStore((s) => s.enterTenant);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enterTarget, setEnterTarget] = useState<Tenant | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const resp = await apiClient.get<Tenant[]>('/api/v1/master/tenants');
        if (!cancelled) {
          setTenants(resp.data);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || 'Failed to load tenants');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Building2 className="h-6 w-6 text-primary-600" />
          Tenants
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          To inspect a tenant&rsquo;s data, click <strong>Enter</strong> and provide
          a reason. The action is recorded in the audit log.
        </p>
      </header>

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
      ) : tenants.length === 0 ? (
        <p className="text-sm text-neutral-500">No tenants on the platform yet.</p>
      ) : (
        <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 dark:bg-neutral-950 text-left text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-2">Tenant</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Model</th>
                <th className="px-4 py-2 text-right">Users</th>
                <th className="px-4 py-2">Last login</th>
                <th className="px-4 py-2">Master access</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {tenants.map((t) => (
                <tr key={t.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-neutral-500">{t.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[t.status] || statusBadge.deactivated}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-neutral-600 dark:text-neutral-400">{t.business_model}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{t.user_count}</td>
                  <td className="px-4 py-3 text-neutral-500 text-xs">
                    {t.last_user_login
                      ? new Date(t.last_user_login).toLocaleString()
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {t.auto_approve_master_access ? (
                      <span className="text-emerald-600">auto-approve</span>
                    ) : (
                      <span className="text-amber-600 inline-flex items-center gap-1">
                        <ShieldAlert className="h-3 w-3" />
                        owner approval required
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setEnterTarget(t)}
                      className="inline-flex items-center gap-1 rounded border border-neutral-300 dark:border-neutral-700 px-2 py-1 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800"
                    >
                      Enter
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {enterTarget && (
        <EnterTenantModal
          tenant={enterTarget}
          onClose={() => setEnterTarget(null)}
          onConfirm={async (reason, mode) => {
            const ok = await enterTenant(enterTarget.slug, reason, mode);
            if (ok) {
              router.push('/dashboard');
            }
            return ok;
          }}
        />
      )}
    </div>
  );
}

function EnterTenantModal({
  tenant,
  onClose,
  onConfirm,
}: {
  tenant: Tenant;
  onClose: () => void;
  onConfirm: (reason: string, mode: 'read' | 'write') => Promise<boolean>;
}) {
  const [reason, setReason] = useState('');
  const [mode, setMode] = useState<'read' | 'write'>('read');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (reason.trim().length < 4) {
      setErr('Please provide a brief reason (4+ characters).');
      return;
    }
    setSubmitting(true);
    setErr(null);
    const ok = await onConfirm(reason.trim(), mode);
    if (!ok) {
      setErr(useAuthStore.getState().error || 'Failed to enter tenant.');
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-lg">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 px-5 py-3">
          <h2 className="font-semibold">Enter {tenant.name}</h2>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-700">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <p className="text-sm text-neutral-600 dark:text-neutral-300">
            You are about to access this tenant&rsquo;s operational data as a
            master user. This action will be recorded in the audit log with
            the reason you provide.
          </p>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-neutral-500 mb-1">
              Reason
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="e.g. Investigating support ticket #1234"
              className="w-full rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 px-2 py-1.5 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-neutral-500 mb-2">
              Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setMode('read')}
                className={
                  'flex items-start gap-2 rounded border p-3 text-left text-sm ' +
                  (mode === 'read'
                    ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                    : 'border-neutral-300 dark:border-neutral-700')
                }
              >
                <Eye className="h-4 w-4 mt-0.5 text-amber-600" />
                <div>
                  <div className="font-medium">Read-only</div>
                  <div className="text-xs text-neutral-500">
                    View data only. Writes blocked.
                  </div>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setMode('write')}
                className={
                  'flex items-start gap-2 rounded border p-3 text-left text-sm ' +
                  (mode === 'write'
                    ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                    : 'border-neutral-300 dark:border-neutral-700')
                }
              >
                <Pencil className="h-4 w-4 mt-0.5 text-red-600" />
                <div>
                  <div className="font-medium">Write</div>
                  <div className="text-xs text-neutral-500">
                    Make changes on the tenant&rsquo;s behalf.
                  </div>
                </div>
              </button>
            </div>
          </div>

          {err && (
            <div className="text-sm text-error-600 flex items-start gap-1">
              <AlertCircle className="h-4 w-4 mt-0.5" />
              {err}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-neutral-200 dark:border-neutral-800 px-5 py-3">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className={
              'px-3 py-1.5 text-sm rounded text-white disabled:opacity-50 ' +
              (mode === 'write'
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-primary-600 hover:bg-primary-700')
            }
          >
            {submitting ? 'Entering…' : `Enter (${mode})`}
          </button>
        </div>
      </div>
    </div>
  );
}
