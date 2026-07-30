export interface HrEvaluationAdminItem {
  id: string;
  session_id: string;
  user_id?: string | null;
  evaluator_name?: string | null;
  rating_matching_accuracy?: number | null;
  rating_ai_rationale?: number | null;
  rating_question_quality?: number | null;
  feedback_notes?: string | null;
  created_at: string;
}
