'use client';

import { useEffect, useState, type KeyboardEvent } from 'react';
import { Check, CheckCircle2, Circle, FileText, ListChecks, Paperclip, Sparkles, Tag, View, X } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { studyTaskStatuses, studyTaskTones, type StudyTask, type StudyTaskStatus, type StudyTaskUpdate } from './studyPlan';

interface TaskModalTopBarProps {
  task: StudyTask;
  onClose: () => void;
}

export function TaskModalTopBar({ task, onClose }: TaskModalTopBarProps) {
  const currentStatus = studyTaskStatuses.find(({ value }) => value === task.status);
  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-100 dark:border-border bg-card px-5 py-3.5 sm:px-6">
      <div className="flex min-w-0 items-center gap-2 text-xs text-(--practice-muted)">
        <View size={16} className="shrink-0 text-(--practice-primary)" aria-hidden="true" />
        <span className="truncate">
          Trong danh sách:{' '}
          <span className="font-semibold text-foreground underline decoration-slate-300 underline-offset-4">
            {currentStatus?.label}
          </span>
        </span>
      </div>

      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Đóng cửa sổ chi tiết đầu việc (Esc)"
        title="Đóng (Esc)"
        onClick={onClose}
        className="rounded-full text-(--practice-muted) hover:bg-red-50 hover:text-destructive"
      >
        <X size={18} aria-hidden="true" />
      </Button>
    </div>
  );
}

interface TaskModalHeaderProps {
  task: StudyTask;
  disabled: boolean;
  onUpdate: (update: StudyTaskUpdate) => Promise<boolean>;
  onFocusChecklist: () => void;
  onFocusSkill: () => void;
  onFocusResources: () => void;
}

export function TaskModalHeader({
  task,
  disabled,
  onUpdate,
  onFocusChecklist,
  onFocusSkill,
  onFocusResources,
}: TaskModalHeaderProps) {
  const [titleDraft, setTitleDraft] = useState(task.title);
  const [savingTitle, setSavingTitle] = useState(false);

  useEffect(() => {
    setTitleDraft(task.title);
  }, [task.id, task.title]);

  const currentStatus = studyTaskStatuses.find(({ value }) => value === task.status);
  const isDone = task.status === 'DONE';

  async function commitTitle() {
    const trimmed = titleDraft.trim();
    if (!trimmed) {
      setTitleDraft(task.title);
      return;
    }
    if (trimmed === task.title || savingTitle || disabled) return;
    setSavingTitle(true);
    try {
      const ok = await onUpdate({ title: trimmed });
      if (!ok) setTitleDraft(task.title);
    } finally {
      setSavingTitle(false);
    }
  }

  function handleTitleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      event.currentTarget.blur();
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      setTitleDraft(task.title);
      event.currentTarget.blur();
    }
  }

  async function toggleDone() {
    if (disabled) return;
    const nextStatus: StudyTaskStatus = isDone ? 'IN_PROGRESS' : 'DONE';
    await onUpdate({ status: nextStatus });
  }

  return (
    <div className="flex items-start gap-3">
        <button
          type="button"
          disabled={disabled}
          onClick={() => void toggleDone()}
          aria-label={isDone ? 'Đánh dấu chưa hoàn thành' : 'Đánh dấu hoàn thành'}
          title={isDone ? 'Chuyển về Đang ôn' : 'Đánh dấu Đã xong'}
          className={cn(
            'mt-1 grid size-7 shrink-0 place-items-center rounded-full transition-all duration-200 focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-50',
            isDone
              ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
              : 'bg-slate-100 dark:bg-muted text-slate-400 dark:text-muted-foreground hover:bg-emerald-50 hover:text-emerald-600',
          )}
        >
          {isDone ? <CheckCircle2 size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}
        </button>

        <div className="min-w-0 flex-1">
          <input
            type="text"
            aria-label="Tên đầu việc"
            disabled={disabled || savingTitle}
            maxLength={255}
            value={titleDraft}
            onChange={(event) => setTitleDraft(event.target.value)}
            onBlur={() => void commitTitle()}
            onKeyDown={handleTitleKeyDown}
            className={cn(
              '-ml-2 w-full rounded-xl bg-transparent px-2 py-1 text-lg font-extrabold tracking-tight text-foreground outline-none transition-all sm:text-xl',
              'hover:bg-slate-100/70 dark:hover:bg-muted/70 focus:bg-(--practice-pale)/70 focus:ring-2 focus:ring-(--practice-primary)/25',
              isDone && 'text-(--practice-muted)',
            )}
          />

          {/* Metadata Pills */}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {task.skillId && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-(--practice-orange)/70 px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-(--practice-primary) uppercase">
                <span className="size-1.5 rounded-full bg-(--practice-primary)" aria-hidden="true" />
                Kỹ năng: {skillLabel(task.skillId)}
              </span>
            )}
            <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold', studyTaskTones[task.status].badge)}>
              {isDone && <Check size={12} aria-hidden="true" />}
              {currentStatus?.label}
            </span>
            {task.gapNeedsConfirmation && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
                <Sparkles size={12} aria-hidden="true" />
                Kỹ năng đã cải thiện · chờ xác nhận
              </span>
            )}
          </div>

          {/* Quick Action Bar */}
          <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              disabled={disabled}
              onClick={onFocusChecklist}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100/90 dark:bg-muted/90 px-2.5 py-1.5 text-xs font-semibold text-slate-700 dark:text-foreground transition-colors hover:bg-slate-200/80 dark:hover:bg-muted/80 disabled:opacity-50"
            >
              <ListChecks size={14} aria-hidden="true" />
              Việc cần làm
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={onFocusSkill}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100/90 dark:bg-muted/90 px-2.5 py-1.5 text-xs font-semibold text-slate-700 dark:text-foreground transition-colors hover:bg-slate-200/80 dark:hover:bg-muted/80 disabled:opacity-50"
            >
              <Tag size={14} aria-hidden="true" />
              Kỹ năng
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={onFocusResources}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100/90 dark:bg-muted/90 px-2.5 py-1.5 text-xs font-semibold text-slate-700 dark:text-foreground transition-colors hover:bg-slate-200/80 dark:hover:bg-muted/80 disabled:opacity-50"
            >
              <Paperclip size={14} aria-hidden="true" />
              Tài liệu
            </button>
            <span className="ml-auto hidden items-center gap-1 text-[11px] text-(--practice-muted) sm:inline-flex">
              <FileText size={12} aria-hidden="true" />
              Nhấn vào tiêu đề để sửa nhanh
            </span>
          </div>
        </div>
      </div>
  );
}
