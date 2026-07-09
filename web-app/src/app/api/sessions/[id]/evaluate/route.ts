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
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload)
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      throw new Error(`Matching-service responded with error: ${backendRes.status} ${errText}`);
    }

    const evalResult = await backendRes.json();
    console.log('[Evaluate] Raw backend response:', evalResult);

    const overallScore = evalResult.overall_score !== undefined ? evalResult.overall_score : (evalResult.overallScore !== undefined ? evalResult.overallScore : 60);
    const overallFeedback = evalResult.overall_summary || evalResult.overallFeedback || '';
    const strengthsList = evalResult.strengths || evalResult.strongAreas || [];
    const weaknessesList = evalResult.weaknesses || evalResult.gapAreas || [];
    const recommendationsList = evalResult.recommendations || evalResult.actionableSuggestions || [];
    const hiringRecommendation = evalResult.hiring_recommendation || evalResult.hiringRecommendation || 'N/A';

    // 5. Update Database
    // Update session table
    await query(
      `UPDATE sessions SET 
        status = 'Completed',
        overall_score = $1,
        overall_feedback = $2,
        strong_areas = $3,
        gap_areas = $4,
        actionable_suggestions = $5,
        hiring_recommendation = $6
       WHERE id = $7`,
      [
        overallScore,
        overallFeedback,
        JSON.stringify(strengthsList),
        JSON.stringify(weaknessesList),
        JSON.stringify(recommendationsList),
        hiringRecommendation,
        id
      ]
    );

    // Update turns table with granular evaluation using index to avoid minor question text mismatches from the LLM
    const evaluatedQuestions = evalResult.turns || evalResult.evaluatedQuestions || [];
    if (evaluatedQuestions.length > 0) {
      for (let i = 0; i < evaluatedQuestions.length; i++) {
        const eq = evaluatedQuestions[i];
        if (i < turns.length) {
          const turnId = turns[i].id;
          await query(
            `UPDATE session_turns SET 
              score = $1,
              strengths = $2,
              improvements = $3,
              suggested_answer = $4
             WHERE id = $5`,
            [
              eq.score || 0,
              eq.evaluation || eq.strengths || '',
              eq.improvements || '',
              eq.suggested_answer || eq.suggestedAnswer || '',
              turnId
            ]
          );
        }
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
