'use client';

import type { ReactNode } from 'react';
import { Edit, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DetailPanelProps {
  title: string;
  subtitle?: string;
  onClose?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  children: ReactNode;
}

export function DetailPanel({
  title,
  subtitle,
  onClose,
  onEdit,
  onDelete,
  children,
}: DetailPanelProps) {
  return (
    <div className="w-full overflow-hidden rounded-lg border border-border bg-white shadow-sm dark:bg-neutral-800">
      <header className="flex flex-col gap-4 border-b border-border px-6 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-semibold text-foreground">{title}</h2>
              {subtitle ? (
                <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
                  {subtitle}
                </p>
              ) : null}
            </div>
            {onClose ? (
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-md p-2 text-neutral-500 transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {onEdit ? (
            <button
              type="button"
              onClick={onEdit}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Edit className="h-4 w-4" aria-hidden />
              Edit
            </button>
          ) : null}
          {onDelete ? (
            <button
              type="button"
              onClick={onDelete}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-error-500/30 bg-error-50 px-3 text-sm font-medium text-error-700 shadow-sm transition-colors hover:bg-error-50/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error-500 dark:border-error-500/40 dark:bg-error-500/10 dark:text-error-500 dark:hover:bg-error-500/20"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              Delete
            </button>
          ) : null}
        </div>
      </header>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

interface FieldGroupProps {
  label: string;
  children: ReactNode;
}

export function FieldGroup({ label, children }: FieldGroupProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
        {label}
      </span>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

const gridCols: Record<1 | 2 | 3 | 4, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
};

interface FieldGridProps {
  children: ReactNode;
  cols?: 1 | 2 | 3 | 4;
}

export function FieldGrid({ children, cols = 2 }: FieldGridProps) {
  return (
    <div className={cn('grid gap-6', gridCols[cols])}>{children}</div>
  );
}
