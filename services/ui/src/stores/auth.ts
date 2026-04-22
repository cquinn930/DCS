'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '@/lib/api';

function detailToErrorString(detail: unknown): string {
  if (detail == null) return 'Login failed';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: unknown) => {
        if (e && typeof e === 'object' && 'msg' in e) {
          const m = (e as { msg?: unknown }).msg;
          if (typeof m === 'string') return m;
        }
        return String(e);
      })
      .join('; ');
  }
  if (typeof detail === 'object') {
    const o = detail as Record<string, unknown>;
    if (typeof o.msg === 'string') return o.msg;
    if (typeof o.message === 'string') return o.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return 'Login failed';
    }
  }
  return String(detail);
}

interface User {
  id: string;
  tenantId: string;
  email: string;
  firstName?: string;
  lastName?: string;
  roles: string[];
  permissions: string[];
  isOwner: boolean;
  isMaster?: boolean;
  // Impersonation context (only set when actingAsMaster is true)
  actingAsMaster?: boolean;
  actingCanWrite?: boolean;
  masterUserId?: string;
  masterTenantId?: string;
  impersonationId?: string;
}

interface ImpersonationState {
  tenantId: string;
  tenantSlug: string;
  mode: 'read' | 'write';
  expiresAt: number; // epoch ms
  startedAt: number; // epoch ms
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // While impersonating, we stash the master's regular tokens here so
  // `exitImpersonation()` can restore them without re-prompting for login.
  masterAccessToken: string | null;
  masterRefreshToken: string | null;
  impersonation: ImpersonationState | null;

  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  refreshAccessToken: () => Promise<boolean>;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearError: () => void;
  hasPermission: (permission: string) => boolean;
  isMasterUser: () => boolean;
  // Master control plane
  enterTenant: (slug: string, reason: string, mode: 'read' | 'write') => Promise<boolean>;
  exitImpersonation: () => Promise<void>;
}

function decodeUserFromToken(accessToken: string): User {
  const payload = JSON.parse(atob(accessToken.split('.')[1]));
  return {
    id: payload.sub,
    tenantId: payload.tenant_id,
    email: payload.email,
    roles: payload.roles || [],
    permissions: payload.permissions || [],
    isOwner: payload.is_owner || false,
    isMaster: Boolean(payload.is_master),
    actingAsMaster: Boolean(payload.acting_as_master),
    actingCanWrite: Boolean(payload.acting_can_write),
    masterUserId: payload.master_user_id || undefined,
    masterTenantId: payload.master_tenant_id || undefined,
    impersonationId: payload.impersonation_id || undefined,
  };
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      masterAccessToken: null,
      masterRefreshToken: null,
      impersonation: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.post('/api/v1/auth/login', {
            email,
            password,
          });

          const { access_token, refresh_token } = response.data as { access_token: string; refresh_token: string };

          set({
            user: decodeUserFromToken(access_token),
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
            masterAccessToken: null,
            masterRefreshToken: null,
            impersonation: null,
          });

          return true;
        } catch (err: unknown) {
          let detail: unknown;
          if (err && typeof err === 'object' && 'response' in err) {
            detail = (err as { response?: { data?: { detail?: unknown } } })
              .response?.data?.detail;
          }
          set({
            error: detail != null ? detailToErrorString(detail) : 'Login failed. Check your credentials and try again.',
            isLoading: false,
          });
          return false;
        }
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
          masterAccessToken: null,
          masterRefreshToken: null,
          impersonation: null,
        });
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) return false;

        try {
          const response = await apiClient.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken,
          });

          set({ accessToken: (response.data as { access_token: string }).access_token });
          return true;
        } catch {
          get().logout();
          return false;
        }
      },

      setTokens: (accessToken: string, refreshToken: string) => {
        set({
          user: decodeUserFromToken(accessToken),
          accessToken,
          refreshToken,
          isAuthenticated: true,
        });
      },

      clearError: () => set({ error: null }),

      hasPermission: (permission: string) => {
        const perms = get().user?.permissions;
        return !!perms?.includes(permission);
      },

      isMasterUser: () => {
        const u = get().user;
        if (!u) return false;
        if (u.isMaster) return true;
        return u.roles.includes('master');
      },

      enterTenant: async (slug: string, reason: string, mode: 'read' | 'write') => {
        const state = get();
        if (!state.user?.isMaster || state.user.actingAsMaster) {
          set({ error: 'Only master users (not already impersonating) can enter a tenant.' });
          return false;
        }
        try {
          const resp = await apiClient.post(
            `/api/v1/master/impersonate/${encodeURIComponent(slug)}`,
            { reason, mode }
          );
          const data = resp.data as {
            access_token: string;
            expires_in_seconds: number;
            tenant_id: string;
            tenant_slug: string;
            mode: 'read' | 'write';
          };
          const now = Date.now();
          set({
            // Stash the master tokens so we can restore them on exit.
            masterAccessToken: state.accessToken,
            masterRefreshToken: state.refreshToken,
            // Switch active tokens to the impersonation token.
            accessToken: data.access_token,
            // Impersonation tokens cannot be refreshed — clear refresh.
            refreshToken: null,
            user: decodeUserFromToken(data.access_token),
            isAuthenticated: true,
            impersonation: {
              tenantId: data.tenant_id,
              tenantSlug: data.tenant_slug,
              mode: data.mode,
              startedAt: now,
              expiresAt: now + data.expires_in_seconds * 1000,
            },
            error: null,
          });
          return true;
        } catch (err: unknown) {
          let detail: unknown;
          if (err && typeof err === 'object' && 'response' in err) {
            detail = (err as { response?: { data?: { detail?: unknown } } })
              .response?.data?.detail;
          }
          set({
            error:
              detail != null
                ? detailToErrorString(detail)
                : 'Failed to enter tenant. Check the slug and try again.',
          });
          return false;
        }
      },

      exitImpersonation: async () => {
        const state = get();
        if (!state.impersonation) {
          return;
        }

        // Best-effort audit ping; never block the UX on it.
        try {
          await apiClient.post('/api/v1/master/exit-impersonation');
        } catch {
          // Token may already be expired — that's fine, we're leaving anyway.
        }

        if (state.masterAccessToken) {
          // Restore master tokens.
          set({
            accessToken: state.masterAccessToken,
            refreshToken: state.masterRefreshToken,
            user: decodeUserFromToken(state.masterAccessToken),
            masterAccessToken: null,
            masterRefreshToken: null,
            impersonation: null,
            isAuthenticated: true,
          });
        } else {
          // No stashed master token (shouldn't happen) — force re-login.
          get().logout();
        }
      },
    }),
    {
      name: 'dcs-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        masterAccessToken: state.masterAccessToken,
        masterRefreshToken: state.masterRefreshToken,
        impersonation: state.impersonation,
      }),
    }
  )
);
