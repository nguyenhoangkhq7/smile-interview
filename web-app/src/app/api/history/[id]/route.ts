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

    // 1. Get session info with joined resumes & job_descriptions for Cloudinary URLs
    const sql = `
      SELECT DISTINCT ON (s.id)
        s.*,
        r.file_url AS cv_file_url,
        r.extracted_text AS cv_extracted_text,
        j.file_url AS jd_file_url,
        j.extracted_text AS jd_extracted_text
      FROM sessions s
      LEFT JOIN resumes r ON (s.resume_id = r.id OR s.cv_filename = r.file_name)
      LEFT JOIN job_descriptions j ON (s.jd_id = j.id OR s.jd_filename = j.title)
      WHERE s.id = $1
      ORDER BY s.id, s.date DESC
    `;
    const sessionRes = await query(sql, [id]);
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
      cvFileUrl: sess.cv_file_url || undefined,
      jdFileUrl: sess.jd_file_url || undefined,
      cvExtractedText: sess.cv_extracted_text || undefined,
      jdExtractedText: sess.jd_extracted_text || undefined,
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
      mustHaveEvidenceItems: parseJsonField(sess.must_have_evidence_items) || parseJsonField(sess.evidence_items) || [],
      preferToHaveEvidenceItems: parseJsonField(sess.prefer_to_have_evidence_items) || parseJsonField(sess.additional_evidence_items) || [],
      evidenceItems: parseJsonField(sess.must_have_evidence_items) || parseJsonField(sess.evidence_items) || [],
      additionalEvidenceItems: parseJsonField(sess.prefer_to_have_evidence_items) || parseJsonField(sess.additional_evidence_items) || [],
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
