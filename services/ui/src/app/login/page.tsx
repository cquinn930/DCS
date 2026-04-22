'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { isElectron, systemSsoLogin } from '@/lib/electron';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isLoading, error, setTokens } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organizationSlug, setOrganizationSlug] = useState(
    () => searchParams.get('tenant') ?? ''
  );

  useEffect(() => {
    const t = searchParams.get('tenant');
    if (t != null && t !== '') {
      setOrganizationSlug(t);
    }
  }, [searchParams]);

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    if (accessToken && refreshToken) {
      setTokens(accessToken, refreshToken);
      router.replace('/dashboard');
    }
  }, [searchParams, setTokens, router]);

  const tenantSlug =
    organizationSlug.trim() ||
    (searchParams.get('tenant')?.trim() ?? '');
  const hasTenantContext = tenantSlug.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await login(email, password);
    if (success) {
      router.push('/dashboard');
    }
  };

  const handleTenantSsoLogin = () => {
    if (!tenantSlug) return;
    const url = `${API_URL}/api/v1/auth/sso/${encodeURIComponent(tenantSlug)}`;
    window.location.href = url;
  };

  const handleLegacySsoLogin = async () => {
    if (isElectron()) {
      const result = await systemSsoLogin();
      if (result.success) {
        router.push('/dashboard');
      } else {
        window.location.href = '/api/auth/sso';
      }
    } else {
      window.location.href = '/api/auth/sso';
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-900 px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-10">
          <h1 className="text-5xl font-bold text-neutral-900 dark:text-white tracking-tight">
            DCS
          </h1>
          <p className="text-lg text-neutral-600 dark:text-neutral-400 mt-3">
            Debt Collection System
          </p>
        </div>

        <div className="bg-white dark:bg-neutral-800 rounded-xl shadow-xl p-10">
          <div className="space-y-6">
            <div>
              <label
                htmlFor="organization"
                className="block text-sm font-medium text-neutral-700 dark:text-neutral-300"
              >
                Organization
              </label>
              <input
                id="organization"
                type="text"
                value={organizationSlug}
                onChange={(e) => setOrganizationSlug(e.target.value)}
                className="mt-1 block w-full px-4 py-3 text-base border border-neutral-300 dark:border-neutral-600 rounded-lg shadow-sm bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white focus:ring-primary-500 focus:border-primary-500"
                placeholder="Enter your organization slug"
                autoComplete="organization"
              />
            </div>

            {hasTenantContext && (
              <div className="rounded-lg border-2 border-primary-500/40 bg-primary-50/50 dark:bg-primary-900/20 p-4">
                <p className="text-sm text-neutral-600 dark:text-neutral-300 mb-3">
                  Sign in with your organization&apos;s identity provider.
                </p>
                <button
                  type="button"
                  onClick={handleTenantSsoLogin}
                  className="w-full flex items-center justify-center py-3 px-4 rounded-md shadow-sm text-base font-semibold text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  SSO Login
                </button>
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-6 mt-6">
            {error && (
              <div className="bg-error-50 dark:bg-error-700/20 border border-error-500 rounded-md p-4">
                <p className="text-sm text-error-700 dark:text-error-500">
                  {error}
                </p>
              </div>
            )}

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-neutral-700 dark:text-neutral-300"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1 block w-full px-4 py-3 text-base border border-neutral-300 dark:border-neutral-600 rounded-lg shadow-sm bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white focus:ring-primary-500 focus:border-primary-500"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-neutral-700 dark:text-neutral-300"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="mt-1 block w-full px-4 py-3 text-base border border-neutral-300 dark:border-neutral-600 rounded-lg shadow-sm bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white focus:ring-primary-500 focus:border-primary-500"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-base font-semibold text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-neutral-300 dark:border-neutral-600" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white dark:bg-neutral-800 text-neutral-500">
                  Or continue with
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleLegacySsoLogin}
              className="mt-4 w-full flex items-center justify-center py-2 px-4 border border-neutral-300 dark:border-neutral-600 rounded-md shadow-sm text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-600"
            >
              <svg
                className="w-5 h-5 mr-2"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
              </svg>
              Single Sign-On (SSO)
            </button>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-neutral-500 dark:text-neutral-400">
          Non-legal guidance: This software assists with compliance but does not
          guarantee it.
        </p>
      </div>
    </div>
  );
}

function LoginFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-900 px-4">
      <div className="text-neutral-600 dark:text-neutral-400 text-sm">
        Loading…
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginPageContent />
    </Suspense>
  );
}
