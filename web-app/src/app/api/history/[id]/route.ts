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
    const turns = turnsRes.rows;

    const parseJsonField = (val: unknown) => {
      if (typeof val === 'string') {
        try {
          return JSON.parse(val);
        } catch {
          return val;
        }
      }
      return val;
    };

    const result = {
      id: sess.id,
      date: sess.date,
      interviewType: sess.interview_type,
      roleTitle: sess.role_title,
      cvFilename: sess.cv_filename,
      jdFilename: sess.jd_filename,
      resumeId: sess.resume_id,
      jdId: sess.jd_id,
      overallScore: sess.overall_score !== null ? sess.overall_score : undefined,
      status: sess.status,
      overallFeedback: sess.overall_feedback !== null ? sess.overall_feedback : undefined,
      competencyFitScore: sess.competency_fit_score !== null ? sess.competency_fit_score : undefined,
      technicalDepthScore: sess.technical_depth_score !== null ? sess.technical_depth_score : undefined,
      matchLevel: sess.match_level ? sess.match_level : undefined,
      candidateLevel: sess.candidate_level ? sess.candidate_level : undefined,
      roleTypeDetected: sess.role_type_detected ? sess.role_type_detected : undefined,
      yearsOfExperienceEstimate: sess.years_of_experience_estimate ? sess.years_of_experience_estimate : undefined,
      strongAreas: parseJsonField(sess.strong_areas) || [],
      gapAreas: parseJsonField(sess.gap_areas) || [],
      criticalMissingSkills: parseJsonField(sess.critical_missing_skills) || [],
      sectionWiseFeedback: parseJsonField(sess.section_wise_feedback) || {},
      actionableSuggestions: parseJsonField(sess.actionable_suggestions) || [],
      evidenceItems: parseJsonField(sess.evidence_items) || [],
      additionalEvidenceItems: parseJsonField(sess.additional_evidence_items) || [],
      scoreBreakdown: parseJsonField(sess.score_breakdown) || null,
      topPriorityImprovements: parseJsonField(sess.top_priority_improvements) || [],
      hiringRecommendation: sess.hiring_recommendation ? sess.hiring_recommendation : undefined,
      eligibility: parseJsonField(sess.eligibility) || null,
      questions: turns.map((t) => ({
        question: t.question,
        answer: t.answer,
        score: t.score,
        strengths: t.strengths,
        improvements: t.improvements,
        suggestedAnswer: t.suggested_answer,
        topicTag: t.topic_tag,
        isDeepDive: t.is_deep_dive,
        goodAnswerSignals: parseJsonField(t.good_answer_signals) || []
      }))
    };

    return NextResponse.json(result);
  } catch (error) {
    const err = error as Error;
    console.error(`[API History Detail] Error fetching session detail:`, err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
