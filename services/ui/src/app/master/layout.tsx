'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import {
  Activity,
  Building2,
  History,
  LogOut,
  ShieldCheck,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { cn } from '@/lib/utils';

const NAV = [
  { href: '/master', label: 'Overview', icon: Activity, exact: true },
  { href: '/master/tenants', label: 'Tenants', icon: Building2 },
  { href: '/master/audit', label: 'Audit log', icon: History },
];

export default function MasterLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, user, logout } = useAuthStore();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!user?.isMaster) {
      router.replace('/dashboard');
      return;
    }
    if (user?.actingAsMaster) {
      // Master is in a tenant — they belong in the operational app.
      router.replace('/dashboard');
    }
  }, [isAuthenticated, isLoading, user, router]);

  if (isLoading || !isAuthenticated || !user?.isMaster || user?.actingAsMaster) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900">
      <aside className="fixed inset-y-0 left-0 hidden lg:flex w-64 flex-col border-r border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950">
        <div className="px-5 py-5 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary-600" />
            <span className="font-semibold">Master console</span>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            Platform administration
          </p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2 rounded px-3 py-2 text-sm',
                  active
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-200'
                    : 'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-neutral-200 dark:border-neutral-800 p-3 space-y-2">
          <div className="text-xs text-neutral-500 px-2 truncate" title={user.email}>
            {user.email}
          </div>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace('/login');
            }}
            className="w-full flex items-center gap-2 rounded px-3 py-2 text-sm text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>
      <div className="lg:pl-64">
        <main className="py-6 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
