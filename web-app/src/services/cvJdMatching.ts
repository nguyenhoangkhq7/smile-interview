import axiosClient from '@/lib/axiosClient';
import type { EligibilityReport } from './eligibility';
import { useAuthStore } from '@/store/authStore';

export type SemanticAlignment = 'MATCH' | 'PARTIAL' | 'MISSING';

export interface JobTask {
  task_id: string;
  description: string;
  evidence_spans: string[];
  required_level: number;
  requirement_kind: 'REQUIRED' | 'OPTIONAL' | 'UNSPECIFIED';
  level_basis: 'EXPLICIT' | 'INFERRED' | 'FALLBACK';
}

export interface SkillGapResult {
  jd_skill_id: string;
  jd_skill_name?: string | null;
  matched_cv_skill_name?: string | null;
  jd_evidence_spans?: string[];
  semantic_alignment: SemanticAlignment;
  matched_cv_skill_id?: string | null;
  priority: number;
  importance_weight: number;
  required_proficiency: number;
  cv_evidence_spans: string[];
  context_job?: string | null;
  job_tasks?: JobTask[];
}

export interface ExtractedCvSkill {
  skill_id: string;
  skill_name?: string | null;
  type: 'explicit' | 'implicit';
  evidence_spans: string[];
}

export interface SkillGapReport {
  eligibility?: EligibilityReport | null;
  cv_skills?: ExtractedCvSkill[] | null;
  matching_score?: number | null;
  degraded: boolean;
}

export interface AnalyzeWithReportResponse {
  analysis_id: string;
  skills: SkillGapResult[];
  report: SkillGapReport;
}

export interface AbductiveReasoning {
  surprising_fact_C: string;
  hypothesis_A: string;
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

interface AnalysisJob {
  job_id: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  result: AnalyzeWithReportResponse | null;
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

  async analyzeSkillGap(sessionId: string, forceRefresh: boolean, signal: AbortSignal,
                        onAccepted: (id: string) => void, previousJob?: string): Promise<AnalyzeWithReportResponse> {
    const path = `/api/v1/sessions/${encodeURIComponent(sessionId)}/analyze-gap`;
    const options = { headers: getAuthHeaders(), signal };
    let jobId = previousJob;
    if (!jobId) {
      const { data } = await axiosClient.post<AnalysisJob | AnalyzeWithReportResponse>(
        path, null, { ...options, params: { forceRefresh } });
      if ('skills' in data) return data;
      jobId = data.job_id;
      onAccepted(jobId);
    }
    while (!signal.aborted) {
      const { data } = await axiosClient.get<AnalysisJob>(`${path}/${encodeURIComponent(jobId)}`, options);
      if (data.status === 'SUCCEEDED' && data.result) return data.result;
      if (data.status !== 'PENDING' && data.status !== 'RUNNING')
        throw new Error('Phân tích chưa hoàn tất. Vui lòng thử lại.');
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
    throw new DOMException('Cancelled', 'AbortError');
  },

};
