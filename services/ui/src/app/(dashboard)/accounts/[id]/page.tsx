'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  CreditCard,
  FileText,
  MessageSquarePlus,
  Send,
  Clock,
  CheckCircle,
  User,
  Phone,
  Mail,
  MapPin,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { StatusBadge } from '@/components/shared/status-badge';

const fmtMoney = (v: number | string | null | undefined) =>
  v != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(v) / 100)
    : '—';

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString() : '—';

const fmtDateTime = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString() : '—';

function parseNote(raw: string | null | undefined): { description: string; details: string; meta: Record<string, string> } {
  if (!raw) return { description: '', details: '', meta: {} };
  const lines = raw.split('\n');
  const meta: Record<string, string> = {};
  const freeText: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx > 0 && eqIdx < 20 && /^[A-Z_]+$/i.test(trimmed.slice(0, eqIdx))) {
      const key = trimmed.slice(0, eqIdx).toUpperCase();
      const val = trimmed.slice(eqIdx + 1).replace(/^"|"$/g, '').trim();
      if (key === 'NOTES' || key === 'CMT') {
        if (val) freeText.push(val);
      } else {
        meta[key] = val;
      }
    } else {
      freeText.push(trimmed);
    }
  }

  const description = meta.DESCRIPT || meta.CODE || freeText[0] || 'Activity';
  const details = freeText.join('\n');
  return { description, details, meta };
}

const PREVIEW_CHARS = 180;

