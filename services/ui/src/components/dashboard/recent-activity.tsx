'use client';

import { CreditCard, FileText, AlertTriangle, Scale, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Activity {
  id: string;
  type: 'payment' | 'dispute' | 'notice' | 'judgment' | 'resolved';
  description: string;
  time: string;
  amount?: string;
}

const activities: Activity[] = [
  {
    id: '1',
    type: 'payment',
    description: 'Payment received - Account #1234',
    time: '5 minutes ago',
    amount: '$450.00',
  },
  {
    id: '2',
    type: 'dispute',
    description: 'Dispute filed - Account #5678',
    time: '1 hour ago',
  },
  {
    id: '3',
    type: 'notice',
    description: 'Validation notice sent - 5 accounts',
    time: '2 hours ago',
  },
  {
    id: '4',
    type: 'resolved',
    description: 'Dispute resolved - Account #9012',
    time: '3 hours ago',
  },
  {
    id: '5',
    type: 'judgment',
    description: 'Judgment entered - Account #3456',
    time: '5 hours ago',
    amount: '$12,500.00',
  },
];

const iconMap = {
  payment: CreditCard,
  dispute: AlertTriangle,
  notice: FileText,
  judgment: Scale,
  resolved: CheckCircle,
};

const colorMap = {
  payment: 'text-success-500 bg-success-50 dark:bg-success-500/10',
  dispute: 'text-warning-500 bg-warning-50 dark:bg-warning-500/10',
  notice: 'text-primary-500 bg-primary-50 dark:bg-primary-500/10',
  judgment: 'text-neutral-500 bg-neutral-50 dark:bg-neutral-500/10',
  resolved: 'text-success-500 bg-success-50 dark:bg-success-500/10',
};

export function RecentActivity() {
  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
      <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-medium text-neutral-900 dark:text-white">
          Recent Activity
        </h2>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
          Latest actions across your accounts
        </p>
      </div>
      <ul className="divide-y divide-neutral-200 dark:divide-neutral-700">
        {activities.map((activity) => {
          const Icon = iconMap[activity.type];
          return (
            <li key={activity.id} className="px-6 py-4 hover:bg-neutral-50 dark:hover:bg-neutral-700/50">
              <div className="flex items-start">
                <div className={cn('flex-shrink-0 p-2 rounded-lg', colorMap[activity.type])}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="ml-4 flex-1">
                  <p className="text-sm text-neutral-900 dark:text-white">
                    {activity.description}
                  </p>
                  <div className="mt-1 flex items-center text-xs text-neutral-500">
                    <span>{activity.time}</span>
                    {activity.amount && (
                      <>
                        <span className="mx-2">·</span>
                        <span className="font-medium text-neutral-700 dark:text-neutral-300">
                          {activity.amount}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="px-6 py-3 border-t border-neutral-200 dark:border-neutral-700">
        <a
          href="/activity"
          className="text-sm font-medium text-primary-600 hover:text-primary-500"
        >
          View all activity
        </a>
      </div>
    </div>
  );
}
