'use client';

import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { PageHeader } from '@/components/shared/page-header';
import { FormField } from '@/components/shared/form-drawer';
import { StatusBadge } from '@/components/shared/status-badge';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { cn } from '@/lib/utils';

const API = '/api/v1/integrations';

type IntegrationStatus = {
  idp?: { provider?: string; status?: string; last_sync?: string | null };
  payments?: {
    provider?: string;
    status?: string;
    tokenization_enabled?: boolean;
  };
  telephony?: {
    provider?: string;
    status?: string;
    voice_enabled?: boolean;
    sms_enabled?: boolean;
  };
  efiling?: { status?: string; connectors?: unknown[] };
};

export default function IntegrationsPage() {
  const { user } = useAuthStore();
  const token = useAuthStore((s) => s.accessToken);

  const { data: status, mutate: mutStatus } = useSWR(
    token ? ['integrations-status', token] : null,
    async () => {
      const { data } = await apiClient.get<IntegrationStatus>(`${API}/status`);
      return data;
    }
  );

  const { data: idpProviders } = useSWR(
    token ? ['idp-providers', token] : null,
    async () => {
      const { data } = await apiClient.get<
        { id: string; name: string; type: string }[]
      >(`${API}/idp/providers`);
      return data;
    }
  );

  const { data: efilingConnectors } = useSWR(
    token ? ['efiling-connectors', token] : null,
    async () => {
      const { data } = await apiClient.get<
        { id: string; name: string; jurisdiction: string; status: string }[]
      >(`${API}/efiling/connectors`);
      return data;
    }
  );

  const [idpProvider, setIdpProvider] = useState('azure_ad');
  const [idpJson, setIdpJson] = useState(
    '{\n  "tenant_id": "",\n  "client_id": "",\n  "client_secret": ""\n}'
  );

  const [efilingConnector, setEfilingConnector] = useState('nj_ecourts');
  const [efilingJson, setEfilingJson] = useState(
    '{\n  "username": "",\n  "password": "",\n  "firm_id": ""\n}'
  );

  const [testBusy, setTestBusy] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<Record<string, string>>({});

  async function testConnection(type: string) {
    setTestBusy(type);
    setTestMsg((m) => ({ ...m, [type]: '' }));
    try {
      const { data } = await apiClient.post<{
        message?: string;
        status?: string;
      }>(`${API}/test-connection/${type}`);
      setTestMsg((m) => ({
        ...m,
        [type]: data.message ?? data.status ?? 'OK',
      }));
    } catch (e: unknown) {
      setTestMsg((m) => ({
        ...m,
        [type]: 'Failed — check permissions and configuration',
      }));
    } finally {
      setTestBusy(null);
      await mutStatus();
    }
  }

  async function saveIdp() {
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(idpJson) as Record<string, unknown>;
    } catch {
      alert('Invalid JSON for IdP config');
      return;
    }
    const q = new URLSearchParams({ provider: idpProvider });
    await apiClient.post(`${API}/idp/configure?${q.toString()}`, config);
    await mutStatus();
  }

  async function saveEfiling() {
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(efilingJson) as Record<string, unknown>;
    } catch {
      alert('Invalid JSON for e-filing config');
      return;
    }
    await apiClient.post(`${API}/efiling/configure/${efilingConnector}`, config);
    await mutStatus();
  }

  const cards = [
    {
      key: 'idp',
      title: 'IdP',
      subtitle: 'Identity provider',
      badge: status?.idp?.status,
      extra: status?.idp?.provider,
    },
    {
      key: 'payments',
      title: 'Payments',
      subtitle: status?.payments?.provider ?? 'Processor',
      badge: status?.payments?.status,
      extra: status?.payments?.tokenization_enabled
        ? 'Tokenization on'
        : undefined,
    },
    {
      key: 'telephony',
      title: 'Telephony',
      subtitle: status?.telephony?.provider ?? 'Voice / SMS',
      badge: status?.telephony?.status,
      extra: undefined,
    },
    {
      key: 'efiling',
      title: 'E-Filing',
      subtitle: 'Court connectors',
      badge: status?.efiling?.status,
      extra: undefined,
    },
  ] as const;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Integrations"
        subtitle={
          user
            ? `External systems · ${user.email}`
            : 'IdP, payments, telephony, and e-filing'
        }
      />

      <section>
        <h2 className="text-lg font-semibold text-foreground">Status overview</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          GET /api/v1/integrations/status
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => (
            <div
              key={c.key}
              className="flex flex-col rounded-lg border border-border bg-card p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    {c.title}
                  </p>
                  <p className="text-xs text-neutral-500">{c.subtitle}</p>
                </div>
                {c.badge ? <StatusBadge status={c.badge} /> : null}
              </div>
              {c.extra ? (
                <p className="mt-2 text-xs text-neutral-600 dark:text-neutral-400">
                  {c.extra}
                </p>
              ) : null}
              <button
                type="button"
                disabled={testBusy === c.key}
                onClick={() => testConnection(c.key)}
                className={cn(
                  'mt-4 inline-flex items-center justify-center rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50'
                )}
              >
                {testBusy === c.key ? 'Testing…' : 'Test connection'}
              </button>
              {testMsg[c.key] ? (
                <p className="mt-2 text-xs text-neutral-600">{testMsg[c.key]}</p>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">IdP configuration</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          GET /idp/providers · POST /idp/configure?provider=…
        </p>
        <div className="mt-4 space-y-4">
          <div>
            <p className="text-sm font-medium">Supported providers</p>
            <ul className="mt-2 space-y-1 text-sm text-neutral-600 dark:text-neutral-400">
              {(idpProviders ?? []).map((p) => (
                <li key={p.id}>
                  <span className="font-mono text-xs">{p.id}</span> — {p.name}{' '}
                  <span className="text-xs">({p.type})</span>
                </li>
              ))}
            </ul>
          </div>
          <FormField label="Provider">
            <select
              className="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={idpProvider}
              onChange={(e) => setIdpProvider(e.target.value)}
            >
              {(idpProviders ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Config (JSON)">
            <textarea
              className="min-h-[140px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={idpJson}
              onChange={(e) => setIdpJson(e.target.value)}
            />
          </FormField>
          <button
            type="button"
            onClick={saveIdp}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Save IdP config
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">E-filing</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          GET /efiling/connectors · POST /efiling/configure/&#123;id&#125;
        </p>
        <div className="mt-4 space-y-4">
          <ul className="space-y-2 text-sm">
            {(efilingConnectors ?? []).map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              >
                <span>
                  {c.name}{' '}
                  <span className="text-xs text-neutral-500">({c.jurisdiction})</span>
                </span>
                <StatusBadge status={c.status} />
              </li>
            ))}
          </ul>
          <FormField label="Connector">
            <select
              className="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={efilingConnector}
              onChange={(e) => setEfilingConnector(e.target.value)}
            >
              {(efilingConnectors ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Config (JSON)">
            <textarea
              className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={efilingJson}
              onChange={(e) => setEfilingJson(e.target.value)}
            />
          </FormField>
          <button
            type="button"
            onClick={saveEfiling}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Save e-filing connector
          </button>
        </div>
      </section>

      <p className="text-sm text-neutral-600 dark:text-neutral-400">
        SSO and tenant-level OIDC fields are under{' '}
        <Link href="/settings" className="text-primary-600 underline">
          Settings → SSO
        </Link>
        .
      </p>
    </div>
  );
}
