'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Users,
  DollarSign,
  AlertTriangle,
  CreditCard,
  TrendingUp,
  Scale,
  Briefcase,
  Clock,
  Activity,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

type LiveMetrics = {
  active_accounts: number;
  total_balance_cents: number;
  open_disputes: number;
  payments_today_cents: number;
  pending_activities: number;
  queue_accounts_pending: number;
};

type StatusBreakdown = {
  status: string;
  count: number;
  balance: number;
};

const fmtMoney = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);

const fmtMoneyFull = (cents: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);

const fmtNum = (n: number) => new Intl.NumberFormat('en-US').format(n);

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null);
  const [statusBreakdown, setStatusBreakdown] = useState<StatusBreakdown[]>([]);
  const [topCreditors, setTopCreditors] = useState<{ client: string; accounts: number; balance_cents: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchDashboard() {
      setLoading(true);
      setError(null);
      try {
        const [metricsRes, breakdownRes] = await Promise.allSettled([
          apiClient.get<LiveMetrics>('/api/v1/dashboard/live-metrics'),
          apiClient.get<any>('/api/v1/dashboard/management'),
        ]);

        if (!cancelled) {
          if (metricsRes.status === 'fulfilled') {
            setMetrics(metricsRes.value.data as LiveMetrics);
          }
          if (breakdownRes.status === 'fulfilled') {
            const mgmt = breakdownRes.value.data as any;
            if (mgmt?.extra?.top_clients) {
              setTopCreditors(mgmt.extra.top_clients);
            }
          }
        }

        // Fetch status breakdown via separate account queries.
        // The AccountStatus enum on the API stores LOWERCASE values
        // (active, hold, closed, ...). Sending uppercase here trips
        // FastAPI's enum-by-value parser and produces a 422 per status.
        const statuses = ['active', 'hold', 'closed', 'paid_in_full', 'settled', 'legal_hold'] as const;
        const breakdowns: StatusBreakdown[] = [];
        for (const s of statuses) {
          try {
            const res = await apiClient.get<any>(`/api/v1/accounts?status_filter=${s}&page=1&page_size=1`);
            const d = res.data as any;
            if (d && d.total > 0) {
              breakdowns.push({ status: s.toUpperCase(), count: d.total, balance: 0 });
            }
          } catch { /* skip */ }
        }
        if (!cancelled) setStatusBreakdown(breakdowns);
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Failed to load dashboard');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="rounded-lg border border-error-200 bg-error-50 dark:bg-error-900/20 p-6 text-center">
        <p className="text-error-700 dark:text-error-400">{error}</p>
        <p className="mt-2 text-sm text-neutral-500">
          Make sure the admin user has the &quot;dashboard:view&quot; permission, or run setup_flg_roles.py.
        </p>
      </div>
    );
  }

  const m = metrics;

  const statCards = [
    {
      title: 'Active Accounts',
      value: fmtNum(m?.active_accounts ?? 0),
      icon: Users,
      color: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20',
      href: '/accounts',
    },
    {
      title: 'Total Portfolio',
      value: fmtMoney(m?.total_balance_cents ?? 0),
      icon: DollarSign,
      color: 'text-green-600 bg-green-50 dark:bg-green-900/20',
      href: '/accounts',
    },
    {
      title: 'Open Disputes',
      value: fmtNum(m?.open_disputes ?? 0),
      icon: AlertTriangle,
      color: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20',
      href: '/disputes',
    },
    {
      title: 'Payments Today',
      value: fmtMoneyFull(m?.payments_today_cents ?? 0),
      icon: CreditCard,
      color: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20',
      href: '/payments',
    },
    {
      title: 'Pending Activities',
      value: fmtNum(m?.pending_activities ?? 0),
      icon: Clock,
      color: 'text-purple-600 bg-purple-50 dark:bg-purple-900/20',
      href: '/workflow',
    },
    {
      title: 'Queue Pending',
      value: fmtNum(m?.queue_accounts_pending ?? 0),
      icon: Activity,
      color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-900/20',
      href: '/workflow',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Welcome back, {user?.firstName || user?.email}
          {loading && <span className="ml-2 text-xs text-neutral-400">(refreshing…)</span>}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.title}
              href={card.href}
              className="group flex items-center gap-4 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className={cn('rounded-lg p-3', card.color)}>
                <Icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
                  {card.title}
                </p>
                <p className="text-2xl font-semibold text-neutral-900 dark:text-white tabular-nums">
                  {card.value}
                </p>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Account Status Breakdown */}
        {statusBreakdown.length > 0 && (
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm">
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700">
              <div className="flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-neutral-400" />
                <h2 className="text-lg font-medium text-neutral-900 dark:text-white">
                  Account Status Breakdown
                </h2>
              </div>
            </div>
            <div className="divide-y divide-neutral-100 dark:divide-neutral-700">
              {statusBreakdown.map((s) => (
                <div key={s.status} className="flex items-center justify-between px-6 py-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'inline-block h-2.5 w-2.5 rounded-full',
                        s.status === 'ACTIVE' && 'bg-green-500',
                        s.status === 'HOLD' && 'bg-amber-500',
                        s.status === 'LEGAL_HOLD' && 'bg-red-500',
                        s.status === 'CLOSED' && 'bg-neutral-400',
                        s.status === 'PAID_IN_FULL' && 'bg-blue-500',
                        s.status === 'SETTLED' && 'bg-teal-500',
                      )}
                    />
                    <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      {s.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <span className="text-sm font-semibold tabular-nums text-neutral-900 dark:text-white">
                    {fmtNum(s.count)}
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-between px-6 py-3 bg-neutral-50 dark:bg-neutral-750">
                <span className="text-sm font-semibold text-neutral-900 dark:text-white">Total</span>
                <span className="text-sm font-bold tabular-nums text-neutral-900 dark:text-white">
                  {fmtNum(statusBreakdown.reduce((sum, s) => sum + s.count, 0))}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Top Creditors */}
        {topCreditors.length > 0 && (
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm">
            <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-neutral-400" />
                <h2 className="text-lg font-medium text-neutral-900 dark:text-white">
                  Top Creditors by Balance
                </h2>
              </div>
            </div>
            <div className="divide-y divide-neutral-100 dark:divide-neutral-700">
              {topCreditors.map((c, i) => (
                <div key={c.client} className="flex items-center justify-between px-6 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30 text-xs font-bold text-primary-700 dark:text-primary-400">
                      {i + 1}
                    </span>
                    <span className="truncate text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      {c.client}
                    </span>
                  </div>
                  <div className="ml-4 shrink-0 text-right">
                    <p className="text-sm font-semibold tabular-nums text-neutral-900 dark:text-white">
                      {fmtMoney(c.balance_cents)}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {fmtNum(c.accounts)} accts
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick Links */}
        {topCreditors.length === 0 && statusBreakdown.length === 0 && (
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6 shadow-sm lg:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <Scale className="h-5 w-5 text-neutral-400" />
              <h2 className="text-lg font-medium text-neutral-900 dark:text-white">
                Quick Links
              </h2>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Accounts', href: '/accounts' },
                { label: 'Consumers', href: '/consumers' },
                { label: 'Payments', href: '/payments' },
                { label: 'Reports', href: '/reports' },
                { label: 'Litigation', href: '/litigation' },
                { label: 'Disputes', href: '/disputes' },
                { label: 'Trust', href: '/trust' },
                { label: 'Settings', href: '/settings' },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-lg border border-neutral-200 dark:border-neutral-700 px-4 py-3 text-center text-sm font-medium text-neutral-700 dark:text-neutral-300 hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:text-primary-700 dark:hover:text-primary-400 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="text-center text-xs text-neutral-500 dark:text-neutral-400">
        Data refreshes every 60 seconds. Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}
