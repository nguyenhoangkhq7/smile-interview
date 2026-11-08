'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { AnswerRequest, EvidenceSession, InterviewConfig, evidenceInterview, interviewError } from '@/services/evidenceInterview';

export function useEvidenceInterview(id: string, readOnly = false) {
  const [session, setSession] = useState<EvidenceSession | null>(null);
  const [metadata, setMetadata] = useState<SessionHistoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [legacy, setLegacy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [answer, setAnswer] = useState('');
  const [secondsLeft, setSecondsLeft] = useState(0);
  const retry = useRef<AnswerRequest | null>(null);
  const stopRequest = useRef<{ id: string; version: number } | null>(null);
  const inFlight = useRef(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const current = await evidenceInterview.get(id);
      const previous = await historyService.getSessionById(id);
      setMetadata(previous);
      setSession(current);
      setLegacy(false);
      if (!current) {
        if (!previous) throw new Error('Không tìm thấy phiên phỏng vấn.');
        setLegacy(readOnly || Boolean(previous.aiInterviewSessionId || previous.questions.length));
      }
      if (current?.pending_turn?.turn_id !== retry.current?.turn_id) retry.current = null;
    } catch (cause) { setError(interviewError(cause)); }
    finally { setLoading(false); }
  }, [id, readOnly]);

  useEffect(() => { void reload(); }, [reload]);

  const run = useCallback(async (operation: () => Promise<EvidenceSession>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError('');
    try { const next = await operation(); setSession(next); return next; }
    catch (cause) { const message = interviewError(cause); setError(message); toast.error(message); return null; }
    finally { inFlight.current = false; setBusy(false); }
  }, []);

  const start = (config: InterviewConfig) => run(() => evidenceInterview.start(id, config));
  const submit = (response = answer) => run(async () => {
    if (!session?.pending_turn || !response.trim()) throw new Error('Hãy nhập câu trả lời.');
    const previous = retry.current;
    if (!previous || previous.candidate_response !== response || previous.turn_id !== session.pending_turn.turn_id) {
      retry.current = { request_id: crypto.randomUUID(), turn_id: session.pending_turn.turn_id,
        expected_state_version: session.state_version, candidate_response: response };
    }
    const next = await evidenceInterview.answer(id, retry.current!);
    retry.current = null; setAnswer('');
    return next;
  });

  const stop = useCallback(() => run(async () => {
    if (!session) throw new Error('Phiên chưa bắt đầu.');
    if (stopRequest.current?.version !== session.state_version) {
      stopRequest.current = { id: crypto.randomUUID(), version: session.state_version };
    }
    const next = await evidenceInterview.stop(session, stopRequest.current.id);
    stopRequest.current = null;
    return next;
  }), [session, run]);

  useEffect(() => {
    if (!session || session.is_finished || readOnly) return;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((Date.parse(session.deadline_at) - Date.now()) / 1000));
      setSecondsLeft(remaining);
      if (!remaining && !inFlight.current && !error) void stop();
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [session, stop, readOnly, error]);

  return { session, metadata, loading, legacy, busy, error, answer, setAnswer, secondsLeft, reload, start, submit, stop };
}
