import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET() {
  try {
    // 1. Get all sessions with joined resumes & job_descriptions for Cloudinary URLs
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
      ORDER BY s.id, s.date DESC
    `;
    const sessionsRes = await query(sql);
    const sessions = sessionsRes.rows;

    if (sessions.length === 0) {
      return NextResponse.json([]);
    }

    // 2. Fetch turns for each session
    const fullSessions = await Promise.all(
      sessions.map(async (sess) => {
        const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [sess.id]);
        
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

        return {
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
          gateEvidenceItems: parseJsonField(sess.gate_evidence_items) || [],
          mustHaveEvidenceItems: parseJsonField(sess.must_have_evidence_items) || parseJsonField(sess.evidence_items) || [],
          preferToHaveEvidenceItems: parseJsonField(sess.prefer_to_have_evidence_items) || parseJsonField(sess.additional_evidence_items) || [],
          evidenceItems: parseJsonField(sess.must_have_evidence_items) || parseJsonField(sess.evidence_items) || [],
          additionalEvidenceItems: parseJsonField(sess.prefer_to_have_evidence_items) || parseJsonField(sess.additional_evidence_items) || [],
          scoreBreakdown: parseJsonField(sess.score_breakdown) || null,
          topPriorityImprovements: parseJsonField(sess.top_priority_improvements) || [],
          quickWins: parseJsonField(sess.quick_wins) || [],
          skillGaps: parseJsonField(sess.skill_gaps) || [],
          hiringRecommendation: sess.hiring_recommendation ? sess.hiring_recommendation : undefined,
          eligibility: parseJsonField(sess.eligibility) || null,
          currentStage: sess.current_stage || 'COMPLETED',
          questions: turnsRes.rows.map((t) => ({
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
      })
    );

    return NextResponse.json(fullSessions);
  } catch (error) {
    const err = error as Error;
    console.error('[API History] Error fetching history:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await request.json();

    if (!session || !session.id) {
      return NextResponse.json({ error: 'Session details with id are required' }, { status: 400 });
    }

    const isValidUuid = (val?: string | null) => 
      !!val && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(val));

    // 1. Upsert session info
    const upsertSessionSql = `
      INSERT INTO sessions (
        id, date, interview_type, role_title, cv_filename, jd_filename,
        overall_score, status, overall_feedback, competency_fit_score,
        technical_depth_score, match_level, candidate_level, role_type_detected,
        years_of_experience_estimate, strong_areas, gap_areas, critical_missing_skills,
        section_wise_feedback, actionable_suggestions, resume_id, jd_id,
        evidence_items, additional_evidence_items, score_breakdown, top_priority_improvements,
        hiring_recommendation, eligibility, gate_evidence_items, must_have_evidence_items, prefer_to_have_evidence_items,
        quick_wins, skill_gaps
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33)
      ON CONFLICT (id) DO UPDATE SET
        date = EXCLUDED.date,
        interview_type = EXCLUDED.interview_type,
        role_title = EXCLUDED.role_title,
        cv_filename = EXCLUDED.cv_filename,
        jd_filename = EXCLUDED.jd_filename,
        overall_score = EXCLUDED.overall_score,
        status = EXCLUDED.status,
        overall_feedback = EXCLUDED.overall_feedback,
        competency_fit_score = EXCLUDED.competency_fit_score,
        technical_depth_score = EXCLUDED.technical_depth_score,
        match_level = EXCLUDED.match_level,
        candidate_level = EXCLUDED.candidate_level,
        role_type_detected = EXCLUDED.role_type_detected,
        years_of_experience_estimate = EXCLUDED.years_of_experience_estimate,
        strong_areas = EXCLUDED.strong_areas,
        gap_areas = EXCLUDED.gap_areas,
        critical_missing_skills = EXCLUDED.critical_missing_skills,
        section_wise_feedback = EXCLUDED.section_wise_feedback,
        actionable_suggestions = EXCLUDED.actionable_suggestions,
        resume_id = EXCLUDED.resume_id,
        jd_id = EXCLUDED.jd_id,
        evidence_items = EXCLUDED.evidence_items,
        additional_evidence_items = EXCLUDED.additional_evidence_items,
        score_breakdown = EXCLUDED.score_breakdown,
        top_priority_improvements = EXCLUDED.top_priority_improvements,
        hiring_recommendation = EXCLUDED.hiring_recommendation,
        eligibility = EXCLUDED.eligibility,
        gate_evidence_items = EXCLUDED.gate_evidence_items,
        must_have_evidence_items = EXCLUDED.must_have_evidence_items,
        prefer_to_have_evidence_items = EXCLUDED.prefer_to_have_evidence_items,
        quick_wins = EXCLUDED.quick_wins,
        skill_gaps = EXCLUDED.skill_gaps
    `;

    await query(upsertSessionSql, [
      session.id,
      session.date || new Date().toISOString(),
      session.interviewType || 'Technical',
      session.roleTitle || '',
      session.cvFilename || '',
      session.jdFilename || '',
      session.overallScore !== undefined ? session.overallScore : null,
      session.status || 'Not started',
      session.overallFeedback !== undefined ? session.overallFeedback : null,
      session.competencyFitScore !== undefined ? session.competencyFitScore : null,
      session.technicalDepthScore !== undefined ? session.technicalDepthScore : null,
      session.matchLevel ? session.matchLevel : null,
      session.candidateLevel ? session.candidateLevel : null,
      session.roleTypeDetected ? session.roleTypeDetected : null,
      session.yearsOfExperienceEstimate ? session.yearsOfExperienceEstimate : null,
      session.strongAreas ? JSON.stringify(session.strongAreas) : null,
      session.gapAreas ? JSON.stringify(session.gapAreas) : null,
      session.criticalMissingSkills ? JSON.stringify(session.criticalMissingSkills) : null,
      session.sectionWiseFeedback ? JSON.stringify(session.sectionWiseFeedback) : null,
      session.actionableSuggestions ? JSON.stringify(session.actionableSuggestions) : null,
      isValidUuid(session.resumeId) ? session.resumeId : null,
      isValidUuid(session.jdId) ? session.jdId : null,
      (session.mustHaveEvidenceItems || session.evidenceItems) ? JSON.stringify(session.mustHaveEvidenceItems || session.evidenceItems) : null,
      (session.preferToHaveEvidenceItems || session.additionalEvidenceItems) ? JSON.stringify(session.preferToHaveEvidenceItems || session.additionalEvidenceItems) : null,
      session.scoreBreakdown ? JSON.stringify(session.scoreBreakdown) : null,
      session.topPriorityImprovements ? JSON.stringify(session.topPriorityImprovements) : null,
      session.hiringRecommendation ? session.hiringRecommendation : null,
      session.eligibility ? (typeof session.eligibility === 'string' ? session.eligibility : JSON.stringify(session.eligibility)) : null,
      session.gateEvidenceItems ? JSON.stringify(session.gateEvidenceItems) : null,
      session.mustHaveEvidenceItems ? JSON.stringify(session.mustHaveEvidenceItems) : null,
      session.preferToHaveEvidenceItems ? JSON.stringify(session.preferToHaveEvidenceItems) : null,
      session.quickWins ? JSON.stringify(session.quickWins) : null,
      session.skillGaps ? JSON.stringify(session.skillGaps) : null,
    ]);


    // 2. Replace turns only when explicitly requested.
    if (session.replaceQuestions === true) {
      await query('DELETE FROM session_turns WHERE session_id = $1', [session.id]);

      if (session.questions && session.questions.length > 0) {
        for (const t of session.questions) {
          const insertTurnSql = `
            INSERT INTO session_turns (
              session_id, question, answer, score, strengths, improvements, suggested_answer, topic_tag, is_deep_dive, good_answer_signals
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
          `;
          await query(insertTurnSql, [
            session.id,
            t.question,
            t.answer,
            t.score,
            t.strengths,
            t.improvements,
            t.suggestedAnswer,
            t.topicTag,
            t.isDeepDive,
            t.goodAnswerSignals ? JSON.stringify(t.goodAnswerSignals) : null
          ]);
        }
      }
    }

    return NextResponse.json({ success: true, session });
  } catch (error) {
    const err = error as Error;
    console.error('[API History] Error saving history:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
