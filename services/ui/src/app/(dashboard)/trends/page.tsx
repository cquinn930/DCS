'use client';

import { useState, useEffect } from 'react';
import { TrendingUp, BarChart3, Scale, DollarSign } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { useAuthStore } from '@/stores/auth';

const API = '/api/v1/trends';

type TrendData = { labels: string[]; [key: string]: number[] | string[] };
type SummaryData = { current_year: number; previous_year: number; accounts: { current: number; previous: number; change_pct: number }; payments: { current: number; previous: number; change_pct: number } };

export default function TrendsPage() {
  const { accessToken } = useAuthStore();
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [inventory, setInventory] = useState<TrendData | null>(null);
  const [payments, setPayments] = useState<TrendData | null>(null);
  const [legal, setLegal] = useState<TrendData | null>(null);
  const [years, setYears] = useState(3);

  useEffect(() => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

    const fetchData = async () => {
      try {
        const [sumRes, invRes, payRes, legRes] = await Promise.all([
          fetch(`${API}/summary`, { headers }),
          fetch(`${API}/inventory?years=${years}`, { headers }),
          fetch(`${API}/payments?years=${years}`, { headers }),
          fetch(`${API}/legal?years=${years}`, { headers }),
        ]);
        if (sumRes.ok) setSummary(await sumRes.json());
        if (invRes.ok) setInventory(await invRes.json());
        if (payRes.ok) setPayments(await payRes.json());
        if (legRes.ok) setLegal(await legRes.json());
      } catch {}
    };
    fetchData();
  }, [accessToken, years]);

  const ChangeIndicator = ({ value }: { value: number }) => (
    <span className={`text-sm font-semibold ${value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
      {value >= 0 ? '+' : ''}{value}%
    </span>
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Trends & Analytics" subtitle="Year-over-year performance comparisons">
        <select value={years} onChange={e => setYears(parseInt(e.target.value))} className="rounded-lg border px-3 py-2 text-sm">
          <option value={2}>Last 2 years</option>
          <option value={3}>Last 3 years</option>
          <option value={5}>Last 5 years</option>
          <option value={10}>Last 10 years</option>
        </select>
      </PageHeader>

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center justify-between mb-2"><span className="text-sm text-gray-500">New Accounts ({summary.current_year})</span><TrendingUp className="h-5 w-5 text-gray-400" /></div>
            <p className="text-2xl font-bold">{summary.accounts.current.toLocaleString()}</p>
            <div className="flex items-center gap-2 mt-1"><ChangeIndicator value={summary.accounts.change_pct} /><span className="text-xs text-gray-400">vs {summary.previous_year}</span></div>
          </div>
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center justify-between mb-2"><span className="text-sm text-gray-500">Previous Year Accounts</span><BarChart3 className="h-5 w-5 text-gray-400" /></div>
            <p className="text-2xl font-bold">{summary.accounts.previous.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center justify-between mb-2"><span className="text-sm text-gray-500">Collections ({summary.current_year})</span><DollarSign className="h-5 w-5 text-gray-400" /></div>
            <p className="text-2xl font-bold">${summary.payments.current.toLocaleString()}</p>
            <div className="flex items-center gap-2 mt-1"><ChangeIndicator value={summary.payments.change_pct} /><span className="text-xs text-gray-400">vs {summary.previous_year}</span></div>
          </div>
          <div className="bg-white rounded-xl border p-5">
            <div className="flex items-center justify-between mb-2"><span className="text-sm text-gray-500">Previous Year Collections</span><DollarSign className="h-5 w-5 text-gray-400" /></div>
            <p className="text-2xl font-bold">${summary.payments.previous.toLocaleString()}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {inventory && (
          <div className="bg-white rounded-xl border p-5">
            <h3 className="font-semibold mb-4">Inventory Trends</h3>
            <div className="space-y-2">
              {(inventory.labels as string[]).map((label, i) => (
                <div key={label} className="flex items-center justify-between py-2 border-b last:border-0">
                  <span className="font-medium">{label}</span>
                  <span className="text-sm">{((inventory.new_accounts as number[]) || [])[i]?.toLocaleString() ?? 0} new accounts</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {payments && (
          <div className="bg-white rounded-xl border p-5">
            <h3 className="font-semibold mb-4">Payment Trends</h3>
            <div className="space-y-2">
              {(payments.labels as string[]).map((label, i) => (
                <div key={label} className="flex items-center justify-between py-2 border-b last:border-0">
                  <span className="font-medium">{label}</span>
                  <div className="text-right">
                    <span className="text-sm font-semibold">${((payments.total_collected as number[]) || [])[i]?.toLocaleString() ?? 0}</span>
                    <span className="text-xs text-gray-400 ml-2">({((payments.payment_count as number[]) || [])[i]?.toLocaleString() ?? 0} payments)</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {legal && (
          <div className="bg-white rounded-xl border p-5">
            <h3 className="font-semibold mb-4">Legal Trends</h3>
            <div className="space-y-2">
              {(legal.labels as string[]).map((label, i) => (
                <div key={label} className="flex items-center justify-between py-2 border-b last:border-0">
                  <span className="font-medium">{label}</span>
                  <span className="text-sm">{((legal.cases_filed as number[]) || [])[i]?.toLocaleString() ?? 0} cases filed</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
