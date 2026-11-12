'use client';

import { useEffect, useRef, useState, type DragEvent, type RefObject } from 'react';
import { Check, Circle, CircleCheck, ListChecks, Plus, X } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { studyTaskStatuses, studyTaskTones, type NewStudyTask, type StudyTask, type StudyTaskStatus } from './studyPlan';
import styles from './practice.module.css';
import { useStudyTaskDrag } from './useStudyTaskDrag';
import { studyGapDragType, type StudyGap } from './StudyGapCard';

interface StudyKanbanProps {
  tasks: readonly StudyTask[];
  selectedTaskId: number | null;
  disabled: boolean;
  hasActiveFilters: boolean;
  completedTaskId: number | null;
  onSelect: (id: number) => void;
  onMove: (task: StudyTask, status: StudyTaskStatus, beforeTaskId?: number | null) => Promise<boolean>;
  onChangeParent: (task: StudyTask, parentTaskId: number | null, status?: StudyTaskStatus) => Promise<boolean>;
  onCreate: (task: NewStudyTask) => Promise<boolean>;
  gapSource: RefObject<StudyGap | null>;
  onGapDrop: (gap: StudyGap, status: StudyTaskStatus) => Promise<boolean>;
}

interface StudyTaskCardProps {
  task: StudyTask;
  children: readonly StudyTask[];
  childrenById: ReadonlyMap<number, readonly StudyTask[]>;
  statusLabel: string;
  selectedTaskId: number | null;
  selectedTaskPathIds: ReadonlySet<number>;
  draggingId: number | null;
  draggable: boolean;
  completedTaskId: number | null;
  nestTargetId: number | null;
  nestingTaskId: number | null;
  onSelect: (task: StudyTask) => void;
  onDragStart: (event: DragEvent<HTMLButtonElement>, task: StudyTask) => void;
  onDragEnd: () => void;
  onDropOnTask: (event: DragEvent<HTMLButtonElement>, target: StudyTask, action?: 'preview' | 'leave') => void;
  onComplete: (task: StudyTask) => void;
}

