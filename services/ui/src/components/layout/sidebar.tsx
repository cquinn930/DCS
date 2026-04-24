'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  Bell,
  BookOpen,
  Briefcase,
  Building,
  Building2,
  Calculator,
  Calendar,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Code,
  CreditCard,
  Database,
  DollarSign,
  Download,
  Eye,
  FileCheck,
  FileText,
  Filter,
  FolderOpen,
  GitBranch,
  Globe,
  Hammer,
  HelpCircle,
  Landmark,
  Layers,
  LayoutDashboard,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Plug,
  Receipt,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Tag,
  Target,
  TrendingUp,
  Upload,
  UserCheck,
  Users,
  Wrench,
  Zap,
  Files,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

type NavItem = {
  name: string;
  href: string;
  icon: LucideIcon;
};

type NavGroup = {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavItem[];
};

const navigationGroups: NavGroup[] = [
  {
    id: 'collection',
    label: 'Collection',
    icon: Briefcase,
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Accounts', href: '/accounts', icon: FileText },
      { name: 'Consumers', href: '/consumers', icon: Users },
      { name: 'Cases', href: '/cases', icon: FolderOpen },
      { name: 'Payments', href: '/payments', icon: CreditCard },
      { name: 'Payment Plans', href: '/payment-plans', icon: Calendar },
      { name: 'Disputes', href: '/disputes', icon: AlertTriangle },
      { name: 'Litigation', href: '/litigation', icon: Scale },
      { name: 'Judgments', href: '/judgments', icon: Hammer },
      { name: 'Courts', href: '/courts', icon: Building2 },
      { name: 'Notices', href: '/notices', icon: Mail },
      { name: 'Flash Messages', href: '/flash-messages', icon: Bell },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    icon: Wrench,
    items: [
      { name: 'Workflow', href: '/workflow', icon: GitBranch },
      { name: 'SubPlans', href: '/subplans', icon: Layers },
      { name: 'Conditions', href: '/conditions', icon: Filter },
      { name: 'Batch Letters', href: '/batch-letters', icon: Mail },
      { name: 'Documents', href: '/documents', icon: Files },
      { name: 'Doc Drafts', href: '/doc-drafts', icon: FileCheck },
      { name: 'Automation', href: '/automation', icon: Zap },
      { name: 'Skip Trace', href: '/skip-trace', icon: MapPin },
      { name: 'Legal Reviews', href: '/reviews', icon: ClipboardCheck },
    ],
  },
  {
    id: 'financial',
    label: 'Financial',
    icon: DollarSign,
    items: [
      { name: 'Trust Accounts', href: '/trust', icon: Landmark },
      { name: 'Remittance', href: '/remittance', icon: Receipt },
      { name: 'Payment Waterfalls', href: '/waterfalls', icon: Layers },
      { name: 'Costs & Billing', href: '/costs', icon: Receipt },
      { name: 'Calculations', href: '/calculations', icon: Calculator },
      { name: 'Safeguards', href: '/safeguards', icon: ShieldAlert },
    ],
  },
  {
    id: 'data',
    label: 'Data',
    icon: Database,
    items: [
      { name: 'Reports', href: '/reports', icon: BarChart3 },
      { name: 'Trends', href: '/trends', icon: TrendingUp },
      { name: 'Imports', href: '/imports', icon: Upload },
      { name: 'Exports', href: '/exports', icon: Download },
      { name: 'EDI', href: '/edi', icon: ArrowLeftRight },
      { name: 'Credit Bureau', href: '/credit-bureau', icon: Building },
      { name: 'Scripting', href: '/scripting', icon: Code },
      { name: 'Help & Docs', href: '/help', icon: HelpCircle },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    icon: ShieldCheck,
    items: [
      { name: 'Tags', href: '/tags', icon: Tag },
      { name: 'Performance', href: '/performance', icon: Target },
      { name: 'Data Masking', href: '/masking', icon: Eye },
      { name: 'Demographics', href: '/demographics', icon: UserCheck },
      { name: 'Compliance', href: '/compliance', icon: Shield },
      { name: 'Integrations', href: '/integrations', icon: Plug },
      { name: 'Client Portal', href: '/client-portal', icon: Globe },
      { name: 'Audit Trail', href: '/audit-trail', icon: Lock },
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

function buildExpandedForPath(pathname: string): Record<string, boolean> {
  const next: Record<string, boolean> = {};
  for (const group of navigationGroups) {
    next[group.id] = group.items.some((item) => pathname.startsWith(item.href));
  }
  return next;
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    buildExpandedForPath(pathname)
  );

  useEffect(() => {
    setExpanded((prev) => {
      const fromPath = buildExpandedForPath(pathname);
      const next = { ...prev };
      for (const id of Object.keys(fromPath)) {
        if (fromPath[id]) {
          next[id] = true;
        }
      }
      return next;
    });
  }, [pathname]);

  const toggleGroup = useCallback((groupId: string) => {
    setExpanded((prev) => ({
      ...prev,
      [groupId]: !prev[groupId],
    }));
  }, []);

  return (
    <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
      <div className="flex flex-col flex-grow overflow-hidden bg-white dark:bg-neutral-800 border-r border-neutral-200 dark:border-neutral-700">
        {/* Logo */}
        <div className="flex items-center h-16 flex-shrink-0 px-4 border-b border-neutral-200 dark:border-neutral-700">
          <span className="text-xl font-bold text-primary-600">DCS</span>
          <span className="ml-2 text-sm text-neutral-500">v0.2.0</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 min-h-0 px-2 py-4 overflow-y-auto">
          <div className="space-y-1">
            {navigationGroups.map((group) => {
              const isOpen = expanded[group.id] ?? false;
              const GroupIcon = group.icon;
              return (
                <div key={group.id} className="rounded-md">
                  <button
                    type="button"
                    onClick={() => toggleGroup(group.id)}
                    className="flex w-full items-center gap-2 px-2 py-2 text-left rounded-md text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-700/80 transition-colors"
                  >
                    {isOpen ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-neutral-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-neutral-400" />
                    )}
                    <GroupIcon className="h-4 w-4 shrink-0 text-neutral-400" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                      {group.label}
                    </span>
                  </button>
                  {isOpen && (
                    <div className="mt-1 space-y-0.5 pl-2">
                      {group.items.map((item) => {
                        const isActive = pathname.startsWith(item.href);
                        const ItemIcon = item.icon;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                              'flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                              isActive
                                ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400'
                                : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-700'
                            )}
                          >
                            <ItemIcon
                              className={cn(
                                'mr-3 h-5 w-5 shrink-0',
                                isActive
                                  ? 'text-primary-600 dark:text-primary-400'
                                  : 'text-neutral-400'
                              )}
                            />
                            {item.name}
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </nav>

        {/* User Section */}
        <div className="flex-shrink-0 p-4 border-t border-neutral-200 dark:border-neutral-700">
          <div className="flex flex-col gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">
                {user?.email ?? '—'}
              </p>
              <p className="text-xs text-neutral-500 truncate mt-0.5">
                {(() => {
                  // Show the most privileged label first so an Owner who
                  // hasn't been assigned an explicit role still reads as
                  // "Owner" instead of falling through to "User".
                  const roleLabels = user?.roles ?? [];
                  if (user?.isMaster && !user?.actingAsMaster) return 'Master';
                  if (user?.isOwner) {
                    return roleLabels.length
                      ? `Owner · ${roleLabels.join(', ')}`
                      : 'Owner';
                  }
                  return roleLabels.join(', ') || 'User';
                })()}
              </p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-neutral-200 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-3 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-200 hover:bg-neutral-50 dark:hover:bg-neutral-700"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
