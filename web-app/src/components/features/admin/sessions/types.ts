import type { Assessment } from '@/services/evidenceInterview';

export type InterviewStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'ANOMALY' | 'OTHER';
export type InterviewFilter = 'all' | InterviewStatus;

export interface InterviewSummary {
  id: string;
  candidateName: string | null;
  roleTitle: string | null;
  status: InterviewStatus;
  mode: 'TEXT' | 'VOICE' | null;
  createdAt: string;
  startedAt: string | null;
  endedAt: string | null;
  userRating: number | null;
}

export interface InterviewPage {
  sessions: InterviewSummary[];
  total: number;
  page: number;
  size: number;
  counts: Partial<Record<InterviewStatus, number>>;
}

export interface InterviewEvidence {
  criterionId: string | null;
  excerpt: string | null;
  rationale: string | null;
  performance: string | null;
}

export interface InterviewTurn {
  id: string;
  skill: string | null;
  mode: string | null;
  question: string | null;
  answer: string | null;
  feedback: string | null;
  score: number | null;
  strengths: string | null;
  improvements: string | null;
  suggestedAnswer: string | null;
  evidence: InterviewEvidence[];
}

export interface InterviewObjective {
  skill: string;
  claim: string | null;
  assessment: Assessment | null;
  strengths: string[];
  weaknesses: string[];
}

export interface InterviewDetail {
  session: InterviewSummary;
  inputs: { cvName: string | null; jdTitle: string | null; company: string | null };
  matching: { score: number | null; available: boolean };
  blueprint: {
    maxQuestions: number | null; durationSeconds: number | null;
    maxQuestionsPerObjective: number | null; questionMode: string | null; objectiveCount: number | null;
    policy: {
      coreImportance: number | null; reserveFollowupFraction: number | null;
      fallbackDepth: number | null; minFailureContexts: number | null; allowExtensionProbes: boolean | null;
    } | null;
  } | null;
  finalized: boolean;
  transcript: { opening: string | null; introduction: string | null; closing: string | null; turns: InterviewTurn[] } | null;
  report: {
    terminationReason: string | null; objectives: InterviewObjective[];
    overallScore: number | null; feedback: string | null;
  } | null;
}

export interface AiQualityFinding {
  status: 'REVIEW' | 'INSUFFICIENT';
  code: string;
  detail: string;
  skill: string | null;
  turn: number | null;
  excerpt: string | null;
}

export interface AiQualitySection {
  total: number;
  findings: AiQualityFinding[];
}

export interface AiQualityReview {
  matching: AiQualitySection;
  questions: AiQualitySection;
}

export type InterviewDocumentKind = 'CV' | 'JD';

export interface InterviewDocument {
  name: string;
  text: string;
  originalAvailable: boolean;
}

export interface InterviewMatchingTask {
  description: string;
  requirement: string | null;
  requiredLevel: number | null;
  evidence: string[];
}

export interface InterviewMatchingSkill {
  id: string;
  name: string | null;
  alignment: string | null;
  cvSkill: string | null;
  requiredLevel: number | null;
  priority: number | null;
  importance: number | null;
  context: string | null;
  cvEvidence: string[];
  jdEvidence: string[];
  tasks: InterviewMatchingTask[];
}

export interface InterviewMatchingDetail {
  score: number | null;
  degraded: boolean;
  available: boolean;
  skills: InterviewMatchingSkill[];
}
