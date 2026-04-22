'use client';

import { AlertTriangle, Clock, FileText, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Alert {
  id: string;
  type: 'warning' | 'error' | 'info';
  title: string;
  description: string;
  time: string;
}

const alerts: Alert[] = [
  {
    id: '1',
    type: 'error',
    title: 'Dispute Response Overdue',
    description: '3 disputes past their 30-day response deadline',
    time: '2 hours ago',
  },
  {
    id: '2',
    type: 'warning',
    title: 'License Expiring',
    description: 'NJ collection license expires in 30 days',
    time: '1 day ago',
  },
  {
    id: '3',
    type: 'info',
    title: 'Validation Notices Due',
    description: '12 accounts require validation notices within 5 days',
    time: '3 days ago',
  },
];

const iconMap = {
  warning: Clock,
  error: XCircle,
  info: FileText,
};

const colorMap = {
  warning: 'text-warning-500 bg-warning-50 dark:bg-warning-500/10',
  error: 'text-error-500 bg-error-50 dark:bg-error-500/10',
  info: 'text-primary-500 bg-primary-50 dark:bg-primary-500/10',
};

export function ComplianceAlerts() {
  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
      <div className="px-6 py-4 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center">
          <AlertTriangle className="h-5 w-5 text-warning-500 mr-2" />
          <h2 className="text-lg font-medium text-neutral-900 dark:text-white">
            Compliance Alerts
          </h2>
        </div>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
          Non-legal guidance: Review with compliance team
        </p>
      </div>
      <ul className="divide-y divide-neutral-200 dark:divide-neutral-700">
        {alerts.map((alert) => {
          const Icon = iconMap[alert.type];
          return (
            <li key={alert.id} className="px-6 py-4 hover:bg-neutral-50 dark:hover:bg-neutral-700/50">
              <div className="flex items-start">
                <div className={cn('flex-shrink-0 p-2 rounded-lg', colorMap[alert.type])}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="ml-4 flex-1">
                  <p className="text-sm font-medium text-neutral-900 dark:text-white">
                    {alert.title}
                  </p>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    {alert.description}
                  </p>
                  <p className="mt-1 text-xs text-neutral-400">{alert.time}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="px-6 py-3 border-t border-neutral-200 dark:border-neutral-700">
        <a
          href="/compliance"
          className="text-sm font-medium text-primary-600 hover:text-primary-500"
        >
          View all alerts
        </a>
      </div>
    </div>
  );
}
