import axios from 'axios';
import axiosClient from '@/lib/axiosClient';

export const questionModes = ['CODING', 'DEBUGGING', 'DESIGN', 'TECHNICAL_EXPLANATION', 'BEHAVIORAL'] as const;
export type QuestionMode = typeof questionModes[number];
export type InteractionMode = 'TEXT' | 'VOICE';
export type SessionPurpose = 'ASSESSMENT' | 'PRACTICE';
export type ClarifyKind = 'CLARIFY_PROMPT' | 'HINT';
export interface TurnClarification {
  kind: ClarifyKind;
  question: string;
  answer: string;
}
export interface ChecklistRef { taskId: number; checklistItemId: number }
export interface InterviewStartConfig {
  recheck?: ChecklistRef;
  interaction_mode: InteractionMode;
  session_purpose?: SessionPurpose;
  include_mastered_skills?: boolean;
  include_behavioral_in_mixed?: boolean;
  focus_skill_ids?: string[];
  focused_question_mode: QuestionMode | null;
  max_questions: number;
  duration_seconds: number;
  max_questions_per_objective?: number;
}
export interface InterviewConfig extends InterviewStartConfig {
  mode: 'MIXED' | 'FOCUSED';
  max_questions_per_objective: number;
}
export const defaultConfig: InterviewStartConfig = {
  interaction_mode: 'TEXT', focused_question_mode: null, max_questions: 10, duration_seconds: 900,
};
export type CodingLanguage = 'python' | 'javascript' | 'sql';
export interface CodingTestCase {
  name: string;
  input_data: string;
  expected_output: string;
}
export interface PublicCodingSpec {
  language: CodingLanguage;
  entry_point: string;
  starter_code: string;
  setup_sql: string;
  sample_tests: CodingTestCase[];
}
export interface CodingCaseResult {
  name: string;
  passed: boolean;
  actual_output: string;
  expected_output: string;
  error: string;
  elapsed_ms: number;
}
export interface RunCodeResult {
  language: CodingLanguage;
  passed: number;
  total: number;
  compile_error: string;
  stdout: string;
  results: CodingCaseResult[];
  environment_notice?: string;
}
export interface PendingTurn {
  turn_id: string; objective_id: string; mode: QuestionMode;
  question: string; introduction?: string; requires_code?: boolean;
  coding_spec?: PublicCodingSpec | null;
  clarifications?: TurnClarification[];
}
export interface EvidenceTurn {
  practice_step?: 'RETRY' | 'TRANSFER' | null;
  turn_id: string; objective_id: string; mode: QuestionMode;
  question: string; answer: string | null; feedback: string | null;
  submitted_code?: string | null; transcript?: string | null;
  clarifications?: TurnClarification[];
  coding_checks?: {
    passed: number; total: number; language?: string; compile_error?: string;
    sample_results?: CodingCaseResult[];
  } | null;
}
export type EvidenceDepthRole = 'TARGET' | 'DIAGNOSTIC' | 'EXTENSION';
export type EvidenceObservation = 'SUPPORTS' | 'CONTRADICTS' | 'UNCLEAR' | 'NO_EVIDENCE';
export interface PublicEvidence {
  turn_id: string;
  criterion_id: string; response_excerpt: string; rationale: string;
  performance: 'BELOW' | 'AT_TARGET' | 'ABOVE' | 'UNDETERMINED';
  depth_role?: EvidenceDepthRole;
  observation?: EvidenceObservation;
}
export interface SessionCoaching {
  overall_summary: string;
  top_strengths: string[];
  priority_gaps: string[];
  actionable_study_steps: string[];
  introduction_feedback?: string;
}
export type Assessment = 'NOT_ASSESSED' | 'INSUFFICIENT_EVIDENCE' | 'NOT_DEMONSTRATED'
  | 'DEMONSTRATED_BELOW_TARGET' | 'DEMONSTRATED_AT_TARGET' | 'DEMONSTRATED_ABOVE_TARGET';
