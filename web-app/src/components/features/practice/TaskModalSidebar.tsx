'use client';

import type { RefObject } from 'react';
import { CheckCircle2, Circle, Clock, ListChecks, Paperclip, RotateCcw, Tag, Trash2 } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { DeleteStudyTaskDialog } from './DeleteStudyTaskDialog';
import { studyTaskStatuses, type StudyTask, type StudyTaskStatus, type StudyTaskUpdate } from './studyPlan';

const statusIcons = {
  TODO: Circle,
  IN_PROGRESS: Clock,
  DONE: CheckCircle2,
} as const;

const statusPillStyles: Record<StudyTaskStatus, { idle: string; active: string }> = {
  TODO: {
    idle: 'border-slate-200/80 bg-card text-slate-700 hover:bg-slate-100',
    active: 'border-slate-500 bg-slate-100 text-slate-900 ring-2 ring-slate-200',
  },
  IN_PROGRESS: {
    idle: 'border-blue-200/80 bg-card text-blue-700 hover:bg-blue-50',
    active: 'border-blue-500 bg-blue-50 text-blue-900 ring-2 ring-blue-100',
  },
  DONE: {
    idle: 'border-emerald-200/80 bg-card text-emerald-700 hover:bg-emerald-50',
    active: 'border-emerald-600 bg-emerald-50 text-emerald-900 ring-2 ring-emerald-100',
  },
};

interface TaskModalSidebarProps {
  task: StudyTask;
  disabled: boolean;
  skillIds: readonly string[];
  skillSelectRef: RefObject<HTMLSelectElement | null>;
  onUpdate: (update: StudyTaskUpdate) => Promise<boolean>;
  onDelete: () => Promise<boolean>;
  onFocusChecklist: () => void;
  onFocusResources: () => void;
  onClose: () => void;
}

export function TaskModalSidebar({
  task,
  disabled,
  skillIds,
  skillSelectRef,
  onUpdate,
  onDelete,
  onFocusChecklist,
  onFocusResources,
  onClose,
}: TaskModalSidebarProps) {
  const isDone = task.status === 'DONE';

  return (
    <aside className="flex flex-col gap-5 rounded-xl border border-slate-200/70 bg-slate-50/85 p-4">
      {/* Status Switcher */}
      <div className="space-y-2">
        <span className="block px-0.5 text-[11px] font-bold tracking-wider text-(--practice-muted) uppercase">
          Trạng thái (Danh sách)
        </span>
        <div role="group" aria-label="Chuyển trạng thái đầu việc" className="flex flex-col gap-1.5">
          {studyTaskStatuses.map(({ value, label }) => {
            const Icon = statusIcons[value];
            const active = task.status === value;
            return (
              <button
                key={value}
                type="button"
                aria-pressed={active}
                disabled={disabled}
                onClick={() => {
                  if (!active) void onUpdate({ status: value });
                }}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-xs font-semibold shadow-2xs transition-all duration-150 focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-55',
                  active ? statusPillStyles[value].active : statusPillStyles[value].idle,
                )}
              >
                <Icon size={15} className="shrink-0" aria-hidden="true" />
                <span>{label}</span>
                {active && <span className="ml-auto text-[10px] font-bold uppercase opacity-75">Hiện tại</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Skill Selector */}
      <div className="space-y-2">
        <label
          htmlFor="task-modal-skill-select"
          className="flex items-center gap-1.5 px-0.5 text-[11px] font-bold tracking-wider text-(--practice-muted) uppercase"
        >
          <Tag size={12} aria-hidden="true" />
          Kỹ năng liên quan
        </label>
        <select
          ref={skillSelectRef}
          id="task-modal-skill-select"
          disabled={disabled}
          value={task.skillId ?? ''}
          onChange={(event) => void onUpdate({ skillId: event.target.value || null })}
          className="w-full cursor-pointer rounded-lg border border-slate-200/90 bg-card px-3 py-2 text-xs font-medium text-foreground shadow-2xs outline-none transition-colors hover:border-slate-300 focus-visible:ring-2 focus-visible:ring-(--practice-primary)/30 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <option value="">Không gắn kỹ năng</option>
          {skillIds.map((id) => (
            <option key={id} value={id}>
              {skillLabel(id)}
            </option>
          ))}
        </select>
      </div>

      {/* Quick Actions */}
      <div className="space-y-2">
        <span className="block px-0.5 text-[11px] font-bold tracking-wider text-(--practice-muted) uppercase">
          Thao tác
        </span>
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            disabled={disabled}
            onClick={onFocusChecklist}
            className="flex w-full items-center gap-2.5 rounded-lg bg-card px-3 py-2 text-left text-xs font-semibold text-foreground shadow-2xs ring-1 ring-slate-200/70 transition-colors hover:bg-slate-100 disabled:opacity-50"
          >
            <ListChecks size={15} className="shrink-0 text-(--practice-muted)" aria-hidden="true" />
            <span>Thêm việc cần làm</span>
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={onFocusResources}
            className="flex w-full items-center gap-2.5 rounded-lg bg-card px-3 py-2 text-left text-xs font-semibold text-foreground shadow-2xs ring-1 ring-slate-200/70 transition-colors hover:bg-slate-100 disabled:opacity-50"
          >
            <Paperclip size={15} className="shrink-0 text-(--practice-muted)" aria-hidden="true" />
            <span>Đính kèm tài liệu</span>
          </button>
          <div className="pt-1">
            <DeleteStudyTaskDialog
              title={task.title}
              disabled={disabled}
              onConfirm={onDelete}
              trigger={
                <button
                  type="button"
                  disabled={disabled}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-card px-3 py-2 text-left text-xs font-semibold text-destructive shadow-2xs ring-1 ring-slate-200/70 transition-colors hover:bg-red-50 disabled:opacity-50"
                >
                  <Trash2 size={15} className="shrink-0" aria-hidden="true" />
                  <span>Xóa đầu việc</span>
                </button>
              }
            />
          </div>
        </div>
      </div>

      {/* Bottom Primary CTA */}
      <div className="mt-auto flex flex-col gap-2 border-t border-slate-200/70 pt-4">
        {!isDone ? (
          <Button
            type="button"
            disabled={disabled}
            onClick={() => void onUpdate({ status: 'DONE' })}
            className="h-10 w-full rounded-xl bg-(--practice-primary) text-sm font-bold text-white shadow-md shadow-(--practice-primary)/20 transition-all hover:bg-(--practice-primary-hover)"
          >
            <CheckCircle2 size={17} aria-hidden="true" />
            {task.gapNeedsConfirmation ? 'Xác nhận đã xử lý' : 'Chuyển sang Đã xong'}
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => void onUpdate({ status: 'IN_PROGRESS' })}
            className="h-10 w-full rounded-xl text-sm font-semibold"
          >
            <RotateCcw size={16} aria-hidden="true" />
            Mở lại (Đang ôn)
          </Button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="w-full rounded-lg py-2 text-center text-xs font-semibold text-(--practice-muted) transition-colors hover:bg-slate-200/60 hover:text-foreground"
        >
          Đóng cửa sổ
        </button>
      </div>
    </aside>
  );
}
