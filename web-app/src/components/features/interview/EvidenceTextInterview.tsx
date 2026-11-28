'use client';

import { useState } from 'react';
import { Check, Clock3, History, LoaderCircle, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { modeLabels } from './EvidenceSetup';
import { InterviewClarifyBar } from './InterviewClarifyBar';
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
  const grading = session?.submission?.status === 'QUEUED';
  const shouldReveal = Boolean(session) && !awaiting && !conversation.closing && Boolean(conversation.text);
  const previousQuestion = awaiting ? session?.turns.at(-1)?.question : '';
  const { displayedText, isRevealing, complete } = useProgressiveText(conversation.text || previousQuestion || '', shouldReveal);
  const pendingTurn = session?.pending_turn ?? null;
  const [codeState, setCodeState] = useState<{ turnId: string; code: string }>({ turnId: '', code: '' });
  if (!session) return null;

  const isPractice = session.config.session_purpose === 'PRACTICE';
  const showClarifyBar = Boolean(
    !conversation.introducing && !conversation.closing && !awaiting && pendingTurn,
  );

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
  const starterCode = (pendingTurn?.coding_spec?.starter_code ?? '').trim();
  const hasEditedCode = Boolean(activeCode.trim() && (!starterCode || activeCode.trim() !== starterCode));
  const canSubmit = Boolean(interview.answer.trim() || (showCodeEditor && hasEditedCode));
  const lastTurnFeedback = session.turns.at(-1)?.feedback?.trim() || '';
  const turnFeedbackText = conversation.phase === 'INTERVIEW'
    ? (session.pending_turn?.introduction || lastTurnFeedback)
    : (conversation.closing && session.turns.length > 0 && lastTurnFeedback && lastTurnFeedback !== (conversation.text || '').trim()
        ? lastTurnFeedback
        : '');

  const readOnlyAnswer = conversation.closing || awaiting || grading;
  const isSubmitting = busy && !awaiting;
  const needsQuestionRetry = awaiting && !busy && Boolean(interview.error);
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
      <div className="flex items-center gap-3">{conversation.phase === 'INTERVIEW' && <span title="Đồng hồ tạm dừng khi AI chấm và tạo câu tiếp theo" className="flex items-center gap-2 text-sm tabular-nums"><Clock3 size={16} />Còn {Math.floor(interview.secondsLeft / 60)}:{String(interview.secondsLeft % 60).padStart(2, '0')}</span>}
        <Button variant="outline" size="sm" onClick={onHistory}><History size={15} />Lịch sử ({session.turns.length} câu)</Button></div>
    </div>
    <section aria-label="Không gian phỏng vấn văn bản" className="grid gap-4 lg:h-[calc(100dvh-13rem)] lg:min-h-[34rem] lg:grid-cols-2">
      <div className="flex min-h-0 min-w-0 flex-col rounded-2xl border bg-card">
        <div className="flex flex-wrap items-start justify-between gap-2 border-b px-5 py-4">
          <div>
            <p className="text-sm font-semibold">{conversation.interviewer}</p>
            {session.pending_turn && <p className="mt-1 text-sm text-muted-foreground">{skillLabel(turnSkillId(session, session.pending_turn))} · {modeLabels[session.pending_turn.mode]}</p>}
          </div>
          {isSubmitting && conversation.phase === 'INTERVIEW' && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
              <LoaderCircle size={12} className="animate-spin text-brand-orange" aria-hidden="true" />
              Đang gửi yêu cầu…
            </span>
          )}
        </div>
        <div key={session.pending_turn?.turn_id || (awaiting ? 'awaiting' : conversation.phase)} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} onClick={() => { if (isRevealing) complete(); }} className="max-h-[45dvh] min-h-0 overflow-y-auto overscroll-contain p-5 animate-in fade-in duration-200 lg:max-h-none lg:flex-1">
          {turnFeedbackText && <div role="status" aria-label="Phản hồi và chuyển tiếp" className={`mb-5 rounded-xl border p-4 text-sm leading-relaxed ${isPractice && session.turns.length > 0 ? 'border-brand-green/35 bg-brand-green/5' : 'bg-muted/30'}`}>
            {isPractice && session.turns.length > 0 ? (
              <p className="mb-1.5 text-[11px] font-semibold tracking-wide text-brand-green uppercase">
                {conversation.closing ? 'Góp ý luyện tập · câu cuối' : 'Góp ý luyện tập'}
              </p>
            ) : conversation.closing ? (
              <p className="mb-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                Phản hồi câu cuối
              </p>
            ) : null}
            <MarkdownContent content={turnFeedbackText} />
          </div>}
          {needsQuestionRetry ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed bg-muted/20 p-5">
              <p role="status" className="text-sm font-medium text-foreground">
                {awaitingMessage}
                {hasPreviousAnswers ? 'Câu tiếp theo đang chờ tải.' : 'Câu hỏi đầu tiên đang chờ tải.'}
              </p>
              <Button variant="outline" size="sm" onClick={() => void interview.loadNextQuestion()}>
                Thử tải lại câu hỏi
              </Button>
            </div>
          ) : (
            <>
              <MarkdownContent content={displayedText} />
              {isRevealing && <span className="mt-1 inline-block h-4 w-1.5 animate-pulse rounded-xs bg-brand-orange/70 align-middle" aria-hidden="true" />}
              {showClarifyBar && pendingTurn && (
                <InterviewClarifyBar
                  key={pendingTurn.turn_id}
                  clarifications={pendingTurn.clarifications ?? []}
                  mode={pendingTurn.mode}
                  isPractice={isPractice}
                  busy={busy}
                  onClarify={(kind, question) => interview.clarify(kind, question)}
                />
              )}
            </>
          )}
        </div>
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {showCodeEditor
            ? <p className="font-semibold">{answerLabel}</p>
            : <label htmlFor="interview-answer" className="font-semibold">{answerLabel}</label>}
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
            defaultAutocomplete={isPractice}
          />
        )}
        {showCodeEditor ? (
          <div className="shrink-0 space-y-1">
            <label htmlFor="interview-answer" className="text-xs font-medium text-muted-foreground">
              Giải thích ngắn hoặc độ phức tạp (tuỳ chọn)
            </label>
            <textarea
              id="interview-answer"
              aria-label="Câu trả lời"
              className={`h-12 min-h-12 w-full resize-none overflow-y-auto rounded-xl border border-border/80 px-3.5 py-1.5 text-sm leading-relaxed transition-colors focus-visible:bg-background focus-visible:outline-2 focus-visible:outline-brand-orange ${readOnlyAnswer ? 'bg-muted/40 text-muted-foreground' : 'bg-muted/20'}`}
              maxLength={50000}
              value={answerValue}
              readOnly={readOnlyAnswer}
              onChange={e => { if (isRevealing) complete(); interview.setAnswer(e.target.value); }}
              disabled={busy || !session.pending_turn}
              placeholder="VD: Dùng TTL 3600s để tự hết hạn cache, độ phức tạp O(1)…"
            />
          </div>
        ) : (
          <textarea id="interview-answer" aria-label="Câu trả lời" className={`h-40 min-h-32 w-full resize-none overflow-y-auto rounded-xl border p-4 text-sm leading-relaxed transition-colors focus-visible:outline-2 focus-visible:outline-brand-orange lg:h-auto lg:flex-1 ${readOnlyAnswer ? 'bg-muted/40 text-muted-foreground' : 'bg-background'} ${session.pending_turn?.mode === 'CODING' ? 'font-mono' : ''}`}
            maxLength={conversation.introducing ? 10000 : 50000} value={answerValue} readOnly={readOnlyAnswer}
            onChange={e => { if (isRevealing) complete(); interview.setAnswer(e.target.value); }} disabled={busy || (!conversation.introducing && !session.pending_turn)}
            placeholder={answerPlaceholder} />
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">{conversation.closing
          ? <Button disabled={busy} onClick={() => void interview.converse('NEXT')}>Xem kết quả</Button>
          : <><div className="flex flex-wrap items-center gap-2">
              {!awaiting && !grading && <Button
                disabled={busy || !canSubmit}
                title={!canSubmit && showCodeEditor && Boolean(starterCode) ? 'Hãy chỉnh sửa mã nguồn hoặc nhập giải thích trước khi gửi' : undefined}
                onClick={() => void interview.submit(interview.answer, showCodeEditor && activeCode.trim() ? activeCode : undefined)}
              >{isSubmitting
                ? <><LoaderCircle size={15} className="animate-spin" />{conversation.introducing ? 'Đang gửi giới thiệu…' : 'Đang nộp bài…'}</>
                : <><Send size={15} />Gửi câu trả lời</>}</Button>}
              {!awaiting && !conversation.introducing && session.pending_turn && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => void interview.submit('Em chưa làm được.')}
                >
                  Chưa làm được
                </Button>
              )}
              {conversation.introducing && <Button variant="ghost" disabled={busy} onClick={() => void interview.converse('SKIP_INTRODUCTION')}>Bỏ qua giới thiệu</Button>}
            </div>
            <Button variant="outline" size="sm" disabled={busy} onClick={onStop}>Kết thúc phiên</Button></>}
        </div>
      </div>
    </section>
  </div>;
}
