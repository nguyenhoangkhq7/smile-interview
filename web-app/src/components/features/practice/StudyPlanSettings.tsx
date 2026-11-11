'use client';

import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { finishedAttempt } from '@/components/features/applications/applicationUi';
import type { InterviewAttempt } from '@/services/applicationProfiles';
import type { StudyPlanDetails } from '@/services/studyPlans';

export function StudyPlanSettings({ plan, attempts, disabled, onSave }: {
  plan: StudyPlanDetails;
  attempts: readonly InterviewAttempt[];
  disabled: boolean;
  onSave: (input: StudyPlanDetails) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);

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
    <section className="rounded-2xl border border-slate-100 bg-card p-4 shadow-xs sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-bold">Thiết lập kế hoạch</h2>
          {plan.targetDate && <p className="text-sm text-(--practice-muted)">Ngày mục tiêu: {plan.targetDate.split('-').reverse().join('/')}</p>}
          {plan.description && <p className="whitespace-pre-wrap text-sm text-(--practice-muted) [overflow-wrap:anywhere]">{plan.description}</p>}
        </div>
        {!editing && <Button type="button" variant="outline" disabled={disabled} onClick={() => setEditing(true)}>Chỉnh sửa kế hoạch</Button>}
      </div>
      {editing && (
        <form className="mt-4 space-y-3" onSubmit={submit}>
          <fieldset disabled={disabled} className="grid gap-3 text-sm sm:grid-cols-2">
            <label className="space-y-1 sm:col-span-2">
              <span className="font-medium">Tên kế hoạch</span>
              <Input name="title" required pattern=".*\S.*" maxLength={255} defaultValue={plan.title} />
            </label>
            <label className="space-y-1">
              <span className="font-medium">Mục tiêu hoàn thành (%)</span>
              <Input name="target" type="number" min={0} max={100} step="0.01" required defaultValue={plan.targetCompletionPercent} />
            </label>
            <label className="space-y-1">
              <span className="font-medium">Ngày mục tiêu</span>
              <Input name="date" type="date" defaultValue={plan.targetDate ?? ''} />
            </label>
            <label className="space-y-1 sm:col-span-2">
              <span className="font-medium">Phiên phỏng vấn nguồn</span>
              <select name="source" className="w-full rounded-lg border bg-card px-3 py-2" defaultValue={plan.sourceSessionId ?? ''}>
                <option value="">Tổng hợp các lượt đã kết thúc</option>
                {sources.map((attempt) => <option key={attempt.id} value={attempt.id}>Lượt {attempt.number}</option>)}
                {plan.sourceSessionId && !sources.some((attempt) => attempt.id === plan.sourceSessionId)
                  && <option value={plan.sourceSessionId}>Phiên đã chọn</option>}
              </select>
            </label>
            <label className="space-y-1 sm:col-span-2">
              <span className="font-medium">Mô tả kế hoạch</span>
              <Textarea name="description" rows={2} maxLength={10000} defaultValue={plan.description ?? ''} />
            </label>
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button type="button" variant="outline" onClick={() => setEditing(false)}>Hủy</Button>
              <Button type="submit" className="bg-(--practice-primary)">Lưu kế hoạch</Button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}
