'use client';

import { useState, useCallback } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { PageHeader } from '@/components/shared/page-header';
import { SearchBar } from '@/components/shared/search-bar';
import { DataTable } from '@/components/shared/data-table';
import { FormDrawer, FormField } from '@/components/shared/form-drawer';
import { DetailPanel, FieldGroup, FieldGrid } from '@/components/shared/detail-panel';
import { StatusBadge } from '@/components/shared/status-badge';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { useApiList, useApiDetail, useApiMutation } from '@/hooks/useApi';
import { apiClient } from '@/lib/api';
import useSWR from 'swr';

const API_PATH = '/api/v1/scripts';

interface Script {
  id: string;
  name: string;
  description: string;
  language: string;
  code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
}

interface ScriptExecution {
  id: string;
  script_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  output?: string;
  error?: string;
}

interface BuiltinFunction {
  name: string;
  description: string;
  parameters: string;
  returns: string;
}

export default function ScriptingPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const [editData, setEditData] = useState<Script | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const [showBuiltins, setShowBuiltins] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; errors?: string[] } | null>(null);

  const { data: scripts, total, isLoading, mutate } = useApiList<Script>(API_PATH, {
    skip: page * pageSize,
    limit: pageSize,
    search,
  });

  const { data: detail, mutate: mutateDetail } = useApiDetail<Script>(API_PATH, selectedId);

  const { trigger: createScript, isMutating: isCreating } = useApiMutation<any, Script>('POST', API_PATH);
  const { trigger: updateScript, isMutating: isUpdating } = useApiMutation<any, Script>('PATCH', API_PATH);
  const { trigger: deleteScript } = useApiMutation('DELETE', API_PATH);

  const [form, setForm] = useState({
    name: '',
    description: '',
    language: 'dcs_script',
    code: '',
    is_active: true,
  });

  const { data: builtins } = useSWR<BuiltinFunction[]>(
    showBuiltins ? `${API_PATH}/builtins/functions` : null,
    async (url: string) => {
      const res = await apiClient.get<any>(url);
      return Array.isArray(res.data) ? res.data : res.data?.items || [];
    }
  );

  const executionsPath = selectedId ? `${API_PATH}/${selectedId}/executions` : null;
  const { data: executions } = useApiList<ScriptExecution>(executionsPath);

  const columns: ColumnDef<Script>[] = [
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'description', header: 'Description', cell: ({ row }) => (row.original.description || '—').slice(0, 60) },
    { accessorKey: 'language', header: 'Language' },
    {
      accessorKey: 'is_active',
      header: 'Active',
      cell: ({ row }) => <StatusBadge status={row.original.is_active ? 'active' : 'inactive'} />,
    },
    {
      accessorKey: 'last_run_at',
      header: 'Last Run',
      cell: ({ row }) => row.original.last_run_at ? new Date(row.original.last_run_at).toLocaleDateString() : '—',
    },
  ];

  const resetForm = useCallback((s?: Script) => {
    if (s) {
      setForm({ name: s.name, description: s.description, language: s.language, code: s.code, is_active: s.is_active });
    } else {
      setForm({ name: '', description: '', language: 'dcs_script', code: '', is_active: true });
    }
  }, []);

  const handleCreate = async () => {
    await createScript(form);
    mutate();
    setShowCreate(false);
    resetForm();
  };

  const handleEdit = async () => {
    if (!editData) return;
    await updateScript(form, editData.id);
    mutate();
    mutateDetail();
    setEditData(null);
    resetForm();
  };

  const handleDelete = async () => {
    if (!detail) return;
    await deleteScript(undefined, detail.id);
    mutate();
    setSelectedId(undefined);
    setShowDelete(false);
  };

  const handleValidate = async () => {
    if (!detail) return;
    try {
      const res = await apiClient.post<any>(`${API_PATH}/validate`, { code: detail.code });
      setValidationResult(res.data);
    } catch (e: any) {
      setValidationResult({ valid: false, errors: [e.message || 'Validation failed'] });
    }
  };

  const handleRun = async () => {
    if (!detail) return;
    await apiClient.post(`${API_PATH}/${detail.id}/run`);
    mutateDetail();
  };

  if (selectedId && detail) {
    return (
      <div className="space-y-6">
        <DetailPanel
          title={detail.name}
          subtitle={detail.description}
          onClose={() => { setSelectedId(undefined); setValidationResult(null); }}
          onEdit={() => { resetForm(detail); setEditData(detail); }}
          onDelete={() => setShowDelete(true)}
        >
          <FieldGrid cols={3}>
            <FieldGroup label="Language">{detail.language}</FieldGroup>
            <FieldGroup label="Status"><StatusBadge status={detail.is_active ? 'active' : 'inactive'} /></FieldGroup>
            <FieldGroup label="Last Run">{detail.last_run_at ? new Date(detail.last_run_at).toLocaleString() : 'Never'}</FieldGroup>
          </FieldGrid>

          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">Code</h3>
              <div className="flex gap-2">
                <button onClick={handleValidate} className="px-3 py-1 text-xs rounded bg-blue-100 text-blue-700 hover:bg-blue-200">
                  Validate
                </button>
                <button onClick={handleRun} className="px-3 py-1 text-xs rounded bg-green-100 text-green-700 hover:bg-green-200">
                  Run
                </button>
              </div>
            </div>
            <pre className="p-4 rounded-lg bg-neutral-900 text-green-400 text-sm font-mono overflow-auto max-h-96 whitespace-pre-wrap">
              {detail.code}
            </pre>
          </div>

          {validationResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${validationResult.valid ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
              {validationResult.valid ? 'Script is valid.' : (
                <div>
                  <p className="font-medium">Validation errors:</p>
                  <ul className="list-disc list-inside mt-1">
                    {validationResult.errors?.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {executions && executions.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-2">Executions</h3>
              <div className="space-y-2">
                {executions.map((ex) => (
                  <div key={ex.id} className="p-3 rounded border bg-white dark:bg-neutral-800 text-sm">
                    <div className="flex items-center justify-between">
                      <StatusBadge status={ex.status} />
                      <span className="text-xs text-neutral-500">{new Date(ex.started_at).toLocaleString()}</span>
                    </div>
                    {ex.output && <pre className="mt-2 text-xs text-neutral-600 dark:text-neutral-400 whitespace-pre-wrap">{ex.output}</pre>}
                    {ex.error && <pre className="mt-2 text-xs text-red-600 whitespace-pre-wrap">{ex.error}</pre>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </DetailPanel>

        <div className="mt-6">
          <button
            onClick={() => setShowBuiltins(!showBuiltins)}
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            {showBuiltins ? 'Hide' : 'Show'} Built-in Functions Reference
          </button>
          {showBuiltins && builtins && (
            <div className="mt-3 border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-neutral-50 dark:bg-neutral-700">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Function</th>
                    <th className="px-4 py-2 text-left font-medium">Parameters</th>
                    <th className="px-4 py-2 text-left font-medium">Returns</th>
                    <th className="px-4 py-2 text-left font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {builtins.map((fn) => (
                    <tr key={fn.name}>
                      <td className="px-4 py-2 font-mono text-primary-600">{fn.name}</td>
                      <td className="px-4 py-2 font-mono text-xs">{fn.parameters}</td>
                      <td className="px-4 py-2 font-mono text-xs">{fn.returns}</td>
                      <td className="px-4 py-2 text-neutral-600 dark:text-neutral-400">{fn.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <ConfirmDialog
          open={showDelete}
          onClose={() => setShowDelete(false)}
          onConfirm={handleDelete}
          title="Delete Script"
          message={`Delete "${detail.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
        />

        <FormDrawer
          open={!!editData}
          onClose={() => { setEditData(null); resetForm(); }}
          title="Edit Script"
          onSubmit={handleEdit}
          isSubmitting={isUpdating}
        >
          <FormField label="Name" required>
            <input className="w-full rounded border px-3 py-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </FormField>
          <FormField label="Description">
            <input className="w-full rounded border px-3 py-2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </FormField>
          <FormField label="Language">
            <input className="w-full rounded border px-3 py-2" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
          </FormField>
          <FormField label="Code" required>
            <textarea className="w-full rounded border px-3 py-2 font-mono text-sm h-64" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </FormField>
          <FormField label="Active">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <span className="text-sm">Active</span>
            </label>
          </FormField>
        </FormDrawer>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scripting"
        subtitle="Custom DCS scripts and automation logic"
        actions={
          <button
            onClick={() => { resetForm(); setShowCreate(true); }}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            New Script
          </button>
        }
      />

      <SearchBar value={search} onChange={setSearch} placeholder="Search scripts..." />

      <DataTable
        columns={columns}
        data={scripts || []}
        isLoading={isLoading}
        onRowClick={(row) => setSelectedId(row.id)}
        pageCount={Math.ceil((total || 0) / pageSize)}
        pageIndex={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
      />

      <FormDrawer
        open={showCreate}
        onClose={() => { setShowCreate(false); resetForm(); }}
        title="New Script"
        onSubmit={handleCreate}
        isSubmitting={isCreating}
      >
        <FormField label="Name" required>
          <input className="w-full rounded border px-3 py-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <FormField label="Description">
          <input className="w-full rounded border px-3 py-2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </FormField>
        <FormField label="Language">
          <input className="w-full rounded border px-3 py-2" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
        </FormField>
        <FormField label="Code" required>
          <textarea className="w-full rounded border px-3 py-2 font-mono text-sm h-64" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="# Write your DCS script here..." />
        </FormField>
        <FormField label="Active">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <span className="text-sm">Active</span>
          </label>
        </FormField>
      </FormDrawer>
    </div>
  );
}
