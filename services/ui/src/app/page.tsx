'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading, setTokens } = useAuthStore();

  // SSO callback lands here as `/?access_token=...&refresh_token=...&expires_in=...`.
  // Consume the tokens, scrub them from the URL, and proceed to the dashboard.
  // Must run before the auth-state redirect below, otherwise we lose the tokens
  // by bouncing to /login first.
  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    if (accessToken && refreshToken) {
      setTokens(accessToken, refreshToken);
      router.replace('/dashboard');
    }
  }, [searchParams, setTokens, router]);

  useEffect(() => {
    // If we just stored tokens above, the next render will see
    // isAuthenticated=true and the replace('/dashboard') will short-circuit
    // this branch. Otherwise: standard auth-gate behaviour.
    if (isLoading) return;
    if (searchParams.get('access_token')) return; // handled by the effect above
    if (isAuthenticated) {
      router.replace('/dashboard');
    } else {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
        <p className="mt-4 text-neutral-600 dark:text-neutral-400">Loading...</p>
      </div>
    </div>
  );
}

function HomeFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
        <p className="mt-4 text-neutral-600 dark:text-neutral-400">Loading...</p>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<HomeFallback />}>
      <HomePageContent />
    </Suspense>
  );
}
