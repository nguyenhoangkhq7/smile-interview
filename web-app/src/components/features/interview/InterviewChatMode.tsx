'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useParams } from 'next/navigation';
import { historyService, QuestionFeedback } from '@/services/historyService';
import { useAuthStore } from '@/store/authStore';
import {
  Send,
  Bot,
  User,
  Loader2,
  Play,
  CornerDownRight,
  MessageSquareDashed,
  CheckCircle2,
  Timer,
  LogOut,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

// ─── Types ────────────────────────────────────────────────────────────────────

type ChatSessionState = 'INITIALIZING' | 'AI_THINKING' | 'LISTENING' | 'FINISHED';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'candidate';
  text: string;
  time: string;
  isDeepDive?: boolean;
}

interface ChatSessionQuestion {
  question: string | { question: string };
  answer?: string;
  score?: number;
  strengths?: string;
  improvements?: string;
  suggestedAnswer?: string;
  topicTag?: string;
  isDeepDive?: boolean;
  goodAnswerSignals?: string[];
}

interface SocketInitialQuestion {
  question: string;
  good_answer_signals: string[];
  topic: string;
}

interface OrchestrationEventPayload {
  actionType?: string;
  text?: string;
  score?: number | null;
  evaluation?: string;
  [key: string]: unknown;
}

