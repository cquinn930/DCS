'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';
import { ImpersonationBanner } from '@/components/master/impersonation-banner';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuthStore();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
      return;
    }
    // Master users land in the master control plane by default. They
    // only enter the operational app via an impersonation token, which
    // sets actingAsMaster=true.
    if (
      !isLoading &&
      isAuthenticated &&
      user?.isMaster &&
      !user?.actingAsMaster
    ) {
      router.replace('/master');
    }
  }, [isAuthenticated, isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  // Don't flash the operational shell while we redirect masters away.
  if (user?.isMaster && !user?.actingAsMaster) {
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900">
      <Sidebar />
      <div className="lg:pl-64">
        <Header />
        <ImpersonationBanner />
        <main className="py-6 px-4 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
