'use client';

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from 'lucide-react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  pageCount?: number;
  pageIndex?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
}

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  emptyMessage = 'No results found',
  onRowClick,
  pageCount,
  pageIndex = 0,
  pageSize = 10,
  onPageChange,
  onPageSizeChange,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const showPagination =
    pageCount !== undefined && onPageChange !== undefined;

  const paginationState = useMemo(
    () => ({ pageIndex, pageSize }),
    [pageIndex, pageSize]
  );

  const onPaginationChange = (
    updater:
      | { pageIndex: number; pageSize: number }
      | ((old: { pageIndex: number; pageSize: number }) => {
          pageIndex: number;
          pageSize: number;
        })
  ) => {
    const next =
      typeof updater === 'function' ? updater(paginationState) : updater;
    onPageChange?.(next.pageIndex);
    if (next.pageSize !== pageSize) {
      onPageSizeChange?.(next.pageSize);
    }
  };

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      ...(showPagination ? { pagination: paginationState } : {}),
    },
    onSortingChange: setSorting,
    ...(showPagination
      ? {
          manualPagination: true,
          pageCount,
          onPaginationChange,
        }
      : {}),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const rows = table.getRowModel().rows;
  const colCount = columns.length;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-white shadow-sm dark:bg-neutral-800">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="border-b border-border bg-neutral-50 dark:bg-neutral-900/40"
              >
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={cn(
                      'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-600 dark:text-neutral-400',
                      header.column.getCanSort() &&
                        'cursor-pointer select-none hover:bg-neutral-100 dark:hover:bg-neutral-800'
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="inline-flex items-center gap-1">
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                      {header.column.getCanSort() ? (
                        <span className="text-neutral-400">
                          {header.column.getIsSorted() === 'desc' ? (
                            <ChevronDown className="h-4 w-4" aria-hidden />
                          ) : header.column.getIsSorted() === 'asc' ? (
                            <ChevronUp className="h-4 w-4" aria-hidden />
                          ) : (
                            <ChevronDown className="h-4 w-4 opacity-40" aria-hidden />
                          )}
                        </span>
                      ) : null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-b border-border last:border-0">
                  {Array.from({ length: Math.max(colCount, 1) }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <div
                        className="h-4 animate-pulse rounded bg-neutral-200 dark:bg-neutral-600"
                        style={{ width: `${60 + ((i + j) % 3) * 12}%` }}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={colCount || 1}
                  className="px-4 py-12 text-center text-sm text-neutral-500 dark:text-neutral-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    'border-b border-border transition-colors last:border-0',
                    onRowClick &&
                      'cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-700/50',
                    !onRowClick && 'hover:bg-neutral-50/80 dark:hover:bg-neutral-900/30'
                  )}
                  onClick={
                    onRowClick ? () => onRowClick(row.original) : undefined
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 text-foreground"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {showPagination && !isLoading && pageCount !== undefined ? (
        <div className="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            Page {pageIndex + 1} of {Math.max(pageCount, 1)}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={pageIndex <= 0}
              onClick={() => onPageChange?.(pageIndex - 1)}
              className={cn(
                'inline-flex h-9 items-center gap-1 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition-colors',
                'hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                'disabled:pointer-events-none disabled:opacity-40'
              )}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
              Previous
            </button>
            <button
              type="button"
              disabled={pageIndex >= pageCount - 1}
              onClick={() => onPageChange?.(pageIndex + 1)}
              className={cn(
                'inline-flex h-9 items-center gap-1 rounded-md border border-border bg-background px-3 text-sm font-medium shadow-sm transition-colors',
                'hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                'disabled:pointer-events-none disabled:opacity-40'
              )}
            >
              Next
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
