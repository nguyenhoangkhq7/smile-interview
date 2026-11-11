'use client';

import { useState, type DragEvent, type RefObject } from 'react';
import { CircleCheck, GripVertical, ListChecks } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { cn } from '@/lib/utils';
import { studyTaskStatuses, studyTaskTones, type StudyTask, type StudyTaskStatus } from './studyPlan';
import styles from './practice.module.css';
import { useStudyTaskDrag } from './useStudyTaskDrag';
import { studyGapDragType, type StudyGap } from './StudyGapCard';

interface StudyKanbanProps {
  tasks: readonly StudyTask[];
  selectedTaskId: number | null;
  disabled: boolean;
  completedTaskId: number | null;
  onSelect: (id: number) => void;
  onMove: (task: StudyTask, status: StudyTaskStatus, beforeTaskId?: number | null) => Promise<boolean>;
  gapSource: RefObject<StudyGap | null>;
  onGapDrop: (gap: StudyGap, status: StudyTaskStatus) => Promise<boolean>;
}

interface StudyTaskCardProps {
  task: StudyTask;
  statusLabel: string;
  selected: boolean;
  dragging: boolean;
  draggable: boolean;
  justCompleted: boolean;
  onSelect: () => void;
  onDragStart: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd: () => void;
}

function StudyTaskCard({ task, statusLabel, selected, dragging, draggable, justCompleted, onSelect, onDragStart, onDragEnd }: StudyTaskCardProps) {
  const tone = studyTaskTones[task.status];
  const completed = task.checklist.filter((item) => item.isCompleted).length;
  const checklistLabel = task.checklist.length ? `${completed}/${task.checklist.length} mục checklist hoàn thành` : 'Chưa có checklist';

  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={task.title}
      data-completed={justCompleted || undefined}
      draggable={draggable}
      onClick={onSelect}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        styles.kanbanCard,
        'group block w-full min-w-0 rounded-xl border bg-card p-2.5 text-left shadow-xs select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--practice-primary) sm:p-3',
        draggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer',
        selected ? 'border-(--practice-primary) ring-2 ring-(--practice-orange)' : 'border-slate-200 hover:border-(--practice-primary)/40',
        dragging && 'opacity-45',
      )}
    >
      <span className="mb-2 flex items-start justify-between gap-1.5">
        <span className="flex min-w-0 items-center gap-1.5">
          {task.status === 'DONE' ? <CircleCheck size={13} className="shrink-0" style={{ color: tone.color }} aria-hidden="true" />
            : <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: tone.color }} aria-hidden="true" />}
          {task.skillId && (
            <span className="min-w-0 rounded-md bg-(--practice-pale) px-1.5 py-0.5 text-[11px] font-medium wrap-anywhere">
              {skillLabel(task.skillId)}
            </span>
          )}
        </span>
        <GripVertical size={15} aria-hidden="true" className="shrink-0 text-slate-400 group-hover:text-(--practice-muted)" />
      </span>
      <span title={task.title} className={cn('line-clamp-2 text-sm leading-snug font-semibold wrap-anywhere', selected && 'text-(--practice-primary)')}>
        {task.title}
      </span>
      <span className="mt-2 flex flex-wrap items-center justify-between gap-1.5 border-t border-slate-100 pt-2 text-[11px]">
        <span className={cn('rounded-md px-1.5 py-0.5 font-medium', tone.badge)}>{statusLabel}</span>
        <span className="inline-flex items-center gap-1 text-(--practice-muted)" title={checklistLabel}>
          <ListChecks size={13} aria-hidden="true" /> {completed}/{task.checklist.length}
        </span>
      </span>
    </button>
  );
}

