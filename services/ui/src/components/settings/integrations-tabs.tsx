'use client';

/**
 * Settings tabs for the three new pluggable integrations: telephony,
 * print & mail, and scan & capture.
 *
 * Each tab is intentionally a single component file so the main
 * settings page stays readable. They share three patterns:
 *
 *   1. The tenant-wide configuration (settings.{telephony,printing,
 *      scanning}) is fetched + PATCHed via the dedicated endpoints
 *      we added on the tenants router.
 *   2. The list of available adapters comes from the /adapters
 *      endpoint on each subsystem; the shape includes a JSON-Schema
 *      style ``config_schema`` so we can render a generic provider
 *      sub-form without hard-coding any single provider's UI here.
 *      (Adding Vonage later is a backend-only change.)
 *   3. Per-resource CRUD (dispositions, DIDs, printers, scanners) is
 *      done directly against the resource router. Owners and admins
 *      are allowed in by RBAC (`MANAGE_TELEPHONY` etc.); others get
 *      a read-only / hidden view.
 */

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { Plus, Trash2, RefreshCw, Save, Phone, Printer as PrinterIcon, ScanLine, Copy } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

type ConfigSchemaField = {
  type?: 'string' | 'integer' | 'boolean';
  format?: 'password' | 'url' | 'email' | 'multiline';
  description?: string;
  default?: unknown;
  enum?: string[];
};

type ConfigSchema = {
  type?: 'object';
  required?: string[];
  properties?: Record<string, ConfigSchemaField>;
};

/**
 * Render a generic form for a provider's `config_schema`. Supports
 * the small subset of JSON Schema we use in adapters: string /
 * integer / boolean, format=password|url|email|multiline, and enum
 * for select fields. Anything fancier should live in a custom sub-
 * form, but for v1 this covers Vonage / Twilio / Teams Graph / SBC
 * / 3CX / SIP / Lob / PostGrid / etc.
 */
function ConfigSchemaForm({
  schema,
  value,
  onChange,
}: {
  schema: ConfigSchema | undefined;
  value: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const props = schema?.properties || {};
  const required = new Set(schema?.required || []);
  const keys = Object.keys(props);
  if (keys.length === 0) {
    return (
      <p className="text-xs text-neutral-500">
        This adapter has no provider-specific configuration.
      </p>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {keys.map((key) => {
        const f = props[key] || {};
        const id = `cfg-${key}`;
        const current = value[key];
        const setVal = (next: unknown) => onChange({ ...value, [key]: next });

        const label = (
          <label htmlFor={id} className="block text-xs font-medium text-foreground">
            {key.replace(/_/g, ' ')}{required.has(key) ? ' *' : ''}
          </label>
        );
        const help = f.description ? (
          <p className="mt-1 text-xs text-neutral-500">{f.description}</p>
        ) : null;

        if (f.enum) {
          return (
            <div key={key}>
              {label}
              <select
                id={id}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={(current as string) ?? ''}
                onChange={(e) => setVal(e.target.value)}
              >
                <option value="">— select —</option>
                {f.enum.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
              {help}
            </div>
          );
        }

        if (f.type === 'boolean') {
          return (
            <div key={key} className="flex items-start gap-2 md:col-span-2">
              <input
                id={id}
                type="checkbox"
                className="mt-0.5"
                checked={Boolean(current)}
                onChange={(e) => setVal(e.target.checked)}
              />
              <div>
                {label}
                {help}
              </div>
            </div>
          );
        }

        if (f.format === 'multiline') {
          return (
            <div key={key} className="md:col-span-2">
              {label}
              <textarea
                id={id}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                rows={4}
                value={(current as string) ?? ''}
                onChange={(e) => setVal(e.target.value)}
              />
              {help}
            </div>
          );
        }

        const inputType =
          f.type === 'integer'
            ? 'number'
            : f.format === 'password'
            ? 'password'
            : f.format === 'email'
            ? 'email'
            : f.format === 'url'
            ? 'url'
            : 'text';

        return (
          <div key={key}>
            {label}
            <input
              id={id}
              type={inputType}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={
                current === null || current === undefined
                  ? ''
                  : String(current)
              }
              onChange={(e) =>
                setVal(
                  f.type === 'integer'
                    ? e.target.value === ''
                      ? null
                      : Number(e.target.value)
                    : e.target.value
                )
              }
            />
            {help}
          </div>
        );
      })}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, subtitle }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <Icon className="h-5 w-5 text-primary-600 mt-0.5" />
      <div>
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {subtitle ? (
          <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>
        ) : null}
      </div>
    </div>
  );
}

function PrimaryButton({
  children,
  onClick,
  disabled,
  type = 'button',
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit';
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center gap-2 rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50',
        className,
      )}
    >
      {children}
    </button>
  );
}

