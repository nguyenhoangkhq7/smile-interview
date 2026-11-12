'use client';

import { Clock3, History, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { modeLabels } from './EvidenceSetup';
import { useTextInterviewConversation } from '@/hooks/useTextInterviewConversation';

export type InterviewController = ReturnType<typeof useEvidenceInterview>;

export function EvidenceTextInterview({ interview, onHistory, onStop }: {
  interview: InterviewController; onHistory: () => void; onStop: () => void;
}) {
  const { session, busy } = interview;
  const conversation = useTextInterviewConversation(interview);
  if (!session) return null;
  return <div data-interview-mode="TEXT" data-conversation-phase={conversation.phase} className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3">
      <p className="text-sm">{conversation.phase === 'INTERVIEW' ? <>Đã trả lời <strong>{session.turns.length}/{session.config.max_questions}</strong> câu</> : 'Phòng phỏng vấn'}</p>
      <div className="flex items-center gap-3">{conversation.phase === 'INTERVIEW' && <span className="flex items-center gap-2 text-sm tabular-nums"><Clock3 size={16} />Còn {Math.floor(interview.secondsLeft / 60)}:{String(interview.secondsLeft % 60).padStart(2, '0')}</span>}
        <Button variant="outline" size="sm" onClick={onHistory}><History size={15} />Lịch sử ({session.turns.length} câu)</Button></div>
    </div>
    <section aria-label="Không gian phỏng vấn văn bản" className="grid gap-4 lg:h-[calc(100dvh-13rem)] lg:min-h-96 lg:grid-cols-2">
      <div className="flex min-h-0 min-w-0 flex-col rounded-2xl border bg-card">
        <div className="border-b px-5 py-4"><p className="text-sm font-semibold">{conversation.interviewer}</p>{session.pending_turn && <p className="mt-1 text-sm text-muted-foreground">{skillLabel(session.pending_turn.skill_id)} · {modeLabels[session.pending_turn.mode]}</p>}</div>
        <div key={session.pending_turn?.turn_id} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} className="max-h-[45dvh] min-h-0 overflow-y-auto overscroll-contain p-5 lg:max-h-none lg:flex-1">
          {conversation.phase === 'INTERVIEW' && (session.pending_turn?.introduction || session.turns.at(-1)?.feedback) && <div role="status" aria-label="Phản hồi và chuyển tiếp" className="mb-5 rounded-xl border bg-muted/30 p-4 text-sm leading-relaxed">
            <MarkdownContent content={session.pending_turn?.introduction || session.turns.at(-1)?.feedback || ''} />
          </div>}
          <MarkdownContent content={conversation.text || ''} />
        </div>
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5">
        <label htmlFor="interview-answer" className="font-semibold">Câu trả lời của bạn</label>
        <textarea id="interview-answer" aria-label="Câu trả lời" className={`h-40 min-h-32 w-full resize-none overflow-y-auto rounded-xl border bg-background p-4 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-brand-orange lg:h-auto lg:flex-1 ${session.pending_turn?.mode === 'CODING' ? 'font-mono' : ''}`}
          maxLength={conversation.introducing ? 10000 : 50000} value={conversation.closing ? session.turns.at(-1)?.answer || '' : interview.answer}
          onChange={e => interview.setAnswer(e.target.value)} disabled={busy || conversation.closing || conversation.phase === 'OPENING'}
          placeholder={conversation.introducing ? 'Bạn có thể giới thiệu về bản thân…' : 'Nhập câu trả lời hoặc code của bạn…'} />
        <div className="flex flex-wrap gap-3">{conversation.closing
          ? <Button disabled={busy} onClick={() => void interview.converse('NEXT')}>Xem kết quả</Button>
          : <><Button disabled={busy || !interview.answer.trim()} onClick={() => void interview.submit()}><Send size={15} />{busy ? 'Đang xử lý…' : 'Gửi câu trả lời'}</Button>
            <Button variant="outline" disabled={busy} onClick={onStop}>Kết thúc phiên</Button>
            {conversation.introducing && <Button variant="ghost" disabled={busy} onClick={() => void interview.converse('SKIP_INTRODUCTION')}>Bỏ qua giới thiệu</Button>}</>}
        </div>
      </div>
    </section>
  </div>;
}
