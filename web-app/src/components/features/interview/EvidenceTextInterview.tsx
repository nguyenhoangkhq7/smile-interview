'use client';

import { useState } from 'react';
import { Check, Clock3, History, LoaderCircle, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { modeLabels } from './EvidenceSetup';
import { InterviewCodeEditor } from './InterviewCodeEditor';
import { turnSkillId } from '@/services/evidenceInterview';
import { useTextInterviewConversation } from '@/hooks/useTextInterviewConversation';
import { useProgressiveText } from '@/hooks/useProgressiveText';

export type InterviewController = ReturnType<typeof useEvidenceInterview>;

export function EvidenceTextInterview({ interview, onHistory, onStop }: {
  interview: InterviewController; onHistory: () => void; onStop: () => void;
}) {
  const { session, busy } = interview;
  const conversation = useTextInterviewConversation(interview);
  const awaiting = Boolean(session?.awaiting_question);
  const shouldReveal = Boolean(session) && !awaiting && !conversation.closing && Boolean(conversation.text);
  const { displayedText, isRevealing, complete } = useProgressiveText(conversation.text || '', shouldReveal);
  const pendingTurn = session?.pending_turn ?? null;
  const [codeState, setCodeState] = useState<{ turnId: string; code: string }>({ turnId: '', code: '' });
  if (!session) return null;

  const showCodeEditor = Boolean(
    !conversation.introducing
    && !conversation.closing
    && !awaiting
    && pendingTurn
    && (pendingTurn.mode === 'CODING' || pendingTurn.requires_code || pendingTurn.coding_spec),
  );
  const activeCode = pendingTurn && codeState.turnId === pendingTurn.turn_id
    ? codeState.code
    : (pendingTurn?.coding_spec?.starter_code ?? '');
  const setActiveCode = (next: string) => {
    if (!pendingTurn) return;
    if (isRevealing) complete();
    setCodeState({ turnId: pendingTurn.turn_id, code: next });
  };
  const canSubmit = Boolean(interview.answer.trim() || (showCodeEditor && activeCode.trim()));

  const readOnlyAnswer = conversation.closing || awaiting;
  const isSubmitting = busy && !awaiting;
  const isLoadingQuestion = awaiting && busy;
  const needsManualRetry = awaiting && !busy;
  const hasPreviousAnswers = session.turns.length > 0;

  const answerLabel = awaiting
    ? (hasPreviousAnswers ? 'Câu trả lời vừa gửi' : 'Phần giới thiệu vừa gửi')
    : conversation.closing
      ? (hasPreviousAnswers ? 'Câu trả lời cuối cùng' : 'Câu trả lời của bạn')
      : 'Câu trả lời của bạn';

  const answerValue = readOnlyAnswer
    ? session.turns.at(-1)?.answer || (awaiting ? session.conversation?.introduction : '') || ''
    : interview.answer;

  const answerPlaceholder = conversation.closing
    ? 'Không có câu trả lời nào được gửi trong phiên này.'
    : awaiting
      ? 'Không có nội dung được gửi.'
      : conversation.introducing
        ? 'Bạn có thể giới thiệu về bản thân…'
        : 'Nhập câu trả lời hoặc code của bạn…';

  const awaitingMessage = hasPreviousAnswers
    ? 'Đã ghi nhận câu trả lời của bạn. '
    : session.conversation?.introduction
      ? 'Đã ghi nhận phần giới thiệu của bạn. '
      : '';

  return <div data-interview-mode="TEXT" data-conversation-phase={conversation.phase} className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3">
      <p className="text-sm">{conversation.phase === 'INTERVIEW' ? <>Đã trả lời <strong>{session.turns.length}/{session.config.max_questions}</strong> câu</> : 'Phòng phỏng vấn'}</p>
      <div className="flex items-center gap-3">{conversation.phase === 'INTERVIEW' && <span className="flex items-center gap-2 text-sm tabular-nums"><Clock3 size={16} />Còn {Math.floor(interview.secondsLeft / 60)}:{String(interview.secondsLeft % 60).padStart(2, '0')}</span>}
        <Button variant="outline" size="sm" onClick={onHistory}><History size={15} />Lịch sử ({session.turns.length} câu)</Button></div>
    </div>
    <section aria-label="Không gian phỏng vấn văn bản" className="grid gap-4 lg:h-[calc(100dvh-13rem)] lg:min-h-96 lg:grid-cols-2">
      <div className="flex min-h-0 min-w-0 flex-col rounded-2xl border bg-card">
        <div className="flex flex-wrap items-start justify-between gap-2 border-b px-5 py-4">
          <div>
            <p className="text-sm font-semibold">{conversation.interviewer}</p>
            {session.pending_turn && <p className="mt-1 text-sm text-muted-foreground">{skillLabel(turnSkillId(session, session.pending_turn))} · {modeLabels[session.pending_turn.mode]}</p>}
            {isLoadingQuestion && <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground"><LoaderCircle size={14} className="animate-spin text-brand-orange" aria-hidden="true" />{hasPreviousAnswers ? 'Đang chuẩn bị câu hỏi tiếp theo…' : 'Đang chuẩn bị câu hỏi đầu tiên…'}</p>}
            {needsManualRetry && <p className="mt-1 text-sm text-amber-600 dark:text-amber-400">Chưa thể tải câu hỏi tiếp theo</p>}
          </div>
          {isSubmitting && conversation.phase === 'INTERVIEW' && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
              <LoaderCircle size={12} className="animate-spin text-brand-orange" aria-hidden="true" />
              Đang đánh giá câu trả lời…
            </span>
          )}
        </div>
        <div key={session.pending_turn?.turn_id || (awaiting ? 'awaiting' : conversation.phase)} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} onClick={() => { if (isRevealing) complete(); }} className="max-h-[45dvh] min-h-0 overflow-y-auto overscroll-contain p-5 animate-in fade-in duration-200 lg:max-h-none lg:flex-1">
          {conversation.phase === 'INTERVIEW' && (session.pending_turn?.introduction || session.turns.at(-1)?.feedback) && <div role="status" aria-label="Phản hồi và chuyển tiếp" className="mb-5 rounded-xl border bg-muted/30 p-4 text-sm leading-relaxed">
            <MarkdownContent content={session.pending_turn?.introduction || session.turns.at(-1)?.feedback || ''} />
          </div>}
          {awaiting ? (
            <div role="status" aria-live="polite" className="space-y-4 rounded-xl border border-dashed bg-muted/20 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                  {isLoadingQuestion && <LoaderCircle size={16} className="shrink-0 animate-spin text-brand-orange" aria-hidden="true" />}
                  <span>
                    {awaitingMessage}
                    {isLoadingQuestion
                      ? (hasPreviousAnswers ? 'Người phỏng vấn đang chuẩn bị câu hỏi tiếp theo…' : 'Người phỏng vấn đang chuẩn bị câu hỏi đầu tiên…')
                      : (hasPreviousAnswers ? 'Câu tiếp theo đang chờ tải.' : 'Câu hỏi đầu tiên đang chờ tải.')}
                  </span>
                </p>
                {needsManualRetry && (
                  <Button variant="outline" size="sm" onClick={() => void interview.loadNextQuestion()}>
                    Thử tải lại câu hỏi
                  </Button>
                )}
              </div>
              {isLoadingQuestion && (
                <div className="space-y-2.5 pt-1" aria-hidden="true">
                  <Skeleton className="h-4 w-11/12" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/5" />
                </div>
              )}
            </div>
          ) : (
            <>
              <MarkdownContent content={displayedText} />
              {isRevealing && <span className="mt-1 inline-block h-4 w-1.5 animate-pulse rounded-xs bg-brand-orange/70 align-middle" aria-hidden="true" />}
            </>
          )}
        </div>
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="interview-answer" className="font-semibold">{answerLabel}</label>
          {awaiting && (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-green-light px-2.5 py-0.5 text-xs font-medium text-brand-green">
              <Check size={12} aria-hidden="true" />
              Đã gửi
            </span>
          )}
          {isSubmitting && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
              <LoaderCircle size={12} className="animate-spin" aria-hidden="true" />
              Đang gửi…
            </span>
          )}
        </div>
        {showCodeEditor && pendingTurn && (
          <InterviewCodeEditor
            key={pendingTurn.turn_id}
            sessionId={session.session_id}
            turnId={pendingTurn.turn_id}
            value={activeCode}
            onChange={setActiveCode}
            codingSpec={pendingTurn.coding_spec}
            questionHint={`${turnSkillId(session, pendingTurn)} ${pendingTurn.question}`}
            disabled={busy}
            readOnly={readOnlyAnswer}
          />
        )}
        <textarea id="interview-answer" aria-label="Câu trả lời" className={`w-full resize-none overflow-y-auto rounded-xl border p-4 text-sm leading-relaxed transition-colors focus-visible:outline-2 focus-visible:outline-brand-orange ${showCodeEditor ? 'h-24 min-h-20' : 'h-40 min-h-32 lg:h-auto lg:flex-1'} ${readOnlyAnswer ? 'bg-muted/40 text-muted-foreground' : 'bg-background'} ${!showCodeEditor && session.pending_turn?.mode === 'CODING' ? 'font-mono' : ''}`}
          maxLength={conversation.introducing ? 10000 : 50000} value={answerValue} readOnly={readOnlyAnswer}
          onChange={e => { if (isRevealing) complete(); interview.setAnswer(e.target.value); }} disabled={busy || (!conversation.introducing && !session.pending_turn)}
          placeholder={showCodeEditor ? 'Giải thích hướng giải hoặc độ phức tạp (tuỳ chọn)…' : answerPlaceholder} />
        <div className="flex flex-wrap items-center gap-3">{conversation.closing
          ? <Button disabled={busy} onClick={() => void interview.converse('NEXT')}>Xem kết quả</Button>
          : <>{!awaiting && <Button disabled={busy || !canSubmit} onClick={() => void interview.submit(interview.answer, showCodeEditor && activeCode.trim() ? activeCode : undefined)}>{isSubmitting
              ? <><LoaderCircle size={15} className="animate-spin" />{conversation.introducing ? 'Đang gửi giới thiệu…' : 'Đang đánh giá…'}</>
              : <><Send size={15} />Gửi câu trả lời</>}</Button>}
            <Button variant="outline" disabled={busy} onClick={onStop}>Kết thúc phiên</Button>
            {conversation.introducing && <Button variant="ghost" disabled={busy} onClick={() => void interview.converse('SKIP_INTRODUCTION')}>Bỏ qua giới thiệu</Button>}
            {isLoadingQuestion && <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"><LoaderCircle size={14} className="animate-spin text-brand-orange" aria-hidden="true" />Đang chuyển tiếp…</span>}</>}
        </div>
      </div>
    </section>
  </div>;
}