export function StudyKanban({ tasks, selectedTaskId, disabled, completedTaskId, onSelect, onMove, gapSource, onGapDrop }: StudyKanbanProps) {
  const { draggingId, dropStatus, savingStatus, announcement, arrival, startDrag, finishDrag, dragOver, dragLeave, drop, finishArrival } =
    useStudyTaskDrag({ disabled, onSelect, onMove });
  const [insertion, setInsertion] = useState<{ status: StudyTaskStatus; beforeId: number | null }>();
  const [gapTarget, setGapTarget] = useState<StudyTaskStatus | null>(null);

  function getInsertion(event: DragEvent<HTMLElement>) {
    const cards = event.currentTarget.querySelectorAll<HTMLLIElement>('[data-kanban-task-id]');
    for (const card of cards) {
      const id = Number(card.dataset.kanbanTaskId);
      const bounds = card.firstElementChild?.getBoundingClientRect();
      if (id !== draggingId && bounds && event.clientY < bounds.top + bounds.height / 2) return id;
    }
    return null;
  }
  return (
    <div className="grid min-h-0 flex-1 gap-2.5 sm:grid-cols-3 xl:grid-rows-[minmax(0,1fr)]">
      <p role="status" className="sr-only">{announcement}</p>
      {studyTaskStatuses.map(({ value: status, label }) => {
        const columnTasks = tasks.filter((task) => task.status === status);
        const isTarget = !disabled && (dropStatus === status || gapTarget === status);
        const isSaving = savingStatus === status;
        return (
          <section key={status} aria-label={label}
            aria-busy={isSaving || undefined}
            data-drop-active={isTarget || isSaving || undefined}
            onDragOver={(event) => {
              if (!disabled && gapSource.current && event.dataTransfer.types.includes(studyGapDragType)) {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'copy';
                setGapTarget(status);
                return;
              }
              if (!dragOver(event, status, true)) return;
              const beforeId = getInsertion(event);
              setInsertion((current) => current?.status === status && current.beforeId === beforeId ? current : { status, beforeId });
            }}
            onDragLeave={(event) => {
              if (!(event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget))) {
                setGapTarget((current) => current === status ? null : current);
              }
              dragLeave(event, status);
            }}
            onDrop={(event) => {
              if (event.dataTransfer.types.includes(studyGapDragType)) {
                event.preventDefault();
                const gap = gapSource.current;
                gapSource.current = null;
                setGapTarget(null);
                if (!disabled && gap && event.dataTransfer.getData(studyGapDragType) === gap.skillId) {
                  void onGapDrop(gap, status);
                }
                return;
              }
              const beforeId = insertion?.status === status ? insertion.beforeId : getInsertion(event);
              const sourceIndex = columnTasks.findIndex((task) => task.id === draggingId);
              setInsertion(undefined);
              if (sourceIndex >= 0 && (columnTasks[sourceIndex + 1]?.id ?? null) === beforeId) {
                event.preventDefault();
                finishDrag();
                return;
              }
              void drop(event, status, label, beforeId);
            }}
            className={cn(
              styles.kanbanColumn,
              'flex min-h-0 min-w-0 flex-col gap-2 rounded-xl border p-2.5',
              (isTarget || isSaving) ? 'border-(--practice-primary) bg-(--practice-orange)/35' : 'border-transparent bg-(--practice-pale)',
            )}>
            <div className="flex shrink-0 items-center justify-between gap-1">
              <h3 className="flex items-center gap-1.5 text-[11px] font-bold tracking-wide uppercase">
                <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: studyTaskTones[status].color }} aria-hidden="true" />
                {label}
              </h3>
              <span className="rounded-full bg-card px-2 py-0.5 text-xs tabular-nums text-(--practice-muted) shadow-xs">{columnTasks.length}</span>
            </div>
            {columnTasks.length ? (
              <ul tabIndex={0} aria-label={`Đầu việc: ${label}`}
                className="min-h-0 space-y-2 rounded-lg focus-visible:outline-2 xl:overflow-y-auto xl:p-0.5">
                {columnTasks.map((task) => (
                  <li key={task.id}
                    data-kanban-task-id={task.id}
                    data-insert-before={isTarget && insertion?.status === status && insertion.beforeId === task.id || undefined}
                    data-arrival={arrival?.id === task.id && arrival.status === status ? arrival.direction : undefined}
                    className={cn(styles.kanbanCardSlot, styles.kanbanInsertion)}
                    onAnimationEnd={(event) => {
                      if (event.target === event.currentTarget) {
                        finishArrival(task);
                      }
                    }}>
                    <StudyTaskCard task={task} statusLabel={label} selected={selectedTaskId === task.id}
                      dragging={draggingId === task.id} draggable={!disabled} justCompleted={task.id === completedTaskId} onSelect={() => onSelect(task.id)}
                      onDragStart={(event) => startDrag(event, task)} onDragEnd={() => { setInsertion(undefined); finishDrag(); }} />
                  </li>
                ))}
                <li aria-hidden="true" className={styles.kanbanEndInsertion}
                  data-insert-before={isTarget && insertion?.status === status && insertion.beforeId === null || undefined} />
              </ul>
            ) : (
              <p className="grid min-h-16 flex-1 place-items-center rounded-lg border border-dashed border-(--practice-blue-strong) bg-card/65 px-2 py-2 text-center text-xs text-(--practice-muted) sm:min-h-40 xl:min-h-0">
                {isSaving ? 'Đang chuyển…' : isTarget ? 'Thả vào đây' : 'Chưa có đầu việc'}
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}