export interface ObjectiveReport {
  objective_id: string; skill_id: string; claim: string; assessment: Assessment;
  jd_evidence_spans: string[];
  target_depth?: number;
  importance_weight?: number;
  is_core?: boolean;
  hinted?: boolean;
  stop_reason: string | null;
  strengths: string[]; weaknesses: string[]; study_recommendations?: string[];
  evidence: PublicEvidence[];
  criteria?: { criterion_id: string; description: string; assessment: Assessment; essential?: boolean; hinted?: boolean; transfer_verified?: boolean }[];
}
export interface TurnReview {
  turn_id: string;
  excerpt: string;
  reason: string;
  gaps?: string[];
  next_step: string;
  reference_answer?: string;
  level_up_tip?: string;
  delivery_notes?: string[];
}
export interface EvidenceReport {
  turn_reviews?: TurnReview[];
  recheck_criterion?: { description: string; assessment: Assessment } | null;
  termination_reason: string | null;
  objectives: ObjectiveReport[];
  coaching?: SessionCoaching | null;
}
export interface EvidenceSession {
  submission?: { status: 'QUEUED' | 'FAILED' | 'UNASSESSED'; turn_id: string; received_at: string; candidate_response: string; submitted_code?: string };
  paused_remaining_seconds?: number | null;
  schema_version: 2; session_id: string; state_version: number; is_finished: boolean;
  deadline_at: string; config: InterviewConfig; pending_turn: PendingTurn | null;
  awaiting_question?: boolean;
  turns: EvidenceTurn[]; report: EvidenceReport;
  conversation?: ConversationState | null;
}
export function turnSkillId(session: Pick<EvidenceSession, 'report'>, turn: { objective_id: string }): string {
  return session.report.objectives.find(objective => objective.objective_id === turn.objective_id)?.skill_id ?? '';
}
export type ConversationAction = 'NEXT' | 'SUBMIT_INTRODUCTION' | 'SKIP_INTRODUCTION';
export interface ConversationState {
  phase: 'OPENING' | 'SELF_INTRODUCTION' | 'INTERVIEW' | 'CLOSING' | 'FINISHED';
  message: { message_id: string; text: string };
  opening: { interviewer_name: string; company: string };
  expires_at: string; introduction: string; opening_text: string;
}
export interface ConversationRequest {
  request_id: string; message_id: string; expected_state_version: number;
  action: ConversationAction; introduction: string;
}
export function conversationPhase(session: EvidenceSession | null) {
  return session?.conversation?.phase ?? (session?.is_finished ? 'FINISHED' : 'INTERVIEW');
}
export function isCodeTurn(turn?: PendingTurn | null): boolean {
  return Boolean(turn && (turn.mode === 'CODING' || turn.requires_code || turn.coding_spec));
}
export function voiceTurn(session: EvidenceSession | null) {
  if (!session) return null;
  const phase = conversationPhase(session);
  const id = phase === 'INTERVIEW' ? session.pending_turn?.turn_id
    : phase !== 'FINISHED' ? session.conversation?.message.message_id : null;
  return id ? { turn_id: id, expected_state_version: session.state_version } : null;
}
export interface AnswerRequest {
  request_id: string; turn_id: string; expected_state_version: number; candidate_response: string; submitted_code?: string;
}
export interface NextQuestionRequest {
  request_id: string; expected_state_version: number;
}
export interface ClarifyRequest {
  request_id: string; turn_id: string; expected_state_version: number;
  kind: ClarifyKind; candidate_question?: string;
}

function endpoint(id: string, operation = '') {
  return `/api/v2/sessions/${encodeURIComponent(id)}/interview${operation ? `/${operation}` : ''}`;
}

const START_RETRY_DELAY_MS = 5000;

async function requestStart(id: string, config: InterviewStartConfig): Promise<EvidenceSession | null> {
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

export interface InterviewLimits {
  maxQuestions: number;
  durationSeconds: number;
  maxQuestionsPerObjective: number;
  voiceEnabled: boolean;
}

export const evidenceInterview = {
  async limits(signal: AbortSignal) {
    return (await axiosClient.get<InterviewLimits>('/api/v2/interview/limits', { signal })).data;
  },
  async get(id: string): Promise<EvidenceSession | null> {
    try {
      return (await axiosClient.get<EvidenceSession>(endpoint(id))).data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return null;
      throw error;
    }
  },
  async start(id: string, config: InterviewStartConfig): Promise<EvidenceSession> {
    const data = await requestStart(id, config);
    if (!data || data.schema_version !== 2 || data.session_id !== id || !data.config || !data.report
      || !Array.isArray(data.turns) || typeof data.is_finished !== 'boolean'
      || (!data.is_finished && !data.awaiting_question && !data.submission && !((data.conversation?.phase === 'OPENING' || data.conversation?.phase === 'SELF_INTRODUCTION')
          && data.conversation.message?.message_id && data.conversation.message.text?.trim())
        && (typeof data.pending_turn?.question !== 'string' || !data.pending_turn.question.trim()))) {
      throw new Error('Chưa nhận được phiên phỏng vấn hợp lệ. Vui lòng bấm bắt đầu để thử lại.');
    }
    return data;
  },
  async answer(id: string, answer: AnswerRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'respond'), answer)).data;
  },
  async nextQuestion(id: string, request: NextQuestionRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'next-question'), request)).data;
  },
  async converse(id: string, request: ConversationRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'conversation'), request)).data;
  },
  async runCode(id: string, payload: { turn_id: string; code: string; language?: CodingLanguage }): Promise<RunCodeResult> {
    return (await axiosClient.post<RunCodeResult>(endpoint(id, 'run-code'), payload)).data;
  },
  async clarify(id: string, request: ClarifyRequest): Promise<EvidenceSession> {
    return (await axiosClient.post<EvidenceSession>(endpoint(id, 'clarify'), request)).data;
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
    if (error.response?.status === 429) return 'Bạn đã hết hạn mức phỏng vấn hôm nay.';
    if (error.response?.status === 422) {
      const serverMessage = error.response?.data?.message || error.response?.data?.detail;
      return serverMessage || 'Thiết lập vượt giới hạn hoặc chế độ phỏng vấn vừa thay đổi. Tải lại để cập nhật.';
    }
    if (error.response?.status === 409) return 'Phiên đã thay đổi. Hãy tải lại phiên trước khi tiếp tục.';
    return error.response?.data?.message || error.response?.data?.detail || 'Không thể xử lý yêu cầu. Bạn có thể thử lại.';
  }
  return error instanceof Error ? error.message : 'Không thể xử lý yêu cầu.';
}