function SecondaryButton({
  children,
  onClick,
  disabled,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-accent disabled:opacity-50',
        className,
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Telephony
// ---------------------------------------------------------------------------

type TelephonyAdapter = {
  id: string;
  label: string;
  family: string;
  capabilities: Record<string, unknown>;
  config_schema: ConfigSchema;
  docs_url: string | null;
};

type TelephonyConfig = {
  adapter_id: string;
  provider_config: Record<string, unknown>;
  record_calls_default: boolean;
  require_recording_disclosure: boolean;
  recording_disclosure_text: string | null;
  enforce_call_window_local: boolean;
  call_window_start_hour: number;
  call_window_end_hour: number;
  suppress_dnc: boolean;
  default_outbound_caller_id: string | null;
};

type Disposition = {
  id: string;
  code: string;
  label: string;
  description: string | null;
  is_contact: boolean;
  is_rpc: boolean;
  requires_note: boolean;
  triggers_followup_days: number | null;
  is_active: boolean;
  sort_order: number;
};

type PhoneNumberRow = {
  id: string;
  e164: string;
  label: string | null;
  adapter_id: string;
  roles: string[];
  is_active: boolean;
};

export function TelephonyTab({ tenantId }: { tenantId?: string }) {
  const token = useAuthStore((s) => s.accessToken);
  const canManage = true; // operational guard already enforces; backend re-checks per endpoint

  const { data: adapters } = useSWR(
    token ? ['telephony-adapters', token] : null,
    async () => (await apiClient.get<TelephonyAdapter[]>('/api/v1/telephony/adapters')).data,
  );

  const { data: cfg, mutate: mutCfg } = useSWR(
    token && tenantId ? ['telephony-config', tenantId, token] : null,
    async () =>
      (await apiClient.get<TelephonyConfig>(`/api/v1/tenants/${tenantId}/telephony-config`)).data,
  );

  const [draft, setDraft] = useState<TelephonyConfig | null>(null);
  useEffect(() => { if (cfg) setDraft(cfg); }, [cfg]);

  const activeAdapter = useMemo(
    () => adapters?.find((a) => a.id === draft?.adapter_id),
    [adapters, draft?.adapter_id],
  );

  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const save = async () => {
    if (!draft || !tenantId) return;
    setSaving(true);
    try {
      await apiClient.patch(`/api/v1/tenants/${tenantId}/telephony-config`, draft);
      await mutCfg();
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTestResult('Testing...');
    try {
      const { data } = await apiClient.post<{ ok: boolean; detail?: string }>(
        '/api/v1/telephony/test-connection',
      );
      setTestResult(data.ok ? 'Connection OK' : `Error: ${data.detail || 'unknown'}`);
    } catch (e: any) {
      setTestResult(`Error: ${e?.response?.data?.detail || 'request failed'}`);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <SectionHeader
          icon={Phone}
          title="Phone system"
          subtitle="Pick the provider you use. Cloud, Microsoft Teams, on-prem PBX, or generic SIP — all routed through the same agent UI."
        />

        {!draft ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium">Provider</label>
              <select
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={draft.adapter_id}
                onChange={(e) =>
                  setDraft({ ...draft, adapter_id: e.target.value, provider_config: {} })
                }
              >
                {(adapters || []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} ({a.family.replace('_', ' ')})
                  </option>
                ))}
              </select>
              {activeAdapter?.docs_url ? (
                <a
                  href={activeAdapter.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs text-primary-600 hover:underline"
                >
                  Setup docs →
                </a>
              ) : null}
            </div>

            <div className="rounded-md border border-border p-4">
              <p className="text-sm font-medium mb-3">Provider configuration</p>
              <ConfigSchemaForm
                schema={activeAdapter?.config_schema}
                value={draft.provider_config || {}}
                onChange={(v) => setDraft({ ...draft, provider_config: v })}
              />
            </div>

            <div className="rounded-md border border-border p-4 space-y-3">
              <p className="text-sm font-medium">Compliance & defaults</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.record_calls_default}
                    onChange={(e) =>
                      setDraft({ ...draft, record_calls_default: e.target.checked })
                    }
                  />
                  <span>Record calls by default</span>
                </label>

                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.require_recording_disclosure}
                    onChange={(e) =>
                      setDraft({ ...draft, require_recording_disclosure: e.target.checked })
                    }
                  />
                  <span>Require recording disclosure to be played</span>
                </label>

                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.suppress_dnc}
                    onChange={(e) => setDraft({ ...draft, suppress_dnc: e.target.checked })}
                  />
                  <span>Block calls to DNC-flagged numbers</span>
                </label>

                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.enforce_call_window_local}
                    onChange={(e) =>
                      setDraft({ ...draft, enforce_call_window_local: e.target.checked })
                    }
                  />
                  <span>Enforce 8a–9p local call window (FDCPA)</span>
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium">Window start (local hour)</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={draft.call_window_start_hour}
                    onChange={(e) =>
                      setDraft({ ...draft, call_window_start_hour: Number(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium">Window end (local hour)</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={draft.call_window_end_hour}
                    onChange={(e) =>
                      setDraft({ ...draft, call_window_end_hour: Number(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium">Default outbound caller ID</label>
                  <input
                    type="tel"
                    placeholder="+15551234567"
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={draft.default_outbound_caller_id || ''}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        default_outbound_caller_id: e.target.value || null,
                      })
                    }
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium">Recording disclosure text</label>
                <textarea
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  rows={2}
                  value={draft.recording_disclosure_text || ''}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      recording_disclosure_text: e.target.value || null,
                    })
                  }
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <PrimaryButton onClick={save} disabled={saving}>
                <Save className="h-4 w-4" />
                {saving ? 'Saving…' : 'Save'}
              </PrimaryButton>
              <SecondaryButton onClick={testConnection} disabled={!cfg || cfg.adapter_id === 'none'}>
                Test connection
              </SecondaryButton>
              {testResult ? (
                <span className="text-xs text-neutral-600 dark:text-neutral-400">{testResult}</span>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {canManage ? <DispositionsTable /> : null}
      {canManage ? <PhoneNumbersTable adapters={adapters || []} /> : null}
    </div>
  );
}

function DispositionsTable() {
  const token = useAuthStore((s) => s.accessToken);
  const { data, mutate } = useSWR(
    token ? ['dispositions', token] : null,
    async () => (await apiClient.get<Disposition[]>('/api/v1/telephony/dispositions?include_inactive=true')).data,
  );
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({
    code: '',
    label: '',
    is_contact: false,
    is_rpc: false,
    requires_note: false,
    triggers_followup_days: null as number | null,
  });

  const create = async () => {
    if (!draft.code || !draft.label) return;
    await apiClient.post('/api/v1/telephony/dispositions', draft);
    setDraft({ code: '', label: '', is_contact: false, is_rpc: false, requires_note: false, triggers_followup_days: null });
    setAdding(false);
    await mutate();
  };

  const archive = async (id: string) => {
    await apiClient.delete(`/api/v1/telephony/dispositions/${id}`);
    await mutate();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold">Call dispositions</h3>
          <p className="text-xs text-neutral-500">
            Wrap-up codes shown to agents after a call. Used for reporting and follow-ups.
          </p>
        </div>
        <SecondaryButton onClick={() => setAdding((v) => !v)}>
          <Plus className="h-4 w-4" /> Add disposition
        </SecondaryButton>
      </div>

      {adding ? (
        <div className="rounded-md border border-border p-3 mb-3 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              placeholder="Code (e.g. RPC)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.code}
              onChange={(e) => setDraft({ ...draft, code: e.target.value })}
            />
            <input
              placeholder="Label (e.g. Right Party Contact)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={draft.is_contact}
                onChange={(e) => setDraft({ ...draft, is_contact: e.target.checked })} />
              Contact
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={draft.is_rpc}
                onChange={(e) => setDraft({ ...draft, is_rpc: e.target.checked })} />
              RPC
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={draft.requires_note}
                onChange={(e) => setDraft({ ...draft, requires_note: e.target.checked })} />
              Requires note
            </label>
            <label className="flex items-center gap-1">
              Follow-up (days):
              <input
                type="number"
                min={0}
                className="w-20 rounded-md border border-input bg-background px-2 py-1"
                value={draft.triggers_followup_days ?? ''}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    triggers_followup_days: e.target.value === '' ? null : Number(e.target.value),
                  })
                }
              />
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <SecondaryButton onClick={() => setAdding(false)}>Cancel</SecondaryButton>
            <PrimaryButton onClick={create}>Save</PrimaryButton>
          </div>
        </div>
      ) : null}

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 dark:bg-neutral-900 text-xs uppercase text-neutral-500">
            <tr>
              <th className="text-left px-3 py-2">Code</th>
              <th className="text-left px-3 py-2">Label</th>
              <th className="text-left px-3 py-2">Flags</th>
              <th className="text-left px-3 py-2">Follow-up</th>
              <th className="text-left px-3 py-2">Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono text-xs">{d.code}</td>
                <td className="px-3 py-2">{d.label}</td>
                <td className="px-3 py-2 text-xs text-neutral-500">
                  {[
                    d.is_contact ? 'Contact' : null,
                    d.is_rpc ? 'RPC' : null,
                    d.requires_note ? 'Note required' : null,
                  ].filter(Boolean).join(' · ') || '—'}
                </td>
                <td className="px-3 py-2 text-xs">
                  {d.triggers_followup_days != null ? `${d.triggers_followup_days}d` : '—'}
                </td>
                <td className="px-3 py-2 text-xs">{d.is_active ? 'Yes' : 'Inactive'}</td>
                <td className="px-3 py-2 text-right">
                  {d.is_active ? (
                    <button
                      type="button"
                      onClick={() => archive(d.id)}
                      className="text-neutral-500 hover:text-red-600"
                      aria-label="Archive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {data && data.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-xs text-neutral-500">
                No dispositions defined. Add one above.
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PhoneNumbersTable({ adapters }: { adapters: TelephonyAdapter[] }) {
  const token = useAuthStore((s) => s.accessToken);
  const { data, mutate } = useSWR(
    token ? ['phone-numbers', token] : null,
    async () => (await apiClient.get<PhoneNumberRow[]>('/api/v1/telephony/phone-numbers')).data,
  );
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({
    e164: '',
    label: '',
    adapter_id: adapters[0]?.id || 'none',
    roles: ['inbound'] as string[],
  });

  useEffect(() => {
    if (adapters.length && draft.adapter_id === 'none') {
      setDraft((d) => ({ ...d, adapter_id: adapters[0].id }));
    }
  }, [adapters, draft.adapter_id]);

  const create = async () => {
    if (!draft.e164) return;
    await apiClient.post('/api/v1/telephony/phone-numbers', {
      ...draft,
      label: draft.label || null,
    });
    setDraft({ e164: '', label: '', adapter_id: adapters[0]?.id || 'none', roles: ['inbound'] });
    setAdding(false);
    await mutate();
  };

  const remove = async (id: string) => {
    await apiClient.delete(`/api/v1/telephony/phone-numbers/${id}`);
    await mutate();
  };

  const toggleRole = (role: string) =>
    setDraft((d) => ({
      ...d,
      roles: d.roles.includes(role) ? d.roles.filter((r) => r !== role) : [...d.roles, role],
    }));

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold">Phone numbers (DIDs)</h3>
          <p className="text-xs text-neutral-500">
            Numbers your tenant owns. Inbound webhooks resolve to a tenant by matching on these.
          </p>
        </div>
        <SecondaryButton onClick={() => setAdding((v) => !v)}>
          <Plus className="h-4 w-4" /> Add number
        </SecondaryButton>
      </div>

      {adding ? (
        <div className="rounded-md border border-border p-3 mb-3 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              placeholder="+15551234567"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.e164}
              onChange={(e) => setDraft({ ...draft, e164: e.target.value })}
            />
            <input
              placeholder="Label (optional)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
            />
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.adapter_id}
              onChange={(e) => setDraft({ ...draft, adapter_id: e.target.value })}
            >
              {adapters.map((a) => (
                <option key={a.id} value={a.id}>{a.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {['inbound', 'outbound_caller_id', 'sms', 'fax'].map((r) => (
              <label key={r} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={draft.roles.includes(r)}
                  onChange={() => toggleRole(r)}
                />
                {r.replace(/_/g, ' ')}
              </label>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <SecondaryButton onClick={() => setAdding(false)}>Cancel</SecondaryButton>
            <PrimaryButton onClick={create}>Save</PrimaryButton>
          </div>
        </div>
      ) : null}

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 dark:bg-neutral-900 text-xs uppercase text-neutral-500">
            <tr>
              <th className="text-left px-3 py-2">Number</th>
              <th className="text-left px-3 py-2">Label</th>
              <th className="text-left px-3 py-2">Adapter</th>
              <th className="text-left px-3 py-2">Roles</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((p) => (
              <tr key={p.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono">{p.e164}</td>
                <td className="px-3 py-2">{p.label || '—'}</td>
                <td className="px-3 py-2 text-xs">{p.adapter_id}</td>
                <td className="px-3 py-2 text-xs">{(p.roles || []).join(', ') || '—'}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => remove(p.id)}
                    className="text-neutral-500 hover:text-red-600"
                    aria-label="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {data && data.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-xs text-neutral-500">
                No numbers configured.
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Print & Mail
// ---------------------------------------------------------------------------

type PrintAdapter = {
  id: string;
  label: string;
  family: string;
  capabilities: Record<string, unknown>;
  config_schema: ConfigSchema;
  docs_url: string | null;
};

type PrintingConfig = {
  bureau_adapter_id: string | null;
  bureau_config: Record<string, unknown>;
  default_local_printer_id: string | null;
  require_certified_for_initial_letter: boolean;
  track_certified_returns: boolean;
  daily_print_cap: number | null;
};

type PrinterRow = {
  id: string;
  name: string;
  description: string | null;
  location: string | null;
  kind: 'OFFICE' | 'THERMAL' | 'LABEL' | 'CHECK' | 'OTHER';
  transport: string;
  host: string | null;
  port: number | null;
  queue_name: string | null;
  is_default: boolean;
  is_active: boolean;
};

const PRINTER_KINDS = ['OFFICE', 'THERMAL', 'LABEL', 'CHECK', 'OTHER'] as const;
const PRINTER_TRANSPORTS = ['PDF_DOWNLOAD', 'ELECTRON_DEFAULT', 'IPP', 'ESCPOS_TCP', 'ZPL_TCP', 'USB'] as const;

export function PrintingTab({ tenantId }: { tenantId?: string }) {
  const token = useAuthStore((s) => s.accessToken);

  const { data: bureaus } = useSWR(
    token ? ['print-bureaus', token] : null,
    async () => (await apiClient.get<PrintAdapter[]>('/api/v1/printing/adapters/bureau')).data,
  );

  const { data: cfg, mutate: mutCfg } = useSWR(
    token && tenantId ? ['printing-config', tenantId, token] : null,
    async () => (await apiClient.get<PrintingConfig>(`/api/v1/tenants/${tenantId}/printing-config`)).data,
  );

  const [draft, setDraft] = useState<PrintingConfig | null>(null);
  useEffect(() => { if (cfg) setDraft(cfg); }, [cfg]);

  const activeBureau = useMemo(
    () => bureaus?.find((a) => a.id === draft?.bureau_adapter_id),
    [bureaus, draft?.bureau_adapter_id],
  );

  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!draft || !tenantId) return;
    setSaving(true);
    try {
      await apiClient.patch(`/api/v1/tenants/${tenantId}/printing-config`, draft);
      await mutCfg();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <SectionHeader
          icon={PrinterIcon}
          title="Mail bureau"
          subtitle="Compliance letters can be auto-printed and mailed by a bureau (Lob, PostGrid, Click2Mail). Picks one provider per tenant; switching is seamless."
        />

        {!draft ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium">Bureau</label>
              <select
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={draft.bureau_adapter_id || ''}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    bureau_adapter_id: e.target.value || null,
                    bureau_config: {},
                  })
                }
              >
                <option value="">— No bureau (skip mail integration) —</option>
                {(bureaus || []).map((a) => (
                  <option key={a.id} value={a.id}>{a.label}</option>
                ))}
              </select>
              {activeBureau?.docs_url ? (
                <a
                  href={activeBureau.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs text-primary-600 hover:underline"
                >
                  Setup docs →
                </a>
              ) : null}
            </div>

            {activeBureau ? (
              <div className="rounded-md border border-border p-4">
                <p className="text-sm font-medium mb-3">Bureau credentials</p>
                <ConfigSchemaForm
                  schema={activeBureau.config_schema}
                  value={draft.bureau_config || {}}
                  onChange={(v) => setDraft({ ...draft, bureau_config: v })}
                />
              </div>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={draft.require_certified_for_initial_letter}
                  onChange={(e) =>
                    setDraft({ ...draft, require_certified_for_initial_letter: e.target.checked })
                  }
                />
                <span>Use certified mail for initial validation notice (Reg F)</span>
              </label>

              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={draft.track_certified_returns}
                  onChange={(e) =>
                    setDraft({ ...draft, track_certified_returns: e.target.checked })
                  }
                />
                <span>Auto-update accounts when mail is returned</span>
              </label>

              <div>
                <label className="block text-xs font-medium">Daily print cap (0 = unlimited)</label>
                <input
                  type="number"
                  min={0}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={draft.daily_print_cap ?? ''}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      daily_print_cap: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>

            <PrimaryButton onClick={save} disabled={saving}>
              <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save'}
            </PrimaryButton>
          </div>
        )}
      </div>

      <PrintersTable />
    </div>
  );
}

function PrintersTable() {
  const token = useAuthStore((s) => s.accessToken);
  const { data, mutate } = useSWR(
    token ? ['printers', token] : null,
    async () => (await apiClient.get<PrinterRow[]>('/api/v1/printing/printers')).data,
  );
  const [adding, setAdding] = useState(false);
  const blank = {
    name: '',
    description: '',
    location: '',
    kind: 'OFFICE' as PrinterRow['kind'],
    transport: 'PDF_DOWNLOAD',
    host: '',
    port: '' as number | '',
    queue_name: '',
    is_default: false,
  };
  const [draft, setDraft] = useState(blank);

  const create = async () => {
    if (!draft.name) return;
    await apiClient.post('/api/v1/printing/printers', {
      name: draft.name,
      description: draft.description || null,
      location: draft.location || null,
      kind: draft.kind,
      transport: draft.transport,
      host: draft.host || null,
      port: draft.port === '' ? null : Number(draft.port),
      queue_name: draft.queue_name || null,
      is_default: draft.is_default,
    });
    setDraft(blank);
    setAdding(false);
    await mutate();
  };

  const remove = async (id: string) => {
    await apiClient.delete(`/api/v1/printing/printers/${id}`);
    await mutate();
  };

  const needsNetwork = ['IPP', 'ESCPOS_TCP', 'ZPL_TCP'].includes(draft.transport);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold">Local printers</h3>
          <p className="text-xs text-neutral-500">
            Office printers, label printers, MICR check printers. Browser-only tenants
            should keep `PDF_DOWNLOAD`; Electron tenants can use `ELECTRON_DEFAULT` or network transports.
          </p>
        </div>
        <SecondaryButton onClick={() => setAdding((v) => !v)}>
          <Plus className="h-4 w-4" /> Add printer
        </SecondaryButton>
      </div>

      {adding ? (
        <div className="rounded-md border border-border p-3 mb-3 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              placeholder="Name (e.g. Office HP M404)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <input
              placeholder="Location (optional)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.location}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
            />
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.kind}
              onChange={(e) => setDraft({ ...draft, kind: e.target.value as PrinterRow['kind'] })}
            >
              {PRINTER_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.transport}
              onChange={(e) => setDraft({ ...draft, transport: e.target.value })}
            >
              {PRINTER_TRANSPORTS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input
              placeholder={needsNetwork ? 'Host / IP' : 'Host (n/a for this transport)'}
              disabled={!needsNetwork}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-50"
              value={draft.host}
              onChange={(e) => setDraft({ ...draft, host: e.target.value })}
            />
            <input
              type="number"
              placeholder="Port"
              disabled={!needsNetwork}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-50"
              value={draft.port}
              onChange={(e) =>
                setDraft({ ...draft, port: e.target.value === '' ? '' : Number(e.target.value) })
              }
            />
          </div>

          <input
            placeholder="Queue name (IPP only, optional)"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={draft.queue_name}
            onChange={(e) => setDraft({ ...draft, queue_name: e.target.value })}
          />

          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={draft.is_default}
              onChange={(e) => setDraft({ ...draft, is_default: e.target.checked })}
            />
            Make this the default printer for its kind
          </label>

          <div className="flex justify-end gap-2">
            <SecondaryButton onClick={() => setAdding(false)}>Cancel</SecondaryButton>
            <PrimaryButton onClick={create}>Save</PrimaryButton>
          </div>
        </div>
      ) : null}

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 dark:bg-neutral-900 text-xs uppercase text-neutral-500">
            <tr>
              <th className="text-left px-3 py-2">Name</th>
              <th className="text-left px-3 py-2">Kind</th>
              <th className="text-left px-3 py-2">Transport</th>
              <th className="text-left px-3 py-2">Endpoint</th>
              <th className="text-left px-3 py-2">Default</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((p) => (
              <tr key={p.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <div>{p.name}</div>
                  {p.location ? <div className="text-xs text-neutral-500">{p.location}</div> : null}
                </td>
                <td className="px-3 py-2 text-xs">{p.kind}</td>
                <td className="px-3 py-2 text-xs">{p.transport}</td>
                <td className="px-3 py-2 text-xs font-mono">
                  {p.host ? `${p.host}${p.port ? `:${p.port}` : ''}` : '—'}
                </td>
                <td className="px-3 py-2 text-xs">{p.is_default ? 'Yes' : '—'}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => remove(p.id)}
                    className="text-neutral-500 hover:text-red-600"
                    aria-label="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {data && data.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-xs text-neutral-500">
                No printers configured. PDF download will be used as a fallback.
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scan & Capture
// ---------------------------------------------------------------------------

type ScanAdapter = {
  id: string;
  label: string;
  family: string;
  kind: 'document' | 'check' | 'id' | 'other';
  capabilities: Record<string, unknown>;
  config_schema: ConfigSchema;
};

type ScanningConfig = {
  auto_route_by_barcode: boolean;
  auto_route_by_account_number: boolean;
  routing_min_confidence: number;
  unrouted_review_inbox: string | null;
  require_dual_review_above_cents: number | null;
  require_micr_match_for_auto_apply: boolean;
  auto_create_payment_on_clear: boolean;
  default_deposit_account_id: string | null;
};

type ScannerRow = {
  id: string;
  name: string;
  description: string | null;
  location: string | null;
  kind: 'DOCUMENT' | 'CHECK' | 'ID' | 'OTHER';
  transport: string;
  intake_inbox_email: string | null;
  deposit_account_id: string | null;
  is_active: boolean;
  has_intake_token: boolean;
};

const SCANNER_KINDS = ['DOCUMENT', 'CHECK', 'ID', 'OTHER'] as const;
const SCANNER_TRANSPORTS_DOC = [
  'MFP_SFTP', 'MFP_EMAIL', 'MFP_HTTPS', 'HOT_FOLDER',
  'ELECTRON_TWAIN', 'ELECTRON_WIA', 'ELECTRON_SANE', 'DYNAMSOFT', 'OTHER',
] as const;
const SCANNER_TRANSPORTS_CHECK = ['X937_CHECK_IMAGE', 'OTHER'] as const;

export function ScanningTab({ tenantId }: { tenantId?: string }) {
  const token = useAuthStore((s) => s.accessToken);

  const { data: cfg, mutate: mutCfg } = useSWR(
    token && tenantId ? ['scanning-config', tenantId, token] : null,
    async () => (await apiClient.get<ScanningConfig>(`/api/v1/tenants/${tenantId}/scanning-config`)).data,
  );

  const [draft, setDraft] = useState<ScanningConfig | null>(null);
  useEffect(() => { if (cfg) setDraft(cfg); }, [cfg]);

  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!draft || !tenantId) return;
    setSaving(true);
    try {
      await apiClient.patch(`/api/v1/tenants/${tenantId}/scanning-config`, draft);
      await mutCfg();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <SectionHeader
          icon={ScanLine}
          title="Routing & check defaults"
          subtitle="How scanned documents get attached to accounts, and how checks are processed and deposited."
        />

        {!draft ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={draft.auto_route_by_barcode}
                  onChange={(e) => setDraft({ ...draft, auto_route_by_barcode: e.target.checked })}
                />
                <span>Auto-route by barcode</span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={draft.auto_route_by_account_number}
                  onChange={(e) =>
                    setDraft({ ...draft, auto_route_by_account_number: e.target.checked })
                  }
                />
                <span>Auto-route by detected account number (OCR)</span>
              </label>
              <div>
                <label className="block text-xs font-medium">Min routing confidence (0–100)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={draft.routing_min_confidence}
                  onChange={(e) =>
                    setDraft({ ...draft, routing_min_confidence: Number(e.target.value) })
                  }
                />
              </div>
              <div>
                <label className="block text-xs font-medium">
                  Unrouted review inbox (email)
                </label>
                <input
                  type="email"
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={draft.unrouted_review_inbox || ''}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      unrouted_review_inbox: e.target.value || null,
                    })
                  }
                />
              </div>
            </div>

            <div className="rounded-md border border-border p-4 space-y-3">
              <p className="text-sm font-medium">Check handling</p>
              <p className="text-xs text-neutral-500">
                Applies only to scanners marked <span className="font-medium">CHECK</span>.
                Check scanners parse the MICR line, store front/back images per Check 21, and
                wait for bank-cleared deposit before creating a payment.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.require_micr_match_for_auto_apply}
                    onChange={(e) =>
                      setDraft({ ...draft, require_micr_match_for_auto_apply: e.target.checked })
                    }
                  />
                  <span>Require MICR routing+account to match consumer record</span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={draft.auto_create_payment_on_clear}
                    onChange={(e) =>
                      setDraft({ ...draft, auto_create_payment_on_clear: e.target.checked })
                    }
                  />
                  <span>Auto-create payment record once deposit clears</span>
                </label>
                <div>
                  <label className="block text-xs font-medium">
                    Dual review threshold (cents). Blank = always
                  </label>
                  <input
                    type="number"
                    min={0}
                    placeholder="100000"
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={draft.require_dual_review_above_cents ?? ''}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        require_dual_review_above_cents:
                          e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
            </div>

            <PrimaryButton onClick={save} disabled={saving}>
              <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save'}
            </PrimaryButton>
          </div>
        )}
      </div>

      <ScannersTable />
    </div>
  );
}

function ScannersTable() {
  const token = useAuthStore((s) => s.accessToken);
  const { data, mutate } = useSWR(
    token ? ['scanners', token] : null,
    async () => (await apiClient.get<ScannerRow[]>('/api/v1/scanning/scanners')).data,
  );

  const blank = {
    name: '',
    description: '',
    location: '',
    kind: 'DOCUMENT' as ScannerRow['kind'],
    transport: 'MFP_SFTP',
    intake_inbox_email: '',
    deposit_account_id: '',
  };

  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(blank);
  const [showToken, setShowToken] = useState<{ id: string; token: string } | null>(null);

  const isCheck = draft.kind === 'CHECK';

  const create = async () => {
    if (!draft.name) return;
    const { data: created } = await apiClient.post<ScannerRow & { intake_token?: string }>(
      '/api/v1/scanning/scanners',
      {
        name: draft.name,
        description: draft.description || null,
        location: draft.location || null,
        kind: draft.kind,
        transport: draft.transport,
        intake_inbox_email: draft.intake_inbox_email || null,
        deposit_account_id: draft.deposit_account_id || null,
      },
    );
    if (created.intake_token) {
      setShowToken({ id: created.id, token: created.intake_token });
    }
    setDraft(blank);
    setAdding(false);
    await mutate();
  };

  const remove = async (id: string) => {
    await apiClient.delete(`/api/v1/scanning/scanners/${id}`);
    await mutate();
  };

  const rotate = async (id: string) => {
    const { data: rotated } = await apiClient.post<ScannerRow & { intake_token?: string }>(
      `/api/v1/scanning/scanners/${id}/rotate-token`,
    );
    if (rotated.intake_token) {
      setShowToken({ id: rotated.id, token: rotated.intake_token });
    }
    await mutate();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold">Scanners</h3>
          <p className="text-xs text-neutral-500">
            Office MFPs, desktop scanners, check scanners. Mark a scanner as
            <span className="font-medium"> CHECK</span> to enable MICR parsing and Check 21 image storage.
          </p>
        </div>
        <SecondaryButton onClick={() => setAdding((v) => !v)}>
          <Plus className="h-4 w-4" /> Add scanner
        </SecondaryButton>
      </div>

      {showToken ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/20 p-3 mb-3">
          <p className="text-xs font-medium mb-1">
            Intake token (shown once — save it now)
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-white dark:bg-black/40 border border-border px-2 py-1 text-xs font-mono">
              {showToken.token}
            </code>
            <SecondaryButton
              onClick={() => navigator.clipboard?.writeText(showToken.token)}
            >
              <Copy className="h-4 w-4" /> Copy
            </SecondaryButton>
            <SecondaryButton onClick={() => setShowToken(null)}>Dismiss</SecondaryButton>
          </div>
          <p className="mt-2 text-xs text-neutral-600 dark:text-neutral-400">
            Configure your MFP / scan-to-cloud target to POST to{' '}
            <code className="font-mono">/api/v1/intake/scan</code> with this token in the JSON body.
          </p>
        </div>
      ) : null}

      {adding ? (
        <div className="rounded-md border border-border p-3 mb-3 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              placeholder="Name (e.g. Reception MFP)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <input
              placeholder="Location (optional)"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.location}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
            />
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.kind}
              onChange={(e) => {
                const newKind = e.target.value as ScannerRow['kind'];
                const validTransports = newKind === 'CHECK' ? SCANNER_TRANSPORTS_CHECK : SCANNER_TRANSPORTS_DOC;
                setDraft({
                  ...draft,
                  kind: newKind,
                  transport: validTransports[0],
                });
              }}
            >
              {SCANNER_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.transport}
              onChange={(e) => setDraft({ ...draft, transport: e.target.value })}
            >
              {(isCheck ? SCANNER_TRANSPORTS_CHECK : SCANNER_TRANSPORTS_DOC).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <input
              type="email"
              placeholder="Inbox for MFP_EMAIL transport"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={draft.intake_inbox_email}
              onChange={(e) => setDraft({ ...draft, intake_inbox_email: e.target.value })}
            />
          </div>

          {isCheck ? (
            <div>
              <label className="block text-xs font-medium">
                Deposit trust account (optional — overrides tenant default)
              </label>
              <input
                placeholder="Trust account UUID"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                value={draft.deposit_account_id}
                onChange={(e) => setDraft({ ...draft, deposit_account_id: e.target.value })}
              />
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <SecondaryButton onClick={() => setAdding(false)}>Cancel</SecondaryButton>
            <PrimaryButton onClick={create}>Save</PrimaryButton>
          </div>
        </div>
      ) : null}

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 dark:bg-neutral-900 text-xs uppercase text-neutral-500">
            <tr>
              <th className="text-left px-3 py-2">Name</th>
              <th className="text-left px-3 py-2">Kind</th>
              <th className="text-left px-3 py-2">Transport</th>
              <th className="text-left px-3 py-2">Intake</th>
              <th className="text-left px-3 py-2">Token</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <div>{s.name}</div>
                  {s.location ? <div className="text-xs text-neutral-500">{s.location}</div> : null}
                </td>
                <td className="px-3 py-2 text-xs">
                  {s.kind}
                  {s.kind === 'CHECK' ? (
                    <span className="ml-1 inline-block rounded bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 px-1 py-0.5 text-[10px] uppercase">
                      check pipeline
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-xs">{s.transport}</td>
                <td className="px-3 py-2 text-xs">
                  {s.intake_inbox_email || '—'}
                </td>
                <td className="px-3 py-2 text-xs">
                  {s.has_intake_token ? (
                    <button
                      type="button"
                      onClick={() => rotate(s.id)}
                      className="inline-flex items-center gap-1 text-primary-600 hover:underline"
                    >
                      <RefreshCw className="h-3 w-3" /> Rotate
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => rotate(s.id)}
                      className="inline-flex items-center gap-1 text-primary-600 hover:underline"
                    >
                      <Plus className="h-3 w-3" /> Issue
                    </button>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => remove(s.id)}
                    className="text-neutral-500 hover:text-red-600"
                    aria-label="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {data && data.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-xs text-neutral-500">
                No scanners configured.
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