function StudyTaskCard({ task, children, childrenById, statusLabel, selectedTaskId, selectedTaskPathIds, draggingId, draggable, completedTaskId, nestTargetId, nestingTaskId, onSelect, onDragStart, onDragEnd, onDropOnTask, onComplete }: StudyTaskCardProps) {
  const tone = studyTaskTones[task.status];
  const completed = task.checklist.filter((item) => item.isCompleted).length;
  const checklistLabel = task.checklist.length ? `${completed}/${task.checklist.length} mục checklist hoàn thành` : 'Chưa có checklist';

  return (
    <div data-task-selected={selectedTaskId === task.id || undefined}
      data-task-dimmed={selectedTaskId !== null && !selectedTaskPathIds.has(task.id) || undefined}
      className={cn(styles.kanbanTaskCard, 'relative rounded-xl border bg-card p-2 shadow-xs sm:p-2.5', nestTargetId === task.id && styles.kanbanNestingTarget, nestingTaskId === task.id && styles.kanbanNestedArrival, selectedTaskId === task.id ? 'border-(--practice-primary) ring-2 ring-(--practice-orange)' : 'border-slate-200')}>
      {task.status !== 'DONE' && <button type="button"
        aria-label={task.gapNeedsConfirmation ? `Xác nhận ${task.title} đã được xử lý` : `Đánh dấu ${task.title} đã hoàn thành`}
        title={task.gapNeedsConfirmation ? 'Xác nhận đã xử lý theo kết quả phỏng vấn mới' : 'Đánh dấu hoàn thành'}
        className={cn(styles.kanbanCompleteButton, 'grid size-6 place-items-center rounded-full border border-(--practice-green) bg-card text-(--practice-green)')}
        onClick={(event) => { event.stopPropagation(); onComplete(task); }}>
        <Check size={14} strokeWidth={2.5} aria-hidden="true" />
      </button>}
      <button type="button" aria-pressed={selectedTaskId === task.id} aria-label={task.title} data-completed={completedTaskId === task.id || undefined}
        draggable={draggable} onClick={() => onSelect(task)} onDragStart={(event) => onDragStart(event, task)} onDragEnd={onDragEnd}
        onDragOver={(event) => {
          if (!draggable || draggingId == null) return;
          event.preventDefault();
          event.stopPropagation();
          event.dataTransfer.dropEffect = 'move';
          if (draggingId !== task.id) onDropOnTask(event, task, 'preview');
        }}
        onDragLeave={(event) => { if (!(event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget))) onDropOnTask(event, task, 'leave'); }}
        onDrop={(event) => onDropOnTask(event, task)}
        className={cn(styles.kanbanCard, 'relative z-0 group block w-full min-w-0 rounded-lg p-1 text-left select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--practice-primary) sm:p-1.5', draggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer', draggingId === task.id && 'opacity-45')}>
        <span className="mb-2 flex items-start justify-between gap-1.5">
          <span className="flex min-w-0 items-center gap-1.5">
            {task.status === 'DONE' ? <CircleCheck size={13} className="shrink-0" style={{ color: tone.color }} aria-hidden="true" />
              : <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: tone.color }} aria-hidden="true" />}
            {task.skillId && <span className="min-w-0 rounded-md bg-(--practice-pale) px-1.5 py-0.5 text-[11px] font-medium wrap-anywhere">{skillLabel(task.skillId)}</span>}
            {task.gapNeedsConfirmation && <span title="Kết quả phỏng vấn mới cho thấy kỹ năng đã cải thiện" className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">Đã cải thiện</span>}
          </span>
        </span>
        <span title={task.title} className={cn('line-clamp-2 text-sm leading-snug font-semibold wrap-anywhere', selectedTaskId === task.id && 'text-(--practice-primary)')}>{task.title}</span>
        <span className="mt-2 flex flex-wrap items-center justify-between gap-1.5 border-t border-slate-100 pt-2 text-[11px]">
          <span className={cn('rounded-md px-1.5 py-0.5 font-medium', tone.badge)}>{statusLabel}</span>
          <span className="inline-flex items-center gap-1 text-(--practice-muted)" title={checklistLabel}><ListChecks size={13} aria-hidden="true" /> {completed}/{task.checklist.length}</span>
        </span>
        {task.checklist.length > 0 && <span className="mt-1.5 grid gap-1 text-[11px] text-(--practice-muted)">
          {task.checklist.slice(0, 2).map((item) => <span key={item.id} className="flex min-w-0 items-center gap-1.5">
            {item.isCompleted ? <CircleCheck size={12} className="shrink-0 text-(--practice-green)" aria-hidden="true" /> : <Circle size={12} className="shrink-0" aria-hidden="true" />}
            <span className={cn('truncate', item.isCompleted && 'line-through')}>{item.content}</span>
          </span>)}
          {task.checklist.length > 2 && <span className="pl-5">+{task.checklist.length - 2} mục khác</span>}
        </span>}
        {nestTargetId === task.id && <span aria-hidden="true" className={cn(styles.kanbanNestPlaceholder, 'mt-2 grid min-h-9 place-items-center rounded-lg border border-dashed px-2 text-center text-[11px] font-medium text-(--practice-primary)')}>Thả để lồng thành task con</span>}
      </button>
      {(children.length > 0 || nestTargetId === task.id) && <div className="mt-2 space-y-2 border-l-2 border-(--practice-blue-strong) pl-2">
        {children.map((child) => <StudyTaskCard key={child.id} task={child} children={childrenById.get(child.id) ?? []} childrenById={childrenById}
          statusLabel={studyTaskStatuses.find(({ value }) => value === child.status)?.label ?? statusLabel} selectedTaskId={selectedTaskId}
          draggingId={draggingId} draggable={draggable} completedTaskId={completedTaskId} nestTargetId={nestTargetId} nestingTaskId={nestingTaskId} selectedTaskPathIds={selectedTaskPathIds} onSelect={(selectedTask) => onSelect(selectedTask)}
          onDragStart={onDragStart} onDragEnd={onDragEnd} onDropOnTask={onDropOnTask} onComplete={onComplete} />)}
      </div>}
    </div>
  );
}

