'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, LogOut, ShieldAlert } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';

function formatRemaining(ms: number): string {
  if (ms <= 0) return 'expired';
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ImpersonationBanner() {
  const router = useRouter();
  const { user, impersonation, exitImpersonation } = useAuthStore();
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    if (!impersonation) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [impersonation]);

  if (!user?.actingAsMaster || !impersonation) return null;

  const remaining = impersonation.expiresAt - now;
  const isReadOnly = !user.actingCanWrite;

  const onExit = async () => {
    await exitImpersonation();
    router.replace('/master');
  };

  return (
    <div
      className={
        'sticky top-0 z-30 border-b px-4 py-2 text-sm flex items-center gap-3 ' +
        (isReadOnly
          ? 'bg-amber-100 border-amber-300 text-amber-900 dark:bg-amber-900/30 dark:text-amber-100'
          : 'bg-red-100 border-red-300 text-red-900 dark:bg-red-900/30 dark:text-red-100')
      }
      role="alert"
      aria-live="polite"
    >
      {isReadOnly ? (
        <Eye className="h-4 w-4 flex-shrink-0" aria-hidden />
      ) : (
        <ShieldAlert className="h-4 w-4 flex-shrink-0" aria-hidden />
      )}
      <div className="flex-1 min-w-0">
        <span className="font-semibold">Master impersonation</span>
        <span className="mx-2">·</span>
        <span>
          You are <strong>{user.email}</strong> acting as{' '}
          <strong>{impersonation.tenantSlug}</strong>{' '}
          ({isReadOnly ? 'read-only' : 'WRITE ENABLED'})
        </span>
        <span className="mx-2">·</span>
        <span className="font-mono">{formatRemaining(remaining)}</span>
      </div>
      <button
        type="button"
        onClick={onExit}
        className={
          'inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ' +
          'border bg-white/80 hover:bg-white dark:bg-black/30 dark:hover:bg-black/40 ' +
          (isReadOnly ? 'border-amber-400' : 'border-red-400')
        }
      >
        <LogOut className="h-3 w-3" aria-hidden />
        Exit impersonation
      </button>
    </div>
  );
}
