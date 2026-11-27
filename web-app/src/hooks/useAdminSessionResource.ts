'use client';

import { useCallback, useEffect, useState } from 'react';

type ResourceState<T> = { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: T };

export function useAdminSessionResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((data) => {
      if (!controller.signal.aborted) setState({ status: 'ready', data });
    }).catch(() => {
      if (!controller.signal.aborted) setState({ status: 'error' });
    });
    return () => controller.abort();
  }, [load, attempt]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((count) => count + 1);
  }, []);
  return { state, retry };
}
