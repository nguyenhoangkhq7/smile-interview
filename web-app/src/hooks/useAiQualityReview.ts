'use client';

import { useEffect, useRef, useState } from 'react';
import type { AiQualityReview } from '@/components/features/admin/sessions/types';
import { adminInterviews } from '@/services/adminInterviews';

export function useAiQualityReview(sessionId: string) {
  const [review, setReview] = useState<AiQualityReview>();
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const request = useRef<AbortController>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function run() {
    request.current?.abort();
    const active = new AbortController();
    request.current = active;
    setRunning(true);
    setFailed(false);
    try {
      const result = await adminInterviews.quality(sessionId, active.signal);
      if (!active.signal.aborted) setReview(result);
    } catch {
      if (!active.signal.aborted) setFailed(true);
    } finally {
      if (!active.signal.aborted) setRunning(false);
    }
  }

  return { review, running, failed, run };
}
