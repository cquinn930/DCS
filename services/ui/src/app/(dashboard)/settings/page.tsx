'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ColumnDef } from '@tanstack/react-table';
import {
  Bell,
  Database,
  Key,
  Plug,
  Shield,
  Sparkles,
  Users,
} from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { StatusBadge } from '@/components/shared/status-badge';
import { useApiList, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { cn } from '@/lib/utils';

type Tenant = {
  id: string;
  name: string;
  slug: string;
  status: string;
  business_model: string;
  default_jurisdiction: string;
  retention_years: number;
  license_number?: string | null;
  settings: Record<string, unknown>;
};

type UserRow = {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  is_active: boolean;
  is_owner: boolean;
  roles: string[];
};

type RoleRow = {
  id: string;
  name: string;
  description?: string | null;
};

const tabs = [
  { id: 'general', name: 'General', icon: Database },
  { id: 'users', name: 'Users & Roles', icon: Users },
  { id: 'security', name: 'Security', icon: Shield },
  { id: 'sso', name: 'SSO', icon: Key },
  { id: 'ai', name: 'AI Assistant', icon: Sparkles },
  { id: 'notifications', name: 'Notifications', icon: Bell },
  { id: 'integrations', name: 'Integrations', icon: Plug },
] as const;

export default function SettingsPage() {
  const { user, isMasterUser } = useAuthStore();
  const token = useAuthStore((s) => s.accessToken);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]['id']>(
    'general'
  );

  const { data: tenant, mutate: mutTenant } = useSWR(
    token && activeTab === 'general' ? ['tenant-current', token] : null,
    async () => {
      const { data } = await apiClient.get<Tenant>('/api/v1/tenants/current');
      return data;
    }
  );

  const { data: tenantSso, mutate: mutTenantSso } = useSWR(
    token && activeTab === 'sso' ? ['tenant-current-sso', token] : null,
    async () => {
      const { data } = await apiClient.get<Tenant>('/api/v1/tenants/current');
      return data;
    }
  );

  const [generalForm, setGeneralForm] = useState({
    name: '',
    default_jurisdiction: 'NJ',
    retention_years: 7,
    license_number: '',
  });

  useEffect(() => {
    if (!tenant) return;
    setGeneralForm({
      name: tenant.name,
      default_jurisdiction: tenant.default_jurisdiction,
      retention_years: tenant.retention_years,
      license_number: tenant.license_number ?? '',
    });
  }, [tenant]);

  const { trigger: patchTenant, isMutating: savingTenant } = useApiMutation<
    Record<string, unknown>,
    Tenant
  >('PATCH', '/api/v1/tenants');

  async function saveGeneral() {
    if (!tenant) return;
    await patchTenant(
      {
        name: generalForm.name,
        default_jurisdiction: generalForm.default_jurisdiction,
        retention_years: generalForm.retention_years,
        license_number: generalForm.license_number || null,
      },
      `/${tenant.id}`
    );
    await mutTenant();
  }

  const [userSearch, setUserSearch] = useState('');
  const [uPage, setUPage] = useState(0);
  const uPageSize = 20;
  const { data: users, total: uTotal, isLoading: uLoading, mutate: mutU } =
    useApiList<UserRow>(
      activeTab === 'users' ? '/api/v1/users' : null,
      { page: uPage + 1, page_size: uPageSize }
    );

  const { data: roles } = useApiList<RoleRow>(
    activeTab === 'users' ? '/api/v1/users/roles' : null,
    {}
  );

  const roleList = roles ?? [];

  const [userDrawer, setUserDrawer] = useState(false);
  const [editUserId, setEditUserId] = useState<string | null>(null);
  const [userForm, setUserForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role_ids: [] as string[],
  });

  const { trigger: postUser, isMutating: creatingU } = useApiMutation<
    Record<string, unknown>,
    UserRow
  >('POST', '/api/v1/users');
  const { trigger: patchUser, isMutating: savingU } = useApiMutation<
    Record<string, unknown>,
    UserRow
  >('PATCH', '/api/v1/users');

  const filteredUsers = useMemo(() => {
    const rows = users ?? [];
    if (!userSearch.trim()) return rows;
    const q = userSearch.toLowerCase();
    return rows.filter(
      (u) =>
        u.email.toLowerCase().includes(q) ||
        (u.first_name ?? '').toLowerCase().includes(q) ||
        (u.last_name ?? '').toLowerCase().includes(q)
    );
  }, [users, userSearch]);

  const userColumns: ColumnDef<UserRow>[] = [
    { accessorKey: 'email', header: 'Email' },
    {
      id: 'name',
      header: 'Name',
      cell: ({ row }) =>
        [row.original.first_name, row.original.last_name]
          .filter(Boolean)
          .join(' ') || '—',
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() ? 'active' : 'inactive'} />
      ),
    },
    {
      accessorKey: 'roles',
      header: 'Roles',
      cell: ({ getValue }) => (getValue() as string[]).join(', ') || '—',
    },
  ];

  function openCreateUser() {
    setEditUserId(null);
    setUserForm({
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      role_ids: [],
    });
    setUserDrawer(true);
  }

  function openEditUser(u: UserRow) {
    setEditUserId(u.id);
    setUserForm({
      email: u.email,
      password: '',
      first_name: u.first_name ?? '',
      last_name: u.last_name ?? '',
      role_ids: roleList
        .filter((r) => u.roles.includes(r.name))
        .map((r) => r.id),
    });
    setUserDrawer(true);
  }

  function toggleUserRole(roleId: string) {
    setUserForm((f) => ({
      ...f,
      role_ids: f.role_ids.includes(roleId)
        ? f.role_ids.filter((x) => x !== roleId)
        : [...f.role_ids, roleId],
    }));
  }

  async function submitUser() {
    if (!editUserId) {
      await postUser({
        email: userForm.email,
        password: userForm.password || undefined,
        first_name: userForm.first_name || null,
        last_name: userForm.last_name || null,
        role_ids: userForm.role_ids,
      });
    } else {
      await patchUser(
        {
          email: userForm.email,
          first_name: userForm.first_name || null,
          last_name: userForm.last_name || null,
          role_ids: userForm.role_ids,
        },
        `/${editUserId}`
      );
    }
    setUserDrawer(false);
    await mutU();
  }

  const security = tenant?.settings?.security as
    | Record<string, unknown>
    | undefined;

  const [ssoForm, setSsoForm] = useState({
    issuer: '',
    client_id: '',
    client_secret: '',
    allowed_domains: '',
  });

  useEffect(() => {
    const oidc = tenantSso?.settings?.oidc as
      | Record<string, unknown>
      | undefined;
    if (!oidc) return;
    const domains = oidc.allowed_domains;
    setSsoForm({
      issuer: String(oidc.issuer ?? ''),
      client_id: String(oidc.client_id ?? ''),
      client_secret: String(oidc.client_secret ?? ''),
      allowed_domains: Array.isArray(domains)
        ? domains.join(', ')
        : String(domains ?? ''),
    });
  }, [tenantSso]);

  const { trigger: patchSso, isMutating: savingSso } = useApiMutation<
    Record<string, unknown>,
    unknown
  >('PATCH', '/api/v1/tenants');

  async function saveSso() {
    if (!user?.tenantId) return;
    const allowed = ssoForm.allowed_domains
      .split(/[,;\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    await patchSso(
      {
        issuer: ssoForm.issuer || undefined,
        client_id: ssoForm.client_id || undefined,
        client_secret: ssoForm.client_secret || undefined,
        allowed_domains: allowed.length ? allowed : undefined,
      },
      `/${user.tenantId}/sso-config`
    );
    await mutTenantSso();
  }

  const uPageCount = Math.max(1, Math.ceil((uTotal ?? 0) / uPageSize));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        subtitle={
          user
            ? `Organization · ${user.email}${isMasterUser() ? ' · Master' : ''}`
            : 'Tenant and user administration'
        }
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="w-full shrink-0 lg:w-56">
          <ul className="space-y-1">
            {tabs.map((tab) => (
              <li key={tab.id}>
                <button
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'flex w-full items-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    activeTab === tab.id
                      ? 'bg-primary-50 text-primary-800 dark:bg-primary-900/20 dark:text-primary-300'
                      : 'text-neutral-600 hover:bg-muted dark:text-neutral-400'
                  )}
                >
                  <tab.icon className="mr-3 h-4 w-4 shrink-0" />
                  {tab.name}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 flex-1 rounded-lg border border-border bg-card p-6 shadow-sm">
          {activeTab === 'general' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-foreground">
                General
              </h2>
              {!tenant ? (
                <p className="text-sm text-neutral-500">Loading tenant…</p>
              ) : (
                <div className="grid max-w-xl gap-4">
                  <FormField label="Organization name">
                    <input
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={generalForm.name}
                      onChange={(e) =>
                        setGeneralForm((f) => ({ ...f, name: e.target.value }))
                      }
                    />
                  </FormField>
                  <FormField label="Default jurisdiction">
                    <input
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm uppercase"
                      maxLength={2}
                      value={generalForm.default_jurisdiction}
                      onChange={(e) =>
                        setGeneralForm((f) => ({
                          ...f,
                          default_jurisdiction: e.target.value.toUpperCase(),
                        }))
                      }
                    />
                  </FormField>
                  <FormField label="Retention (years)">
                    <input
                      type="number"
                      min={7}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={generalForm.retention_years}
                      onChange={(e) =>
                        setGeneralForm((f) => ({
                          ...f,
                          retention_years: parseInt(e.target.value, 10) || 7,
                        }))
                      }
                    />
                  </FormField>
                  <FormField label="License number">
                    <input
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={generalForm.license_number}
                      onChange={(e) =>
                        setGeneralForm((f) => ({
                          ...f,
                          license_number: e.target.value,
                        }))
                      }
                    />
                  </FormField>
                  <button
                    type="button"
                    disabled={savingTenant}
                    onClick={saveGeneral}
                    className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                  >
                    {savingTenant ? 'Saving…' : 'Save changes'}
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'users' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-lg font-semibold text-foreground">
                  Users &amp; roles
                </h2>
                <button
                  type="button"
                  onClick={openCreateUser}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
                >
                  Create user
                </button>
              </div>
              <SearchBar
                value={userSearch}
                onChange={setUserSearch}
                placeholder="Search users…"
              />
              <DataTable<UserRow>
                columns={userColumns}
                data={filteredUsers}
                isLoading={uLoading}
                emptyMessage="No users"
                onRowClick={openEditUser}
                pageCount={uPageCount}
                pageIndex={uPage}
                pageSize={uPageSize}
                onPageChange={setUPage}
              />
              <div className="rounded-md border border-border p-4">
                <h3 className="text-sm font-semibold">Roles</h3>
                <ul className="mt-2 space-y-1 text-sm text-neutral-600 dark:text-neutral-400">
                  {roleList.map((r) => (
                    <li key={r.id}>
                      <span className="font-medium text-foreground">
                        {r.name}
                      </span>
                      {r.description ? ` — ${r.description}` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-foreground">
                Security
              </h2>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                Values below come from tenant settings when present; otherwise
                defaults are shown.
              </p>
              <div className="space-y-3">
                <div className="rounded-md border border-border p-4">
                  <p className="text-sm font-medium">Password policy</p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Min length:{' '}
                    {security?.password_min_length != null
                      ? String(security.password_min_length)
                      : '12'}{' '}
                    characters (from API user creation rules)
                  </p>
                </div>
                <div className="rounded-md border border-border p-4">
                  <p className="text-sm font-medium">Account lockout</p>
                  <p className="mt-1 text-xs text-neutral-500">
                    {security?.lockout
                      ? JSON.stringify(security.lockout)
                      : 'Configure via identity provider or platform defaults.'}
                  </p>
                </div>
                <div className="rounded-md border border-border p-4">
                  <p className="text-sm font-medium">Session timeout</p>
                  <p className="mt-1 text-xs text-neutral-500">
                    {security?.session_timeout_minutes != null
                      ? `${String(security.session_timeout_minutes)} minutes`
                      : 'JWT access tokens — see auth deployment settings.'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sso' && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-foreground">SSO</h2>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                PATCH /api/v1/tenants/&#123;id&#125;/sso-config (OIDC)
              </p>
              <div className="grid max-w-xl gap-4">
                <FormField label="Issuer (URL)">
                  <input
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={ssoForm.issuer}
                    onChange={(e) =>
                      setSsoForm((f) => ({ ...f, issuer: e.target.value }))
                    }
                  />
                </FormField>
                <FormField label="Client ID">
                  <input
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={ssoForm.client_id}
                    onChange={(e) =>
                      setSsoForm((f) => ({ ...f, client_id: e.target.value }))
                    }
                  />
                </FormField>
                <FormField label="Client secret">
                  <input
                    type="password"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={ssoForm.client_secret}
                    onChange={(e) =>
                      setSsoForm((f) => ({
                        ...f,
                        client_secret: e.target.value,
                      }))
                    }
                    autoComplete="new-password"
                  />
                </FormField>
                <FormField label="Allowed domains (comma-separated)">
                  <input
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={ssoForm.allowed_domains}
                    onChange={(e) =>
                      setSsoForm((f) => ({
                        ...f,
                        allowed_domains: e.target.value,
                      }))
                    }
                    placeholder="example.com, app.example.com"
                  />
                </FormField>
                <button
                  type="button"
                  disabled={savingSso}
                  onClick={saveSso}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {savingSso ? 'Saving…' : 'Save SSO config'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'ai' && (
            <AiConfigTab tenantId={tenant?.id} settings={tenant?.settings} onSave={() => mutTenant()} />
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Notifications
              </h2>
              <p className="text-sm text-neutral-500">
                Notification channels and alert rules will be configured here.
              </p>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Integrations
              </h2>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                Manage IdP, payments, telephony, and e-filing connections on the
                dedicated page.
              </p>
              <Link
                href="/integrations"
                className="inline-flex rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
              >
                Open integrations
              </Link>
            </div>
          )}
        </div>
      </div>

      <FormDrawer
        open={userDrawer}
        onClose={() => setUserDrawer(false)}
        title={editUserId ? 'Edit user' : 'Create user'}
        onSubmit={submitUser}
        isSubmitting={creatingU || savingU}
        submitLabel={editUserId ? 'Save' : 'Create'}
      >

        <div className="flex flex-col gap-4">
          <FormField label="Email" required>
            <input
              type="email"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={userForm.email}
              onChange={(e) =>
                setUserForm((f) => ({ ...f, email: e.target.value }))
              }
            />
          </FormField>
          {!editUserId ? (
            <FormField label="Password" required>
              <input
                type="password"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={userForm.password}
                onChange={(e) =>
                  setUserForm((f) => ({ ...f, password: e.target.value }))
                }
                placeholder="12+ chars, upper, lower, digit, special"
              />
            </FormField>
          ) : null}
          <FormField label="First name">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={userForm.first_name}
              onChange={(e) =>
                setUserForm((f) => ({ ...f, first_name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Last name">
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={userForm.last_name}
              onChange={(e) =>
                setUserForm((f) => ({ ...f, last_name: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Roles">
            <div className="flex flex-col gap-2 rounded-md border border-border p-3">
              {roleList.map((r) => (
                <label key={r.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={userForm.role_ids.includes(r.id)}
                    onChange={() => toggleUserRole(r.id)}
                  />
                  {r.name}
                </label>
              ))}
            </div>
          </FormField>
        </div>
      </FormDrawer>
    </div>
  );
}

const AI_PROVIDERS = [
  { id: 'openai', name: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1', 'o1-mini'] },
  { id: 'anthropic', name: 'Anthropic', models: ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'] },
  { id: 'azure_openai', name: 'Azure OpenAI', models: ['gpt-4o', 'gpt-4-turbo', 'gpt-35-turbo'] },
  { id: 'local', name: 'Local / Self-hosted', models: ['custom'] },
] as const;

type AiConfig = {
  provider: string;
  model: string;
  api_key: string;
  api_endpoint?: string;
  temperature: number;
  max_tokens: number;
  system_prompt?: string;
  enabled: boolean;
};

function AiConfigTab({
  tenantId,
  settings,
  onSave,
}: {
  tenantId?: string;
  settings?: Record<string, unknown>;
  onSave: () => void;
}) {
  const existing = (settings?.ai_assistant ?? {}) as Partial<AiConfig>;

  const [config, setConfig] = useState<AiConfig>({
    provider: existing.provider || 'openai',
    model: existing.model || 'gpt-4o-mini',
    api_key: '',
    api_endpoint: existing.api_endpoint || '',
    temperature: existing.temperature ?? 0.3,
    max_tokens: existing.max_tokens ?? 2048,
    system_prompt: existing.system_prompt || '',
    enabled: existing.enabled ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const selectedProvider = AI_PROVIDERS.find((p) => p.id === config.provider);

  const handleSave = async () => {
    if (!tenantId) return;
    setSaving(true);
    try {
      await apiClient.patch(`/api/v1/tenants/${tenantId}`, {
        settings: {
          ...((settings as Record<string, unknown>) || {}),
          ai_assistant: {
            provider: config.provider,
            model: config.model,
            api_key: config.api_key || undefined,
            api_endpoint: config.api_endpoint || undefined,
            temperature: config.temperature,
            max_tokens: config.max_tokens,
            system_prompt: config.system_prompt || undefined,
            enabled: config.enabled,
          },
        },
      });
      onSave();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // handled by hook
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiClient.post<{ response: string; connected: boolean }>(
        '/api/v1/ai/assist',
        { prompt: 'Hello, are you connected?', context: 'test' }
      );
      setTestResult({
        ok: res.data.connected !== false,
        message: res.data.connected !== false
          ? `Connected to ${config.provider} (${config.model})`
          : 'AI backend returned placeholder response — API key may not be configured on the server yet.',
      });
    } catch (e: any) {
      setTestResult({
        ok: false,
        message: e?.response?.data?.detail || 'Connection failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const inputCls = 'w-full rounded-md border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">AI Assistant Configuration</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Configure the AI provider used by the Help & Docs assistant to generate scripts, reports, and automation rules from natural language.
        </p>
      </div>

      <div className="flex items-center gap-3 p-4 rounded-lg bg-neutral-50 dark:bg-neutral-700/50 border border-neutral-200 dark:border-neutral-700">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
            className="h-4 w-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
          />
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Enable AI Assistant</span>
        </label>
        {config.enabled && (
          <span className="text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-2 py-0.5 rounded-full">Active</span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">Provider</label>
          <select
            className={inputCls}
            value={config.provider}
            onChange={(e) => {
              const prov = AI_PROVIDERS.find((p) => p.id === e.target.value);
              setConfig({
                ...config,
                provider: e.target.value,
                model: prov?.models[0] || 'custom',
              });
            }}
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">Model</label>
          {selectedProvider && selectedProvider.id !== 'local' ? (
            <select className={inputCls} value={config.model} onChange={(e) => setConfig({ ...config, model: e.target.value })}>
              {selectedProvider.models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <input className={inputCls} value={config.model} onChange={(e) => setConfig({ ...config, model: e.target.value })} placeholder="model-name" />
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">API Key</label>
          <input
            type="password"
            className={inputCls}
            value={config.api_key}
            onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
            placeholder={existing.api_key ? '••••••••••••••••' : 'sk-... or key-...'}
          />
          <p className="text-xs text-neutral-500 mt-1">Stored encrypted in tenant settings. Leave blank to keep existing key.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
            Custom API Endpoint <span className="text-neutral-400 font-normal">(optional)</span>
          </label>
          <input
            className={inputCls}
            value={config.api_endpoint}
            onChange={(e) => setConfig({ ...config, api_endpoint: e.target.value })}
            placeholder={config.provider === 'azure_openai' ? 'https://your-resource.openai.azure.com' : config.provider === 'local' ? 'http://localhost:11434/v1' : ''}
          />
          <p className="text-xs text-neutral-500 mt-1">
            {config.provider === 'azure_openai' && 'Required for Azure OpenAI. Enter your resource endpoint.'}
            {config.provider === 'local' && 'URL of your local model server (e.g., Ollama, vLLM, LM Studio).'}
            {config.provider === 'openai' && 'Leave blank to use the default OpenAI endpoint.'}
            {config.provider === 'anthropic' && 'Leave blank to use the default Anthropic endpoint.'}
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">Temperature</label>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={config.temperature}
              onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
              className="flex-1"
            />
            <span className="text-sm font-mono w-8 text-center text-neutral-600 dark:text-neutral-400">{config.temperature}</span>
          </div>
          <p className="text-xs text-neutral-500 mt-1">Lower = more precise, higher = more creative. Recommended: 0.2–0.4 for code generation.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">Max Tokens</label>
          <input
            type="number"
            className={inputCls}
            value={config.max_tokens}
            onChange={(e) => setConfig({ ...config, max_tokens: parseInt(e.target.value) || 2048 })}
            min={256}
            max={16384}
            step={256}
          />
          <p className="text-xs text-neutral-500 mt-1">Maximum response length. 2048 is usually sufficient for script generation.</p>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
          Custom System Prompt <span className="text-neutral-400 font-normal">(optional)</span>
        </label>
        <textarea
          className={inputCls + ' h-32 font-mono text-xs'}
          value={config.system_prompt}
          onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
          placeholder="Override the default system prompt. Leave blank to use the built-in DCS context prompt that includes scripting language reference, report builder syntax, and entity schemas."
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Configuration'}
        </button>
        <button
          onClick={handleTest}
          disabled={testing}
          className="rounded-lg border border-neutral-300 dark:border-neutral-600 px-4 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700 disabled:opacity-50"
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </button>
      </div>

      {testResult && (
        <div className={cn(
          'p-3 rounded-lg text-sm',
          testResult.ok
            ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800'
            : 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
        )}>
          {testResult.message}
        </div>
      )}

      <div className="border-t border-neutral-200 dark:border-neutral-700 pt-4">
        <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2">How It Works</h3>
        <ul className="text-sm text-neutral-600 dark:text-neutral-400 space-y-1.5 list-disc pl-5">
          <li>The AI Assistant is available on the <strong>Help & Docs</strong> page under the AI Assistant tab.</li>
          <li>Users describe what they need in plain English, and the AI generates DCS scripts, report templates, import/export mappings, or automation rules.</li>
          <li>The system prompt includes full DCS language reference, entity schemas, and examples so the AI produces ready-to-use configurations.</li>
          <li>API keys are stored per-tenant — each tenant can use their own AI provider and billing.</li>
          <li>When no AI provider is configured, the assistant falls back to pattern-matched local responses and directs users to the documentation.</li>
        </ul>
      </div>
    </div>
  );
}
