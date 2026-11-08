'use client';
import { MarkdownContent } from '@/components/common/MarkdownContent';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { cvJdMatchingService, type RespondInterviewResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import {
  Send,
  Bot,
  User,
  Loader2,
  CornerDownRight,
  CheckCircle2,
  Timer,
  LogOut,
  Sparkles,
  Brain,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';

type ChatSessionState = 'INITIALIZING' | 'AI_THINKING' | 'LISTENING' | 'FINISHED' | 'ERROR';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'candidate';
  text: string;
  time: string;
  skillId?: string | null;
  isDeepDive?: boolean;
  judgeFeedback?: {
    reflectiveInsight: string;
    metamorphicTag: string;
    previousBelief: number[];
    updatedBelief: number[];
    tvDelta: number;
    skillVerified: boolean;
  };
}

const formatCurrentTime = () =>
  new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

const formatCountdown = (secs: number) => {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const generateId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

export function InterviewChatMode() {
  const params = useParams();
  const router = useRouter();
  const sessionId = (params?.id as string) || '';

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sessionState, setSessionState] = useState<ChatSessionState>('INITIALIZING');
  const [sessionError, setSessionError] = useState('');
  const [roleTitle, setRoleTitle] = useState('Phỏng vấn Thích ứng NCKH');
  const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
  const [currentTurn, setCurrentTurn] = useState<number>(1);
  const [completionRate, setCompletionRate] = useState<number>(0);
  const [timeLeft, setTimeLeft] = useState(1200); // 20 min

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, sessionState]);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Load or initialize the Module 3 Adaptive Interview session
  useEffect(() => {
    if (!sessionId) return;
    let mounted = true;

    (async () => {
      try {
        const sess = await historyService.getSessionById(sessionId);
        if (!mounted) return;

        if (sess?.roleTitle) {
          setRoleTitle(sess.roleTitle);
        }

        if (sess?.status === 'Completed') {
          setSessionState('FINISHED');
        }

        const existingTurns = sess?.questions || [];
        if (sess?.status === 'Completed' && existingTurns.length === 0) return;
        if (!sess) throw new Error('Không thể tải phiên phỏng vấn.');
        if (existingTurns.length > 0) {
          const rebuilt: ChatMessage[] = [];
          existingTurns.forEach((t, idx) => {
            rebuilt.push({
              id: `turn-q-${idx}`,
              sender: 'ai',
              text: t.question,
              time: formatCurrentTime(),
              skillId: t.topicTag,
              isDeepDive: t.isDeepDive,
            });
            if (t.answer && t.answer.trim() !== '') {
              rebuilt.push({
                id: `turn-a-${idx}`,
                sender: 'candidate',
                text: t.answer,
                time: formatCurrentTime(),
                skillId: t.topicTag,
                judgeFeedback: t.strengths
                  ? {
                      reflectiveInsight: t.strengths,
                      metamorphicTag: t.improvements || 'EVALUATED',
                      previousBelief: [],
                      updatedBelief: [],
                      tvDelta: 0,
                      skillVerified: false,
                    }
                  : undefined,
              });
            }
          });
          setMessages(rebuilt);
          const lastTurn = existingTurns[existingTurns.length - 1];
          setActiveSkillId(lastTurn?.topicTag || null);
          setCurrentTurn(existingTurns.length);
          if (sess?.status !== 'Completed') {
            setSessionState('LISTENING');
          }
          return;
        }

        // No turns yet: call startAdaptiveInterview
        const startRes = await cvJdMatchingService.startAdaptiveInterview(sessionId);
        if (!mounted) return;

        setActiveSkillId(startRes.active_skill_id || null);
        setCurrentTurn(startRes.turn);

        if (startRes.is_finished || !startRes.question) {
          setSessionState('FINISHED');
          return;
        }

        setMessages([
          {
            id: generateId(),
            sender: 'ai',
            text: startRes.question,
            time: formatCurrentTime(),
            skillId: startRes.active_skill_id,
            isDeepDive: false,
          },
        ]);
        setSessionState('LISTENING');
      } catch (err) {
        console.error('[InterviewChatMode] Initialization error:', err);
        setSessionError('Không thể tải phiên phỏng vấn. Vui lòng tải lại trang để thử lại.');
        setSessionState('ERROR');
      }
    })();

    return () => {
      mounted = false;
    };
  }, [sessionId]);

  const handleSendAnswer = useCallback(async () => {
    const answerText = inputValue.trim();
    if (!answerText || sessionState !== 'LISTENING') return;

    const candidateMsgId = generateId();
    setSessionError('');
    setInputValue('');
    setSessionState('AI_THINKING');

    setMessages((prev) => [
      ...prev,
      {
        id: candidateMsgId,
        sender: 'candidate',
        text: answerText,
        time: formatCurrentTime(),
        skillId: activeSkillId,
      },
    ]);

    try {
      const resp: RespondInterviewResponse = await cvJdMatchingService.respondAdaptiveInterview(
        sessionId,
        answerText
      );

      // Attach Judge feedback to candidate's message
      setMessages((prev) =>
        prev.map((m) =>
          m.id === candidateMsgId
            ? {
                ...m,
                judgeFeedback: {
                  reflectiveInsight: resp.reflective_insight,
                  metamorphicTag: resp.metamorphic_tag,
                  previousBelief: resp.previous_belief,
                  updatedBelief: resp.updated_belief,
                  tvDelta: resp.tv_delta,
                  skillVerified: resp.skill_verified,
                },
              }
            : m
        )
      );

      setCompletionRate(Math.round((resp.completion_rate || 0) * 100));
      setCurrentTurn(resp.turn);

      if (resp.is_finished || !resp.next_question) {
        setSessionState('FINISHED');
        return;
      }

      const isFollowUpOnSameSkill =
        Boolean(resp.evaluated_skill_id) &&
        Boolean(resp.active_skill_id) &&
        resp.evaluated_skill_id === resp.active_skill_id;

      setActiveSkillId(resp.active_skill_id || null);

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          sender: 'ai',
          text: resp.next_question || '',
          time: formatCurrentTime(),
          skillId: resp.active_skill_id,
          isDeepDive: isFollowUpOnSameSkill,
        },
      ]);
      setSessionState('LISTENING');
      setTimeout(() => textareaRef.current?.focus(), 100);
    } catch (err) {
      console.error('[InterviewChatMode] respondAdaptiveInterview error:', err);
      setMessages((prev) => prev.filter((m) => m.id !== candidateMsgId));
      setInputValue(answerText);
      setSessionError('Không thể gửi câu trả lời. Vui lòng kiểm tra phiên trước khi thử lại.');
      setSessionState('LISTENING');
    }
  }, [activeSkillId, inputValue, sessionId, sessionState]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendAnswer();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-950 font-sans">
      {sessionError && <div role="alert" className="bg-red-50 px-6 py-3 text-sm text-red-700">{sessionError}</div>}
      {/* Top Header */}
      <header className="border-b border-border bg-card px-6 py-3.5 flex items-center justify-between shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-brand-orange/15 text-brand-orange">
            <Brain size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-foreground">{roleTitle}</h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                Phỏng vấn thích ứng
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Lượt #{currentTurn} • Kỹ năng đang thẩm định:{' '}
              <strong className="text-brand-orange uppercase">{activeSkillId || 'Đang xử lý'}</strong> •
              Tiến độ hội tụ: <strong>{completionRate}%</strong>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted text-xs font-mono font-bold">
            <Timer size={14} className="text-brand-orange" />
            <span>{formatCountdown(timeLeft)}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/interview/session/${sessionId}/result`)}
            className="gap-1.5 text-xs"
          >
            <LogOut size={14} />
            Xem Báo cáo Kết quả
          </Button>
        </div>
      </header>

      {/* Chat Messages Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-5">
          {sessionState === 'INITIALIZING' && (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
              <Loader2 size={28} className="animate-spin text-brand-orange" />
              <p className="text-sm font-medium">
                Đang khởi tạo phiên Phỏng vấn Thích ứng (Abductive CoT & Belief Anchoring)...
              </p>
            </div>
          )}

          {messages.map((msg) => {
            const isAi = msg.sender === 'ai';
            return (
              <div key={msg.id} className="space-y-2">
                <div className={`flex items-start gap-3 ${isAi ? '' : 'flex-row-reverse'}`}>
                  <div
                    className={`flex size-8 shrink-0 items-center justify-center rounded-xl border ${
                      isAi
                        ? 'bg-brand-orange/10 border-brand-orange/30 text-brand-orange'
                        : 'bg-slate-800 border-slate-700 text-white'
                    }`}
                  >
                    {isAi ? <Bot size={16} /> : <User size={16} />}
                  </div>

                  <div
                    className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                      isAi
                        ? 'bg-card border border-border text-foreground'
                        : 'bg-brand-orange text-white'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1 text-[11px] opacity-80">
                      <span className="font-bold">
                        {isAi ? 'AI Interviewer (Step 2A)' : 'Ứng viên'}
                      </span>
                      {msg.skillId && (
                        <span className="px-1.5 py-0.2 rounded bg-black/10 font-mono uppercase text-[10px]">
                          {msg.skillId}
                        </span>
                      )}
                      {isAi && msg.isDeepDive && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-700 dark:text-purple-300 text-[10px] font-bold">
                          <CornerDownRight size={10} /> Follow-up Đào sâu (Sub-slot)
                        </span>
                      )}
                      <span>• {msg.time}</span>
                    </div>
                    {isAi ? <MarkdownContent content={msg.text} /> : <div className="whitespace-pre-wrap">{msg.text}</div>}
                  </div>
                </div>

                {/* Reflective Judge Feedback Box under Candidate Response */}
                {!isAi && msg.judgeFeedback && (
                  <div className="ml-11 mr-11 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3 text-xs space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                        <Sparkles size={13} />
                        Step 2B Reflective Metamorphic PBA Judge
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {msg.judgeFeedback.metamorphicTag}
                        </Badge>
                        {msg.judgeFeedback.skillVerified && (
                          <Badge className="bg-emerald-600 text-white text-[10px] gap-1">
                            <CheckCircle2 size={10} /> Đã hội tụ (VERIFIED)
                          </Badge>
                        )}
                      </div>
                    </div>
                    <MarkdownContent className="text-muted-foreground" content={msg.judgeFeedback.reflectiveInsight} />
                    {msg.judgeFeedback.updatedBelief &&
                      msg.judgeFeedback.updatedBelief.length === 3 && (
                        <div className="text-[11px] font-mono text-muted-foreground pt-1">
                          Posterior Belief [Low, Med, High]: [
                          {msg.judgeFeedback.updatedBelief.map((p) => p.toFixed(2)).join(', ')}] •
                          TV Shift: {msg.judgeFeedback.tvDelta.toFixed(3)}
                        </div>
                      )}
                  </div>
                )}
              </div>
            );
          })}

          {sessionState === 'AI_THINKING' && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground pl-2">
              <Loader2 size={16} className="animate-spin text-brand-orange" />
              <span>
                Reflective Judge đang đánh giá câu trả lời, cập nhật phân phối niềm tin trên Simplex và sinh câu hỏi tiếp theo...
              </span>
            </div>
          )}

          {sessionState === 'FINISHED' && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center space-y-4">
              <CheckCircle2 size={36} className="text-emerald-600 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-base font-extrabold text-foreground">
                  Phiên Phỏng vấn Thích ứng đã Hoàn tất!
                </h3>
                <p className="text-xs text-muted-foreground">
                  Hệ thống đã kiểm chứng hội tụ các kỹ năng mục tiêu và xuất Báo cáo Kiểm toán HITL (Phase 4).
                </p>
              </div>
              <Button
                onClick={() => router.push(`/interview/session/${sessionId}/result`)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
              >
                Xem Báo cáo Kiểm toán HITL (Phase 4)
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Input Area */}
      {sessionState !== 'FINISHED' && (
        <div className="border-t border-border bg-card p-4 shrink-0">
          <div className="max-w-3xl mx-auto flex items-end gap-3">
            <Textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sessionState !== 'LISTENING'}
              placeholder="Nhập câu trả lời kỹ thuật của bạn (Enter để gửi, Shift+Enter xuống dòng)..."
              className="min-h-[64px] max-h-[160px] resize-none text-sm"
            />
            <Button
              onClick={handleSendAnswer}
              disabled={sessionState !== 'LISTENING' || !inputValue.trim()}
              className="h-[64px] px-5 bg-brand-orange hover:bg-brand-orange-hover text-white font-bold gap-2 shrink-0"
            >
              <Send size={16} />
              Gửi
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
