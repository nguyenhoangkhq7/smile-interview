import axiosClient from '@/lib/axiosClient';
import type { SkillGapResult, StaticGapAuditReport } from './cvJdMatching';
import type { Assessment } from './evidenceInterview';

export type CompetencyStatus = Assessment | 'NEEDS_VERIFICATION' | 'PARTIALLY_ASSESSED';
export interface CompetencySource { sessionId: string; attemptNumber: number; assessedAt: string | null }
export interface CompetencyEvidence {
  source: CompetencySource; turnId: string; question: string; responseExcerpt: string;
  rationale: string; performance: string; context: string;
}
export interface CompetencyCriterion {
  id: string; description: string; essential: boolean; assessment: CompetencyStatus;
  lastAssessment: CompetencySource | null; evidence: CompetencyEvidence[];
}
export interface CompetencyObjective {
  id: string; claim: string; assessment: CompetencyStatus; lastChecked: CompetencySource | null;
  lastAssessment: CompetencySource | null; explanation: string; criteria: CompetencyCriterion[];
}
export interface CurrentCompetency {
  policyVersion: string; completedAttempts: number; incompatibleAssessments: number;
  lastAssessment: CompetencySource | null;
  summary: { totalSkills: number; meetingTarget: number; belowTarget: number; needsVerification: number; incomplete: number; notAssessed: number };
  skills: { skillId: string; baselineAlignment: string; assessment: CompetencyStatus;
    evidencedCriteria: number; totalCriteria: number; lastChecked: CompetencySource | null; objectives: CompetencyObjective[] }[];
}

export type AttemptStatus = 'Not started' | 'In progress' | 'Completed' | 'Stopped early' | 'Cancelled';
export interface InterviewAttempt {
  id: string; number: number; status: AttemptStatus; startedAt: string;
  endedAt: string | null; answeredCount: number; terminationReason: string | null;
}
export interface ApplicationProfile {
  id: string; title: string; company: string | null; roleTitle: string;
  cvFilename: string; jdTitle: string; createdAt: string;
  skills: SkillGapResult[]; analysis: StaticGapAuditReport; attempts: InterviewAttempt[];
}
export const attemptLabels: Record<AttemptStatus, string> = {
  'Not started': 'Chưa bắt đầu', 'In progress': 'Đang phỏng vấn', Completed: 'Đã hoàn thành',
  'Stopped early': 'Kết thúc sớm', Cancelled: 'Đã hủy — chưa trả lời',
};
const base = '/api/v1/application-profiles';
export const applicationProfiles = {
  async competency(id: string): Promise<CurrentCompetency> { return (await axiosClient.get(`${base}/${id}/competency`)).data; },
  async list(): Promise<ApplicationProfile[]> { return (await axiosClient.get(base)).data; },
  async get(id: string): Promise<ApplicationProfile> { return (await axiosClient.get(`${base}/${id}`)).data; },
  async create(sourceSessionId: string, title: string, company: string): Promise<ApplicationProfile> {
    return (await axiosClient.post(base, { sourceSessionId, title, company })).data;
  },
  async newAttempt(id: string): Promise<InterviewAttempt> {
    return (await axiosClient.post(`${base}/${id}/attempts`)).data;
  },
};
