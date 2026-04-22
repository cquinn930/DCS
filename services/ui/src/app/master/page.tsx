'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  Building2,
  CheckCircle2,
  Clock,
  Database,
  History,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { apiClient } from '@/lib/api';

type SystemStatus = {
  api_version: string;
  api_uptime_seconds: number;
  database_ok: boolean;
  database_latency_ms: number | null;
  tenant_count: number;
  active_tenant_count: number;
  master_user_count: number;
  impersonations_active_now: number;
  impersonations_last_24h: number;
  server_time_utc: string;
};

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function MasterOverviewPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const resp = await apiClient.get<SystemStatus>('/api/v1/master/system-status');
        if (!cancelled) {
          setStatus(resp.data);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || 'Failed to load system status');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary-600" />
          Master overview
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Platform-level status. No tenant operational data is shown here. To
          inspect a tenant&rsquo;s data, go to <Link href="/master/tenants" className="text-primary-600 underline">Tenants</Link> and
          start an impersonation session.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-error-200 bg-error-50 dark:bg-error-900/20 p-4">
          <div className="flex items-start gap-2 text-error-700 dark:text-error-300">
            <AlertCircle className="h-4 w-4 mt-0.5" />
            <p className="text-sm">{error}</p>
          </div>
        </div>
      )}

      {loading && !status && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      )}

      {status && (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatusCard
              icon={Database}
              tone={status.database_ok ? 'good' : 'bad'}
              label="Database"
              value={status.database_ok ? 'Healthy' : 'Unreachable'}
              hint={
                status.database_latency_ms != null
                  ? `${status.database_latency_ms} ms ping`
                  : undefined
              }
            />
            <StatusCard
              icon={Activity}
              tone="neutral"
              label="API uptime"
              value={formatUptime(status.api_uptime_seconds)}
              hint={`v${status.api_version}`}
            />
            <StatusCard
              icon={Building2}
              tone="neutral"
              label="Tenants"
              value={`${status.active_tenant_count} / ${status.tenant_count}`}
              hint={`active / total`}
            />
            <StatusCard
              icon={Users}
              tone="neutral"
              label="Master users"
              value={String(status.master_user_count)}
              hint="across the platform"
            />
          </section>

          <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <StatusCard
              icon={ShieldCheck}
              tone={status.impersonations_active_now > 0 ? 'warn' : 'neutral'}
              label="Active impersonations"
              value={String(status.impersonations_active_now)}
              hint="last 30 minutes"
            />
            <StatusCard
              icon={Clock}
              tone="neutral"
              label="Impersonations (24h)"
              value={String(status.impersonations_last_24h)}
              hint="see audit log for details"
            />
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              href="/master/tenants"
              className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 hover:shadow-sm transition"
            >
              <Building2 className="h-5 w-5 text-primary-600" />
              <h3 className="mt-2 font-semibold">Manage tenants</h3>
              <p className="text-sm text-neutral-500 mt-1">
                List, configure, and enter tenants for support work.
              </p>
            </Link>
            <Link
              href="/master/audit"
              className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 hover:shadow-sm transition"
            >
              <History className="h-5 w-5 text-primary-600" />
              <h3 className="mt-2 font-semibold">Audit log</h3>
              <p className="text-sm text-neutral-500 mt-1">
                Every master login and impersonation event, oldest-first
                visible here.
              </p>
            </Link>
          </section>

          <p className="text-xs text-neutral-400">
            Server time: {new Date(status.server_time_utc).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}

type Tone = 'good' | 'bad' | 'warn' | 'neutral';

function StatusCard({
  icon: Icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint?: string;
  tone: Tone;
}) {
  const toneClasses: Record<Tone, string> = {
    good: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20',
    bad: 'text-error-600 bg-error-50 dark:bg-error-900/20',
    warn: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20',
    neutral: 'text-primary-600 bg-primary-50 dark:bg-primary-900/20',
  };
  const ToneIcon = tone === 'good' ? CheckCircle2 : tone === 'bad' ? AlertCircle : null;
  return (
    <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5">
      <div className="flex items-start justify-between">
        <div className={`rounded-md p-2 ${toneClasses[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
        {ToneIcon && <ToneIcon className={`h-4 w-4 ${tone === 'good' ? 'text-emerald-500' : 'text-error-500'}`} />}
      </div>
      <div className="mt-3">
        <p className="text-xs text-neutral-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-semibold mt-1">{value}</p>
        {hint && <p className="text-xs text-neutral-500 mt-1">{hint}</p>}
      </div>
    </div>
  );
}
