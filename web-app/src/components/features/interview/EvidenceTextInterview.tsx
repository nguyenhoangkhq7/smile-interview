'use client';

import { Clock3, History, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { modeLabels } from './EvidenceSetup';

export type InterviewController = ReturnType<typeof useEvidenceInterview>;

export function EvidenceTextInterview({ interview, onHistory, onStop }: {
  interview: InterviewController; onHistory: () => void; onStop: () => void;
}) {
  const { session, busy } = interview;
  if (!session) return null;
  return <div data-interview-mode="TEXT" className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3">
      <p className="text-sm">Đã trả lời <strong>{session.turns.length}/{session.config.max_questions}</strong> câu</p>
      <div className="flex items-center gap-3"><span className="flex items-center gap-2 text-sm tabular-nums"><Clock3 size={16} />Còn {Math.floor(interview.secondsLeft / 60)}:{String(interview.secondsLeft % 60).padStart(2, '0')}</span>
        <Button variant="outline" size="sm" onClick={onHistory}><History size={15} />Lịch sử ({session.turns.length} câu)</Button></div>
    </div>
    <section aria-label="Không gian phỏng vấn văn bản" className="grid gap-4 lg:h-[calc(100dvh-13rem)] lg:min-h-96 lg:grid-cols-2">
      <div className="flex min-h-0 min-w-0 flex-col rounded-2xl border bg-card">
        <div className="border-b px-5 py-4"><p className="text-xs font-semibold uppercase tracking-wide text-brand-orange">Câu hỏi hiện tại</p><p className="mt-1 text-sm text-muted-foreground">{session.pending_turn?.skill_id} · {session.pending_turn && modeLabels[session.pending_turn.mode]}</p></div>
        <div key={session.pending_turn?.turn_id} role="region" aria-label="Nội dung câu hỏi" tabIndex={0} className="max-h-[45dvh] min-h-0 overflow-y-auto overscroll-contain p-5 lg:max-h-none lg:flex-1">
          {(session.pending_turn?.introduction || session.turns.at(-1)?.feedback) && <div role="status" aria-label="Phản hồi và chuyển tiếp" className="mb-5 rounded-xl border bg-muted/30 p-4 text-sm leading-relaxed">
            <MarkdownContent content={session.pending_turn?.introduction || session.turns.at(-1)?.feedback || ''} />
          </div>}
          <MarkdownContent content={session.pending_turn?.question || ''} />
        </div>
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5">
        <label htmlFor="interview-answer" className="font-semibold">Câu trả lời của bạn</label>
        <textarea id="interview-answer" aria-label="Câu trả lời" className={`h-40 min-h-32 w-full resize-none overflow-y-auto rounded-xl border bg-background p-4 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-brand-orange lg:h-auto lg:flex-1 ${session.pending_turn?.mode === 'CODING' ? 'font-mono' : ''}`}
          value={interview.answer} onChange={e => interview.setAnswer(e.target.value)} disabled={busy} placeholder="Nhập câu trả lời hoặc code của bạn…" />
        <div className="flex flex-wrap gap-3"><Button disabled={busy || !interview.answer.trim()} onClick={() => void interview.submit()}><Send size={15} />{busy ? 'Đang xử lý…' : 'Gửi câu trả lời'}</Button>
          <Button variant="outline" disabled={busy} onClick={onStop}>Kết thúc phiên</Button></div>
      </div>
    </section>
  </div>;
}
