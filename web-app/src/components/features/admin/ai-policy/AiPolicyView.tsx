'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  adminAiPolicy, aiPolicyError, unchangedCredentials,
  type AiConfiguration, type AiSettings,
} from '@/services/adminAiPolicy';
import { useAiServiceHealth } from '@/hooks/useAiServiceHealth';
import AdaptivePolicyForm from './AdaptivePolicyForm';
import AiModelsForm from './AiModelsForm';
import AiPolicyHeader from './AiPolicyHeader';
import ServiceHealthGrid from './ServiceHealthGrid';
import themeStyles from '../layout/admin-theme.module.css';

export default function AiPolicyView() {
  const [configuration, setConfiguration] = useState<AiConfiguration>();
  const [draft, setDraft] = useState<AiSettings>();
  const [credentials, setCredentials] = useState(unchangedCredentials);
  const health = useAiServiceHealth();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ text: string; error?: boolean }>();

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const current = await adminAiPolicy.configuration(signal);
      setConfiguration(current);
      setDraft(current.settings);
      setCredentials(unchangedCredentials);
      return true;
    } catch (error) {
      if (!signal?.aborted) setNotice({ text: aiPolicyError(error), error: true });
      return false;
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const request = new AbortController();
    void load(request.signal);
    return () => request.abort();
  }, [load]);

  async function update(reset: boolean) {
    if (!configuration || !draft) return;
    if (reset && !window.confirm('Khôi phục model và chính sách mặc định của môi trường?')) return;
    setBusy(true);
    setNotice(undefined);
    try {
      if (reset) await adminAiPolicy.reset(configuration.revision);
      else await adminAiPolicy.save(configuration.revision, draft, credentials);
      setCredentials(unchangedCredentials);
      const refreshed = await load();
      if (refreshed) {
        setNotice({ text: reset ? 'Đã khôi phục model và chính sách mặc định.' : 'Đã lưu cấu hình AI.' });
      } else {
        setConfiguration(undefined);
        setNotice({ text: 'Đã lưu cấu hình. Tải lại để xem phiên bản mới.', error: true });
      }
      void health.run('status');
    } catch (error) {
      setNotice({ text: aiPolicyError(error), error: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-8 pb-8">
      <AiPolicyHeader isMeasuring={health.pending === 'measure'} isRefreshing={health.pending === 'status'}
        disabled={health.pending !== null || busy} onMeasure={() => void health.run('measure')}
        onRefresh={() => void health.run('status')} />
      <ServiceHealthGrid services={health.checks} isCheckingHealth={health.pending !== null} measuredAt={health.measuredAt} />
      {health.error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{health.error}</p>}
      {notice && <div role={notice.error ? 'alert' : 'status'}
        className={notice.error ? 'text-sm text-red-700 dark:text-red-300' : 'text-sm text-green-800 dark:text-green-300'}>
        {notice.text}
        {notice.error && <button type="button" className="ml-3 underline" disabled={loading || busy}
          onClick={() => { setNotice(undefined); void load(); }}>Tải lại cấu hình</button>}
      </div>}
      {loading && <p role="status" className="text-sm">Đang tải cấu hình…</p>}
      {draft && configuration && <AdaptivePolicyForm config={draft.policy}
        parameters={configuration.skillGapParameters}
        isSaving={busy || loading}
        models={<div className={themeStyles.surface}>
          <AiModelsForm settings={configuration} models={draft.models} credentials={credentials}
            onModels={(models) => setDraft({ ...draft, models })} onCredentials={setCredentials} />
        </div>}
        onUpdateField={(key, value) => setDraft({ ...draft, policy: { ...draft.policy, [key]: value } })}
        onResetDefault={() => void update(true)}
        onCancelChanges={() => { setDraft(configuration.settings); setCredentials(unchangedCredentials); setNotice(undefined); }}
        onSavePolicy={() => void update(false)}
      />}
    </div>
  );
}
