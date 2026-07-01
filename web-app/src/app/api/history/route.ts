import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET() {
  try {
    // 1. Get all sessions
    const sessionsRes = await query('SELECT * FROM sessions ORDER BY date DESC');
    const sessions = sessionsRes.rows;

    if (sessions.length === 0) {
      return NextResponse.json([]);
    }

    // 2. Fetch turns for each session
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
      })
    );

    return NextResponse.json(fullSessions);
  } catch (error: any) {
    console.error('[API History] Error fetching history:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await request.json();

    if (!session || !session.id) {
      return NextResponse.json({ error: 'Session details with id are required' }, { status: 400 });
    }

    // 1. Upsert session info
    const upsertSessionSql = `
      INSERT INTO sessions (
        id, date, interview_type, role_title, cv_filename, jd_filename,
        overall_score, status, overall_feedback, competency_fit_score,
        skills_analysis, experience_evaluation, project_evaluation, actionable_suggestions
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
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
        skills_analysis = EXCLUDED.skills_analysis,
        experience_evaluation = EXCLUDED.experience_evaluation,
        project_evaluation = EXCLUDED.project_evaluation,
        actionable_suggestions = EXCLUDED.actionable_suggestions
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
      session.skillsAnalysis ? session.skillsAnalysis : null,
      session.experienceEvaluation !== undefined ? session.experienceEvaluation : null,
      session.projectEvaluation !== undefined ? session.projectEvaluation : null,
      session.actionableSuggestions ? session.actionableSuggestions : null,
    ]);

    // 2. Delete existing turns
    await query('DELETE FROM session_turns WHERE session_id = $1', [session.id]);

    // 3. Insert new turns if present
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

    return NextResponse.json({ success: true, session });
  } catch (error: any) {
    console.error('[API History] Error saving history:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
