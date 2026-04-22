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
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  refreshAccessToken: () => Promise<boolean>;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearError: () => void;
  hasPermission: (permission: string) => boolean;
  isMasterUser: () => boolean;
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

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.post('/api/v1/auth/login', {
            email,
            password,
          });

          const { access_token, refresh_token } = response.data as { access_token: string; refresh_token: string };

          // Decode JWT to get user info (simple decode, validation happens server-side)
          const payload = JSON.parse(atob(access_token.split('.')[1]));

          const user: User = {
            id: payload.sub,
            tenantId: payload.tenant_id,
            email: payload.email,
            roles: payload.roles || [],
            permissions: payload.permissions || [],
            isOwner: payload.is_owner || false,
            isMaster: Boolean(payload.is_master),
          };

          set({
            user,
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
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
        const payload = JSON.parse(atob(accessToken.split('.')[1]));

        const user: User = {
          id: payload.sub,
          tenantId: payload.tenant_id,
          email: payload.email,
          roles: payload.roles || [],
          permissions: payload.permissions || [],
          isOwner: payload.is_owner || false,
          isMaster: Boolean(payload.is_master),
        };

        set({
          user,
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
    }),
    {
      name: 'dcs-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
);