export function StudyKanban({ tasks, selectedTaskId, disabled, hasActiveFilters, completedTaskId, onSelect, onMove, onChangeParent, onCreate, gapSource, onGapDrop }: StudyKanbanProps) {
  const { draggingId, dropStatus, savingStatus, announcement, arrival, startDrag, finishDrag, dragOver, dragLeave, drop, finishArrival } =
    useStudyTaskDrag({ disabled, onMove });
  const [insertion, setInsertion] = useState<{ status: StudyTaskStatus; beforeId: number | null }>();
  const [gapTarget, setGapTarget] = useState<StudyTaskStatus | null>(null);
  const [nestTargetId, setNestTargetId] = useState<number | null>(null);
  const [nestingTaskId, setNestingTaskId] = useState<number | null>(null);
  const nestTimer = useRef<number | null>(null);
  const [addingStatus, setAddingStatus] = useState<StudyTaskStatus | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const childrenById = new Map<number, StudyTask[]>();
  for (const task of tasks) {
    if (task.parentTaskId == null || !taskById.has(task.parentTaskId)) continue;
    const children = childrenById.get(task.parentTaskId) ?? [];
    children.push(task);
    childrenById.set(task.parentTaskId, children);
  }
  const selectedTaskPathIds = new Set<number>();
  let selectedAncestor = selectedTaskId == null ? undefined : taskById.get(selectedTaskId);
  while (selectedAncestor) {
    selectedTaskPathIds.add(selectedAncestor.id);
    selectedAncestor = selectedAncestor.parentTaskId == null ? undefined : taskById.get(selectedAncestor.parentTaskId);
  }

  useEffect(() => () => { if (nestTimer.current !== null) window.clearTimeout(nestTimer.current); }, []);

  function nestOnDrop(event: DragEvent<HTMLButtonElement>, target: StudyTask, action?: 'preview' | 'leave') {
    if (action === 'preview') {
      if (!event.dataTransfer.types.includes(studyGapDragType) && draggingId != null && draggingId !== target.id) setNestTargetId(target.id);
      return;
    }
    if (action === 'leave') {
      setNestTargetId((current) => current === target.id ? null : current);
      return;
    }
    if (event.dataTransfer.types.includes(studyGapDragType) || draggingId == null) return;
    const source = taskById.get(draggingId);
    if (!source) return;
    event.preventDefault();
    event.stopPropagation();
    setNestTargetId(null);
    if (source.id === target.id || source.parentTaskId === target.id) return;
    let ancestor: number | null | undefined = target.parentTaskId;
    while (ancestor != null) {
      if (ancestor === source.id) return;
      ancestor = taskById.get(ancestor)?.parentTaskId;
    }
    if (event.dataTransfer.getData('text/plain') !== String(source.id)) return;
    finishDrag();
    void onChangeParent(source, target.id).then((saved) => {
      if (!saved) return;
      setNestingTaskId(source.id);
      if (nestTimer.current !== null) window.clearTimeout(nestTimer.current);
      nestTimer.current = window.setTimeout(() => setNestingTaskId(null), 700);
    });
  }

  async function addQuickTask(status: StudyTaskStatus) {
    const title = newTitle.trim();
    if (!title || disabled) return;
    const saved = await onCreate({ title, status, checklist: [] });
    if (saved) {
      setNewTitle('');
      setAddingStatus(null);
    }
  }

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
        const columnTasks = tasks.filter((task) => task.status === status && (task.parentTaskId == null || !taskById.has(task.parentTaskId)));
        const countNested = (task: StudyTask): number => 1 + (childrenById.get(task.id) ?? []).reduce((count, child) => count + countNested(child), 0);
        const visibleCardCount = columnTasks.reduce((count, task) => count + countNested(task), 0);
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
              const draggedTask = draggingId == null ? undefined : taskById.get(draggingId);
              if (draggedTask?.parentTaskId != null) {
                event.preventDefault();
                event.stopPropagation();
                finishDrag();
                void onChangeParent(draggedTask, null, status);
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
              'flex h-[68dvh] min-h-[26rem] min-w-0 flex-col gap-2 rounded-2xl border p-2.5 shadow-sm',
              (isTarget || isSaving) ? 'border-(--practice-primary) bg-(--practice-orange)/35' : 'border-slate-200 bg-(--practice-pale)',
            )}>
            <div className="flex shrink-0 items-center justify-between gap-1 rounded-lg px-1 py-1"
              onDragOver={(event) => { if (!disabled && draggingId != null) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; } }}
              onDrop={(event) => {
                const draggedTask = draggingId == null ? undefined : taskById.get(draggingId);
                if (!draggedTask || event.dataTransfer.types.includes(studyGapDragType)) return;
                event.preventDefault();
                event.stopPropagation();
                finishDrag();
                void onChangeParent(draggedTask, null, status);
              }}>
              <h3 className="flex items-center gap-1.5 text-[11px] font-bold tracking-wide uppercase">
                <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: studyTaskTones[status].color }} aria-hidden="true" />
                {label}
              </h3>
              <span className="rounded-full bg-card px-2 py-0.5 text-xs tabular-nums text-(--practice-muted) shadow-xs">{visibleCardCount}</span>
            </div>
            {columnTasks.length ? (
              <ul tabIndex={0} aria-label={`Đầu việc: ${label}`}
                className="min-h-0 flex-1 space-y-2 overflow-y-auto rounded-lg focus-visible:outline-2 xl:p-0.5">
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
                    <StudyTaskCard task={task} children={childrenById.get(task.id) ?? []} childrenById={childrenById}
                      statusLabel={label} selectedTaskId={selectedTaskId} draggingId={draggingId} draggable={!disabled} completedTaskId={completedTaskId}
                      nestTargetId={nestTargetId} nestingTaskId={nestingTaskId} selectedTaskPathIds={selectedTaskPathIds}
                      onSelect={(selectedTask) => onSelect(selectedTask.id)} onDragStart={(event, dragged) => startDrag(event, dragged)}
                      onDragEnd={() => { setInsertion(undefined); setNestTargetId(null); finishDrag(); }} onDropOnTask={nestOnDrop} onComplete={(completedTask) => { void onMove(completedTask, 'DONE'); }} />
                  </li>
                ))}
                <li aria-hidden="true" className={styles.kanbanEndInsertion}
                  data-insert-before={isTarget && insertion?.status === status && insertion.beforeId === null || undefined} />
              </ul>
            ) : (
              <p className="grid min-h-16 flex-1 place-items-center rounded-lg border border-dashed border-(--practice-blue-strong) bg-card/65 px-2 py-2 text-center text-xs text-(--practice-muted) sm:min-h-40 xl:min-h-0">
                {isSaving ? 'Đang chuyển…' : isTarget ? 'Thả vào đây' : hasActiveFilters ? 'Không có task phù hợp' : 'Chưa có đầu việc'}
              </p>
            )}
            {addingStatus === status ? (
              <form className="space-y-2 rounded-xl border border-(--practice-blue-strong) bg-card p-2" onSubmit={(event) => { event.preventDefault(); void addQuickTask(status); }}>
                <Input autoFocus aria-label={`Tên task mới trong ${label}`} maxLength={160} placeholder="Nhập tiêu đề task…" value={newTitle}
                  onChange={(event) => setNewTitle(event.target.value)} className="h-9 border-0 bg-(--practice-pale) px-2 text-sm shadow-none" />
                <div className="flex items-center gap-1.5">
                  <Button type="submit" size="sm" disabled={disabled || !newTitle.trim()} className="h-8 rounded-lg bg-[#315f86] px-3 text-white hover:bg-[#294f70]">Thêm thẻ</Button>
                  <Button type="button" size="icon-sm" variant="ghost" aria-label="Hủy thêm task" onClick={() => { setAddingStatus(null); setNewTitle(''); }}><X aria-hidden="true" /></Button>
                </div>
              </form>
            ) : (
              <Button type="button" variant="ghost" disabled={disabled} onClick={() => { setAddingStatus(status); setNewTitle(''); }}
                className="h-9 w-full justify-start rounded-lg px-2 text-sm text-(--practice-muted) hover:bg-card hover:text-(--practice-ink)">
                <Plus size={16} aria-hidden="true" /> Thêm thẻ
              </Button>
            )}
          </section>
        );
      })}
    </div>
  );
}
