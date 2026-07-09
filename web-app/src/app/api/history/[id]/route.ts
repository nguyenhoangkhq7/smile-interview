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
    let turns = turnsRes.rows;



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
      strongAreas: sess.strong_areas ? sess.strong_areas : undefined,
      gapAreas: sess.gap_areas ? sess.gap_areas : undefined,
      criticalMissingSkills: sess.critical_missing_skills ? sess.critical_missing_skills : undefined,
      sectionWiseFeedback: sess.section_wise_feedback ? sess.section_wise_feedback : undefined,
      actionableSuggestions: sess.actionable_suggestions ? sess.actionable_suggestions : undefined,
      evidenceItems: sess.evidence_items ? sess.evidence_items : undefined,
      additionalEvidenceItems: sess.additional_evidence_items ? sess.additional_evidence_items : undefined,
      scoreBreakdown: sess.score_breakdown ? sess.score_breakdown : undefined,
      topPriorityImprovements: sess.top_priority_improvements ? sess.top_priority_improvements : undefined,
      hiringRecommendation: sess.hiring_recommendation ? sess.hiring_recommendation : undefined,
      questions: turns.map((t) => ({
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
