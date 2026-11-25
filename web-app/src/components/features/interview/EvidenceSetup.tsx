'use client';
import { useEffect, useState } from 'react';
import { ChevronDown, Clock3, LoaderCircle, MessageSquareText, Mic, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { InterviewLimits, InterviewStartConfig, QuestionMode, defaultConfig, evidenceInterview, questionModes } from '@/services/evidenceInterview';

export const modeLabels: Record<QuestionMode, string> = {
  CODING: 'Lập trình', DEBUGGING: 'Tìm và sửa lỗi', DESIGN: 'Thiết kế hệ thống',
  TECHNICAL_EXPLANATION: 'Giải thích kỹ thuật', BEHAVIORAL: 'Kinh nghiệm và cách ứng xử',
};

const interactionOptions = [
  {
    value: 'TEXT',
    title: 'Bằng văn bản',
    description: 'Đọc câu hỏi, viết câu trả lời và code theo nhịp của bạn.',
    icon: MessageSquareText,
  },
  {
    value: 'VOICE',
    title: 'Bằng giọng nói',
    description: 'Trò chuyện với người phỏng vấn ảo, giải thích bằng lời và có phụ đề.',
    icon: Mic,
  },
] as const;

const selectClass =
  'h-10 w-full appearance-none rounded-lg border border-input bg-background px-3 pr-9 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50';

interface Props { busy: boolean; onStart: (config: InterviewStartConfig) => void }

export function EvidenceSetup({ busy, onStart }: Props) {
  const [config, setConfig] = useState(defaultConfig);
  const [limits, setLimits] = useState<InterviewLimits>();
  const [ready, setReady] = useState(false);
  const maxQuestions = limits?.maxQuestions ?? 40;
  const maxMinutes = Math.floor((limits?.durationSeconds ?? 7200) / 60);
  const invalidLimits = config.max_questions < 1 || config.max_questions > maxQuestions
    || config.duration_seconds < 60 || config.duration_seconds > maxMinutes * 60;

  useEffect(() => {
    const request = new AbortController();
    void evidenceInterview.limits(request.signal).then((current) => {
      if (request.signal.aborted) return;
      setLimits(current);
      setConfig((previous) => ({
        ...previous,
        interaction_mode: current.voiceEnabled ? previous.interaction_mode : 'TEXT',
        max_questions: Math.min(previous.max_questions, current.maxQuestions),
        duration_seconds: Math.min(previous.duration_seconds, Math.floor(current.durationSeconds / 60) * 60),
        max_questions_per_objective: current.maxQuestionsPerObjective < 8 ? current.maxQuestionsPerObjective : undefined,
      }));
    }).catch(() => {}).finally(() => {
      if (!request.signal.aborted) setReady(true);
    });
    return () => request.abort();
  }, []);

  return (
    <section aria-busy={busy} className="space-y-6 rounded-2xl border bg-card p-6 shadow-xs sm:p-8">
      <header className="space-y-1.5 border-b pb-5">
        <h1 className="text-2xl font-semibold tracking-tight">Chuẩn bị phỏng vấn</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          Câu hỏi được chọn theo JD và kỹ năng cần kiểm chứng. AI sẽ hỏi tiếp khi cần làm rõ trong thời lượng và số câu bạn chọn.
        </p>
      </header>

      <fieldset disabled={busy} className="space-y-3">
        <legend className="text-sm font-semibold text-foreground">Hình thức phỏng vấn</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {interactionOptions.map(({ value, title, description, icon: Icon }) => {
            if (value === 'VOICE' && limits?.voiceEnabled === false) return null;
            const selected = config.interaction_mode === value;
            return (
              <label
                key={value}
                className={`flex cursor-pointer items-start gap-3.5 rounded-xl border p-4 transition-colors ${
                  selected
                    ? 'border-brand-orange bg-brand-orange/5 ring-1 ring-brand-orange/20'
                    : 'bg-background hover:border-foreground/20 hover:bg-muted/30'
                }`}
              >
                <input
                  className="mt-1 size-4 shrink-0 accent-brand-orange"
                  type="radio"
                  name="interaction-mode"
                  value={value}
                  checked={selected}
                  onChange={() => setConfig({ ...config, interaction_mode: value })}
                />
                <span className="min-w-0 space-y-1.5">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Icon size={17} aria-hidden="true" className={selected ? 'text-brand-orange' : 'text-muted-foreground'} />
                    {title}
                  </span>
                  <span className="block text-sm leading-5 text-muted-foreground">{description}</span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="grid gap-4 rounded-xl border bg-muted/25 p-4 sm:grid-cols-12 sm:p-5">
        <label className="grid gap-1.5 sm:col-span-6">
          <span className="text-sm font-medium text-foreground">Dạng phỏng vấn</span>
          <span className="relative">
            <select
              className={selectClass}
              disabled={busy}
              value={config.focused_question_mode ?? 'MIXED'}
              onChange={e => setConfig({ ...config, focused_question_mode: e.target.value === 'MIXED' ? null : e.target.value as QuestionMode })}
            >
              <option value="MIXED">Tổng hợp</option>
              {questionModes.map(mode => <option key={mode} value={mode}>{modeLabels[mode]}</option>)}
            </select>
            <ChevronDown size={16} aria-hidden="true" className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground" />
          </span>
        </label>

        <label className="grid gap-1.5 sm:col-span-3">
          <span className="text-sm font-medium text-foreground">Thời lượng (phút)</span>
          <Input
            aria-label="Thời lượng"
            className="h-10 bg-background px-3 tabular-nums"
            type="number"
            min={1}
            max={maxMinutes}
            disabled={busy}
            value={config.duration_seconds / 60}
            onChange={e => setConfig({ ...config, duration_seconds: Number(e.target.value) * 60 })}
          />
        </label>

        <label className="grid gap-1.5 sm:col-span-3">
          <span className="text-sm font-medium text-foreground">Tối đa số câu hỏi</span>
          <Input
            aria-label="Số câu hỏi"
            className="h-10 bg-background px-3 tabular-nums"
            type="number"
            min={1}
            max={maxQuestions}
            disabled={busy}
            value={config.max_questions}
            onChange={e => setConfig({ ...config, max_questions: Number(e.target.value) })}
          />
        </label>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-4 border-t pt-5">
        <p role={busy ? 'status' : undefined} className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock3 size={15} aria-hidden="true" className="shrink-0" />
          Lần phỏng vấn đầu tiên có thể mất vài phút để chuẩn bị câu hỏi.
        </p>
        <Button size="lg" className="w-full px-5 sm:w-auto" disabled={busy || !ready || invalidLimits} onClick={() => onStart(config)}>
          {busy ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Play aria-hidden="true" />}
          {busy ? 'Đang chuẩn bị mục tiêu và câu hỏi…' : 'Bắt đầu phỏng vấn'}
        </Button>
      </footer>
    </section>
  );
}
