import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function POST(
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
    const session = sessionRes.rows[0];

    // 2. Fetch turns (QA details) for the session
    const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [id]);
    const turns = turnsRes.rows;

    if (turns.length === 0) {
      // If no questions were answered, just update status and default scores
      await query(
        `UPDATE sessions SET 
          status = 'Completed', 
          overall_score = 60, 
          overall_feedback = 'Không có câu hỏi nào được trả lời trong phiên phỏng vấn này.' 
         WHERE id = $1`,
        [id]
      );
      return NextResponse.json({ success: true, message: 'No questions answered' });
    }

    const matchingServiceUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${matchingServiceUrl}/api/v2/assess-resume/evaluate-session`;

    const payload = {
      sessionId: id,
      roleTitle: session.role_title || '',
      interviewType: session.interview_type || 'Technical',
      turns: turns.map(t => ({
        question: t.question || '',
        answer: t.answer || '',
        score: t.score || 0,
        strengths: t.strengths || ''
      }))
    };

    console.log(`[API Evaluate] Forwarding evaluation to matching-service: ${targetUrl}`);
    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      throw new Error(`Matching-service responded with error: ${backendRes.status} ${errText}`);
    }

    const evalResult = await backendRes.json();

    // 5. Update Database
    // Update session table
    await query(
      `UPDATE sessions SET 
        status = 'Completed',
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

    // Update turns table with granular evaluation
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

    console.log(`[API Evaluate] Session ${id} successfully evaluated and saved.`);
    return NextResponse.json({ success: true, data: evalResult });

  } catch (error: any) {
    console.error(`[API Evaluate] Error evaluating session:`, error);
    // Graceful fallback
    try {
      const { id } = await params;
      await query(
        `UPDATE sessions SET status = 'Completed' WHERE id = $1`,
        [id]
      );
    } catch {}
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
