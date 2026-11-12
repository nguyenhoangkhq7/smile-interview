'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { Check, Pencil } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { ObjectiveSuggestion, CriterionSuggestion } from '@/services/studyPlans';
import type { NewStudyTask, StudyTaskStatus } from './studyPlan';

const labels: Record<CriterionSuggestion['kind'], string> = {
  REVIEW: 'Cần ôn', VERIFY: 'Cần thử lại', REINFORCE: 'Củng cố thêm', UNASSESSED: 'Chưa đánh giá', MET: 'Đã đạt',
};

function studyReason(item: CriterionSuggestion) {
  switch (item.kind) {
    case 'REVIEW': return 'Trong phần trả lời phỏng vấn, bạn chưa làm được đầy đủ nội dung này.';
    case 'VERIFY': return item.assessment === 'NEEDS_VERIFICATION'
      ? 'Kết quả các lần kiểm tra chưa nhất quán. Bạn nên thực hành thêm rồi thử trả lời lại.'
      : 'Câu trả lời trước chưa đủ rõ để biết bạn đã làm được nội dung này hay chưa.';
    case 'REINFORCE': return 'Bạn đã đạt yêu cầu. Luyện thêm sẽ giúp bạn tự thực hiện vững hơn.';
    case 'UNASSESSED': return 'Nội dung này chưa được kiểm tra trong buổi phỏng vấn. Bạn có thể chủ động ôn trước.';
    case 'MET': return 'Bạn đã làm được nội dung này trong phần trả lời phỏng vấn. Có thể ôn lại nếu cần.';
  }
}

function studyGoals(goal: string) {
  return goal.split(/[;\n]+/).map(value => value.trim()
    .replace(/\bloading\b/gi, 'trạng thái đang tải')
    .replace(/\berror state\b/gi, 'trạng thái lỗi')).filter(Boolean);
}

