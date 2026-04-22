'use client';

import { cn } from '@/lib/utils';

const DEFAULT_COLOR_MAP: Record<string, string> = {
  active: 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  completed: 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  pending: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500',
  failed: 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500',
  open: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  closed: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300',
  investigating: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500',
  resolved: 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  draft: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300',
  published: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  processing: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  error: 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500',
  warning: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500',
  filed: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  served: 'bg-accent text-accent-foreground',
  judgment: 'bg-neutral-100 text-neutral-800 dark:bg-neutral-700 dark:text-neutral-200',
  dismissed: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400',
  garnishment: 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-500',
  scheduled: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
  ready: 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  cancelled: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400',
  matched: 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500',
  unmatched: 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-500',
};

function formatStatusLabel(status: string): string {
  return status
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

interface StatusBadgeProps {
  status: string;
  colorMap?: Record<string, string>;
}

export function StatusBadge({ status, colorMap }: StatusBadgeProps) {
  const key = status.toLowerCase().trim();
  const merged = { ...DEFAULT_COLOR_MAP, ...colorMap };
  const colorClass =
    merged[key] ??
    'bg-neutral-100 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300';

  return (
    <span
      className={cn(
        'inline-flex max-w-full items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        colorClass
      )}
    >
      {formatStatusLabel(status)}
    </span>
  );
}