function HistoryCard({ item }: { item: any }) {
  const [expanded, setExpanded] = useState(false);
  const parsed = item.type === 'activity' ? parseNote(item.notes) : null;
  const isManualNote = item.result && (item.result as any).type === 'manual_note';
  const typeLabel = item.hist_type === 'A' ? 'Activity' : item.hist_type === 'N' ? 'Note' : item.hist_type === 'S' ? 'System' : item.hist_type || '';

  const rawContent = isManualNote ? (item.notes || '') : (parsed?.details || '');
  const isLong = rawContent.length > PREVIEW_CHARS;

  return (
    <div
      className={cn(
        'rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-5 py-4',
        isLong && 'cursor-pointer hover:border-neutral-300 dark:hover:border-neutral-600'
      )}
      onClick={isLong ? () => setExpanded(!expanded) : undefined}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          'mt-0.5 rounded-lg p-2 shrink-0',
          item.type === 'payment'
            ? 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400'
            : isManualNote
              ? 'bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400'
              : 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
        )}>
          {item.type === 'payment' ? (
            <CreditCard className="h-4 w-4" />
          ) : isManualNote ? (
            <MessageSquarePlus className="h-4 w-4" />
          ) : item.status === 'COMPLETED' || item.status === 'completed' ? (
            <CheckCircle className="h-4 w-4" />
          ) : item.status === 'SCHEDULED' || item.status === 'scheduled' ? (
            <Clock className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-medium text-neutral-900 dark:text-white">
                {item.type === 'payment' ? (
                  <>Payment — {fmtMoney(item.amount_cents)} via {item.method?.replace(/_/g, ' ') || 'unknown'}</>
                ) : isManualNote ? (
                  'Manual Note'
                ) : (
                  parsed?.description || 'Activity'
                )}
              </p>
              {typeLabel && (
                <span className={cn(
                  'rounded px-1.5 py-0.5 text-xs',
                  typeLabel === 'Note' ? 'bg-amber-50 text-amber-600 dark:bg-amber-900/20' :
                  typeLabel === 'System' ? 'bg-neutral-100 text-neutral-500 dark:bg-neutral-700' :
                  'bg-blue-50 text-blue-600 dark:bg-blue-900/20'
                )}>{typeLabel}</span>
              )}
              {item.tag && item.tag !== 'N' && item.tag !== 'A' && item.tag !== 'S' && (
                <span className="rounded bg-neutral-100 dark:bg-neutral-700 px-1.5 py-0.5 text-xs text-neutral-500">{item.tag}</span>
              )}
              {parsed?.meta?.OP && (
                <span className="text-xs text-neutral-400">by {parsed.meta.OP}</span>
              )}
            </div>
            <span className="text-xs text-neutral-400 shrink-0">
              {fmtDateTime(item.date)}
            </span>
          </div>

          {item.type === 'activity' && parsed && (
            <div className="mt-2 space-y-1">
              {parsed.details && (
                <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap leading-relaxed">
                  {!expanded && isLong ? parsed.details.slice(0, PREVIEW_CHARS) + '...' : parsed.details}
                </p>
              )}
              {(expanded || !isLong) && Object.keys(parsed.meta).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400">
                  {parsed.meta.ASSOC && <span>Assoc: {parsed.meta.ASSOC}</span>}
                  {parsed.meta.ACTDATE && parsed.meta.ACTDATE !== '01/01/1900' && <span>Date: {parsed.meta.ACTDATE}</span>}
                  {parsed.meta.CODE && parsed.meta.CODE !== parsed.description && <span>Code: {parsed.meta.CODE}</span>}
                </div>
              )}
              {isLong && (
                <button
                  type="button"
                  className="text-xs text-primary-600 dark:text-primary-400 hover:underline mt-1"
                  onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                >
                  {expanded ? 'Show less' : 'Show more'}
                </button>
              )}
            </div>
          )}

          {isManualNote && item.notes && (
            <p className="mt-1 text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
              {!expanded && isLong ? item.notes.slice(0, PREVIEW_CHARS) + '...' : item.notes}
              {isLong && (
                <button
                  type="button"
                  className="ml-1 text-xs text-primary-600 dark:text-primary-400 hover:underline"
                  onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                >
                  {expanded ? 'Show less' : 'Show more'}
                </button>
              )}
            </p>
          )}

          {item.type === 'payment' && (
            <p className="mt-1 text-xs text-neutral-500">
              Status: <span className="font-medium">{item.status}</span>
              {item.source && <> · Source: {item.source}</>}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

type Debtor = {
  id: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  suffix: string | null;
  ssn_last_four: string | null;
  date_of_birth: string | null;
  is_deceased: boolean;
  is_represented: boolean;
  attorney_name: string | null;
  attorney_contact: string | null;
  phones: { type: string; value: string; is_primary: boolean }[];
  emails: { value: string; is_primary: boolean }[];
  addresses: {
    type: string; line1: string | null; line2: string | null;
    city: string | null; state: string | null; zip: string | null;
    is_primary: boolean;
  }[];
};

type AccountDetail = {
  id: string;
  account_reference: string;
  consumer_id: string;
  original_creditor: string;
  current_creditor: string | null;
  client_account_number: string | null;
  status: string;
  debt_type: string;
  jurisdiction: string;
  original_principal: number;
  current_principal: number;
  current_interest: number;
  current_fees: number;
  total_balance: number;
  date_placed: string | null;
  date_of_service: string | null;
  date_of_first_delinquency: string | null;
  legal_hold: boolean;
  legal_hold_reason: string | null;
  legal_hold_date: string | null;
  debtor: Debtor | null;
};

type HistoryItem = {
  type: 'activity' | 'payment';
  id: string;
  date: string;
  notes?: string | null;
  result?: Record<string, unknown> | null;
  status?: string | null;
  priority?: string | null;
  amount_cents?: number;
  method?: string | null;
  source?: string | null;
  tag?: string;
  hist_type?: string;
};

type TabKey = 'history' | 'debtor' | 'details';
type EntryTypeFilter = 'all' | 'activity' | 'payment';

const PAGE_SIZE = 50;

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const accountId = params.id as string;

  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [activityCount, setActivityCount] = useState(0);
  const [paymentCount, setPaymentCount] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>('history');
  const [noteText, setNoteText] = useState('');
  const [addingNote, setAddingNote] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // History search & filter
  const [historySearch, setHistorySearch] = useState('');
  const [historySearchCommitted, setHistorySearchCommitted] = useState('');
  const [historyTypeFilter, setHistoryTypeFilter] = useState<EntryTypeFilter>('all');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadAccount = useCallback(async () => {
    try {
      const res = await apiClient.get<AccountDetail>(`/api/v1/accounts/${accountId}`);
      setAccount(res.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load account:', err);
      setAccount(null);
      setError(`Failed to load account: ${err?.response?.data?.detail || err?.message || 'Unknown error'}`);
    }
  }, [accountId]);

  const loadHistory = useCallback(async (p: number, search: string, typeFilter: EntryTypeFilter) => {
    setHistoryLoading(true);
    try {
      const qp = new URLSearchParams({
        page: String(p),
        page_size: String(PAGE_SIZE),
      });
      if (search) qp.set('search', search);
      if (typeFilter !== 'all') qp.set('entry_type', typeFilter);

      const res = await apiClient.get<any>(
        `/api/v1/accounts/${accountId}/history?${qp.toString()}`
      );
      const d = res.data;
      setHistory(d.items ?? []);
      setHistoryTotal(d.total ?? 0);
      setActivityCount(d.activity_count ?? 0);
      setPaymentCount(d.payment_count ?? 0);
    } catch (err: any) {
      console.error('Failed to load history:', err);
      setHistory([]);
      setHistoryTotal(0);
    } finally {
      setHistoryLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    async function init() {
      setLoading(true);
      await Promise.all([loadAccount(), loadHistory(1, '', 'all')]);
      setLoading(false);
    }
    init();
  }, [loadAccount, loadHistory]);

  // Re-fetch when page, search, or type filter changes
  useEffect(() => {
    if (!loading) {
      loadHistory(historyPage, historySearchCommitted, historyTypeFilter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyPage, historySearchCommitted, historyTypeFilter]);

  function handleSearchInput(value: string) {
    setHistorySearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setHistoryPage(1);
      setHistorySearchCommitted(value.trim());
    }, 400);
  }

  function clearSearch() {
    setHistorySearch('');
    setHistorySearchCommitted('');
    setHistoryPage(1);
  }

  function handleTypeFilterChange(t: EntryTypeFilter) {
    setHistoryTypeFilter(t);
    setHistoryPage(1);
  }

  async function handleAddNote() {
    if (!noteText.trim()) return;
    setAddingNote(true);
    try {
      await apiClient.post(`/api/v1/accounts/${accountId}/notes`, {
        notes: noteText.trim(),
      });
      setNoteText('');
      setNoteOpen(false);
      setHistoryPage(1);
      await loadHistory(1, historySearchCommitted, historyTypeFilter);
    } catch {
      alert('Failed to add note');
    } finally {
      setAddingNote(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!account) {
    return (
      <div className="text-center py-20">
        <p className="text-neutral-500">{error || 'Account not found'}</p>
        {error && <p className="text-xs text-red-500 mt-2 max-w-lg mx-auto">{error}</p>}
        <Link href="/accounts" className="text-primary-600 text-sm mt-2 inline-block">Back to accounts</Link>
      </div>
    );
  }

  const historyPages = Math.max(1, Math.ceil(historyTotal / PAGE_SIZE));
  const debtor = account.debtor;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <button onClick={() => router.back()} className="p-2 rounded-md hover:bg-muted">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-2xl font-semibold text-neutral-900 dark:text-white">
              {account.account_reference}
            </h1>
            <p className="text-sm text-neutral-500">
              {account.original_creditor}
              {debtor && <> · <span className="font-medium text-neutral-700 dark:text-neutral-300">{debtor.first_name} {debtor.last_name}</span></>}
            </p>
          </div>
          <StatusBadge status={account.status} />
        </div>
        <button
          type="button"
          onClick={() => setNoteOpen(!noteOpen)}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
        >
          <MessageSquarePlus className="h-4 w-4" />
          Add Note
        </button>
      </div>

      {/* Debtor quick info bar */}
      {debtor && (
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-5 py-3 flex items-center gap-6 flex-wrap text-sm">
          <div className="flex items-center gap-2 text-neutral-700 dark:text-neutral-300">
            <User className="h-4 w-4 text-neutral-400" />
            <span className="font-medium">{debtor.first_name} {debtor.middle_name ? debtor.middle_name + ' ' : ''}{debtor.last_name}{debtor.suffix ? ' ' + debtor.suffix : ''}</span>
            {debtor.ssn_last_four && <span className="text-neutral-400 ml-1">SSN: ***-**-{debtor.ssn_last_four}</span>}
          </div>
          {debtor.date_of_birth && (
            <span className="text-neutral-500">DOB: {fmtDate(debtor.date_of_birth)}</span>
          )}
          {debtor.phones.length > 0 && (
            <div className="flex items-center gap-1 text-neutral-500">
              <Phone className="h-3.5 w-3.5" />
              {debtor.phones[0].value}
            </div>
          )}
          {debtor.emails.length > 0 && (
            <div className="flex items-center gap-1 text-neutral-500">
              <Mail className="h-3.5 w-3.5" />
              {debtor.emails[0].value}
            </div>
          )}
          {debtor.is_deceased && <span className="rounded-full bg-red-100 text-red-700 px-2 py-0.5 text-xs font-medium">Deceased</span>}
          {debtor.is_represented && <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-xs font-medium">Represented by Attorney</span>}
        </div>
      )}

      {/* Balance cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {[
          { label: 'Total Balance', value: account.total_balance, highlight: true },
          { label: 'Principal', value: account.current_principal },
          { label: 'Interest', value: account.current_interest },
          { label: 'Fees/Costs', value: account.current_fees },
          { label: 'Original', value: account.original_principal },
        ].map((b) => (
          <div
            key={b.label}
            className={cn(
              'rounded-xl border p-4',
              b.highlight
                ? 'border-primary-200 bg-primary-50 dark:border-primary-800 dark:bg-primary-900/20'
                : 'border-neutral-200 bg-white dark:border-neutral-700 dark:bg-neutral-800'
            )}
          >
            <p className="text-xs font-medium text-neutral-500 uppercase">{b.label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-neutral-900 dark:text-white">
              {fmtMoney(b.value)}
            </p>
          </div>
        ))}
      </div>

      {/* Add note form */}
      {noteOpen && (
        <div className="rounded-xl border border-primary-200 dark:border-primary-800 bg-primary-50/50 dark:bg-primary-900/10 p-4">
          <div className="flex items-start gap-3">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Type your note here..."
              rows={3}
              className="flex-1 rounded-lg border border-input bg-background px-4 py-3 text-sm resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleAddNote}
                disabled={addingNote || !noteText.trim()}
                className="inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
                {addingNote ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => { setNoteOpen(false); setNoteText(''); }}
                className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-6 border-b border-neutral-200 dark:border-neutral-700">
        {([
          { key: 'history' as TabKey, label: `History (${historyTotal})` },
          { key: 'debtor' as TabKey, label: 'Debtor Info' },
          { key: 'details' as TabKey, label: 'Account Details' },
        ]).map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'relative pb-3 text-sm font-medium transition-colors',
              tab === t.key
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300'
            )}
          >
            {t.label}
            {tab === t.key && (
              <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-primary-600 dark:bg-primary-400" />
            )}
          </button>
        ))}
      </div>

      {/* History tab */}
      {tab === 'history' && (
        <div className="space-y-4">
          {/* Search + filter bar */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="relative flex-1 w-full sm:max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
              <input
                type="text"
                value={historySearch}
                onChange={(e) => handleSearchInput(e.target.value)}
                placeholder="Search notes, tags, payment method…"
                className="w-full rounded-lg border border-input bg-background pl-10 pr-9 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {historySearch && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-0.5">
              {([
                { key: 'all' as EntryTypeFilter, label: 'All', count: activityCount + paymentCount },
                { key: 'activity' as EntryTypeFilter, label: 'Activities', count: activityCount },
                { key: 'payment' as EntryTypeFilter, label: 'Payments', count: paymentCount },
              ]).map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => handleTypeFilterChange(f.key)}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                    historyTypeFilter === f.key
                      ? 'bg-primary-600 text-white'
                      : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700'
                  )}
                >
                  {f.label} ({f.count.toLocaleString()})
                </button>
              ))}
            </div>
          </div>

          {/* Filtered results info */}
          {(historySearchCommitted || historyTypeFilter !== 'all') && (
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Filter className="h-3.5 w-3.5" />
              <span>
                {historyTotal.toLocaleString()} result{historyTotal !== 1 ? 's' : ''}
                {historySearchCommitted && <> matching &ldquo;{historySearchCommitted}&rdquo;</>}
              </span>
              {(historySearchCommitted || historyTypeFilter !== 'all') && (
                <button
                  type="button"
                  onClick={() => { clearSearch(); setHistoryTypeFilter('all'); }}
                  className="text-primary-600 hover:underline ml-1"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}

          {historyLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-12 text-center text-neutral-500">
              {historySearchCommitted
                ? `No results matching "${historySearchCommitted}"`
                : 'No history entries found for this account.'}
            </div>
          ) : (
            <div className="space-y-2">
              {history.map((item) => (
                <HistoryCard key={`${item.type}-${item.id}`} item={item} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {historyPages > 1 && !historyLoading && (
            <div className="flex items-center justify-between pt-2 border-t border-neutral-100 dark:border-neutral-800">
              <p className="text-sm text-neutral-500">
                Showing {((historyPage - 1) * PAGE_SIZE) + 1}–{Math.min(historyPage * PAGE_SIZE, historyTotal)} of {historyTotal.toLocaleString()}
              </p>
              <div className="flex items-center gap-1">
                <button
                  disabled={historyPage <= 1}
                  onClick={() => setHistoryPage(1)}
                  className="h-8 rounded-md border border-border px-2 text-xs disabled:opacity-30 hover:bg-muted"
                  title="First page"
                >
                  1
                </button>
                <button
                  disabled={historyPage <= 1}
                  onClick={() => setHistoryPage((p) => p - 1)}
                  className="h-8 rounded-md border border-border px-2 text-sm disabled:opacity-30 hover:bg-muted"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="px-3 text-sm font-medium text-neutral-700 dark:text-neutral-300">
                  {historyPage} / {historyPages}
                </span>
                <button
                  disabled={historyPage >= historyPages}
                  onClick={() => setHistoryPage((p) => p + 1)}
                  className="h-8 rounded-md border border-border px-2 text-sm disabled:opacity-30 hover:bg-muted"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  disabled={historyPage >= historyPages}
                  onClick={() => setHistoryPage(historyPages)}
                  className="h-8 rounded-md border border-border px-2 text-xs disabled:opacity-30 hover:bg-muted"
                  title="Last page"
                >
                  {historyPages}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Debtor tab */}
      {tab === 'debtor' && (
        <div className="space-y-6">
          {debtor ? (
            <>
              {/* Identity */}
              <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6">
                <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-4 flex items-center gap-2">
                  <User className="h-4 w-4" /> Identity
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Field label="First Name" value={debtor.first_name} />
                  <Field label="Middle Name" value={debtor.middle_name} />
                  <Field label="Last Name" value={debtor.last_name} />
                  <Field label="Suffix" value={debtor.suffix} />
                  <Field label="SSN (last 4)" value={debtor.ssn_last_four ? `***-**-${debtor.ssn_last_four}` : null} />
                  <Field label="Date of Birth" value={fmtDate(debtor.date_of_birth)} />
                  <Field label="Deceased" value={debtor.is_deceased ? 'Yes' : 'No'} />
                  <Field label="Represented" value={debtor.is_represented ? `Yes — ${debtor.attorney_name || 'Unknown'}` : 'No'} />
                </div>
                {debtor.attorney_contact && (
                  <div className="mt-3">
                    <Field label="Attorney Contact" value={debtor.attorney_contact} />
                  </div>
                )}
              </div>

              {/* Phone numbers */}
              {debtor.phones.length > 0 && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6">
                  <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-4 flex items-center gap-2">
                    <Phone className="h-4 w-4" /> Phone Numbers ({debtor.phones.length})
                  </h3>
                  <div className="space-y-2">
                    {debtor.phones.map((ph, i) => (
                      <div key={i} className="flex items-center gap-3 text-sm">
                        <span className="text-neutral-900 dark:text-white font-medium">{ph.value}</span>
                        <span className="text-neutral-400 capitalize text-xs">{ph.type.replace(/_/g, ' ')}</span>
                        {ph.is_primary && <span className="rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400 px-2 py-0.5 text-xs">Primary</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Emails */}
              {debtor.emails.length > 0 && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6">
                  <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-4 flex items-center gap-2">
                    <Mail className="h-4 w-4" /> Email Addresses ({debtor.emails.length})
                  </h3>
                  <div className="space-y-2">
                    {debtor.emails.map((em, i) => (
                      <div key={i} className="flex items-center gap-3 text-sm">
                        <span className="text-neutral-900 dark:text-white font-medium">{em.value}</span>
                        {em.is_primary && <span className="rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400 px-2 py-0.5 text-xs">Primary</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Addresses */}
              {debtor.addresses.length > 0 && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6">
                  <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-4 flex items-center gap-2">
                    <MapPin className="h-4 w-4" /> Addresses ({debtor.addresses.length})
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {debtor.addresses.map((addr, i) => (
                      <div key={i} className="rounded-lg border border-neutral-100 dark:border-neutral-700 p-4">
                        <p className="text-xs text-neutral-400 uppercase mb-1 capitalize">{addr.type.replace(/_/g, ' ')}{addr.is_primary ? ' (Primary)' : ''}</p>
                        <p className="text-sm text-neutral-900 dark:text-white">{addr.line1}</p>
                        {addr.line2 && <p className="text-sm text-neutral-900 dark:text-white">{addr.line2}</p>}
                        <p className="text-sm text-neutral-900 dark:text-white">{addr.city}, {addr.state} {addr.zip}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-12 text-center text-neutral-500">
              No debtor information linked to this account.
            </div>
          )}
        </div>
      )}

      {/* Details tab */}
      {tab === 'details' && (
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <Field label="Account Reference" value={account.account_reference} />
            <Field label="Consumer ID" value={account.consumer_id} mono />
            <Field label="Original Creditor" value={account.original_creditor} />
            <Field label="Current Creditor" value={account.current_creditor} />
            <Field label="Client Account #" value={account.client_account_number} />
            <Field label="Status" value={account.status} />
            <Field label="Debt Type" value={account.debt_type} />
            <Field label="Jurisdiction" value={account.jurisdiction} />
            <Field label="Date Placed" value={fmtDate(account.date_placed)} />
            <Field label="Date of Service" value={fmtDate(account.date_of_service)} />
            <Field label="First Delinquency" value={fmtDate(account.date_of_first_delinquency)} />
            <Field label="Legal Hold" value={account.legal_hold ? `Yes — ${account.legal_hold_reason || 'No reason'}` : 'No'} />
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs font-medium text-neutral-500 uppercase">{label}</p>
      <p className={cn('mt-1 text-sm text-neutral-900 dark:text-white', mono && 'font-mono text-xs')}>
        {value || '—'}
      </p>
    </div>
  );
}