export function StudyGapTaskDialog({ objective, status, disabled, onCreate, onClose }: {
  objective: ObjectiveSuggestion;
  status: StudyTaskStatus;
  disabled: boolean;
  onCreate: (task: NewStudyTask) => Promise<boolean>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(`Ôn luyện: ${objective.claim}`.slice(0, 255));
  const [items, setItems] = useState(() => objective.criteria.map(criterion => ({
    ...criterion, selected: criterion.selectedByDefault, content: criterion.description.slice(0, 500),
  })));
  const [notes, setNotes] = useState('');
  const [failed, setFailed] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const selected = items.filter(item => item.selected);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || !title.trim() || !selected.length || selected.some(item => !item.content.trim())) return;
    setFailed(false);
    const referenceUrl = objective.source
      ? new URL(`/interview/session/${encodeURIComponent(objective.source.sessionId)}/result`, window.location.origin).href : undefined;
    const saved = await onCreate({
      title: title.trim(), skillId: objective.skillId, status,
      notes: [notes.trim(), ...selected.map(item => [`Nội dung ôn: ${item.content.trim()}`,
        `Vì sao nên ôn: ${studyReason(item)}`,
        item.goal ? `Sau khi ôn, bạn cần làm được:\n${studyGoals(item.goal).map(goal => `- ${goal}`).join('\n')}` : '',
      ].filter(Boolean).join('\n'))].filter(Boolean).join('\n\n').slice(0, 10000),
      checklist: selected.map(item => item.content.trim()),
      checklistOrigins: selected.map(item => ({ sourceCriterionId: item.criterionId,
        sourceSessionId: item.source?.sessionId, sourceAttemptNumber: item.source?.attemptNumber })),
      referenceUrl,
      gapOrigin: { skillId: objective.skillId, objectiveId: objective.objectiveId,
        sessionId: objective.source?.sessionId, attemptNumber: objective.source?.attemptNumber },
    });
    if (saved) onClose();
    else setFailed(true);
  }

  return <Dialog open onOpenChange={open => { if (!open && !disabled) onClose(); }}>
    <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden rounded-2xl p-0 sm:max-w-xl">
      <div className="space-y-1 border-b px-5 py-4 pr-12">
        <DialogTitle>Tạo đầu việc ôn tập</DialogTitle>
        <DialogDescription>{skillLabel(objective.skillId)}</DialogDescription>
      </div>
      <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <fieldset disabled={disabled} className="min-w-0 space-y-5 px-5 py-4">
            <label className="block space-y-1.5 text-sm font-medium">Tên đầu việc
              <Input required maxLength={255} value={title} onChange={event => setTitle(event.target.value)} />
            </label>
            <div className="space-y-2">
            <p className="text-sm font-semibold">Nội dung ôn tập ({selected.length}/{items.length})</p>
            <div className="divide-y rounded-xl border">
              {items.map((item, index) => <div key={item.criterionId} className="space-y-2 px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2 text-sm">
                    <input type="checkbox" checked={item.selected} aria-label={`Ôn ${item.description}`}
                      className="mt-0.5 size-4 shrink-0 accent-(--practice-primary)"
                      onChange={event => setItems(current => current.map((value, i) => i === index ? { ...value, selected: event.target.checked } : value))} />
                    <span className="min-w-0 flex-1 wrap-anywhere">{item.content || item.description}</span>
                  </label>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{labels[item.kind]}</span>
                  {item.selected && <Button type="button" variant="ghost" size="icon-xs"
                    aria-label={`Sửa nội dung ${item.description}`} aria-expanded={editingId === item.criterionId}
                    onClick={() => setEditingId(current => current === item.criterionId ? null : item.criterionId)}>
                    {editingId === item.criterionId ? <Check size={13} /> : <Pencil size={13} />}
                  </Button>}
                </div>
                {item.selected && editingId === item.criterionId && <Input autoFocus required maxLength={500}
                  aria-label={`Nội dung checklist ${item.description}`} value={item.content}
                  onChange={event => setItems(current => current.map((value, i) => i === index ? { ...value, content: event.target.value } : value))} />}
              </div>)}
            </div>
            </div>
            <details className="text-xs">
              <summary className="w-fit cursor-pointer text-muted-foreground hover:text-foreground">Thông tin thêm</summary>
              <div className="mt-3 space-y-4">
                {selected.map(item => <div key={item.criterionId} className="space-y-3 rounded-lg bg-muted/40 p-3 leading-5">
                  <p className="font-medium">{item.content || item.description}</p>
                  <div className="space-y-1">
                    <p className="font-medium">Vì sao nên ôn?</p>
                    <p className="text-muted-foreground">{studyReason(item)}</p>
                  </div>
                  {item.goal && <div className="space-y-1">
                    <p className="font-medium">Sau khi ôn, bạn cần làm được:</p>
                    <ul className="list-disc space-y-1 pl-4 text-muted-foreground">
                      {studyGoals(item.goal).map((goal, index) => <li key={index}>{goal}</li>)}
                    </ul>
                  </div>}
                  {item.source && <Link href={`/interview/session/${encodeURIComponent(item.source.sessionId)}/result`} target="_blank"
                    className="inline-block font-medium text-(--practice-primary) hover:underline">Xem lại kết quả phỏng vấn · Lượt {item.source.attemptNumber}</Link>}
                </div>)}
                <label className="block space-y-1.5 font-medium">Ghi chú thêm
                  <Textarea value={notes} onChange={event => setNotes(event.target.value)} maxLength={2000} rows={2} />
                </label>
              </div>
            </details>
          </fieldset>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t bg-card px-5 py-3">
          {failed && <p role="alert" className="mr-auto text-xs text-destructive">Không tạo được đầu việc. Hãy thử lại.</p>}
          {!selected.length && <p role="status" className="mr-auto text-xs text-muted-foreground">Chọn ít nhất một tiêu chí để tạo checklist.</p>}
          <DialogClose render={<Button variant="outline" type="button" disabled={disabled} />}>Hủy</DialogClose>
          <Button type="submit" disabled={disabled || !selected.length || !title.trim() || selected.some(item => !item.content.trim())}>{disabled ? 'Đang lưu…' : `Tạo đầu việc · ${selected.length} mục`}</Button>
        </div>
      </form>
    </DialogContent>
  </Dialog>;
}
