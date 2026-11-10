export const DEFAULT_TARGET_COMPLETION_PERCENT = 80;

export const studyTaskStatuses = [
  { value: 'TODO', label: 'Cần ôn' },
  { value: 'IN_PROGRESS', label: 'Đang ôn' },
  { value: 'DONE', label: 'Đã xong' },
] as const;

export interface StudyTask {
  id: string;
  title: string;
  status: (typeof studyTaskStatuses)[number]['value'];
  skillId?: string;
  notes?: string;
  checklist?: readonly string[];
  completedChecklist?: readonly number[];
  referenceUrl?: string;
}

export type NewStudyTask = Omit<StudyTask, 'id'>;
export type StudyTaskUpdate = Partial<Pick<StudyTask, 'status' | 'notes' | 'completedChecklist'>>;

export const studyTaskTones = {
  TODO: { color: '#665956', badge: 'bg-(--practice-blue) text-(--practice-muted)' },
  IN_PROGRESS: { color: '#2563eb', badge: 'bg-blue-100 text-blue-800' },
  DONE: { color: '#146535', badge: 'bg-(--practice-green-bg) text-(--practice-green)' },
};

const percentFormat = new Intl.NumberFormat('vi-VN', { style: 'percent', maximumFractionDigits: 2 });
export const formatStudyPercent = (value: number) => percentFormat.format(value / 100);

export function getStudyReferenceUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

export interface StudyPlan {
  targetCompletionPercent: number;
  tasks: readonly StudyTask[];
}

export function getStudyProgress({ targetCompletionPercent, tasks }: StudyPlan) {
  const total = tasks.length;
  const done = tasks.filter((task) => task.status === 'DONE').length;
  const percent = total ? (done / total) * 100 : null;
  const meetsTarget = total ? done * 100 >= targetCompletionPercent * total : null;

  return { targetCompletionPercent, done, total, percent, meetsTarget };
}
