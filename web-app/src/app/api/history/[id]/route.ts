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

    // Check if evaluation is needed (session is Completed, and there are turns, and they haven't been evaluated yet)
    const needsEvaluation = sess.status === 'Completed' && 
                            turns.length > 0 && 
                            (!turns[0].suggested_answer || turns[0].suggested_answer.trim() === '');

    if (needsEvaluation) {
      console.log(`[API History Detail] Session ${id} is completed but not evaluated. Triggering auto-evaluation...`);
      try {
        const matchingServiceUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
        const targetUrl = `${matchingServiceUrl}/api/v2/assess-resume/evaluate-session`;

        const payload = {
          sessionId: id,
          roleTitle: sess.role_title || '',
          interviewType: sess.interview_type || 'Technical',
          turns: turns.map(t => ({
            question: t.question || '',
            answer: t.answer || '',
            score: t.score || 0,
            strengths: t.strengths || ''
          }))
        };

        const backendRes = await fetch(targetUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (backendRes.ok) {
          const evalResult = await backendRes.json();

          // Update session table in db
          await query(
            `UPDATE sessions SET 
              overall_score = $1,
              overall_feedback = $2,
              strong_areas = $3,
              gap_areas = $4,
              actionable_suggestions = $5
             WHERE id = $6`,
            [
              evalResult.overallScore || 60,
              evalResult.overallFeedback || '',
              JSON.stringify(evalResult.strongAreas || []),
              JSON.stringify(evalResult.gapAreas || []),
              JSON.stringify(evalResult.actionableSuggestions || []),
              id
            ]
          );

          // Update turns table in db
          if (evalResult.evaluatedQuestions && evalResult.evaluatedQuestions.length > 0) {
            for (const eq of evalResult.evaluatedQuestions) {
              await query(
                `UPDATE session_turns SET 
                  score = $1,
                  strengths = $2,
                  improvements = $3,
                  suggested_answer = $4
                 WHERE session_id = $5 AND question = $6`,
                [
                  eq.score || 0,
                  eq.strengths || '',
                  eq.improvements || '',
                  eq.suggestedAnswer || '',
                  id,
                  eq.question
                ]
              );
            }
          }

          // Reload updated session and turns to return the correct data
          const updatedSessionRes = await query('SELECT * FROM sessions WHERE id = $1', [id]);
          if (updatedSessionRes.rows.length > 0) {
            sess.overall_score = updatedSessionRes.rows[0].overall_score;
            sess.overall_feedback = updatedSessionRes.rows[0].overall_feedback;
            sess.strong_areas = updatedSessionRes.rows[0].strong_areas;
            sess.gap_areas = updatedSessionRes.rows[0].gap_areas;
            sess.critical_missing_skills = updatedSessionRes.rows[0].critical_missing_skills;
            sess.section_wise_feedback = updatedSessionRes.rows[0].section_wise_feedback;
            sess.actionable_suggestions = updatedSessionRes.rows[0].actionable_suggestions;
          }
          const updatedTurnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [id]);
          turns = updatedTurnsRes.rows;
        }
      } catch (evalErr) {
        console.error(`[API History Detail] Auto-evaluation failed for session ${id}:`, evalErr);
      }
    }

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
