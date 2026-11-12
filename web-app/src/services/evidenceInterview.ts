import axios from 'axios';
import axiosClient from '@/lib/axiosClient';

export const questionModes = ['CODING', 'DEBUGGING', 'DESIGN', 'TECHNICAL_EXPLANATION', 'BEHAVIORAL'] as const;
export type QuestionMode = typeof questionModes[number];
export type InteractionMode = 'TEXT' | 'VOICE';
export interface InterviewConfig {
  interaction_mode: InteractionMode;
  mode: 'MIXED' | 'FOCUSED';
  focused_question_mode: QuestionMode | null;
  max_questions: number;
  duration_seconds: number;
  max_questions_per_objective: number;
}
export const defaultConfig: InterviewConfig = {
  interaction_mode: 'TEXT', mode: 'MIXED', focused_question_mode: null, max_questions: 10,
  duration_seconds: 900, max_questions_per_objective: 8,
};
export interface EvidenceTurn {
  turn_id: string; objective_id: string; skill_id: string; mode: QuestionMode;
  question: string; answer: string | null; feedback: string | null;
  introduction?: string;
}
export interface Observation {
  turn_id: string;
  criterion_id: string; response_excerpt: string; rationale: string;
  observation: 'SUPPORTS' | 'CONTRADICTS' | 'UNCLEAR' | 'NO_EVIDENCE';
  performance: 'BELOW' | 'AT_TARGET' | 'ABOVE' | 'UNDETERMINED';
}
export type Assessment = 'NOT_ASSESSED' | 'INSUFFICIENT_EVIDENCE' | 'NOT_DEMONSTRATED'
  | 'DEMONSTRATED_BELOW_TARGET' | 'DEMONSTRATED_AT_TARGET' | 'DEMONSTRATED_ABOVE_TARGET';
export interface ObjectiveReport {
  objective_id: string; skill_id: string; claim: string; assessment: Assessment;
  inferred: boolean; jd_evidence_spans: string[];
  lifecycle: string; stop_reason: string | null; excluded_reason: string | null;
  covered_criteria: string[]; missing_criteria: string[];
  strengths: string[]; weaknesses: string[]; study_recommendations?: string[];
  evidence: Observation[]; evidence_turn_ids: string[];
  criteria?: { criterion_id: string; description: string; assessment: Assessment;
    turns_spent: number; stop_reason: string | null }[];
}
export interface EvidenceReport {
  schema_version: 2; state_version: number; is_finished: boolean;
  termination_reason: string | null; progress: number; evidence_coverage: number;
  target_attainment: number | null; study_recommendations?: string[];
  objectives: ObjectiveReport[];
}
export interface EvidenceSession {
  schema_version: 2; session_id: string; state_version: number; is_finished: boolean;
  deadline_at: string; config: InterviewConfig; pending_turn: EvidenceTurn | null;
  turns: EvidenceTurn[]; report: EvidenceReport;
  conversation?: ConversationState | null;
}
export type ConversationAction = 'NEXT' | 'SUBMIT_INTRODUCTION' | 'SKIP_INTRODUCTION';
export interface ConversationState {
  phase: 'OPENING' | 'SELF_INTRODUCTION' | 'INTERVIEW' | 'CLOSING' | 'FINISHED';
  message: { message_id: string; text: string };
  opening: { interviewer_name: string; company: string; company_description: string; role_title: string };
  expires_at: string; introduction: string; introduction_skipped: boolean; opening_text: string;
}
export interface ConversationRequest {
  request_id: string; message_id: string; expected_state_version: number;
  action: ConversationAction; introduction: string;
}
export function conversationPhase(session: EvidenceSession | null) {
  return session?.conversation?.phase ?? (session?.is_finished ? 'FINISHED' : 'INTERVIEW');
}
export function voiceTurn(session: EvidenceSession | null) {
  if (!session) return null;
  const phase = conversationPhase(session);
  const id = phase === 'INTERVIEW' ? session.pending_turn?.turn_id
    : phase !== 'FINISHED' ? session.conversation?.message.message_id : null;
  return id ? { turn_id: id, expected_state_version: session.state_version } : null;
}
export interface AnswerRequest {
  request_id: string; turn_id: string; expected_state_version: number; candidate_response: string;
}

function endpoint(id: string, operation = '') {
  return `/api/v2/sessions/${encodeURIComponent(id)}/interview${operation ? `/${operation}` : ''}`;
}

const START_RETRY_DELAY_MS = 5000;

async function requestStart(id: string, config: InterviewConfig): Promise<EvidenceSession | null> {
  try {
    return (await axiosClient.post<EvidenceSession | null>(endpoint(id, 'start'), config)).data;
  } catch (cause) {
    if (!axios.isAxiosError(cause) || cause.response?.status !== 503) throw cause;
    // Start is idempotent. The AI retains completed blueprint batches, so a
    // transient provider failure can resume without repeating successful work.
    await new Promise(resolve => setTimeout(resolve, START_RETRY_DELAY_MS));
    return (await axiosClient.post<EvidenceSession | null>(endpoint(id, 'start'), config)).data;
  }
}

export const evidenceInterview = {
  async get(id: string): Promise<EvidenceSession | null> {
    try {
      return (await axiosClient.get<EvidenceSession>(endpoint(id))).data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return null;
      throw error;
    }
  },
  async start(id: string, config: InterviewConfig): Promise<EvidenceSession> {
    const data = await requestStart(id, config);
    if (!data || data.schema_version !== 2 || data.session_id !== id || !data.config || !data.report
      || !Array.isArray(data.turns) || typeof data.is_finished !== 'boolean'
      || (!data.is_finished && !((data.conversation?.phase === 'OPENING' || data.conversation?.phase === 'SELF_INTRODUCTION')
          && data.conversation.message?.message_id && data.conversation.message.text?.trim())
        && (typeof data.pending_turn?.question !== 'string' || !data.pending_turn.question.trim()))) {
      throw new Error('Chưa nhận được phiên phỏng vấn hợp lệ. Vui lòng bấm bắt đầu để thử lại.');
    }
    return data;
  },
  async answer(id: string, answer: AnswerRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'respond'), answer)).data;
  },
  async converse(id: string, request: ConversationRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'conversation'), request)).data;
  },
  async stop(session: EvidenceSession, requestId: string): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(session.session_id, 'stop'), {
      request_id: requestId, expected_state_version: session.state_version,
    })).data;
  },
};

export function interviewError(error: unknown): string {
  if (axios.isAxiosError<{ message?: string; detail?: string }>(error)) {
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' || error.response?.status === 504)
      return 'Chuẩn bị phỏng vấn mất quá nhiều thời gian. Vui lòng thử lại; dữ liệu hồ sơ của bạn vẫn được giữ nguyên.';
    if (error.response?.status === 409) return 'Phiên đã thay đổi. Hãy tải lại phiên trước khi tiếp tục.';
    return error.response?.data?.message || error.response?.data?.detail || 'Không thể xử lý yêu cầu. Bạn có thể thử lại.';
  }
  return error instanceof Error ? error.message : 'Không thể xử lý yêu cầu.';
}
