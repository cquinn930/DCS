'use client';

import {
  Users,
  DollarSign,
  AlertTriangle,
  CreditCard,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatsCardProps {
  title: string;
  value: string;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
  icon: 'accounts' | 'currency' | 'disputes' | 'payments';
}

const icons = {
  accounts: Users,
  currency: DollarSign,
  disputes: AlertTriangle,
  payments: CreditCard,
};

export function StatsCard({
  title,
  value,
  change,
  changeType,
  icon,
}: StatsCardProps) {
  const Icon = icons[icon];

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <div className="p-3 bg-primary-50 dark:bg-primary-900/20 rounded-lg">
            <Icon className="h-6 w-6 text-primary-600 dark:text-primary-400" />
          </div>
        </div>
        <div className="ml-4 flex-1">
          <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            {title}
          </p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-white">
            {value}
          </p>
        </div>
      </div>
      <div className="mt-4 flex items-center">
        {changeType === 'positive' ? (
          <TrendingUp className="h-4 w-4 text-success-500" />
        ) : changeType === 'negative' ? (
          <TrendingDown className="h-4 w-4 text-error-500" />
        ) : null}
        <span
          className={cn(
            'ml-1 text-sm font-medium',
            changeType === 'positive' && 'text-success-700 dark:text-success-500',
            changeType === 'negative' && 'text-error-700 dark:text-error-500',
            changeType === 'neutral' && 'text-neutral-500'
          )}
        >
          {change}
        </span>
        <span className="ml-1 text-sm text-neutral-500 dark:text-neutral-400">
          from last month
        </span>
      </div>
    </div>
  );
}
