import axiosClient from '@/lib/axiosClient';
import { useAuthStore } from '@/store/authStore';

export type SemanticAlignment = 'MATCH' | 'PARTIAL' | 'MISSING';
export type QuestionStrategy = 'NONE' | 'COMPARE_SUBSTITUTE' | 'PROBE_DEPTH' | 'LEARNING_AGILITY';

export interface SkillGapResult {
  jd_skill_id: string;
  semantic_alignment: SemanticAlignment;
  matched_cv_skill_id?: string | null;
  is_substituted: boolean;
  gap_magnitude: number;
  severity: number;
  priority: number;
  required_proficiency: number;
  candidate_proficiency: number;
  cv_evidence_spans: string[];
  context_job?: string | null;
  suggested_strategy: QuestionStrategy;
  degraded?: boolean;
  flags?: string[];
}

export interface StaticSkillAuditItem extends SkillGapResult {
  soft_match: number;
  substitution_factor: number;
  importance_weight: number;
  jd_reasoning: string;
  effective_candidate_proficiency: number;
  effective_months: number;
  c_evidence: number;
  recency_flag: boolean;
  static_diagnosis: string;
}

export interface StaticGapAuditReport {
  analysis_id: string;
  total_jd_skills: number;
  matched_count: number;
  partial_count: number;
  missing_count: number;
  skills_requiring_probing: number;
  degraded: boolean;
  system_flags: string[];
  items: StaticSkillAuditItem[];
  markdown_summary: string;
}

export interface AnalyzeWithReportResponse {
  analysis_id: string;
  skills: SkillGapResult[];
  report: StaticGapAuditReport;
}

export interface AbductiveReasoning {
  surprising_fact_C: string;
  hypothesis_A: string;
}

export interface StartInterviewResponse {
  session_id: string;
  turn: number;
  active_skill_id?: string | null;
  initial_belief: number[];
  abductive_reasoning?: AbductiveReasoning | null;
  question?: string | null;
  is_finished: boolean;
}

export interface RespondInterviewResponse {
  session_id: string;
  turn: number;
  evaluated_skill_id: string;
  previous_belief: number[];
  updated_belief: number[];
  tv_delta: number;
  metamorphic_tag: 'INVARIANT' | 'MINOR_SHIFT' | 'MODERATE_SHIFT' | 'DECISIVE_SHIFT' | string;
  reflective_insight: string;
  skill_verified: boolean;
  active_skill_id?: string | null;
  next_question?: string | null;
  completion_rate: number;
  is_finished: boolean;
}

export interface SkillAuditReportItem {
  jd_skill_id: string;
  matched_cv_skill_id?: string | null;
  suggested_strategy: string;
  initial_cv_proficiency: number;
  verified_proficiency: number;
  required_jd_proficiency: number;
  verified_skill_gap: number;
  map_rubric_level: 'Low' | 'Med' | 'High' | string;
  is_verified: boolean;
  verification_reason?: string | null;
  local_turns_spent: number;
  prior_belief: number[];
  final_belief: number[];
  belief_trajectory: number[][];
  metamorphic_tags: string[];
  judge_justifications: string[];
  primary_slot_value?: string | null;
  consolidated_finding?: string | null;
}

export interface TurnLogItem {
  turn: number;
  local_turn: number;
  skill_id: string;
  target_slot_id: string;
  abductive_reasoning: AbductiveReasoning;
  question: string;
  candidate_response?: string | null;
  extracted_slot_value?: string | null;
  reflective_insight?: string | null;
  metamorphic_tag?: string | null;
  previous_belief: number[];
  updated_belief?: number[] | null;
  tv_delta?: number | null;
  skill_verified_after_turn: boolean;
  verification_reason?: string | null;
}

export interface HITLReportResponse {
  session_id: string;
  is_finished: boolean;
  termination_reason?: string | null;
  total_turns: number;
  total_initial_primary_skills: number;
  verified_primary_skills: number;
  completion_rate: number;
  evaluated_skills: SkillAuditReportItem[];
  turn_audit_trail: TurnLogItem[];
  markdown_summary: string;
}

export interface IngestResponse {
  sessionId: string;
  success: boolean;
  cvFilename?: string;
  jdFilename?: string;
  cvTextLength?: number;
  jdTextLength?: number;
  cvMarkdown?: string;
  jdMarkdown?: string;
  rawCvText?: string | null;
  rawJdText?: string | null;
}

function getAuthHeaders(includeJsonContentType = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (includeJsonContentType) {
    headers['Content-Type'] = 'application/json';
  }
  const token = useAuthStore.getState().token;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const cvJdMatchingService = {
  async ingestCvJd(
    sessionId: string,
    cvFile: File | null,
    jdFile: File | null,
    jdText: string | null,
    resumeId?: string | null,
    jdId?: string | null,
    roleTitle?: string | null
  ): Promise<IngestResponse> {
    const formData = new FormData();
    if (cvFile) formData.append('cvFile', cvFile);
    if (jdFile) formData.append('jdFile', jdFile);
    if (jdText) formData.append('jdText', jdText);
    if (resumeId) formData.append('resumeId', String(resumeId));
    if (jdId) formData.append('jdId', String(jdId));
    if (roleTitle) formData.append('roleTitle', roleTitle);

    const { data } = await axiosClient.post<IngestResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/documents`,
      formData,
      {
        headers: {
          ...getAuthHeaders(false),
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return data;
  },

  async analyzeSkillGap(sessionId: string, forceRefresh = false): Promise<AnalyzeWithReportResponse> {
    const { data } = await axiosClient.post<AnalyzeWithReportResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/analyze-gap?forceRefresh=${forceRefresh}`,
      null,
      { headers: getAuthHeaders(false) }
    );
    return data;
  },

  async startAdaptiveInterview(sessionId: string): Promise<StartInterviewResponse> {
    const { data } = await axiosClient.post<StartInterviewResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/interview/start`,
      null,
      { headers: getAuthHeaders(false) }
    );
    return data;
  },

  async respondAdaptiveInterview(
    sessionId: string,
    candidateResponse: string
  ): Promise<RespondInterviewResponse> {
    const { data } = await axiosClient.post<RespondInterviewResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/interview/respond`,
      { candidate_response: candidateResponse },
      { headers: getAuthHeaders(true) }
    );
    return data;
  },

  async getInterviewReport(sessionId: string): Promise<HITLReportResponse> {
    const { data } = await axiosClient.get<HITLReportResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/interview/report`,
      { headers: getAuthHeaders(false) }
    );
    return data;
  },
};
