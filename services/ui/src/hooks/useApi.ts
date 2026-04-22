'use client';

import { useCallback, useState } from 'react';
import useSWR, { type KeyedMutator } from 'swr';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { apiClient } from '@/lib/api';
import { getApiUrl, isElectron } from '@/lib/electron';

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getErrorStatus(err: unknown): number | undefined {
  if (err && typeof err === 'object' && 'response' in err) {
    const r = (err as { response?: { status?: number } }).response;
    return r?.status;
  }
  return undefined;
}

function handleUnauthorized(
  err: unknown,
  logout: () => void,
  router: ReturnType<typeof useRouter>
) {
  if (getErrorStatus(err) === 401) {
    logout();
    router.push('/login');
  }
}

function parsePaginatedResponse<T>(body: unknown): { data: T[]; total: number } {
  if (body === null || body === undefined) {
    return { data: [], total: 0 };
  }
  if (Array.isArray(body)) {
    return { data: body as T[], total: body.length };
  }
  if (typeof body === 'object') {
    const o = body as Record<string, unknown>;
    const rawItems = o.items ?? o.data ?? o.results;
    const items = Array.isArray(rawItems) ? (rawItems as T[]) : [];
    const totalRaw = o.total ?? o.count;
    const total = typeof totalRaw === 'number' ? totalRaw : items.length;
    return { data: items, total };
  }
  return { data: [], total: 0 };
}

function buildListQuery(params?: Record<string, any>): string {
  const merged: Record<string, any> = {
    skip: 0,
    limit: 20,
    ...params,
  };
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(merged)) {
    if (value === undefined || value === null) continue;
    q.set(key, String(value));
  }
  return q.toString();
}

export function useApiList<T>(
  path: string | null,
  params?: Record<string, any>
) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const accessToken = useAuthStore((s) => s.accessToken);

  const queryString = buildListQuery(params);
  const url =
    path != null
      ? `${path.includes('?') ? path + '&' : path + '?'}${queryString}`
      : null;

  const key =
    path != null ? (['api-list', url, accessToken ?? ''] as const) : null;

  const fetcher = async ([, u]: readonly ['api-list', string, string]) => {
    try {
      const { data: body } = await apiClient.get<unknown>(u);
      return parsePaginatedResponse<T>(body);
    } catch (err) {
      handleUnauthorized(err, logout, router);
      throw err;
    }
  };

  const { data, error, isLoading, mutate } = useSWR(key, fetcher);

  return {
    data: data?.data,
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate: mutate as KeyedMutator<{ data: T[]; total: number }>,
  };
}

export function useApiDetail<T>(path: string | null, id?: string) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const accessToken = useAuthStore((s) => s.accessToken);

  const base = path?.replace(/\/$/, '') ?? '';
  const detailPath =
    path != null && id !== undefined ? `${base}/${id}` : null;

  const key =
    detailPath != null
      ? (['api-detail', detailPath, accessToken ?? ''] as const)
      : null;

  const fetcher = async ([, u]: readonly ['api-detail', string, string]) => {
    try {
      const { data } = await apiClient.get<T>(u);
      return data;
    } catch (err) {
      handleUnauthorized(err, logout, router);
      throw err;
    }
  };

  const { data, error, isLoading, mutate } = useSWR(key, fetcher);

  return {
    data,
    isLoading,
    error,
    mutate: mutate as KeyedMutator<T>,
  };
}

export function useApiMutation<TInput = unknown, TOutput = unknown>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  basePath: string
) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const trigger = useCallback(
    async (data?: TInput, pathSuffix?: string) => {
      setError(null);
      setIsMutating(true);
      const path = `${basePath}${pathSuffix ?? ''}`;
      try {
        let result: { data: TOutput; status: number };
        switch (method) {
          case 'POST':
            result = await apiClient.post<TOutput>(path, data);
            break;
          case 'PATCH':
            result = await apiClient.patch<TOutput>(path, data);
            break;
          case 'PUT':
            result = await apiClient.put<TOutput>(path, data);
            break;
          case 'DELETE':
            result = await apiClient.delete<TOutput>(path);
            break;
        }
        return result.data;
      } catch (err) {
        handleUnauthorized(err, logout, router);
        setError(err);
        throw err;
      } finally {
        setIsMutating(false);
      }
    },
    [basePath, method, logout, router]
  );

  return { trigger, isMutating, error };
}

export function useApiUpload(basePath: string) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const accessToken = useAuthStore((s) => s.accessToken);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const upload = useCallback(
    async (file: File, pathSuffix?: string) => {
      setError(null);
      setIsUploading(true);
      const path = `${basePath}${pathSuffix ?? ''}`;
      let baseUrl = DEFAULT_API_URL;
      if (isElectron()) {
        baseUrl = await getApiUrl();
      }
      const formData = new FormData();
      formData.append('file', file);
      try {
        const headers: Record<string, string> = {};
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
        const response = await fetch(`${baseUrl}${path}`, {
          method: 'POST',
          body: formData,
          headers,
        });
        if (response.status === 401) {
          logout();
          router.push('/login');
          const err = Object.assign(new Error('Unauthorized'), {
            response: { status: 401, data: {} },
          });
          throw err;
        }
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          const err = Object.assign(new Error('Upload failed'), {
            response: { status: response.status, data },
          });
          throw err;
        }
        return response.json();
      } catch (err) {
        handleUnauthorized(err, logout, router);
        setError(err);
        throw err;
      } finally {
        setIsUploading(false);
      }
    },
    [basePath, accessToken, logout, router]
  );

  return { upload, isUploading, error };
}
