'use client';
import { useState } from 'react';
import { MessageSquareText, Mic } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { InterviewConfig, QuestionMode, defaultConfig, questionModes } from '@/services/evidenceInterview';

export const modeLabels: Record<QuestionMode, string> = {
  CODING: 'Coding', DEBUGGING: 'Debugging', DESIGN: 'Thiết kế hệ thống',
  TECHNICAL_EXPLANATION: 'Giải thích kỹ thuật', BEHAVIORAL: 'Behavioral',
};

interface Props { busy: boolean; onStart: (config: InterviewConfig) => void }
export function EvidenceSetup({ busy, onStart }: Props) {
  const [config, setConfig] = useState(defaultConfig);
  return <section className="space-y-5 rounded-xl border p-6">
    <h1 className="text-2xl font-semibold">Chuẩn bị phỏng vấn</h1>
    <p>Câu hỏi được chọn theo công việc trong JD, kỹ năng cần kiểm chứng và thời lượng của bạn.</p>
    <p className="text-sm text-muted-foreground">Mỗi lượt tập trung vào một nội dung. Người phỏng vấn sẽ hỏi tiếp khi cần làm rõ hoặc kiểm chứng câu trả lời, trong thời lượng và số câu bạn chọn.</p>
    <fieldset disabled={busy} className="space-y-3">
      <legend className="mb-3 font-semibold">Bạn muốn phỏng vấn bằng cách nào?</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {([{ value: 'TEXT', title: 'Bằng văn bản', description: 'Đọc câu hỏi, viết câu trả lời và code theo nhịp của bạn.', icon: MessageSquareText },
          { value: 'VOICE', title: 'Bằng giọng nói', description: 'Trò chuyện với người phỏng vấn ảo. Giải thích bằng lời cả với câu hỏi lập trình, có phụ đề lời bạn nói.', icon: Mic }] as const)
          .map(({ value, title, description, icon: Icon }) => <label key={value}
            className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${config.interaction_mode === value ? 'border-brand-orange bg-brand-orange/5' : 'bg-card'}`}>
            <input className="mt-1" type="radio" name="interaction-mode" value={value} checked={config.interaction_mode === value}
              onChange={() => setConfig({ ...config, interaction_mode: value })} />
            <span className="space-y-2"><span className="flex items-center gap-2 font-semibold"><Icon size={18} />{title}</span><span className="block text-sm text-muted-foreground">{description}</span></span>
          </label>)}
      </div>
    </fieldset>
    <label className="block">Dạng phỏng vấn
      <select className="ml-3 rounded border p-2" disabled={busy} value={config.focused_question_mode ?? 'MIXED'}
        onChange={e => setConfig({ ...config, mode: e.target.value === 'MIXED' ? 'MIXED' : 'FOCUSED', focused_question_mode: e.target.value === 'MIXED' ? null : e.target.value as QuestionMode })}>
        <option value="MIXED">Tổng hợp</option>
        {questionModes.map(mode => <option key={mode} value={mode}>{modeLabels[mode]}</option>)}
      </select>
    </label>
    <label className="block">Thời lượng (phút)
      <input aria-label="Thời lượng" className="ml-3 w-24 rounded border p-2" type="number" min={1} max={120} disabled={busy}
        value={config.duration_seconds / 60} onChange={e => setConfig({ ...config, duration_seconds: Number(e.target.value) * 60 })} />
    </label>
    <label className="block">Tối đa số câu hỏi
      <input aria-label="Số câu hỏi" className="ml-3 w-24 rounded border p-2" type="number" min={1} max={40} disabled={busy}
        value={config.max_questions} onChange={e => setConfig({ ...config, max_questions: Number(e.target.value) })} />
    </label>
    <Button disabled={busy || config.max_questions < 1 || config.max_questions > 40 || config.duration_seconds < 60 || config.duration_seconds > 7200} onClick={() => onStart(config)}>
      {busy ? 'Đang chuẩn bị mục tiêu và câu hỏi…' : 'Bắt đầu phỏng vấn'}
    </Button>
  </section>;
}
