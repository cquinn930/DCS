'use client';

import { useState } from 'react';
import { PageHeader } from '@/components/shared/page-header';
import { FormField } from '@/components/shared/form-drawer';
import { useApiMutation } from '@/hooks/useApi';
import { useAuthStore } from '@/stores/auth';

type FieldChange = {
  field: string;
  from_value: unknown;
  to_value: unknown;
};

type TargetPreview = {
  consumer_id: string;
  changes: FieldChange[];
};

type PreviewResponse = {
  source_consumer_id: string;
  linked_targets: number;
  targets: TargetPreview[];
};

type ApplyResponse = {
  updated_consumer_ids: string[];
  fields_applied: string[];
  applied_at: string;
};

const API = '/api/v1/demographics';

export default function DemographicsPage() {
  const { user } = useAuthStore();
  const [consumerId, setConsumerId] = useState('');
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [applyResult, setApplyResult] = useState<ApplyResponse | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  const { trigger: previewSync, isMutating: previewing } = useApiMutation<
    { source_consumer_id: string },
    PreviewResponse
  >('POST', `${API}/preview`);
  const { trigger: applySync, isMutating: applying } = useApiMutation<
    { source_consumer_id: string; confirmed?: boolean },
    ApplyResponse
  >('POST', `${API}/apply`);

  async function onPreview() {
    setApplyResult(null);
    setApplyError(null);
    if (!consumerId.trim()) return;
    const res = await previewSync({
      source_consumer_id: consumerId.trim(),
    });
    setPreview(res);
  }

  async function onApply() {
    setApplyError(null);
    if (!consumerId.trim()) return;
    try {
      const res = await applySync({
        source_consumer_id: consumerId.trim(),
        confirmed: true,
      });
      setApplyResult(res);
      setPreview(null);
    } catch (e: unknown) {
      const msg =
        e &&
        typeof e === 'object' &&
        'response' in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      setApplyError(typeof msg === 'string' ? msg : 'Apply failed');
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Demographics sync"
        subtitle={
          user
            ? `Preview and propagate linked consumer fields · ${user.email}`
            : 'Align demographic fields across linked consumer records'
        }
      />

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-base font-semibold text-foreground">
          Preview &amp; apply
        </h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Enter a source consumer ID. Preview shows linked consumers that would
          change; apply copies allowed fields from the source to those targets.
        </p>
        <div className="mt-4 max-w-xl space-y-4">
          <FormField label="Consumer ID" required>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              value={consumerId}
              onChange={(e) => setConsumerId(e.target.value)}
              placeholder="Source consumer UUID"
            />
          </FormField>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={previewing || !consumerId.trim()}
              onClick={onPreview}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {previewing ? 'Previewing…' : 'Preview sync'}
            </button>
            <button
              type="button"
              disabled={applying || !consumerId.trim()}
              onClick={onApply}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
            >
              {applying ? 'Applying…' : 'Apply sync'}
            </button>
          </div>
        </div>
      </section>

      {preview && (
        <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h3 className="text-base font-semibold">Preview results</h3>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
            Linked targets: {preview.linked_targets}. Showing consumers with
            field changes only.
          </p>
          <ul className="mt-4 space-y-4">
            {preview.targets.length === 0 ? (
              <li className="text-sm text-neutral-500">
                No changes — all linked consumers already match, or none linked.
              </li>
            ) : (
              preview.targets.map((t) => (
                <li
                  key={t.consumer_id}
                  className="rounded-md border border-border p-4"
                >
                  <p className="font-mono text-sm font-medium">
                    Consumer {t.consumer_id}
                  </p>
                  <table className="mt-2 w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase text-neutral-500">
                        <th className="py-1">Field</th>
                        <th className="py-1">From</th>
                        <th className="py-1">To</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.changes.map((c) => (
                        <tr key={c.field} className="border-t border-border">
                          <td className="py-2 font-mono text-xs">{c.field}</td>
                          <td className="py-2 text-xs text-neutral-600">
                            {formatVal(c.from_value)}
                          </td>
                          <td className="py-2 text-xs">{formatVal(c.to_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      {applyError && (
        <p className="rounded-md border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-800 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-500">
          {applyError}
        </p>
      )}

      {applyResult && (
        <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
          <h3 className="text-base font-semibold text-foreground">
            Apply results
          </h3>
          <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
            Updated {applyResult.updated_consumer_ids.length} consumer(s) at{' '}
            {new Date(applyResult.applied_at).toLocaleString()}.
          </p>
          <p className="mt-2 text-sm">
            Fields applied: {applyResult.fields_applied.join(', ') || '—'}
          </p>
          <ul className="mt-3 max-h-48 list-inside list-disc overflow-y-auto font-mono text-xs">
            {applyResult.updated_consumer_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function formatVal(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}
