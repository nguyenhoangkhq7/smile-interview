'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { AnswerRequest, ConversationAction, ConversationRequest, EvidenceSession, InterviewConfig, conversationPhase, evidenceInterview, interviewError } from '@/services/evidenceInterview';

const EXPIRY_RETRY_DELAY_MS = 5000;

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
  const conversationRetry = useRef<ConversationRequest | null>(null);

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
  const converse = useCallback((action: ConversationAction, introduction = '') => run(async () => {
    if (!session?.conversation) throw new Error('Chưa có lượt hội thoại.');
    const previous = conversationRetry.current;
    const messageId = session.conversation.message.message_id;
    if (!previous || previous.action !== action || previous.introduction !== introduction
        || previous.expected_state_version !== session.state_version || previous.message_id !== messageId) {
      conversationRetry.current = { request_id: crypto.randomUUID(), message_id: messageId,
        expected_state_version: session.state_version, action, introduction };
    }
    const next = await evidenceInterview.converse(id, conversationRetry.current!);
    conversationRetry.current = null; setAnswer('');
    return next;
  }), [id, run, session]);
  const submit = (response = answer) => conversationPhase(session) === 'SELF_INTRODUCTION'
    ? converse('SUBMIT_INTRODUCTION', response) : run(async () => {
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
    let next: EvidenceSession;
    try { next = await evidenceInterview.stop(session, stopRequest.current.id); }
    catch (cause) {
      if (!axios.isAxiosError(cause) || cause.response?.status !== 409) throw cause;
      // Another tab or an answer may have committed first. Retry expiry with its version.
      const current = await evidenceInterview.get(id);
      if (!current) throw cause;
      next = current;
    }
    stopRequest.current = null;
    return next;
  }), [id, session, run]);

  useEffect(() => {
    if (!session || session.is_finished || readOnly) return;
    let nextAttemptAt = 0;
    const tick = () => {
      const now = Date.now();
      const phase = conversationPhase(session);
      const prelude = phase === 'OPENING' || phase === 'SELF_INTRODUCTION';
      const deadline = prelude ? session.conversation!.expires_at : session.deadline_at;
      const remaining = Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000));
      setSecondsLeft(remaining);
      // Earlier grading errors must never prevent expiry. Serialize with answer submission
      // and retry transient stop failures using the same idempotent request ID.
      if (!remaining && !inFlight.current && now >= nextAttemptAt) {
        nextAttemptAt = now + EXPIRY_RETRY_DELAY_MS;
        if (prelude) void converse('SKIP_INTRODUCTION');
        else void stop();
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    window.addEventListener('focus', tick);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', tick);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [session, stop, converse, readOnly]);

  return { session, metadata, loading, legacy, busy, error, answer, setAnswer, secondsLeft, reload, start, submit, stop, converse };
}
