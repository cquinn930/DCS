'use client';

import { useState } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Filter, Plus, Eye, Trash2, Play, Code } from 'lucide-react';
import { PageHeader } from '@/components/shared/page-header';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGrid, FieldGroup } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';

const API = '/api/v1/conditions';

type ConditionRow = { id: string; code: string; name: string; category: string; condition_script: string | null; is_active: boolean; version: number; created_at: string };

const CATEGORY_MAP: Record<string, string> = {
  workflow: 'bg-blue-100 text-blue-700',
  document: 'bg-purple-100 text-purple-700',
  flash_message: 'bg-orange-100 text-orange-700',
  review: 'bg-green-100 text-green-700',
  automation: 'bg-cyan-100 text-cyan-700',
  report: 'bg-yellow-100 text-yellow-700',
  general: 'bg-gray-100 text-gray-700',
};

const OPERATORS = [
  { value: 'eq', label: 'Equals' },
  { value: 'neq', label: 'Not Equals' },
  { value: 'gt', label: 'Greater Than' },
  { value: 'gte', label: 'Greater or Equal' },
  { value: 'lt', label: 'Less Than' },
  { value: 'lte', label: 'Less or Equal' },
  { value: 'contains', label: 'Contains' },
  { value: 'is_null', label: 'Is Empty' },
  { value: 'not_null', label: 'Is Not Empty' },
];

const FIELDS = [
  'account.balance', 'account.status', 'account.days_delinquent', 'account.jurisdiction',
  'consumer.state', 'consumer.zip_code', 'consumer.age',
  'payment.amount', 'payment.method',
];

export default function ConditionsPage() {
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [rules, setRules] = useState([{ field: 'account.balance', operator: 'gt', value: '' }]);
  const [ruleOperator, setRuleOperator] = useState('AND');
  const [form, setForm] = useState({ code: '', name: '', description: '', category: 'general' });

  const { data, total, isLoading, mutate } = useApiList<ConditionRow>(API, { page: pageIndex + 1, page_size: pageSize });
  const { data: detail } = useApiDetail<ConditionRow>(API, selectedId ?? undefined);
  const { trigger: create } = useApiMutation('POST', API);
  const { trigger: remove } = useApiMutation('DELETE', API);
  const { trigger: convert } = useApiMutation('POST', API);

  const columns: ColumnDef<ConditionRow>[] = [
    { accessorKey: 'code', header: 'Code' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'category', header: 'Category', cell: ({ row }) => <StatusBadge status={row.original.category} colorMap={CATEGORY_MAP} /> },
    { accessorKey: 'is_active', header: 'Active', cell: ({ row }) => row.original.is_active ? 'Yes' : 'No' },
    { accessorKey: 'version', header: 'Ver.' },
    {
      id: 'actions', header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <button onClick={() => setSelectedId(row.original.id)} className="p-1 hover:bg-gray-100 rounded"><Eye className="h-4 w-4" /></button>
          <button onClick={() => { setSelectedId(row.original.id); setDeleteOpen(true); }} className="p-1 hover:bg-red-100 rounded text-red-600"><Trash2 className="h-4 w-4" /></button>
        </div>
      ),
    },
  ];

  const addRule = () => setRules([...rules, { field: 'account.balance', operator: 'gt', value: '' }]);
  const removeRule = (i: number) => setRules(rules.filter((_, idx) => idx !== i));
  const updateRule = (i: number, key: string, val: string) => { const r = [...rules]; (r[i] as Record<string, string>)[key] = val; setRules(r); };

  const handleCreate = async () => {
    const condJson = { operator: ruleOperator, rules: rules.map(r => ({ field: r.field, operator: r.operator, value: r.value })) };
    await create({ ...form, condition_json: condJson });
    setDrawerOpen(false);
    setForm({ code: '', name: '', description: '', category: 'general' });
    setRules([{ field: 'account.balance', operator: 'gt', value: '' }]);
    mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Condition Editor" subtitle="Visual condition builder for workflows, automation, and reports">
        <button onClick={() => setDrawerOpen(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"><Plus className="h-4 w-4" /> New Condition</button>
      </PageHeader>

      <DataTable columns={columns} data={data ?? []} isLoading={isLoading} pageIndex={pageIndex} pageSize={pageSize} pageCount={Math.ceil((total ?? 0) / pageSize)} onPageChange={setPageIndex} />

      {selectedId && detail && (
        <DetailPanel title={detail.name} onClose={() => setSelectedId(null)}>
          <FieldGroup label="Condition Details">
            <FieldGrid>
              <div><span className="text-xs text-gray-500">Code</span><p className="text-sm font-mono">{detail.code}</p></div>
              <div><span className="text-xs text-gray-500">Category</span><p className="text-sm"><StatusBadge status={detail.category} colorMap={CATEGORY_MAP} /></p></div>
              <div><span className="text-xs text-gray-500">Version</span><p className="text-sm">{detail.version}</p></div>
            </FieldGrid>
          </FieldGroup>
          {detail.condition_script && (
            <FieldGroup label="Generated Script">
              <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">{detail.condition_script}</pre>
            </FieldGroup>
          )}
        </DetailPanel>
      )}

      <FormDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="New Condition" onSubmit={handleCreate}>
        <FormField label="Code"><input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" placeholder="e.g., HIGH_BAL_NY" /></FormField>
        <FormField label="Name"><input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" /></FormField>
        <FormField label="Category"><select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="w-full rounded border px-3 py-2 text-sm"><option value="general">General</option><option value="workflow">Workflow</option><option value="document">Document</option><option value="flash_message">Flash Message</option><option value="review">Review</option><option value="automation">Automation</option><option value="report">Report</option></select></FormField>
        <FormField label="Description"><textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={2} /></FormField>

        <div className="border-t pt-4 mt-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-sm">Rules</h4>
            <div className="flex items-center gap-2">
              <select value={ruleOperator} onChange={e => setRuleOperator(e.target.value)} className="rounded border px-2 py-1 text-xs"><option value="AND">Match ALL</option><option value="OR">Match ANY</option></select>
              <button type="button" onClick={addRule} className="text-xs text-blue-600 hover:text-blue-700">+ Add Rule</button>
            </div>
          </div>
          {rules.map((rule, i) => (
            <div key={i} className="flex gap-2 mb-2 items-center">
              <select value={rule.field} onChange={e => updateRule(i, 'field', e.target.value)} className="rounded border px-2 py-1.5 text-xs flex-1">
                {FIELDS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
              <select value={rule.operator} onChange={e => updateRule(i, 'operator', e.target.value)} className="rounded border px-2 py-1.5 text-xs">
                {OPERATORS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <input value={rule.value} onChange={e => updateRule(i, 'value', e.target.value)} className="rounded border px-2 py-1.5 text-xs flex-1" placeholder="Value" />
              {rules.length > 1 && <button type="button" onClick={() => removeRule(i)} className="text-red-500 text-xs hover:text-red-600">x</button>}
            </div>
          ))}
        </div>
      </FormDrawer>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={async () => { if (selectedId) { await remove(undefined, `/${selectedId}`); setSelectedId(null); setDeleteOpen(false); mutate(); } }} title="Delete Condition" message="Are you sure you want to delete this condition template?" />
    </div>
  );
}
