'use client';

import { useEffect, useRef } from 'react';
import { conversationPhase } from '@/services/evidenceInterview';
import type { useEvidenceInterview } from './useEvidenceInterview';

/** Reading a greeting does not require a separate navigation step. */
export function useTextInterviewConversation(interview: ReturnType<typeof useEvidenceInterview>) {
  const { session, busy, converse } = interview;
  const phase = conversationPhase(session);
  const attempted = useRef('');
  const messageId = session?.conversation?.message.message_id;
  useEffect(() => {
    if (phase !== 'OPENING' || busy || !messageId || attempted.current === messageId) return;
    attempted.current = messageId;
    void converse('NEXT');
  }, [phase, busy, messageId, converse]);
  return { phase, introducing: phase === 'SELF_INTRODUCTION', closing: phase === 'CLOSING',
    text: phase === 'INTERVIEW' ? session?.pending_turn?.question : session?.conversation?.message.text,
    interviewer: session?.conversation?.opening.interviewer_name || 'Người phỏng vấn' };
}
