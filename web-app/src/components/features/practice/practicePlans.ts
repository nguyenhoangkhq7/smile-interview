import { finishedAttempt } from '@/components/features/applications/applicationUi';
import type { ApplicationProfile } from '@/services/applicationProfiles';

export const practiceStatuses = [
  { value: 'no-result', label: 'Chưa có kết quả phỏng vấn' },
  { value: 'has-result', label: 'Đã có kết quả phỏng vấn' },
] as const;

export type PracticeStatus = (typeof practiceStatuses)[number]['value'];
export type PracticeFilter = 'all' | PracticeStatus;

export interface PracticePlan {
  id: string;
  title: string;
  roleTitle: string;
  company: string | null;
  cvFilename: string;
  createdAt: string;
  status: PracticeStatus;
  skillCount: number;
  interviewCount: number;
}

export function toPracticePlan(profile: ApplicationProfile): PracticePlan {
  const hasResult = profile.attempts.some((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);

  return {
    id: profile.id,
    title: profile.title,
    roleTitle: profile.roleTitle,
    company: profile.company,
    cvFilename: profile.cvFilename,
    createdAt: profile.createdAt,
    status: hasResult ? 'has-result' : 'no-result',
    skillCount: profile.skills.length,
    interviewCount: profile.attempts.length,
  };
}
