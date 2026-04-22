'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { ColumnDef } from '@tanstack/react-table';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormField } from '@/components/shared/form-drawer';
import { StatusBadge } from '@/components/shared/status-badge';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/compliance';

const US_STATES = [
  'AL',
  'AK',
  'AZ',
  'AR',
  'CA',
  'CO',
  'CT',
  'DE',
  'FL',
  'GA',
  'NJ',
  'NY',
  'PA',
  'TX',
] as const;

const DEBT_CATEGORIES = [
  { value: 'written_contract', label: 'Written contract' },
  { value: 'oral_contract', label: 'Oral contract' },
  { value: 'promissory_note', label: 'Promissory note' },
  { value: 'open_account', label: 'Open account' },
  { value: 'judgment', label: 'Judgment' },
] as const;

type PolicyPackRow = Record<string, unknown> & {
  id?: string;
  name?: string;
  jurisdiction?: string;
  status?: string;
  version?: string;
};

export default function CompliancePage() {
  const { user } = useAuthStore();
  const token = useAuthStore((s) => s.accessToken);

  const { data: packs, isLoading: packsLoading } = useSWR(
    token ? ['compliance-packs', token] : null,
    async () => {
      const { data } = await apiClient.get<PolicyPackRow[]>(
        `${API}/policy-packs`
      );
      return data;
    }
  );

  const [activeState, setActiveState] = useState('NJ');
  const activeKey =
    token && activeState
      ? ([API + '/active', activeState, token] as const)
      : null;
  const { data: activePack, error: activeError } = useSWR(
    activeKey,
    async () => {
      try {
        const { data } = await apiClient.get<Record<string, unknown>>(
          `${API}/policy-packs/active/${activeState}`
        );
        return data;
      } catch (e: unknown) {
        const st =
          e &&
          typeof e === 'object' &&
          'response' in e &&
          (e as { response?: { status?: number } }).response?.status;
        if (st === 404) return null;
        throw e;
      }
    }
  );

  const [solJ, setSolJ] = useState('NJ');
  const [solCat, setSolCat] = useState<(typeof DEBT_CATEGORIES)[number]['value']>(
    'written_contract'
  );
  const [solResult, setSolResult] = useState<Record<string, unknown> | null>(
    null
  );
  const [solLoading, setSolLoading] = useState(false);

  const [usuryJ, setUsuryJ] = useState('NJ');
  const [usuryCat, setUsuryCat] = useState<
    (typeof DEBT_CATEGORIES)[number]['value']
  >('written_contract');
  const [usuryRate, setUsuryRate] = useState('18.99');
  const [usuryResult, setUsuryResult] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [usuryLoading, setUsuryLoading] = useState(false);

  const [crJ, setCrJ] = useState('NJ');
  const [crResult, setCrResult] = useState<Record<string, unknown> | null>(
    null
  );
  const [crLoading, setCrLoading] = useState(false);

  const packRows = packs ?? [];
  const packColumns: ColumnDef<PolicyPackRow>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'Name',
        cell: ({ row }) => String(row.original.name ?? row.original.id ?? '—'),
      },
      {
        accessorKey: 'jurisdiction',
        header: 'Jurisdiction',
        cell: ({ getValue }) => String(getValue() ?? '—'),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ getValue }) => (
          <StatusBadge status={String(getValue() ?? 'unknown')} />
        ),
      },
      {
        accessorKey: 'version',
        header: 'Version',
        cell: ({ getValue }) => String(getValue() ?? '—'),
      },
    ],
    []
  );

  async function runSolLookup() {
    setSolLoading(true);
    setSolResult(null);
    try {
      const { data } = await apiClient.get<Record<string, unknown>>(
        `${API}/statute-of-limitations/${solJ}/${solCat}`
      );
      setSolResult(data);
    } finally {
      setSolLoading(false);
    }
  }

  async function runUsuryCheck() {
    setUsuryLoading(true);
    setUsuryResult(null);
    try {
      const q = new URLSearchParams({
        jurisdiction: usuryJ,
        debt_category: usuryCat,
        rate: usuryRate,
      });
      const { data } = await apiClient.post<Record<string, unknown>>(
        `${API}/validate-rate?${q.toString()}`
      );
      setUsuryResult(data);
    } finally {
      setUsuryLoading(false);
    }
  }

  async function runContactRules() {
    setCrLoading(true);
    setCrResult(null);
    try {
      const { data } = await apiClient.get<Record<string, unknown>>(
        `${API}/contact-rules/${crJ}`
      );
      setCrResult(data);
    } finally {
      setCrLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Compliance"
        subtitle={
          user
            ? `Policy packs, SOL, usury, and contact rules · ${user.email}`
            : 'Jurisdiction rules and validation tools'
        }
      />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Policy packs</h2>
        <DataTable<PolicyPackRow>
          columns={packColumns}
          data={packRows}
          isLoading={packsLoading}
          emptyMessage="No policy packs returned"
        />
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">
          Active pack by jurisdiction
        </h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Select a state to load the active policy pack for that jurisdiction.
        </p>
        <div className="mt-4 flex max-w-xs flex-col gap-2">
          <label className="text-sm font-medium">State</label>
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={activeState}
            onChange={(e) => setActiveState(e.target.value)}
          >
            {US_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        {activeError ? (
          <p className="mt-4 text-sm text-error-600">
            Unable to load active pack.
          </p>
        ) : activePack === undefined ? (
          <p className="mt-4 text-sm text-neutral-500">Loading…</p>
        ) : activePack === null ? (
          <p className="mt-4 text-sm text-neutral-500">
            No active policy pack for {activeState}.
          </p>
        ) : (
          <pre className="mt-4 max-h-64 overflow-auto rounded-md bg-muted p-4 text-xs">
            {JSON.stringify(activePack, null, 2)}
          </pre>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">SOL lookup</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          GET /statute-of-limitations/&#123;jurisdiction&#125;/&#123;category&#125;
        </p>
        <div className="mt-4 grid max-w-2xl gap-4 sm:grid-cols-2">
          <FormField label="Jurisdiction">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={solJ}
              onChange={(e) => setSolJ(e.target.value)}
            >
              {US_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Debt category">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={solCat}
              onChange={(e) =>
                setSolCat(e.target.value as typeof solCat)
              }
            >
              {DEBT_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </FormField>
        </div>
        <button
          type="button"
          className="mt-4 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          disabled={solLoading}
          onClick={runSolLookup}
        >
          {solLoading ? 'Loading…' : 'Lookup SOL'}
        </button>
        {solResult && (
          <pre className="mt-4 max-h-56 overflow-auto rounded-md bg-muted p-4 text-xs">
            {JSON.stringify(solResult, null, 2)}
          </pre>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Usury check</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          POST /validate-rate with jurisdiction, debt category, and rate.
        </p>
        <div className="mt-4 grid max-w-2xl gap-4 sm:grid-cols-3">
          <FormField label="Jurisdiction">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={usuryJ}
              onChange={(e) => setUsuryJ(e.target.value)}
            >
              {US_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Debt category">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={usuryCat}
              onChange={(e) =>
                setUsuryCat(e.target.value as typeof usuryCat)
              }
            >
              {DEBT_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Rate (% APR)">
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={usuryRate}
              onChange={(e) => setUsuryRate(e.target.value)}
            />
          </FormField>
        </div>
        <button
          type="button"
          className="mt-4 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          disabled={usuryLoading}
          onClick={runUsuryCheck}
        >
          {usuryLoading ? 'Checking…' : 'Validate rate'}
        </button>
        {usuryResult && (
          <pre className="mt-4 max-h-56 overflow-auto rounded-md bg-muted p-4 text-xs">
            {JSON.stringify(usuryResult, null, 2)}
          </pre>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Contact rules</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          GET /contact-rules/&#123;jurisdiction&#125;
        </p>
        <div className="mt-4 max-w-xs">
          <FormField label="Jurisdiction">
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={crJ}
              onChange={(e) => setCrJ(e.target.value)}
            >
              {US_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FormField>
        </div>
        <button
          type="button"
          className="mt-4 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          disabled={crLoading}
          onClick={runContactRules}
        >
          {crLoading ? 'Loading…' : 'Load contact rules'}
        </button>
        {crResult && (
          <pre className="mt-4 max-h-56 overflow-auto rounded-md bg-muted p-4 text-xs">
            {JSON.stringify(crResult, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}
