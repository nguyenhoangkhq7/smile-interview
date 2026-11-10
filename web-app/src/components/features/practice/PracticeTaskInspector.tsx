'use client';

import { useState, type FormEvent } from 'react';
import { CircleCheck, ClipboardList, ExternalLink, Pencil, X } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { formatStudyPercent, getStudyReferenceUrl, studyTaskStatuses, studyTaskTones,
  type StudyTask, type StudyTaskUpdate } from './studyPlan';

interface PracticeTaskInspectorProps {
  task: StudyTask;
  onUpdate: (update: StudyTaskUpdate) => void;
  onClose?: () => void;
}

export function PracticeTaskInspector({ task, onUpdate, onClose }: PracticeTaskInspectorProps) {
  const [editingNotes, setEditingNotes] = useState(false);
  const status = studyTaskStatuses.find(({ value }) => value === task.status);
  const checklist = task.checklist ?? [];
  const completed = new Set(task.completedChecklist);
  const count = checklist.filter((_, index) => completed.has(index)).length;
  const reference = task.referenceUrl ? getStudyReferenceUrl(task.referenceUrl) : null;

  function saveNotes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onUpdate({ notes: String(data.get('notes') ?? '').trim() });
    setEditingNotes(false);
  }

  return (
    <aside aria-label="Chi tiết đầu việc" className="flex min-h-0 min-w-0 flex-col bg-card">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 sm:px-5">
        <h2 className="flex items-center gap-2 text-sm font-bold tracking-wide uppercase">
          <ClipboardList size={18} className="text-(--practice-primary)" aria-hidden="true" /> Chi tiết đầu việc
        </h2>
        {onClose && <Button type="button" variant="ghost" size="icon-sm" aria-label="Đóng chi tiết đầu việc" onClick={onClose}>
          <X aria-hidden="true" />
        </Button>}
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4 text-sm sm:px-5">
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5 text-xs font-semibold">
            {task.skillId && <span className="rounded-full bg-(--practice-orange)/60 px-2 py-0.5 text-(--practice-primary)">{skillLabel(task.skillId)}</span>}
            <span className={cn('rounded-full px-2 py-0.5', studyTaskTones[task.status].badge)}>{status?.label}</span>
          </div>
          <h3 className="text-lg leading-snug font-bold [overflow-wrap:anywhere]">{task.title}</h3>
        </div>
        <div role="group" aria-label="Trạng thái hiện tại" className="space-y-2 rounded-xl bg-(--practice-pale) p-3">
          <p className="text-xs font-semibold">Trạng thái hiện tại</p>
          <div className="grid grid-cols-3 gap-1.5">
            {studyTaskStatuses.map(({ value, label }) => (
              <button key={value} type="button" aria-pressed={value === task.status} onClick={() => onUpdate({ status: value })}
                className={cn('cursor-pointer rounded-lg px-1 py-1.5 text-xs font-semibold focus-visible:outline-2',
                  value === task.status ? studyTaskTones[value].badge : 'bg-card text-(--practice-muted) hover:bg-(--practice-blue)')}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-semibold">Danh sách kiểm tra{checklist.length > 0 && ` (${count}/${checklist.length})`}</h4>
            {checklist.length > 0 && <span className="text-xs font-semibold text-(--practice-primary)">{formatStudyPercent(count / checklist.length * 100)}</span>}
          </div>
          {checklist.length ? (
            <ul className="space-y-1.5">
              {checklist.map((item, index) => (
                <li key={index}>
                  <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-(--practice-blue-strong) px-2.5 py-2 hover:bg-(--practice-pale)">
                    <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-(--practice-primary)" checked={completed.has(index)}
                      onChange={(event) => {
                        const next = new Set(completed);
                        if (event.target.checked) next.add(index);
                        else next.delete(index);
                        onUpdate({ completedChecklist: [...next] });
                      }} />
                    <span className={cn('text-xs leading-5 [overflow-wrap:anywhere]', completed.has(index) && 'text-(--practice-muted) line-through')}>{item}</span>
                  </label>
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-(--practice-muted)">Chưa có mục kiểm tra.</p>}
        </div>
        <div className="space-y-2">
          <h4 className="font-semibold">Ghi chú ôn tập</h4>
          {editingNotes ? (
            <form onSubmit={saveNotes} className="space-y-2">
              <Textarea autoFocus aria-label="Ghi chú ôn tập" name="notes" rows={4} maxLength={2000} defaultValue={task.notes} />
              <div className="flex justify-end gap-2">
                <Button type="button" size="sm" variant="ghost" onClick={() => setEditingNotes(false)}>Hủy</Button>
                <Button type="submit" size="sm" className="bg-(--practice-primary)">Lưu ghi chú</Button>
              </div>
            </form>
          ) : <p className="rounded-xl bg-(--practice-pale) p-3 text-xs leading-5 whitespace-pre-wrap text-(--practice-muted) [overflow-wrap:anywhere]">
            {task.notes || 'Chưa có ghi chú.'}
          </p>}
        </div>
        {reference && (
          <div className="space-y-2">
            <h4 className="font-semibold">Tài liệu tham khảo</h4>
            <a href={reference} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-2 rounded-xl bg-(--practice-pale) p-3 text-xs font-medium text-(--practice-primary) hover:underline">
              Mở tài liệu tham khảo <ExternalLink size={14} aria-hidden="true" />
            </a>
          </div>
        )}
      </div>
      <div className="shrink-0 space-y-1.5 border-t border-slate-100 px-4 py-3 sm:px-5">
        {task.status !== 'DONE' && (
          <Button type="button" className="w-full rounded-full bg-(--practice-primary) hover:bg-(--practice-primary-hover)"
            onClick={() => onUpdate({ status: 'DONE' })}>
            <CircleCheck aria-hidden="true" /> Chuyển sang Đã xong
          </Button>
        )}
        {!editingNotes && (
          <Button type="button" variant="ghost" className="w-full rounded-full" onClick={() => setEditingNotes(true)}>
            <Pencil aria-hidden="true" /> {task.notes ? 'Sửa ghi chú cá nhân' : 'Thêm ghi chú cá nhân'}
          </Button>
        )}
      </div>
    </aside>
  );
}
