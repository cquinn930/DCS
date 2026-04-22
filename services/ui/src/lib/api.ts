/**
 * API Client for DCS
 *
 * Handles authentication, token refresh, and API calls.
 */

import { getApiUrl, isElectron } from './electron';

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string = DEFAULT_API_URL;
  private initialized: boolean = false;

  async init() {
    if (this.initialized) return;

    if (isElectron()) {
      this.baseUrl = await getApiUrl();
    }

    this.initialized = true;
  }

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;

    try {
      const stored = localStorage.getItem('dcs-auth');
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed.state?.accessToken || null;
      }
    } catch {
      return null;
    }
    return null;
  }

  private async request<T>(
    method: string,
    path: string,
    data?: any,
    options: RequestInit = {}
  ): Promise<{ data: T; status: number }> {
    await this.init();

    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw {
        response: {
          status: response.status,
          data: error,
        },
      };
    }

    if (response.status === 204 || response.status === 205) {
      return { data: undefined as T, status: response.status };
    }

    const responseData = await response.json();
    return { data: responseData, status: response.status };
  }

  async get<T>(path: string, options?: RequestInit) {
    return this.request<T>('GET', path, undefined, options);
  }

  async post<T>(path: string, data?: any, options?: RequestInit) {
    return this.request<T>('POST', path, data, options);
  }

  async put<T>(path: string, data?: any, options?: RequestInit) {
    return this.request<T>('PUT', path, data, options);
  }

  async patch<T>(path: string, data?: any, options?: RequestInit) {
    return this.request<T>('PATCH', path, data, options);
  }

  async delete<T>(path: string, options?: RequestInit) {
    return this.request<T>('DELETE', path, undefined, options);
  }
}

export const apiClient = new ApiClient();
