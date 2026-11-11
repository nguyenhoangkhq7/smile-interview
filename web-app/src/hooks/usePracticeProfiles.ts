import { useCallback, useEffect, useState } from 'react';
import { applicationProfiles } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import { studyPlans } from '@/services/studyPlans';

type ProfileRequestState<T> =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: T };

export function usePracticeRequest<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ProfileRequestState<T>>({ status: 'loading' });
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    void load(signal).then(
      (data) => { if (!signal.aborted) setState({ status: 'ready', data }); },
      (error: unknown) => {
        if (!signal.aborted) setState({ status: 'error', message: interviewError(error) });
      },
    );

    return () => controller.abort();
  }, [load, revision]);

  function retry() {
    setState({ status: 'loading' });
    setRevision((current) => current + 1);
  }

  return { state, retry };
}

export function usePracticeProfiles() {
  return usePracticeRequest(applicationProfiles.list);
}

export function usePracticePlanDetail(profileId: string) {
  const load = useCallback(async (signal: AbortSignal) => {
    const [profile, plan] = await Promise.all([applicationProfiles.get(profileId, signal), studyPlans.get(profileId, signal)]);
    return { profile, plan };
  }, [profileId]);
  return usePracticeRequest(load);
}

export function usePracticeKnowledgeGaps(profileId: string) {
  const load = useCallback((signal: AbortSignal) => studyPlans.gaps(profileId, signal), [profileId]);
  return usePracticeRequest(load);
}
