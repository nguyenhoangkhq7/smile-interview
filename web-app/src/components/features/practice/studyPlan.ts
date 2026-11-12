export const studyTaskStatuses = [
  { value: 'TODO', label: 'Cần ôn' },
  { value: 'IN_PROGRESS', label: 'Đang ôn' },
  { value: 'DONE', label: 'Đã xong' },
] as const;

export type StudyTaskStatus = (typeof studyTaskStatuses)[number]['value'];

export interface StudyTaskFields {
  title: string;
  status: StudyTaskStatus;
  skillId?: string | null;
  notes?: string | null;
  sortOrder?: number;
}

export interface StudyChecklistItem {
  id: number;
  content: string;
  isCompleted: boolean;
  sortOrder: number;
}

export interface StudyResource {
  id: number;
  title: string;
  url: string | null;
  fileName: string | null;
}

export interface StudyTask extends StudyTaskFields {
  id: number;
  parentTaskId?: number | null;
  gapSourceSkillId?: string | null;
  gapSourceSessionId?: string | null;
  gapSourceAttemptNumber?: number | null;
  gapNeedsConfirmation?: boolean;
  checklist: readonly StudyChecklistItem[];
  resources: readonly StudyResource[];
}

export interface NewStudyTask extends StudyTaskFields {
  parentTaskId?: number;
  checklist: readonly string[];
  referenceUrl?: string;
  gapOrigin?: { skillId: string; sessionId?: string | null; attemptNumber?: number | null };
}

export type StudyTaskUpdate = Partial<StudyTaskFields>;

export const studyTaskTones = {
  TODO: { color: '#665956', badge: 'bg-(--practice-blue) text-(--practice-muted)' },
  IN_PROGRESS: { color: '#2563eb', badge: 'bg-blue-100 text-blue-800' },
  DONE: { color: '#146535', badge: 'bg-(--practice-green-bg) text-(--practice-green)' },
};

const percentFormat = new Intl.NumberFormat('vi-VN', { style: 'percent', maximumFractionDigits: 2 });
export const formatStudyPercent = (value: number) => percentFormat.format(value / 100);

export const suggestedStudyTarget = 80;

export function studyProgressTone(percent: number | null, target: number) {
  if (percent === null) return { text: 'text-(--practice-muted)', fill: '', badge: 'bg-(--practice-blue)' };
  if (percent <= 35) return { text: 'text-red-700', fill: 'bg-red-600', badge: 'bg-red-100' };
  if (percent <= target) return { text: 'text-amber-800', fill: 'bg-amber-500', badge: 'bg-amber-100' };
  return { text: 'text-(--practice-green)', fill: 'bg-(--practice-green)', badge: 'bg-(--practice-green-bg)' };
}

export function getStudyReferenceUrl(value: string) {
  try {
    const url = new URL(value);
    return (url.protocol === 'http:' || url.protocol === 'https:') && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export interface StudyProgress {
  done: number;
  total: number;
  percent: number | null;
  meetsTarget: boolean | null;
}
