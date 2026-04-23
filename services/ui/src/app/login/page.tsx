'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

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

          {!hasTenantContext && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-neutral-300 dark:border-neutral-600" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white dark:bg-neutral-800 text-neutral-500">
                    Single Sign-On
                  </span>
                </div>
              </div>
              <p className="mt-4 text-center text-sm text-neutral-500 dark:text-neutral-400">
                Enter your organization slug above to sign in with your
                identity provider (Okta, Azure AD, etc.).
              </p>
            </div>
          )}
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
