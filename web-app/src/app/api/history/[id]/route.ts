import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    // 1. Get session info
    const sessionRes = await query('SELECT * FROM sessions WHERE id = $1', [id]);
    if (sessionRes.rows.length === 0) {
      return NextResponse.json({ error: 'Session not found' }, { status: 404 });
    }
    const sess = sessionRes.rows[0];

    // 2. Fetch turns for the session
    const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [id]);

    const result = {
      id: sess.id,
      date: sess.date,
      interviewType: sess.interview_type,
      roleTitle: sess.role_title,
      cvFilename: sess.cv_filename,
      jdFilename: sess.jd_filename,
      overallScore: sess.overall_score !== null ? sess.overall_score : undefined,
      status: sess.status,
      overallFeedback: sess.overall_feedback !== null ? sess.overall_feedback : undefined,
      competencyFitScore: sess.competency_fit_score !== null ? sess.competency_fit_score : undefined,
      skillsAnalysis: sess.skills_analysis ? sess.skills_analysis : undefined,
      experienceEvaluation: sess.experience_evaluation !== null ? sess.experience_evaluation : undefined,
      projectEvaluation: sess.project_evaluation !== null ? sess.project_evaluation : undefined,
      actionableSuggestions: sess.actionable_suggestions ? sess.actionable_suggestions : undefined,
      questions: turnsRes.rows.map((t) => ({
        question: t.question,
        answer: t.answer,
        score: t.score,
        strengths: t.strengths,
        improvements: t.improvements,
        suggestedAnswer: t.suggested_answer,
        topicTag: t.topic_tag,
        isDeepDive: t.is_deep_dive
      }))
    };

    return NextResponse.json(result);
  } catch (error: any) {
    console.error(`[API History Detail] Error fetching session detail:`, error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
