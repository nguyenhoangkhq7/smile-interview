import axiosClient from '@/lib/axiosClient';
import type { SkillGapResult, SkillGapReport } from './cvJdMatching';
import type { Assessment } from './evidenceInterview';

export type CompetencyStatus = Assessment | 'NEEDS_VERIFICATION' | 'PARTIALLY_ASSESSED';
export interface CompetencySource { sessionId: string; attemptNumber: number; assessedAt: string | null }
export interface CompetencyEvidence {
  source: CompetencySource; turnId: string; question: string; responseExcerpt: string;
  rationale: string; performance: string;
}
export interface CompetencyCriterion {
  trend?: 'IMPROVING' | 'DECLINING' | null;
  id: string; description: string; essential: boolean; atTarget?: string; assessment: CompetencyStatus;
  lastAssessment: CompetencySource | null; evidence: CompetencyEvidence[];
}
export interface CompetencyObjective {
  id: string; claim: string; assessment: CompetencyStatus; lastChecked: CompetencySource | null;
  lastAssessment: CompetencySource | null; explanation: string; criteria: CompetencyCriterion[];
}
export interface CompetencySkill {
  skillId: string; baselineAlignment: string; assessment: CompetencyStatus;
  objectives: CompetencyObjective[];
}
export interface ProgressPoint {
  sessionId: string;
  attemptNumber: number;
  assessedAt: string | null;
  kind: 'ASSESSMENT' | 'RECHECK';
  essentialCriteriaMet: number;
  essentialCriteriaTotal: number;
  weightedReadinessPercent: number;
}
export interface CurrentCompetency {
  completedAttempts: number; incompatibleAssessments: number;
  practiceAttempts?: number;
  timeline?: ProgressPoint[];
  skills: CompetencySkill[];
}
export function newerSource(a: CompetencySource | null, b: CompetencySource | null): CompetencySource | null {
  return !a ? b : !b || a.attemptNumber >= b.attemptNumber ? a : b;
}
export function competencySummary(skills: readonly CompetencySkill[]) {
  let meetingTarget = 0, belowTarget = 0, needsVerification = 0, incomplete = 0, notAssessed = 0;
  for (const skill of skills) {
    if (skill.assessment === 'DEMONSTRATED_AT_TARGET' || skill.assessment === 'DEMONSTRATED_ABOVE_TARGET') meetingTarget++;
    else if (skill.assessment === 'DEMONSTRATED_BELOW_TARGET' || skill.assessment === 'NOT_DEMONSTRATED') belowTarget++;
    else if (skill.assessment === 'NEEDS_VERIFICATION') needsVerification++;
    else if (skill.assessment === 'INSUFFICIENT_EVIDENCE' || skill.assessment === 'PARTIALLY_ASSESSED') incomplete++;
    else notAssessed++;
  }
  return { totalSkills: skills.length, meetingTarget, belowTarget, needsVerification, incomplete, notAssessed };
}
export function competencyLastAssessment(skills: readonly CompetencySkill[]): CompetencySource | null {
  let latest: CompetencySource | null = null;
  for (const skill of skills) {
    for (const objective of skill.objectives) {
      latest = newerSource(latest, objective.lastAssessment);
      for (const criterion of objective.criteria) latest = newerSource(latest, criterion.lastAssessment);
    }
  }
  return latest;
}
export function skillLastChecked(skill: CompetencySkill): CompetencySource | null {
  return skill.objectives.reduce<CompetencySource | null>((latest, objective) => newerSource(latest, objective.lastChecked), null);
}
export function skillCriteriaCounts(skill: CompetencySkill) {
  let evidenced = 0, total = 0;
  for (const objective of skill.objectives) {
    total += objective.criteria.length;
    evidenced += objective.criteria.filter(criterion => criterion.evidence.length > 0).length;
  }
  return { evidenced, total };
}

export type AttemptStatus = 'Not started' | 'In progress' | 'Completed' | 'Stopped early' | 'Cancelled';
export interface InterviewAttempt {
  id: string; number: number; status: AttemptStatus; startedAt: string;
  endedAt: string | null; answeredCount: number; terminationReason: string | null;
}
export interface ApplicationProfile {
  id: string; title: string; company: string | null; roleTitle: string;
  cvFilename: string; jdTitle: string; jdFilename?: string; createdAt: string;
  skills: SkillGapResult[]; analysis: SkillGapReport; attempts: InterviewAttempt[];
}
export interface ApplicationDocuments {
  cvFilename: string; cvFileUrl: string | null; cvText: string;
  jdTitle: string; jdFilename: string; jdFileUrl: string | null; jdText: string;
}
export interface ApplicationTrashEntry {
  profile: ApplicationProfile; deletedAt: string; expiresAt: string;
}
export const attemptLabels: Record<AttemptStatus, string> = {
  'Not started': 'Chưa bắt đầu', 'In progress': 'Đang phỏng vấn', Completed: 'Đã hoàn thành',
  'Stopped early': 'Kết thúc sớm', Cancelled: 'Đã hủy — chưa trả lời',
};
const base = '/api/v1/application-profiles';
export const applicationProfiles = {
  async competency(id: string, signal?: AbortSignal): Promise<CurrentCompetency> {
    return (await axiosClient.get(`${base}/${id}/competency`, { signal })).data;
  },
  async list(signal?: AbortSignal): Promise<ApplicationProfile[]> { return (await axiosClient.get(base, { signal })).data; },
  async get(id: string, signal?: AbortSignal): Promise<ApplicationProfile> {
    return (await axiosClient.get(`${base}/${encodeURIComponent(id)}`, { signal })).data;
  },
  async documents(id: string, signal?: AbortSignal): Promise<ApplicationDocuments> {
    return (await axiosClient.get(`${base}/${encodeURIComponent(id)}/documents`, { signal })).data;
  },
  async trash(signal?: AbortSignal): Promise<ApplicationTrashEntry[]> {
    return (await axiosClient.get(`${base}/trash`, { signal })).data;
  },
  async delete(id: string): Promise<void> {
    await axiosClient.delete(`${base}/${encodeURIComponent(id)}`);
  },
  async restore(id: string): Promise<void> {
    await axiosClient.post(`${base}/${encodeURIComponent(id)}/restore`);
  },
  async create(sourceSessionId: string, title: string, company: string): Promise<ApplicationProfile> {
    return (await axiosClient.post(base, { sourceSessionId, title, company })).data;
  },
  async newAttempt(id: string): Promise<InterviewAttempt> {
    return (await axiosClient.post(`${base}/${id}/attempts`)).data;
  },
};
