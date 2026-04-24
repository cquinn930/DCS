'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ColumnDef } from '@tanstack/react-table';
import {
  Bell,
  Database,
  Key,
  Phone,
  Plug,
  Printer as PrinterIcon,
  ScanLine,
  Shield,
  Sparkles,
  Users,
} from 'lucide-react';
import {
  PrintingTab,
  ScanningTab,
  TelephonyTab,
} from '@/components/settings/integrations-tabs';
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

type SsoProtocol = 'oidc' | 'saml' | 'none';

type OidcSubResponse = {
  issuer: string;
  client_id: string;
  redirect_uri: string;
  allowed_domains: string[];
  scopes: string[];
  enabled: boolean;
  group_claim: string;
  group_role_map: Record<string, string>;
  owner_groups: string[];
  sync_groups_on_login: boolean;
};

type SamlSubResponse = {
  idp_entity_id: string;
  idp_sso_url: string;
  idp_cert_present: boolean;
  idp_slo_url: string | null;
  sp_entity_id: string;
  sp_acs_url: string;
  sp_metadata_url: string;
  sign_authn_requests: boolean;
  sp_cert_present: boolean;
  sp_key_present: boolean;
  allowed_domains: string[];
  group_attribute: string;
  group_role_map: Record<string, string>;
  owner_groups: string[];
  sync_groups_on_login: boolean;
  first_name_attribute: string;
  last_name_attribute: string;
  email_attribute: string;
  enabled: boolean;
};

type UnifiedSsoResponse = {
  protocol: SsoProtocol;
  oidc: OidcSubResponse;
  saml: SamlSubResponse;
};

const tabs = [
  { id: 'general', name: 'General', icon: Database },
  { id: 'users', name: 'Users & Roles', icon: Users },
  { id: 'security', name: 'Security', icon: Shield },
  { id: 'sso', name: 'SSO', icon: Key },
  { id: 'ai', name: 'AI Assistant', icon: Sparkles },
  { id: 'telephony', name: 'Telephony', icon: Phone },
  { id: 'printing', name: 'Print & Mail', icon: PrinterIcon },
  { id: 'scanning', name: 'Scan & Capture', icon: ScanLine },
  { id: 'notifications', name: 'Notifications', icon: Bell },
  { id: 'integrations', name: 'Integrations', icon: Plug },
] as const;

