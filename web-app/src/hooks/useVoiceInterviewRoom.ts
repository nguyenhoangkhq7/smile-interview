'use client';

import { useEffect, useRef, useState } from 'react';
import { conversationPhase } from '@/services/evidenceInterview';
import { useEvidenceVoice } from './useEvidenceVoice';
import type { InterviewController } from '@/components/features/interview/EvidenceTextInterview';

export function useVoiceInterviewRoom(interview: InterviewController, suspended: boolean) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { session, busy } = interview;
  const phase = conversationPhase(session);
  const presenting = phase === 'OPENING' || phase === 'CLOSING';
  const videoRef = useRef<HTMLVideoElement>(null), audioRef = useRef<HTMLAudioElement>(null);
  const captionBox = useRef<HTMLDivElement>(null), questionBox = useRef<HTMLDivElement>(null);
  const voice = useEvidenceVoice({ id: session?.session_id || '', session, busy, answer: interview.answer,
    setAnswer: interview.setAnswer, submit: interview.submit, nextConversation: () => interview.converse('NEXT'),
    suspended, videoRef, audioRef });
  const previous = session?.turns.at(-1)?.answer || session?.conversation?.introduction || '';
  const caption = voice.captions || interview.answer || (!voice.listening && !voice.transcribing && !voice.retryAvailable ? previous : '');
  const turnId = session?.pending_turn?.turn_id || session?.conversation?.message.message_id;
  useEffect(() => { const box = captionBox.current; if (box) box.scrollTop = box.scrollHeight; }, [caption]);
  useEffect(() => { if (questionBox.current) questionBox.current.scrollTop = 0; }, [turnId]);
  const status = voice.starting ? 'Đang kết nối avatar…' : !voice.enabled ? 'Sẵn sàng trò chuyện'
    : voice.paused ? 'Micro đang tạm dừng' : busy ? 'Đang chuẩn bị câu hỏi tiếp theo…'
    : voice.listening ? 'Đang nghe bạn…' : voice.transcribing ? 'Đang nhận diện lời nói…'
    : voice.retryAvailable ? 'Chưa nhận diện được lời nói' : voice.speaking ? 'Người phỏng vấn đang nói'
    : voice.loadingSpeech ? 'Đang chuẩn bị giọng đọc…' : presenting ? 'Đang trò chuyện' : 'Đến lượt bạn trả lời';
  return { interview, session, phase, busy, presenting, voice, videoRef, audioRef, captionBox, questionBox,
    settingsOpen, setSettingsOpen, status, caption, sent: !voice.captions && !interview.answer && Boolean(caption),
    question: phase === 'INTERVIEW' ? session?.pending_turn?.question || '' : session?.conversation?.message.text || '',
    introduction: phase === 'INTERVIEW' ? session?.pending_turn?.introduction || '' : '',
    cannotSubmit: busy || presenting || voice.transcribing || voice.listening || voice.retryAvailable || Boolean(voice.review),
    interrupt: () => { voice.interrupt(); if (presenting) void interview.converse('NEXT'); },
    skipIntroduction: () => { setSettingsOpen(false); voice.interrupt(); void interview.converse('SKIP_INTRODUCTION'); },
    continueConversation: () => { voice.interrupt(); void interview.converse('NEXT'); },
  };
}

export type VoiceInterviewRoom = ReturnType<typeof useVoiceInterviewRoom>;
