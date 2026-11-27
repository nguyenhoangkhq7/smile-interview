'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { adminAiPolicy, aiHealthError, type AiServiceCheck } from '@/services/adminAiPolicy';

type RequestMode = 'status' | 'measure';

export function useAiServiceHealth() {
  const [checks, setChecks] = useState<AiServiceCheck[]>([]);
  const [pending, setPending] = useState<RequestMode | null>('status');
  const [measuredAt, setMeasuredAt] = useState<Date>();
  const [error, setError] = useState('');
  const active = useRef<AbortController | null>(null);

  const run = useCallback(async (mode: RequestMode) => {
    active.current?.abort();
    const request = new AbortController();
    active.current = request;
    setPending(mode);
    setError('');
    try {
      const load = mode === 'measure' ? adminAiPolicy.measureHealth : adminAiPolicy.health;
      const result = await load(request.signal);
      if (request.signal.aborted) return;
      setChecks(result);
      setMeasuredAt(mode === 'measure' ? new Date() : undefined);
    } catch (error) {
      if (request.signal.aborted) return;
      if (mode === 'status') {
        setChecks([]);
        setMeasuredAt(undefined);
      }
      setError(aiHealthError(error, mode === 'measure'));
    } finally {
      if (!request.signal.aborted) setPending(null);
    }
  }, []);

  useEffect(() => {
    void run('status');
    return () => active.current?.abort();
  }, [run]);

  return { checks, pending, measuredAt, error, run };
}
