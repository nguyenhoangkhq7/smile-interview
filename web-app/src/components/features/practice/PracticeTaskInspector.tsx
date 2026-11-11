'use client';

import { useState, type FormEvent } from 'react';
import { CircleCheck, ClipboardList, Pencil, StickyNote, Trash2, X } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { studyTaskStatuses, studyTaskTones, type StudyTask, type StudyTaskUpdate } from './studyPlan';
import { StudyTaskChecklist, type StudyTaskChecklistActions } from './StudyTaskChecklist';
import { StudyTaskResources, type StudyTaskResourceActions } from './StudyTaskResources';

interface PracticeTaskInspectorProps {
  task: StudyTask;
  className?: string;
  disabled: boolean;
  skillIds: readonly string[];
  onUpdate: (update: StudyTaskUpdate) => Promise<boolean>;
  onDelete: () => void;
  checklist: StudyTaskChecklistActions;
  resources: StudyTaskResourceActions;
  onClose?: () => void;
}

export function PracticeTaskInspector({ task, className, disabled, skillIds, onUpdate, onDelete, checklist, resources, onClose }: PracticeTaskInspectorProps) {
  const [editingNotes, setEditingNotes] = useState(false);
  const status = studyTaskStatuses.find(({ value }) => value === task.status);

  async function saveNotes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const title = String(data.get('title') ?? '').trim();
    if (!title) return;
    const saved = await onUpdate({
      title,
      skillId: String(data.get('skill') ?? '') || null,
      notes: String(data.get('notes') ?? '').trim() || null,
    });
    if (saved) setEditingNotes(false);
  }

  return (
    <aside aria-label="Chi tiết đầu việc" className={cn('flex min-h-0 min-w-0 flex-col bg-card', className)}>
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 sm:px-5">
        <h2 className="flex items-center gap-2 text-sm font-bold tracking-wide uppercase">
          <ClipboardList size={18} className="text-(--practice-primary)" aria-hidden="true" /> Chi tiết / Ghi chú
        </h2>
        {onClose && <Button type="button" variant="ghost" size="icon-sm" aria-label="Đóng chi tiết đầu việc" onClick={onClose}>
          <X aria-hidden="true" />
        </Button>}
      </div>
      <div role="region" aria-label="Nội dung ghi chú và đầu việc" tabIndex={0}
        className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4 text-sm focus-visible:outline-2 focus-visible:-outline-offset-2 sm:px-5 xl:[scrollbar-gutter:stable]">
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5 text-xs font-semibold">
            {task.skillId && <span className="rounded-md bg-(--practice-orange)/60 px-2 py-0.5 text-(--practice-primary)">Kỹ năng: {skillLabel(task.skillId)}</span>}
            <span className={cn('rounded-full px-2 py-0.5', studyTaskTones[task.status].badge)}>{status?.label}</span>
          </div>
          <h3 className="text-lg leading-snug font-bold [overflow-wrap:anywhere]">{task.title}</h3>
        </div>
        <div role="group" aria-label="Trạng thái hiện tại" className="space-y-2 rounded-xl bg-(--practice-pale) p-3">
          <p className="text-xs font-semibold">Trạng thái hiện tại</p>
          <div className="grid grid-cols-3 gap-1.5">
            {studyTaskStatuses.map(({ value, label }) => (
              <button key={value} type="button" aria-pressed={value === task.status} disabled={disabled}
                onClick={() => { if (value !== task.status) void onUpdate({ status: value }); }}
                className={cn('cursor-pointer rounded-lg px-1 py-1.5 text-xs font-semibold focus-visible:outline-2',
                  value === task.status ? studyTaskTones[value].badge : 'bg-card text-(--practice-muted) hover:bg-(--practice-blue)')}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <section className="space-y-2 rounded-xl border border-(--practice-blue-strong) bg-(--practice-pale)/65 p-3">
          <h4 className="flex items-center gap-1.5 font-semibold">
            <StickyNote size={15} className="text-(--practice-primary)" aria-hidden="true" /> Ghi chú trọng tâm
          </h4>
          {editingNotes ? (
            <form onSubmit={saveNotes} className="space-y-2">
              <fieldset disabled={disabled} className="space-y-2">
                <Input aria-label="Tên đầu việc" name="title" required pattern=".*\S.*" maxLength={255} defaultValue={task.title} />
                <select aria-label="Kỹ năng liên quan" name="skill" defaultValue={task.skillId ?? ''} className="w-full rounded-lg border bg-card p-2">
                  <option value="">Không chọn kỹ năng</option>
                  {skillIds.map((id) => <option key={id} value={id}>{skillLabel(id)}</option>)}
                </select>
                <Textarea autoFocus aria-label="Ghi chú ôn tập" name="notes" rows={4} maxLength={10000} defaultValue={task.notes ?? ''} />
                <div className="flex justify-end gap-2">
                  <Button type="button" size="sm" variant="ghost" onClick={() => setEditingNotes(false)}>Hủy</Button>
                  <Button type="submit" size="sm" className="bg-(--practice-primary)">Lưu đầu việc</Button>
                </div>
              </fieldset>
            </form>
          ) : <p className="text-sm leading-relaxed whitespace-pre-wrap text-(--practice-muted) wrap-anywhere">
            {task.notes || 'Chưa có ghi chú.'}
          </p>}
        </section>
        <StudyTaskChecklist items={task.checklist} actions={checklist} disabled={disabled} />
        <StudyTaskResources items={task.resources} actions={resources} disabled={disabled} />
      </div>
      <div className="shrink-0 space-y-1.5 border-t border-slate-100 px-4 py-3 sm:px-5">
        {task.status !== 'DONE' && (
          <Button type="button" className="w-full rounded-full bg-(--practice-primary) hover:bg-(--practice-primary-hover)"
            disabled={disabled} onClick={() => void onUpdate({ status: 'DONE' })}>
            <CircleCheck aria-hidden="true" /> Chuyển sang Đã xong
          </Button>
        )}
        <div className="flex justify-between gap-2">
          {!editingNotes && (
            <Button type="button" variant="ghost" className="flex-1 rounded-full" disabled={disabled} onClick={() => setEditingNotes(true)}>
              <Pencil aria-hidden="true" /> Sửa đầu việc
            </Button>
          )}
          <Button type="button" variant="ghost" size="icon" aria-label="Xóa đầu việc" disabled={disabled} onClick={onDelete}>
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
