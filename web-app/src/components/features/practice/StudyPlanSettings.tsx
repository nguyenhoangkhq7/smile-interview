'use client';

import { type FormEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { finishedAttempt } from '@/components/features/applications/applicationUi';
import type { InterviewAttempt } from '@/services/applicationProfiles';
import type { StudyPlanDetails } from '@/services/studyPlans';

export function StudyPlanSettings({ plan, attempts, disabled, onSave, onClose }: {
  plan: StudyPlanDetails;
  attempts: readonly InterviewAttempt[];
  disabled: boolean;
  onSave: (input: StudyPlanDetails) => Promise<boolean>;
  onClose: () => void;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (field: string) => String(data.get(field) ?? '').trim();
    const title = value('title');
    if (!title) return;
    const saved = await onSave({
      title,
      description: value('description') || null,
      targetCompletionPercent: plan.targetCompletionPercent,
      targetDate: value('date') || null,
      sourceSessionId: value('source') || null,
    });
    if (saved) onClose();
  }

  const sources = attempts.filter((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);

  return (
    <DialogContent className="max-h-[90dvh] max-w-xl overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Thiết lập kế hoạch</DialogTitle>
        <DialogDescription>Chỉnh tên, mô tả, ngày mục tiêu và phiên phỏng vấn dùng để tổng hợp kỹ năng.</DialogDescription>
      </DialogHeader>
        <form onSubmit={submit}>
          <fieldset disabled={disabled} className="min-w-0 space-y-4 text-sm">
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
              <label className="grid gap-1.5">
                <span className="font-medium">Ngày mục tiêu <span className="font-normal text-(--practice-muted)">(tùy chọn)</span></span>
                <Input className="h-10 rounded-xl bg-card px-3" name="date" type="date" defaultValue={plan.targetDate ?? ''} />
              </label>
              </div>
            <div className="flex flex-wrap justify-end gap-2 border-t border-(--practice-blue) pt-4">
              <Button type="button" variant="outline" className="h-10 rounded-full px-5" onClick={onClose}>Hủy</Button>
              <Button type="submit" className="h-10 rounded-full bg-(--practice-primary) px-5 text-white hover:bg-(--practice-primary-hover)">Lưu kế hoạch</Button>
            </div>
          </fieldset>
        </form>
    </DialogContent>
  );
}