export default function SettingsPage() {
  const { user, isMasterUser } = useAuthStore();
  const token = useAuthStore((s) => s.accessToken);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]['id']>(
    'general'
  );

  const TENANT_FETCH_TABS: ReadonlyArray<(typeof tabs)[number]['id']> = [
    'general',
    'ai',
    'telephony',
    'printing',
    'scanning',
  ];
  const { data: tenant, mutate: mutTenant } = useSWR(
    token && TENANT_FETCH_TABS.includes(activeTab) ? ['tenant-current', token] : null,
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

  const { data: unifiedSso, mutate: mutUnifiedSso } = useSWR(
    token && activeTab === 'sso' && tenantSso?.id
      ? ['tenant-sso-unified', tenantSso.id, token]
      : null,
    async () => {
      const { data } = await apiClient.get<UnifiedSsoResponse>(
        `/api/v1/tenants/${tenantSso!.id}/sso-config/unified`
      );
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
    await mutUnifiedSso();
  }

  // ---- SAML state ------------------------------------------------------
  const [samlForm, setSamlForm] = useState({
    idp_entity_id: '',
    idp_sso_url: '',
    idp_x509_cert: '',
    idp_slo_url: '',
    sign_authn_requests: false,
    sp_x509_cert: '',
    sp_private_key: '',
    allowed_domains: '',
    group_attribute: 'groups',
    group_role_map: '', // edited as JSON in the textarea
    owner_groups: '',
    sync_groups_on_login: true,
    first_name_attribute: 'firstName',
    last_name_attribute: 'lastName',
    email_attribute: 'email',
  });

  useEffect(() => {
    if (!unifiedSso?.saml) return;
    const s = unifiedSso.saml;
    setSamlForm({
      idp_entity_id: s.idp_entity_id || '',
      idp_sso_url: s.idp_sso_url || '',
      // never echoed back; leave blank so admin can paste a new value
      idp_x509_cert: '',
      idp_slo_url: s.idp_slo_url || '',
      sign_authn_requests: s.sign_authn_requests || false,
      sp_x509_cert: '',
      sp_private_key: '',
      allowed_domains: (s.allowed_domains ?? []).join(', '),
      group_attribute: s.group_attribute || 'groups',
      group_role_map: Object.keys(s.group_role_map || {}).length
        ? JSON.stringify(s.group_role_map, null, 2)
        : '',
      owner_groups: (s.owner_groups ?? []).join(', '),
      sync_groups_on_login: s.sync_groups_on_login ?? true,
      first_name_attribute: s.first_name_attribute || 'firstName',
      last_name_attribute: s.last_name_attribute || 'lastName',
      email_attribute: s.email_attribute || 'email',
    });
  }, [unifiedSso]);

  const { trigger: patchSaml, isMutating: savingSaml } = useApiMutation<
    Record<string, unknown>,
    unknown
  >('PATCH', '/api/v1/tenants');
  const { trigger: putProtocol, isMutating: switchingProtocol } =
    useApiMutation<{ protocol: SsoProtocol }, unknown>(
      'PUT',
      '/api/v1/tenants'
    );

  async function saveSaml() {
    if (!user?.tenantId) return;
    const splitList = (s: string) =>
      s
        .split(/[,;\s]+/)
        .map((x) => x.trim())
        .filter(Boolean);
    let groupRoleMap: Record<string, string> | undefined;
    if (samlForm.group_role_map.trim()) {
      try {
        const parsed = JSON.parse(samlForm.group_role_map);
        if (parsed && typeof parsed === 'object') {
          groupRoleMap = parsed as Record<string, string>;
        }
      } catch {
        alert('Group → role map is not valid JSON');
        return;
      }
    }
    const allowed = splitList(samlForm.allowed_domains);
    const ownerGroups = splitList(samlForm.owner_groups);
    await patchSaml(
      {
        idp_entity_id: samlForm.idp_entity_id || undefined,
        idp_sso_url: samlForm.idp_sso_url || undefined,
        // only PATCH the cert when the admin has typed a new one,
        // otherwise we'd wipe the stored cert with an empty string
        idp_x509_cert: samlForm.idp_x509_cert || undefined,
        idp_slo_url: samlForm.idp_slo_url || undefined,
        sign_authn_requests: samlForm.sign_authn_requests,
        sp_x509_cert: samlForm.sp_x509_cert || undefined,
        sp_private_key: samlForm.sp_private_key || undefined,
        allowed_domains: allowed.length ? allowed : undefined,
        group_attribute: samlForm.group_attribute || undefined,
        group_role_map: groupRoleMap,
        owner_groups: ownerGroups.length ? ownerGroups : undefined,
        sync_groups_on_login: samlForm.sync_groups_on_login,
        first_name_attribute: samlForm.first_name_attribute || undefined,
        last_name_attribute: samlForm.last_name_attribute || undefined,
        email_attribute: samlForm.email_attribute || undefined,
      },
      `/${user.tenantId}/sso-config/saml`
    );
    await mutUnifiedSso();
  }

  async function switchSsoProtocol(target: SsoProtocol) {
    if (!user?.tenantId) return;
    await putProtocol({ protocol: target }, `/${user.tenantId}/sso-config/protocol`);
    await mutUnifiedSso();
  }

  function copyToClipboard(text: string) {
    if (!text) return;
    navigator.clipboard?.writeText(text).catch(() => {
      // best-effort
    });
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
            <SsoTab
              activeProtocol={unifiedSso?.protocol ?? 'none'}
              oidcEnabled={unifiedSso?.oidc?.enabled ?? false}
              samlEnabled={unifiedSso?.saml?.enabled ?? false}
              samlMeta={unifiedSso?.saml}
              onSwitch={switchSsoProtocol}
              switching={switchingProtocol}
              ssoForm={ssoForm}
              setSsoForm={setSsoForm}
              saveOidc={saveSso}
              savingOidc={savingSso}
              samlForm={samlForm}
              setSamlForm={setSamlForm}
              saveSaml={saveSaml}
              savingSaml={savingSaml}
              copyToClipboard={copyToClipboard}
            />
          )}

          {activeTab === 'ai' && (
            <AiConfigTab tenantId={tenant?.id} settings={tenant?.settings} onSave={() => mutTenant()} />
          )}

          {activeTab === 'telephony' && (
            <TelephonyTab tenantId={tenant?.id} />
          )}

          {activeTab === 'printing' && (
            <PrintingTab tenantId={tenant?.id} />
          )}

          {activeTab === 'scanning' && (
            <ScanningTab tenantId={tenant?.id} />
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

type SsoTabProps = {
  activeProtocol: SsoProtocol;
  oidcEnabled: boolean;
  samlEnabled: boolean;
  samlMeta?: SamlSubResponse;
  onSwitch: (target: SsoProtocol) => Promise<void>;
  switching: boolean;
  ssoForm: {
    issuer: string;
    client_id: string;
    client_secret: string;
    allowed_domains: string;
  };
  setSsoForm: React.Dispatch<
    React.SetStateAction<{
      issuer: string;
      client_id: string;
      client_secret: string;
      allowed_domains: string;
    }>
  >;
  saveOidc: () => Promise<void>;
  savingOidc: boolean;
  samlForm: {
    idp_entity_id: string;
    idp_sso_url: string;
    idp_x509_cert: string;
    idp_slo_url: string;
    sign_authn_requests: boolean;
    sp_x509_cert: string;
    sp_private_key: string;
    allowed_domains: string;
    group_attribute: string;
    group_role_map: string;
    owner_groups: string;
    sync_groups_on_login: boolean;
    first_name_attribute: string;
    last_name_attribute: string;
    email_attribute: string;
  };
  setSamlForm: React.Dispatch<React.SetStateAction<SsoTabProps['samlForm']>>;
  saveSaml: () => Promise<void>;
  savingSaml: boolean;
  copyToClipboard: (text: string) => void;
};

function SsoTab({
  activeProtocol,
  oidcEnabled,
  samlEnabled,
  samlMeta,
  onSwitch,
  switching,
  ssoForm,
  setSsoForm,
  saveOidc,
  savingOidc,
  samlForm,
  setSamlForm,
  saveSaml,
  savingSaml,
  copyToClipboard,
}: SsoTabProps) {
  // Local view state — when admin opens a protocol form they may not
  // have switched the active protocol yet. Default to whichever is
  // active, fall back to "oidc".
  const [view, setView] = useState<SsoProtocol>(
    activeProtocol === 'none' ? 'oidc' : activeProtocol
  );
  useEffect(() => {
    if (activeProtocol !== 'none') setView(activeProtocol);
  }, [activeProtocol]);

  const inputCls =
    'w-full rounded-md border border-input bg-background px-3 py-2 text-sm';

  const acsUrl = samlMeta?.sp_acs_url ?? '';
  const spEntity = samlMeta?.sp_entity_id ?? '';
  // Provided server-side from API_PUBLIC_URL so the UI doesn't have
  // to know what the public base looks like.
  const metadataUrl = samlMeta?.sp_metadata_url ?? '';

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-foreground">SSO</h2>

      <div className="rounded-md border border-border p-4">
        <p className="text-sm font-medium">Active protocol</p>
        <p className="mt-1 text-xs text-neutral-500">
          A tenant can use OIDC <em>or</em> SAML, never both at once.
          Switching requires the target protocol to already be configured
          below.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
              activeProtocol === 'oidc' &&
                'bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-300',
              activeProtocol === 'saml' &&
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
              activeProtocol === 'none' &&
                'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400'
            )}
          >
            {activeProtocol === 'none' ? 'Disabled' : activeProtocol.toUpperCase()}
          </span>
          {activeProtocol !== 'oidc' && (
            <button
              type="button"
              disabled={switching || !oidcEnabled}
              onClick={() => onSwitch('oidc')}
              className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
              title={oidcEnabled ? 'Switch to OIDC' : 'Configure OIDC first'}
            >
              Use OIDC
            </button>
          )}
          {activeProtocol !== 'saml' && (
            <button
              type="button"
              disabled={switching || !samlEnabled}
              onClick={() => onSwitch('saml')}
              className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
              title={samlEnabled ? 'Switch to SAML' : 'Configure SAML first'}
            >
              Use SAML
            </button>
          )}
          {activeProtocol !== 'none' && (
            <button
              type="button"
              disabled={switching}
              onClick={() => onSwitch('none')}
              className="rounded-md border border-border px-3 py-1 text-xs font-medium text-neutral-600 hover:bg-muted disabled:opacity-50"
            >
              Disable SSO
            </button>
          )}
        </div>
      </div>

      <div className="border-b border-border">
        <nav className="-mb-px flex gap-4">
          {(['oidc', 'saml'] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setView(p)}
              className={cn(
                'border-b-2 px-3 py-2 text-sm font-medium',
                view === p
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-neutral-500 hover:text-foreground'
              )}
            >
              {p.toUpperCase()}
              {p === activeProtocol && (
                <span className="ml-2 rounded-full bg-primary-100 px-1.5 py-0.5 text-[10px] text-primary-800 dark:bg-primary-900/30 dark:text-primary-300">
                  active
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {view === 'oidc' && (
        <div className="grid max-w-xl gap-4">
          <p className="text-xs text-neutral-500">
            PATCH /api/v1/tenants/&#123;id&#125;/sso-config
          </p>
          <FormField label="Issuer (URL)">
            <input
              className={inputCls}
              value={ssoForm.issuer}
              onChange={(e) =>
                setSsoForm((f) => ({ ...f, issuer: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Client ID">
            <input
              className={inputCls}
              value={ssoForm.client_id}
              onChange={(e) =>
                setSsoForm((f) => ({ ...f, client_id: e.target.value }))
              }
            />
          </FormField>
          <FormField label="Client secret">
            <input
              type="password"
              className={inputCls}
              value={ssoForm.client_secret}
              onChange={(e) =>
                setSsoForm((f) => ({ ...f, client_secret: e.target.value }))
              }
              autoComplete="new-password"
            />
          </FormField>
          <FormField label="Allowed domains (comma-separated)">
            <input
              className={inputCls}
              value={ssoForm.allowed_domains}
              onChange={(e) =>
                setSsoForm((f) => ({ ...f, allowed_domains: e.target.value }))
              }
              placeholder="example.com, app.example.com"
            />
          </FormField>
          <button
            type="button"
            disabled={savingOidc}
            onClick={saveOidc}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {savingOidc ? 'Saving…' : 'Save OIDC config'}
          </button>
        </div>
      )}

      {view === 'saml' && (
        <div className="space-y-6">
          <div className="rounded-md border border-dashed border-border bg-muted/30 p-4 text-sm">
            <p className="font-medium">Service Provider URLs</p>
            <p className="mt-1 text-xs text-neutral-500">
              Hand these to your IdP admin when configuring the SAML
              application.
            </p>
            <dl className="mt-3 grid gap-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <dt className="w-32 text-neutral-500">ACS URL</dt>
                <dd className="break-all font-mono">{acsUrl || '—'}</dd>
                {acsUrl && (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(acsUrl)}
                    className="rounded border border-border px-2 py-0.5 text-[10px] hover:bg-muted"
                  >
                    Copy
                  </button>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <dt className="w-32 text-neutral-500">SP Entity ID</dt>
                <dd className="break-all font-mono">{spEntity || '—'}</dd>
                {spEntity && (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(spEntity)}
                    className="rounded border border-border px-2 py-0.5 text-[10px] hover:bg-muted"
                  >
                    Copy
                  </button>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <dt className="w-32 text-neutral-500">SP Metadata</dt>
                <dd>
                  {metadataUrl ? (
                    <a
                      href={metadataUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="font-mono text-primary-600 underline hover:text-primary-700"
                    >
                      Download XML
                    </a>
                  ) : (
                    <span className="text-neutral-500">
                      Save SAML config first
                    </span>
                  )}
                </dd>
              </div>
            </dl>
          </div>

          <div className="grid max-w-xl gap-4">
            <p className="text-xs text-neutral-500">
              PATCH /api/v1/tenants/&#123;id&#125;/sso-config/saml
            </p>
            <FormField label="IdP Entity ID">
              <input
                className={inputCls}
                value={samlForm.idp_entity_id}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, idp_entity_id: e.target.value }))
                }
                placeholder="http://www.okta.com/exk..."
              />
            </FormField>
            <FormField label="IdP Single Sign-On URL">
              <input
                className={inputCls}
                value={samlForm.idp_sso_url}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, idp_sso_url: e.target.value }))
                }
                placeholder="https://yourorg.okta.com/app/.../sso/saml"
              />
            </FormField>
            <FormField label="IdP X.509 Certificate (PEM)">
              <textarea
                className={inputCls + ' h-32 font-mono text-xs'}
                value={samlForm.idp_x509_cert}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, idp_x509_cert: e.target.value }))
                }
                placeholder={
                  samlMeta?.idp_cert_present
                    ? '••••• (cert configured — paste a new value to replace)'
                    : '-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----'
                }
              />
            </FormField>
            <FormField label="IdP Single Logout URL (optional)">
              <input
                className={inputCls}
                value={samlForm.idp_slo_url}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, idp_slo_url: e.target.value }))
                }
              />
            </FormField>

            <div className="rounded-md border border-border p-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={samlForm.sign_authn_requests}
                  onChange={(e) =>
                    setSamlForm((f) => ({
                      ...f,
                      sign_authn_requests: e.target.checked,
                    }))
                  }
                />
                Sign AuthnRequests (requires SP cert + key below)
              </label>
              {samlForm.sign_authn_requests && (
                <div className="mt-3 grid gap-3">
                  <FormField label="SP X.509 Certificate (PEM)">
                    <textarea
                      className={inputCls + ' h-24 font-mono text-xs'}
                      value={samlForm.sp_x509_cert}
                      onChange={(e) =>
                        setSamlForm((f) => ({
                          ...f,
                          sp_x509_cert: e.target.value,
                        }))
                      }
                      placeholder={
                        samlMeta?.sp_cert_present
                          ? '••••• (configured — paste a new value to replace)'
                          : '-----BEGIN CERTIFICATE-----\n...'
                      }
                    />
                  </FormField>
                  <FormField label="SP Private Key (PEM)">
                    <textarea
                      className={inputCls + ' h-24 font-mono text-xs'}
                      value={samlForm.sp_private_key}
                      onChange={(e) =>
                        setSamlForm((f) => ({
                          ...f,
                          sp_private_key: e.target.value,
                        }))
                      }
                      placeholder={
                        samlMeta?.sp_key_present
                          ? '••••• (configured — paste a new value to replace)'
                          : '-----BEGIN PRIVATE KEY-----\n...'
                      }
                    />
                  </FormField>
                </div>
              )}
            </div>

            <FormField label="Allowed email domains (comma-separated)">
              <input
                className={inputCls}
                value={samlForm.allowed_domains}
                onChange={(e) =>
                  setSamlForm((f) => ({
                    ...f,
                    allowed_domains: e.target.value,
                  }))
                }
                placeholder="example.com, app.example.com"
              />
            </FormField>

            <div className="rounded-md border border-border p-3 space-y-3">
              <p className="text-sm font-medium">Attribute mapping</p>
              <p className="text-xs text-neutral-500">
                Names of the SAML AttributeStatement fields the IdP sends.
                Defaults match Okta. ADFS / Azure AD typically use
                fully-qualified URI names (e.g. http://schemas.xmlsoap.org/...
                ).
              </p>
              <FormField label="Email attribute">
                <input
                  className={inputCls}
                  value={samlForm.email_attribute}
                  onChange={(e) =>
                    setSamlForm((f) => ({
                      ...f,
                      email_attribute: e.target.value,
                    }))
                  }
                />
              </FormField>
              <FormField label="First-name attribute">
                <input
                  className={inputCls}
                  value={samlForm.first_name_attribute}
                  onChange={(e) =>
                    setSamlForm((f) => ({
                      ...f,
                      first_name_attribute: e.target.value,
                    }))
                  }
                />
              </FormField>
              <FormField label="Last-name attribute">
                <input
                  className={inputCls}
                  value={samlForm.last_name_attribute}
                  onChange={(e) =>
                    setSamlForm((f) => ({
                      ...f,
                      last_name_attribute: e.target.value,
                    }))
                  }
                />
              </FormField>
              <FormField label="Group attribute (carries the IdP group memberships)">
                <input
                  className={inputCls}
                  value={samlForm.group_attribute}
                  onChange={(e) =>
                    setSamlForm((f) => ({
                      ...f,
                      group_attribute: e.target.value,
                    }))
                  }
                />
              </FormField>
            </div>

            <FormField label="Owner groups (comma-separated; membership grants is_owner)">
              <input
                className={inputCls}
                value={samlForm.owner_groups}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, owner_groups: e.target.value }))
                }
                placeholder="DCS Owners, DCS Admins"
              />
            </FormField>
            <FormField label="Group → role map (JSON)">
              <textarea
                className={inputCls + ' h-24 font-mono text-xs'}
                value={samlForm.group_role_map}
                onChange={(e) =>
                  setSamlForm((f) => ({ ...f, group_role_map: e.target.value }))
                }
                placeholder={'{\n  "DCSAdmins": "Admin",\n  "DCSCollectors": "Collector"\n}'}
              />
            </FormField>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={samlForm.sync_groups_on_login}
                onChange={(e) =>
                  setSamlForm((f) => ({
                    ...f,
                    sync_groups_on_login: e.target.checked,
                  }))
                }
              />
              Sync roles from IdP groups on every login (REPLACE assignments)
            </label>

            <button
              type="button"
              disabled={savingSaml}
              onClick={saveSaml}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {savingSaml ? 'Saving…' : 'Save SAML config'}
            </button>
          </div>
        </div>
      )}
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
