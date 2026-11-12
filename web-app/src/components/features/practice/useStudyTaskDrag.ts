import { useRef, useState, type DragEvent } from 'react';
import { studyTaskStatuses, type StudyTask, type StudyTaskStatus } from './studyPlan';

type Arrival = { id: number; status: StudyTaskStatus; direction: 'left' | 'right' };

interface StudyTaskDragOptions {
  disabled: boolean;
  onMove: (task: StudyTask, status: StudyTaskStatus, beforeTaskId?: number | null) => Promise<boolean>;
}

export function useStudyTaskDrag({ disabled, onMove }: StudyTaskDragOptions) {
  const dragSource = useRef<StudyTask | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dropStatus, setDropStatus] = useState<StudyTaskStatus | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [arrival, setArrival] = useState<Arrival | null>(null);
  const [savingStatus, setSavingStatus] = useState<StudyTaskStatus | null>(null);

  function finishDrag() {
    dragSource.current = null;
    setDraggingId(null);
    setDropStatus(null);
  }

  function startDrag(event: DragEvent<HTMLButtonElement>, task: StudyTask) {
    if (disabled) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(task.id));
    dragSource.current = task;
    setDraggingId(task.id);
    setArrival(null);
    setAnnouncement('');
  }

  function dragOver(event: DragEvent<HTMLElement>, status: StudyTaskStatus, allowReorder = false) {
    if (disabled || !dragSource.current || (!allowReorder && dragSource.current.status === status)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setDropStatus(status);
    return true;
  }

  async function drop(event: DragEvent<HTMLElement>, status: StudyTaskStatus, label: string, beforeTaskId?: number | null) {
    const task = dragSource.current;
    if (!task) return;
    event.preventDefault();
    finishDrag();
    if (disabled || (beforeTaskId === undefined && task.status === status) || event.dataTransfer.getData('text/plain') !== String(task.id)) return;

    const from = studyTaskStatuses.findIndex(({ value }) => value === task.status);
    const to = studyTaskStatuses.findIndex(({ value }) => value === status);
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setArrival({ id: task.id, status, direction: from < to ? 'left' : 'right' });
    }
    setSavingStatus(status);
    setAnnouncement(`Đang chuyển ${task.title} sang ${label}.`);
    const saved = await onMove(task, status, beforeTaskId);
    setSavingStatus(null);
    if (!saved) setArrival(null);
    setAnnouncement(saved ? `Đã chuyển ${task.title} sang ${label}.` : `Không chuyển được ${task.title}.`);
  }

  function dragLeave(event: DragEvent<HTMLElement>, status: StudyTaskStatus) {
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
    setDropStatus((current) => current === status ? null : current);
  }

  function finishArrival(task: StudyTask) {
    setArrival((current) => current?.id === task.id && current.status === task.status ? null : current);
  }

  return { draggingId, dropStatus, savingStatus, announcement, arrival, startDrag, finishDrag, dragOver, dragLeave, drop, finishArrival };
}
