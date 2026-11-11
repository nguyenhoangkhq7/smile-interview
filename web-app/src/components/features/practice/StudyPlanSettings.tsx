'use client';

import { useState, type FormEvent } from 'react';
import { CalendarDays, ChevronDown, Flag, Pencil, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { finishedAttempt } from '@/components/features/applications/applicationUi';
import type { InterviewAttempt } from '@/services/applicationProfiles';
import type { StudyPlanDetails } from '@/services/studyPlans';
import { formatStudyPercent, suggestedStudyTarget } from './studyPlan';

export function StudyPlanSettings({ plan, attempts, disabled, onSave }: {
  plan: StudyPlanDetails;
  attempts: readonly InterviewAttempt[];
  disabled: boolean;
  onSave: (input: StudyPlanDetails) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [targetDraft, setTargetDraft] = useState(String(plan.targetCompletionPercent));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (field: string) => String(data.get(field) ?? '').trim();
    const title = value('title');
    if (!title) return;
    const saved = await onSave({
      title,
      description: value('description') || null,
      targetCompletionPercent: Number(value('target')),
      targetDate: value('date') || null,
      sourceSessionId: value('source') || null,
    });
    if (saved) setEditing(false);
  }

  const sources = attempts.filter((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);

  return (
    <section className="rounded-2xl border border-slate-100 bg-card p-4 shadow-xs sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-(--practice-orange) text-(--practice-primary)">
            <Settings2 size={19} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-bold">Thiết lập kế hoạch</h2>
            {!editing && plan.targetDate && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-(--practice-muted)">
                <CalendarDays size={14} aria-hidden="true" />
                Ngày mục tiêu: {plan.targetDate.split('-').reverse().join('/')}
              </p>
            )}
            {!editing && plan.description && (
              <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-(--practice-muted) [overflow-wrap:anywhere]">{plan.description}</p>
            )}
          </div>
        </div>
        {!editing && <Button type="button" variant="outline" disabled={disabled} onClick={() => {
          setTargetDraft(String(plan.targetCompletionPercent));
          setEditing(true);
        }}><Pencil aria-hidden="true" />Chỉnh sửa kế hoạch</Button>}
      </div>
      {editing && (
        <form className="mt-5 border-t border-(--practice-blue) pt-5" onSubmit={submit}>
          <fieldset disabled={disabled} className="min-w-0 space-y-5 text-sm">
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
              <div className="grid gap-4">
                <label className="grid gap-1.5">
                  <span className="font-medium">Tên kế hoạch</span>
                  <Input className="h-10 rounded-xl bg-card px-3" name="title" required pattern=".*\S.*" maxLength={255} defaultValue={plan.title} />
                </label>
                <label className="grid gap-1.5">
                  <span className="font-medium">Phiên phỏng vấn nguồn</span>
                  <span className="relative">
                    <select name="source" className="h-10 w-full appearance-none rounded-xl border border-input bg-card py-2 pl-3 pr-9 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" defaultValue={plan.sourceSessionId ?? ''}>
                      <option value="">Tổng hợp các lượt đã kết thúc</option>
                      {sources.map((attempt) => <option key={attempt.id} value={attempt.id}>Lượt {attempt.number}</option>)}
                      {plan.sourceSessionId && !sources.some((attempt) => attempt.id === plan.sourceSessionId)
                        && <option value={plan.sourceSessionId}>Phiên đã chọn</option>}
                    </select>
                    <ChevronDown size={16} aria-hidden="true" className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-(--practice-muted)" />
                  </span>
                </label>
                <label className="grid gap-1.5">
                  <span className="font-medium">Mô tả kế hoạch <span className="font-normal text-(--practice-muted)">(tùy chọn)</span></span>
                  <Textarea className="min-h-24 resize-y rounded-xl bg-card px-3 py-2.5" name="description" rows={3} maxLength={10000}
                    placeholder="Ví dụ: Ôn lại SQL và luyện giải thích các quyết định kỹ thuật." defaultValue={plan.description ?? ''} />
                </label>
              </div>
              <div className="grid gap-4 rounded-2xl bg-(--practice-pale) p-4 sm:p-5">
                <h3 className="flex items-center gap-2 font-semibold">
                  <Flag size={17} className="text-(--practice-primary)" aria-hidden="true" />
                  Mục tiêu ôn tập
                </h3>
                <div className="grid gap-2">
                  <label className="grid gap-1.5">
                    <span className="font-medium">Mục tiêu hoàn thành (%)</span>
                    <Input className="h-10 rounded-xl bg-card px-3 tabular-nums" name="target" type="number" min={0} max={100} step="0.01" required
                      value={targetDraft} onChange={(event) => setTargetDraft(event.target.value)} />
                  </label>
                  <p className="text-xs leading-5 text-(--practice-muted)">
                    Hệ thống gợi ý hoàn thành {formatStudyPercent(suggestedStudyTarget)} số đầu việc trước buổi phỏng vấn tiếp theo.
                  </p>
                  <Button type="button" size="sm" variant="outline" className="w-fit rounded-full"
                    onClick={() => setTargetDraft(String(suggestedStudyTarget))}>
                    Dùng mức gợi ý {formatStudyPercent(suggestedStudyTarget)}
                  </Button>
                </div>
                <label className="grid gap-1.5">
                  <span className="font-medium">Ngày mục tiêu <span className="font-normal text-(--practice-muted)">(tùy chọn)</span></span>
                  <Input className="h-10 rounded-xl bg-card px-3" name="date" type="date" defaultValue={plan.targetDate ?? ''} />
                </label>
              </div>
            </div>
            <div className="flex flex-wrap justify-end gap-2 border-t border-(--practice-blue) pt-4">
              <Button type="button" variant="outline" className="h-10 rounded-full px-5" onClick={() => setEditing(false)}>Hủy</Button>
              <Button type="submit" className="h-10 rounded-full bg-(--practice-primary) px-5 text-white hover:bg-(--practice-primary-hover)">Lưu kế hoạch</Button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}
