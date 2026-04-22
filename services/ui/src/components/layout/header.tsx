'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Menu, Bell, Search, Moon, Sun, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

type SearchResult = {
  id: string;
  account_reference: string;
  original_creditor: string;
  total_balance: number;
  status: string;
};

const fmtMoney = (v: number | string | null) =>
  v != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
        Number(v) / 100
      )
    : '—';

export function Header() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [darkMode, setDarkMode] = useState(false);
  const [query, setQuery] = useState('');
  const [includeClosed, setIncludeClosed] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle('dark');
  };

  const doSearch = useCallback(
    async (term: string) => {
      if (!term.trim() || term.trim().length < 2) {
        setResults([]);
        setIsOpen(false);
        return;
      }
      setSearching(true);
      try {
        const params = new URLSearchParams({
          search: term.trim(),
          page: '1',
          page_size: '8',
        });
        if (!includeClosed) {
          params.set('status_group', 'open');
        }
        const { data } = await apiClient.get<{
          items?: SearchResult[];
          data?: SearchResult[];
        }>(`/api/v1/accounts?${params}`);
        const items = (data as any)?.items ?? (data as any)?.data ?? [];
        setResults(items);
        setIsOpen(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    },
    [includeClosed]
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, doSearch]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  function selectResult(id: string) {
    setIsOpen(false);
    setQuery('');
    router.push(`/accounts/${id}`);
  }

  function goToFullSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setIsOpen(false);
    const group = includeClosed ? '' : '&status_group=open';
    router.push(`/accounts?search=${encodeURIComponent(query.trim())}${group}`);
    setQuery('');
  }

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        <button className="lg:hidden p-2 rounded-md text-neutral-400 hover:text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-700">
          <Menu className="h-6 w-6" />
        </button>

        {/* Global search */}
        <div ref={wrapperRef} className="relative flex-1 max-w-lg mx-4">
          <form onSubmit={goToFullSearch}>
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => {
                if (results.length > 0) setIsOpen(true);
              }}
              placeholder="Search accounts, consumers…"
              className="w-full pl-10 pr-4 py-2 text-sm bg-neutral-50 dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  setResults([]);
                  setIsOpen(false);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </form>

          {/* Dropdown */}
          {isOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg overflow-hidden z-50">
              {/* Include closed toggle */}
              <div className="flex items-center gap-2 px-4 py-2 border-b border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-750">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-neutral-500">
                  <input
                    type="checkbox"
                    checked={includeClosed}
                    onChange={(e) => setIncludeClosed(e.target.checked)}
                    className="rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                  />
                  Include closed accounts
                </label>
                {searching && (
                  <span className="ml-auto text-xs text-neutral-400">Searching…</span>
                )}
              </div>

              {results.length > 0 ? (
                <ul className="max-h-80 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-700">
                  {results.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => selectResult(r.id)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">
                            {r.account_reference}
                          </p>
                          <p className="text-xs text-neutral-500 truncate">
                            {r.original_creditor}
                          </p>
                        </div>
                        <div className="ml-4 flex shrink-0 items-center gap-3">
                          <span className="text-sm font-medium tabular-nums text-foreground">
                            {fmtMoney(r.total_balance)}
                          </span>
                          <span
                            className={cn(
                              'rounded-full px-2 py-0.5 text-xs font-medium',
                              r.status === 'ACTIVE' || r.status === 'active'
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                : r.status === 'CLOSED' || r.status === 'closed'
                                ? 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-400'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            )}
                          >
                            {r.status}
                          </span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-neutral-500">
                  {searching
                    ? 'Searching…'
                    : query.trim().length < 2
                    ? 'Type at least 2 characters…'
                    : 'No accounts found'}
                </div>
              )}

              {results.length > 0 && (
                <button
                  type="button"
                  onClick={(e) => goToFullSearch(e as any)}
                  className="block w-full border-t border-neutral-100 dark:border-neutral-700 px-4 py-2.5 text-center text-xs font-medium text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/20"
                >
                  View all results for &ldquo;{query}&rdquo;
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right side */}
        <div className="flex items-center space-x-4">
          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-md text-neutral-400 hover:text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-700"
            title={darkMode ? 'Light mode' : 'Dark mode'}
          >
            {darkMode ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </button>

          <button className="relative p-2 rounded-md text-neutral-400 hover:text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-700">
            <Bell className="h-5 w-5" />
            <span className="absolute top-1 right-1 h-2 w-2 bg-error-500 rounded-full" />
          </button>
        </div>
      </div>
    </header>
  );
}
