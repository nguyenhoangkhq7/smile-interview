export interface QuestionItem {
  id?: string;
  type?: 'behavioural' | 'technical' | 'coding' | 'system_design' | string;
  difficulty?: 'easy' | 'medium' | 'hard' | string;
  topic?: string;
  question?: string;
  star_prompt?: string;
  hints?: string[];
  components_to_cover?: string[];
  evaluation_criteria?: string;
  expected_competency?: string;
  rationale?: string;
}

export interface QuestionBankMetadata {
  candidate_level?: string;
  overall_match?: string;
  years_of_experience?: number | null;
  role_type?: string;
  target_domain?: string;
  strong_areas?: string[];
  gap_areas?: string[];
  difficulty_distribution?: Record<string, string>;
  total_questions?: number;
  generation_rationale?: string;
}

export interface QuestionBankData {
  id?: string;
  session_id?: string;
  metadata?: QuestionBankMetadata;
  question_bank?: QuestionItem[];
  created_at?: string;
}

export interface HrEvaluationPayload {
  session_id: string;
  evaluator_name?: string;
  rating_ai_rationale?: number;
  rating_question_quality?: number;
  feedback_notes?: string;
}

export interface HrEvaluationResponse {
  id?: string;
  session_id?: string;
  created_at?: string;
  message?: string;
  error?: string;
}
