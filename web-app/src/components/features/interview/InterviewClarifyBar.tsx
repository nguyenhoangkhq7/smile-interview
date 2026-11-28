'use client';

import { useEffect, useState } from 'react';
import { HelpCircle, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { ClarifyKind, QuestionMode, TurnClarification } from '@/services/evidenceInterview';

const CLARIFY_PLACEHOLDER_BY_MODE: Record<QuestionMode, string> = {
  CODING: 'VD: Input có thể rỗng không? Có cần giữ thứ tự ban đầu không?',
  DEBUGGING: 'VD: Dịch vụ đang chạy đơn luồng hay đa luồng? Có yêu cầu giữ nguyên chữ ký hàm không?',
  DESIGN: 'VD: Tải dự kiến bao nhiêu QPS? Yêu cầu nhất quán mạnh hay eventual consistency?',
  TECHNICAL_EXPLANATION: 'VD: Câu hỏi đang xét trong ngữ cảnh hệ đơn nút hay hệ phân tán?',
  BEHAVIORAL: 'VD: Mình có thể chia sẻ tình huống từ đồ án tốt nghiệp hoặc dự án cá nhân không?',
};

interface InterviewClarifyBarProps {
  clarifications: readonly TurnClarification[];
  mode: QuestionMode;
  isPractice: boolean;
  busy: boolean;
  compact?: boolean;
  onClarify: (kind: ClarifyKind, question?: string) => Promise<unknown>;
  onInputActiveChange?: (active: boolean) => void;
}

export function InterviewClarifyBar({
  clarifications,
  mode,
  isPractice,
  busy,
  compact = false,
  onClarify,
  onInputActiveChange,
}: InterviewClarifyBarProps) {
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyQuestion, setClarifyQuestion] = useState('');

  const remaining = Math.max(0, 2 - clarifications.length);
  const canClarifyPrompt = remaining > 0;
  const canRequestHint = isPractice && remaining > 0 && !clarifications.some(item => item.kind === 'HINT');

  useEffect(() => {
    onInputActiveChange?.(clarifyOpen && canClarifyPrompt);
  }, [clarifyOpen, canClarifyPrompt, onInputActiveChange]);

  useEffect(() => () => {
    onInputActiveChange?.(false);
  }, [onInputActiveChange]);

  if (!clarifications.length && !canClarifyPrompt && !canRequestHint) return null;

  return (
    <div className={compact ? 'mt-3 space-y-2 border-t pt-2.5' : 'mt-4 space-y-2 border-t pt-3'}>
      {clarifications.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            Trao đổi làm rõ đề bài
          </p>
          {clarifications.map((item, idx) => (
            <div key={idx} className="space-y-1 rounded-xl border bg-muted/25 p-2.5 text-xs leading-relaxed">
              <p className="font-semibold text-foreground">
                {item.kind === 'HINT' ? 'Gợi ý hướng tiếp cận' : `Câu hỏi của bạn: ${item.question}`}
              </p>
              <p className="text-muted-foreground">{item.answer}</p>
            </div>
          ))}
        </div>
      )}

      {(canClarifyPrompt || canRequestHint) && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {canClarifyPrompt && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={busy}
                onClick={() => setClarifyOpen(open => !open)}
              >
                <HelpCircle size={13} aria-hidden="true" />
                Hỏi làm rõ đề bài (còn {remaining}/2)
              </Button>
            )}
            {canRequestHint && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-brand-green"
                disabled={busy}
                onClick={() => void onClarify('HINT')}
              >
                <Lightbulb size={13} aria-hidden="true" />
                Xin gợi ý nhỏ
              </Button>
            )}
          </div>
          {clarifyOpen && canClarifyPrompt && (
            <form
              className="flex flex-wrap gap-2"
              onSubmit={event => {
                event.preventDefault();
                if (!clarifyQuestion.trim() || busy) return;
                void onClarify('CLARIFY_PROMPT', clarifyQuestion).then(updated => {
                  if (updated) {
                    setClarifyQuestion('');
                    setClarifyOpen(false);
                  }
                });
              }}
            >
              <Input
                aria-label="Nội dung cần làm rõ đề bài"
                className="h-8 min-w-44 flex-1 text-xs"
                placeholder={CLARIFY_PLACEHOLDER_BY_MODE[mode]}
                value={clarifyQuestion}
                disabled={busy}
                onChange={e => setClarifyQuestion(e.target.value)}
              />
              <Button type="submit" size="sm" className="h-8 text-xs" disabled={busy || !clarifyQuestion.trim()}>
                Gửi câu hỏi
              </Button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
