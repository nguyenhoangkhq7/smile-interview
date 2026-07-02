import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

// GET: List all sessions
export async function GET() {
  try {
    const sessionsRes = await query('SELECT * FROM sessions ORDER BY date DESC');
    const sessions = sessionsRes.rows;

    const fullSessions = await Promise.all(
      sessions.map(async (sess) => {
        const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [sess.id]);
        return {
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
      })
    );

    return NextResponse.json(fullSessions);
  } catch (error: any) {
    console.error('[API Sessions] Error fetching sessions:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Save/Upsert a session
export async function POST(request: NextRequest) {
  try {
    const session = await request.json();

    if (!session || !session.id) {
      return NextResponse.json({ error: 'Session details with id are required' }, { status: 400 });
    }

    const upsertSessionSql = `
      INSERT INTO sessions (
        id, date, interview_type, role_title, cv_filename, jd_filename,
        overall_score, status, overall_feedback, competency_fit_score,
        technical_depth_score, match_level, candidate_level, role_type_detected,
        years_of_experience_estimate, strong_areas, gap_areas, critical_missing_skills,
        section_wise_feedback, actionable_suggestions, resume_id, jd_id
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
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
        jd_id = EXCLUDED.jd_id
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
      session.resumeId !== undefined ? session.resumeId : null,
      session.jdId !== undefined ? session.jdId : null,
    ]);

    if (session.replaceQuestions === true) {
      await query('DELETE FROM session_turns WHERE session_id = $1', [session.id]);

      if (session.questions && session.questions.length > 0) {
        for (const t of session.questions) {
          const insertTurnSql = `
            INSERT INTO session_turns (
              session_id, question, answer, score, strengths, improvements, suggested_answer, topic_tag, is_deep_dive
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
            t.isDeepDive
          ]);
        }
      }
    }

    return NextResponse.json({ success: true, session });
  } catch (error: any) {
    console.error('[API Sessions] Error saving session:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// DELETE: Delete a session
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    await query('DELETE FROM sessions WHERE id = $1', [id]);
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[API Sessions] Error deleting session:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
