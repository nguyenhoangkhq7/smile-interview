import { assessmentLabels, resultReasons } from '@/components/features/interview/result/resultData';
import type { Assessment } from '@/services/evidenceInterview';
import type { InterviewStatus, InterviewSummary } from './types';

export const statusLabels: Record<InterviewStatus, string> = {
  NOT_STARTED: 'Chưa bắt đầu',
  IN_PROGRESS: 'Đang diễn ra',
  COMPLETED: 'Đã hoàn thành',
  ANOMALY: 'Dừng sớm / bất thường',
  OTHER: 'Trạng thái khác',
};

const statusTheme: Record<InterviewStatus, string> = {
  NOT_STARTED: 'bg-[#edf0ff] text-[#474e60]',
  IN_PROGRESS: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-100 text-green-800',
  ANOMALY: 'bg-red-100 text-red-800',
  OTHER: 'bg-slate-100 text-slate-700',
};

const date = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short',
});

export function dateLabel(stamp: string | null) {
  return stamp ? date.format(new Date(stamp)) : '—';
}

export function durationLabel(session: InterviewSummary) {
  if (!session.startedAt || !session.endedAt) return '—';
  const seconds = Math.floor((Date.parse(session.endedAt) - Date.parse(session.startedAt)) / 1000);
  return seconds >= 0 ? Math.floor(seconds / 60) + ' phút ' + seconds % 60 + ' giây' : '—';
}

export function modeLabel(mode: InterviewSummary['mode']) {
  return mode === 'VOICE' ? 'Giọng nói' : mode === 'TEXT' ? 'Văn bản' : '—';
}

export function terminationLabel(reason: string | null | undefined) {
  if (reason === 'USER_STOP') return 'Ứng viên chủ động dừng phiên';
  if (reason === 'ALL_COMPATIBLE_SKILLS_MASTERED') return 'Đã đạt các kỹ năng cần đánh giá';
  return reason && Object.hasOwn(resultReasons, reason) ? resultReasons[reason] : reason ?? null;
}

export function assessmentLabel(assessment: Assessment) {
  return Object.hasOwn(assessmentLabels, assessment) ? assessmentLabels[assessment] : assessment;
}

export function statusStyle(status: InterviewStatus) {
  return statusTheme[status];
}