interface OrchestrationEvent {
  type: string;
  payload?: OrchestrationEventPayload;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrentTime = () =>
  new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

const formatCountdown = (secs: number) => {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const generateId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

// ─── Component ────────────────────────────────────────────────────────────────

export function InterviewChatMode() {
  const params = useParams();
  const sessionId = (params?.id as string) || '';

  // ── Local state ──────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sessionState, setSessionState] = useState<ChatSessionState>('INITIALIZING');
  const [socketConnected, setSocketConnected] = useState(false);
  const [baseQuestionIndex, setBaseQuestionIndex] = useState(0);
  const [timeLeft, setTimeLeft] = useState(900); // 15 min
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  // ── Refs ─────────────────────────────────────────────────────────────────
  const socketRef = useRef<Socket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const currentQuestionRef = useRef<string>('');
  const isFinishingRef = useRef(false);

  // ── Auto scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, sessionState]);

  // ── Countdown timer ───────────────────────────────────────────────────────
  const startTimer = useCallback(() => {
    if (timerRef.current) return;
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  // ── Finish interview ──────────────────────────────────────────────────────
  const handleFinishInterview = useCallback(async () => {
    if (isFinishingRef.current) return;
    isFinishingRef.current = true;
    setSessionState('FINISHED');
    if (timerRef.current) clearInterval(timerRef.current);

    try {
      const currentSession = await historyService.getSessionById(sessionId);
      if (currentSession) {
        currentSession.status = 'Completed';
        // NOTE: Do NOT calculate or write overallScore here.
        // The evaluate API (called below fire-and-forget) reads session_turns from DB
        // and computes the real score via LLM. Writing a 0/placeholder here would
        // overwrite that result. We only update the status field.
        await historyService.saveSession({ ...currentSession, replaceQuestions: true });

        const token = useAuthStore.getState().token;
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        fetch(`/api/sessions/${sessionId}/evaluate`, { method: 'POST', headers }).catch(() => {});
        fetch('/api/hr-realtime', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId, stage: 'COMPLETED' }),
        }).catch(() => {});
      }
    } catch (err) {
      console.error('[ChatMode] Error finishing interview:', err);
    }
  }, [sessionId]);

  // ── Load session & connect socket ─────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return;

    // Load existing session data (populate past messages if resuming)
    historyService.getSessionById(sessionId).then((data) => {
      if (data?.questions && data.questions.length > 0) {
        const pastMessages: ChatMessage[] = [];
        let answeredBaseCount = 0;
        (data.questions as unknown as ChatSessionQuestion[]).forEach((q) => {
          if (q.answer) {
            const qText =
              typeof q.question === 'object' && q.question !== null
                ? (q.question as { question: string }).question
                : (q.question as string);
            if (qText) {
              pastMessages.push({
                id: generateId(),
                sender: 'ai',
                text: qText,
                time: formatCurrentTime(),
                isDeepDive: q.isDeepDive,
              });
            }
            pastMessages.push({
              id: generateId(),
              sender: 'candidate',
              text: q.answer,
              time: formatCurrentTime(),
            });
            if (!q.isDeepDive) answeredBaseCount++;
          }
        });
        if (pastMessages.length > 0) {
          setMessages(pastMessages);
          setBaseQuestionIndex(answeredBaseCount);
        }
      }
    });

    // Connect to streaming service socket
    const streamingUrl =
      process.env.NEXT_PUBLIC_STREAMING_SERVICE_URL || 'http://localhost:8001';
    const socket = io(streamingUrl, {
      transports: ['websocket'],
      reconnectionAttempts: 3,
      timeout: 4000,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setSocketConnected(true);
      console.log('[ChatMode] Socket connected:', socket.id);
    });

    socket.on('connect_error', (err) => {
      console.error('[ChatMode] Socket connection error:', err.message);
      setSocketConnected(false);
    });

    socket.on('orchestration-event', (data: OrchestrationEvent) => {
      if (data.type === 'INTERVIEWER_ACTION') {
        const { actionType, text, score, evaluation } = (data.payload || {}) as {
          actionType?: string;
          text?: string;
          score?: number | null;
          evaluation?: string;
        };

        if (actionType === 'CONCLUDING') {
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              sender: 'ai',
              text: text || 'Cảm ơn bạn đã tham gia phỏng vấn!',
              time: formatCurrentTime(),
            },
          ]);
          setTimeout(() => handleFinishInterview(), 1500);
          return;
        }

        // ── Persist the incoming follow-up question to DB ──────────────────────
        // This is critical: follow-up questions are AI-generated and not in the
        // initial question bank. We add them here so handleSend() can find and
        // match them by text when the candidate submits their answer.
        if (actionType === 'FOLLOW_UP' && text) {
          historyService.getSessionById(sessionId).then((sess) => {
            if (sess) {
              const updated = sess.questions
                ? [...(sess.questions as unknown as ChatSessionQuestion[])]
                : [];
              const alreadyExists = updated.some((q) => {
                const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
                return qStr && qStr.trim() === text.trim();
              });
              if (!alreadyExists) {
                let lastAnsweredIdx = -1;
                for (let i = updated.length - 1; i >= 0; i--) {
                  if (updated[i].answer) {
                    lastAnsweredIdx = i;
                    break;
                  }
                }
                const newFollowUp: ChatSessionQuestion = {
                  question: text,
                  answer: '',
                  score: 0,
                  strengths: '',
                  improvements: '',
                  suggestedAnswer: '',
                  topicTag: '',
                  isDeepDive: true,
                };
                if (lastAnsweredIdx !== -1) {
                  updated.splice(lastAnsweredIdx + 1, 0, newFollowUp);
                } else {
                  updated.push(newFollowUp);
                }
                historyService.saveSession({
                  ...sess,
                  questions: updated as unknown as QuestionFeedback[],
                  replaceQuestions: true,
                });
              }
            }
          });
        }

        // ── Persist score/evaluation on the previously answered question ────────
        // NOTE: Server currently emits score: null in INTERVIEWER_ACTION, so this
        // block is effectively reserved for future use when server sends real scores.
        if (score !== null && score !== undefined) {
          historyService.getSessionById(sessionId).then((session) => {
            if (session?.questions) {
              const updated = [...(session.questions as unknown as ChatSessionQuestion[])];
              const answeredQText = currentQuestionRef.current;

              // 1. Find and update the question that was just answered
              let answeredIdx = updated.findIndex((q) => {
                const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
                return qStr && answeredQText && qStr.trim() === answeredQText.trim();
              });

              if (answeredIdx === -1) {
                for (let i = updated.length - 1; i >= 0; i--) {
                  if (updated[i].answer && !updated[i].score) {
                    answeredIdx = i;
                    break;
                  }
                }
              }

              if (answeredIdx !== -1) {
                updated[answeredIdx] = {
                  ...updated[answeredIdx],
                  score: score ?? 0,
                  strengths: evaluation,
                  improvements: actionType === 'FOLLOW_UP' ? 'Cần bổ sung chi tiết' : '',
                };
              }

              historyService.saveSession({
                ...session,
                questions: updated as unknown as QuestionFeedback[],
                replaceQuestions: true,
              });
            }
          });
        }

        // ── For TRANSITION: update currentQuestionRef to the base question text ─
        // The server sends the full "prefix\n\n👉 rawQuestion" as `text`.
        // Extract just the rawQuestion portion so handleSend can match it in DB.
        if (actionType === 'TRANSITION' && text) {
          const arrowIdx = text.indexOf('👉');
          currentQuestionRef.current = arrowIdx !== -1
            ? text.slice(arrowIdx + 2).trim()  // text after "👉 "
            : text;
        } else {
          currentQuestionRef.current = text || '';
        }

        setMessages((prev) => {
          if (prev.length > 0 && prev[prev.length - 1].text === text) {
            return prev;
          }
          return [
            ...prev,
            {
              id: generateId(),
              sender: 'ai',
              text: text || '',
              time: formatCurrentTime(),
              isDeepDive: actionType === 'FOLLOW_UP',
            },
          ];
        });
        setSessionState('LISTENING');
        setTimeout(() => textareaRef.current?.focus(), 100);
      } else if (data.type === 'STATE_UPDATE') {
        const { status } = (data.payload || {}) as { status?: string };
        if (status === 'COMPLETED') {
          handleFinishInterview();
        } else if (status === 'IN_PROGRESS') {
          setSessionState((prev) => (prev === 'AI_THINKING' ? 'LISTENING' : prev));
        }
      }
    });

    return () => {
      socket.disconnect();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionId]);

  // ── Start interview (join socket room) ────────────────────────────────────
  const handleStartInterview = useCallback(async () => {
    setSessionState('AI_THINKING');
    startTimer();

    const data = await historyService.getSessionById(sessionId);
    let initialQuestions: SocketInitialQuestion[] = [];
    try {
      if (data?.questions && data.questions.length > 0) {
        initialQuestions = (data.questions as unknown as ChatSessionQuestion[]).map((q) => ({
          question:
            typeof q.question === 'object' && q.question !== null
              ? (q.question as { question: string }).question
              : (q.question as string),
          good_answer_signals: q.goodAnswerSignals || [],
          topic: q.topicTag || '',
        }));
      }
    } catch {
      console.error('[ChatMode] Could not parse questions');
    }

    if (socketRef.current?.connected) {
      const sampleQ = initialQuestions[0]?.question || '';
      const isVi = /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i.test(sampleQ);
      const detectedLang = isVi ? 'vi' : 'en';
      const user = useAuthStore.getState().user;

      socketRef.current.emit('join-interview', {
        interviewId: sessionId,
        userId: user?.id || 'candidate-user',
        candidateName: user?.username || '',
        initialQuestions,
        baseQuestionIndex,
        interviewDomain: data?.interviewType || 'IT',
        targetJobTitle: data?.roleTitle || (detectedLang === 'en' ? 'Software Engineer' : 'Kỹ sư Phần mềm'),
        resumeText: data?.cvExtractedText || '',
        jdText: data?.jdExtractedText || '',
        language: detectedLang,
        chatMode: true,  // ← signals server to bypass avatar generation & TTS
      });
    } else {
      console.warn('[ChatMode] Socket not connected when starting interview.');
      setSessionState('INITIALIZING');
    }
  }, [sessionId, startTimer, baseQuestionIndex]);

  // ── Restart interview from beginning ─────────────────────────────────────
  const handleRestartInterview = useCallback(async () => {
    setShowRestartConfirm(false);
    setMessages([]);
    setInputValue('');
    setBaseQuestionIndex(0);
    setTimeLeft(900);
    setSessionState('INITIALIZING');
    currentQuestionRef.current = '';

    // Reset saved question answers and scores in local storage / session history
    try {
      const currentSession = await historyService.getSessionById(sessionId);
      if (currentSession?.questions) {
        const resetQuestions = currentSession.questions.map((q) => ({
          ...q,
          answer: '',
          score: 0,
          strengths: '',
          improvements: '',
          suggestedAnswer: '',
        }));
        await historyService.saveSession({
          ...currentSession,
          status: 'In progress',
          overallScore: undefined,
          overallFeedback: undefined,
          questions: resetQuestions,
          replaceQuestions: true,
        });
      }
    } catch (e) {
      console.warn('[ChatMode] Failed to reset session history for restart:', e);
    }

    if (socketRef.current?.connected) {
      socketRef.current.emit('orchestration-event', {
        type: 'RESTART_INTERVIEW',
        payload: { sessionId },
      });
    } else {
      // Re-trigger start interview with force restart if socket was disconnected
      handleStartInterview();
    }
  }, [sessionId, handleStartInterview]);

  // ── Send candidate answer ─────────────────────────────────────────────────
  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || sessionState !== 'LISTENING') return;

    if (!socketRef.current?.connected) {
      alert('Không thể kết nối với máy chủ phỏng vấn. Vui lòng kiểm tra lại kết nối!');
      return;
    }

    setMessages((prev) => [
      ...prev,
      { id: generateId(), sender: 'candidate', text, time: formatCurrentTime() },
    ]);
    setInputValue('');
    setSessionState('AI_THINKING');

    // Persist to history matching currentQuestionRef
    historyService.getSessionById(sessionId).then((session) => {
      if (session) {
        const updated: ChatSessionQuestion[] = session.questions
          ? [...(session.questions as unknown as ChatSessionQuestion[])]
          : [];
        const activeQText = currentQuestionRef.current;

        const isWarmupText = (t?: string) => {
          if (!t) return false;
          const low = t.toLowerCase();
          return low.includes('giới thiệu đôi nét về bản thân') || low.includes('giới thiệu về bản thân') || low.includes('khởi động');
        };

        if (isWarmupText(activeQText)) {
          const warmupIdx = updated.findIndex(q => {
            const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
            return isWarmupText(qStr) || q.topicTag === 'Warmup';
          });
          if (warmupIdx !== -1) {
            updated[warmupIdx] = { ...updated[warmupIdx], answer: text };
          } else {
            updated.unshift({
              question: activeQText || 'Giới thiệu bản thân',
              answer: text,
              score: 0,
              strengths: 'Khởi động / Giới thiệu làm quen',
              improvements: '',
              suggestedAnswer: '',
              topicTag: 'Warmup',
              isDeepDive: false,
            });
          }
        } else {
          const targetIdx = updated.findIndex((q) => {
            const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
            return qStr && activeQText && qStr.trim() === activeQText.trim();
          });

          if (targetIdx !== -1) {
            updated[targetIdx] = { ...updated[targetIdx], answer: text };
          } else {
            let lastAnsweredIdx = -1;
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].answer) {
                lastAnsweredIdx = i;
                break;
              }
            }
            const newTurn: ChatSessionQuestion = {
              question: activeQText || 'Câu hỏi',
              answer: text,
              score: 0,
              strengths: '',
              improvements: '',
              suggestedAnswer: '',
              topicTag: '',
              isDeepDive: false,
            };
            if (lastAnsweredIdx !== -1) {
              updated.splice(lastAnsweredIdx + 1, 0, newTurn);
            } else {
              updated.push(newTurn);
            }
          }
        }
        historyService.saveSession({
          ...session,
          questions: updated as unknown as QuestionFeedback[],
          replaceQuestions: true,
        });
      }
    });

    socketRef.current.emit('orchestration-event', {
      type: 'CANDIDATE_TEXT_SUBMIT',
      payload: { text },
    });
  }, [inputValue, sessionState, sessionId]);

  // ── Keyboard shortcut ─────────────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ─── FINISHED screen ──────────────────────────────────────────────────────
  if (sessionState === 'FINISHED') {
    return (
      <div className="flex flex-col h-screen bg-slate-50 items-center justify-center gap-6 p-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="size-16 rounded-full bg-emerald-100 flex items-center justify-center">
            <CheckCircle2 size={32} className="text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-slate-800">Phỏng vấn đã hoàn tất!</h2>
          <p className="text-sm text-slate-500 max-w-sm leading-relaxed">
            Cảm ơn bạn đã hoàn thành buổi phỏng vấn. Kết quả đang được AI phân tích và sẽ sẵn sàng trong giây lát.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            onClick={() =>
              (window.location.href = `/interview/session/${sessionId}/result`)
            }
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
          >
            Xem kết quả đánh giá
          </Button>
          <Button variant="outline" onClick={() => (window.location.href = '/history')}>
            Về trang lịch sử
          </Button>
        </div>
      </div>
    );
  }

  // ─── Main chat UI ─────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-[#f5f7fa] font-sans">

      {/* ── Header ── */}
      <header className="flex items-center justify-between px-5 py-3 bg-white border-b border-slate-200 shadow-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-indigo-50 border border-indigo-200 text-indigo-700 text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full">
            <MessageSquareDashed size={11} />
            <span>Chế độ Text</span>
          </div>
          <span className="text-sm font-semibold text-slate-700">
            Phỏng vấn AI — Phiên #{sessionId?.slice(-6)}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 text-[11px] font-semibold ${
              socketConnected ? 'text-emerald-600' : 'text-slate-400'
            }`}
          >
            <span
              className={`size-2 rounded-full ${
                socketConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'
              }`}
            />
            {socketConnected ? 'Đã kết nối' : 'Đang kết nối...'}
          </div>

          <div
            className={`flex items-center gap-1.5 font-mono text-sm font-bold ${
              timeLeft <= 60
                ? 'text-red-600 animate-pulse'
                : timeLeft <= 180
                ? 'text-amber-600'
                : 'text-slate-700'
            }`}
          >
            <Timer size={14} />
            {formatCountdown(timeLeft)}
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowRestartConfirm(true)}
            className="text-xs text-slate-600 border-slate-300 hover:border-amber-400 hover:text-amber-700 gap-1.5"
            title="Làm lại phỏng vấn từ đầu"
          >
            <RotateCcw size={12} />
            Phỏng vấn lại
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowExitConfirm(true)}
            className="text-xs text-slate-600 border-slate-300 hover:border-red-300 hover:text-red-600 gap-1.5"
          >
            <LogOut size={12} />
            Thoát
          </Button>
        </div>
      </header>

      {/* ── Chat area ── */}
      <div className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-4 py-4 min-h-0">

        {/* Messages scroll container */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto space-y-4 pr-1"
          style={{ scrollbarWidth: 'thin' }}
        >
          {/* Empty state */}
          {messages.length === 0 && sessionState === 'INITIALIZING' && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-16">
              <div className="size-16 rounded-full bg-slate-100 flex items-center justify-center">
                <Bot size={28} className="text-slate-400" />
              </div>
              <div>
                <p className="font-semibold text-slate-600 mb-1">Sẵn sàng bắt đầu?</p>
                <p className="text-sm text-slate-400">
                  Nhấn &ldquo;Bắt đầu phỏng vấn&rdquo; để AI đặt câu hỏi đầu tiên.
                </p>
              </div>
            </div>
          )}

          {/* Message bubbles */}
          {messages.map((msg) => {
            const isAi = msg.sender === 'ai';
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isAi ? 'justify-start' : 'justify-end'}`}
              >
                {isAi && (
                  <div className="size-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 mt-1 shadow-md">
                    <Bot size={15} className="text-white" />
                  </div>
                )}

                <div className={`flex flex-col max-w-[75%] ${isAi ? 'items-start' : 'items-end'}`}>
                  <span className="text-[10px] font-bold text-slate-400 mb-1 px-1 uppercase tracking-wider">
                    {isAi ? 'Người phỏng vấn (AI)' : 'Bạn'}
                  </span>
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                      isAi
                        ? 'bg-white text-slate-800 border border-slate-200 rounded-tl-none'
                        : 'bg-indigo-600 text-white rounded-tr-none'
                    }`}
                  >
                    {isAi && msg.isDeepDive && (
                      <div className="flex items-center gap-1 text-[10px] font-bold text-purple-600 mb-1.5">
                        <CornerDownRight size={10} />
                        <span>HỎI SÂU HƠN</span>
                      </div>
                    )}
                    <p className="whitespace-pre-line">{msg.text}</p>
                    <span
                      className={`block text-[9px] mt-1.5 text-right ${
                        isAi ? 'text-slate-400' : 'text-white/60'
                      }`}
                    >
                      {msg.time}
                    </span>
                  </div>
                </div>

                {!isAi && (
                  <div className="size-8 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-1">
                    <User size={15} className="text-slate-600" />
                  </div>
                )}
              </div>
            );
          })}

          {/* AI thinking indicator */}
          {sessionState === 'AI_THINKING' && (
            <div className="flex gap-3 justify-start">
              <div className="size-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 mt-1 shadow-md">
                <Bot size={15} className="text-white" />
              </div>
              <div className="flex flex-col items-start">
                <span className="text-[10px] font-bold text-slate-400 mb-1 px-1 uppercase tracking-wider">
                  Người phỏng vấn (AI)
                </span>
                <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none px-5 py-4 shadow-sm flex items-center gap-2">
                  <Loader2 size={14} className="text-indigo-500 animate-spin" />
                  <span className="text-sm text-slate-500 italic">AI đang phân tích câu trả lời...</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Input area ── */}
        <div className="shrink-0 mt-3">
          {sessionState === 'INITIALIZING' && (
            <div className="flex justify-center">
              <Button
                onClick={handleStartInterview}
                disabled={!socketConnected}
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-8 h-11 rounded-xl shadow-md gap-2"
              >
                {socketConnected ? (
                  <>
                    <Play size={15} fill="currentColor" />
                    {messages.length > 0 ? 'Tiếp tục phỏng vấn' : 'Bắt đầu phỏng vấn'}
                  </>
                ) : (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Đang kết nối...
                  </>
                )}
              </Button>
            </div>
          )}

          {sessionState === 'LISTENING' && (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-md p-3">
              <Textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nhập câu trả lời của bạn... (Enter để gửi, Shift+Enter để xuống dòng)"
                className="min-h-[80px] max-h-[200px] resize-none text-sm border-0 shadow-none focus-visible:ring-0 bg-transparent p-1 leading-relaxed"
                autoFocus
              />
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
                <span className="text-[11px] text-slate-400">
                  <kbd className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px] font-mono">Enter</kbd>{' '}
                  gửi &nbsp;·&nbsp;{' '}
                  <kbd className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px] font-mono">Shift+Enter</kbd>{' '}
                  xuống dòng
                </span>
                <Button
                  onClick={handleSend}
                  disabled={!inputValue.trim()}
                  size="sm"
                  className={`gap-1.5 h-9 px-4 rounded-xl font-semibold text-sm transition-all ${
                    inputValue.trim()
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md'
                      : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}
                >
                  <Send size={14} />
                  Gửi
                </Button>
              </div>
            </div>
          )}

          {sessionState === 'AI_THINKING' && (
            <div className="flex justify-center py-3">
              <div className="flex items-center gap-2 text-sm text-indigo-600 font-medium bg-indigo-50 border border-indigo-200 px-5 py-2.5 rounded-full shadow-sm">
                <Loader2 size={14} className="animate-spin" />
                AI đang xử lý câu trả lời của bạn...
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Restart confirm modal ── */}
      {showRestartConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full">
            <h3 className="text-base font-bold text-slate-800 mb-2">Phỏng vấn lại từ đầu?</h3>
            <p className="text-sm text-slate-500 leading-relaxed mb-5">
              Toàn bộ câu trả lời trước đó trong phiên này sẽ được làm mới và bắt đầu lại từ câu hỏi đầu tiên. Bạn có chắc chắn không?
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" size="sm" onClick={() => setShowRestartConfirm(false)}>
                Hủy bỏ
              </Button>
              <Button
                size="sm"
                onClick={handleRestartInterview}
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold"
              >
                Xác nhận làm lại
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Exit confirm modal ── */}
      {showExitConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full">
            <h3 className="text-base font-bold text-slate-800 mb-2">Kết thúc phỏng vấn sớm?</h3>
            <p className="text-sm text-slate-500 leading-relaxed mb-5">
              Nếu thoát bây giờ, chỉ những câu hỏi đã hoàn thành mới được tính điểm. Bạn có chắc chắn không?
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" size="sm" onClick={() => setShowExitConfirm(false)}>
                Hủy bỏ
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setShowExitConfirm(false);
                  handleFinishInterview();
                }}
                className="bg-red-600 hover:bg-red-700 text-white font-semibold"
              >
                Đồng ý thoát
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
