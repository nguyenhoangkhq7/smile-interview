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

    // 1a. Idempotency guard: skip re-evaluation if already completed
    const alreadyEvaluated =
      session.overall_score !== null &&
      session.overall_score > 0 &&
      session.overall_feedback !== null &&
      session.overall_feedback !== '';
    if (alreadyEvaluated) {
      console.log(`[API Evaluate] Session ${id} already evaluated (score=${session.overall_score}). Skipping LLM call.`);
      return NextResponse.json({
        success: true,
        cached: true,
        data: {
          overallScore: session.overall_score,
          hiringRecommendation: session.hiring_recommendation,
        }
      });
    }

    // 2. Fetch all turns (QA details) for the session in chronological order
    const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [id]);
    const turns = turnsRes.rows;

    if (turns.length === 0) {
      // If no questions exist, update status and 0 scores
      await query(
        `UPDATE sessions SET 
          status = 'Completed', 
          overall_score = 0, 
          overall_feedback = 'Không có câu hỏi nào trong phiên phỏng vấn này.',
          hiring_recommendation = 'Strong No Hire'
         WHERE id = $1`,
        [id]
      );
      return NextResponse.json({ success: true, message: 'No questions found' });
    }

    // 3. Helper to detect warmup introduction turn
    const isWarmupTurn = (t: { is_warmup?: boolean; topic_tag?: string; question?: string; evaluation?: string }) => {
      const qText = (t.question || '').toLowerCase();
      return (
        t.is_warmup === true ||
        t.topic_tag === 'Warmup' ||
        t.topic_tag === 'Khởi động' ||
        qText.includes('giới thiệu đôi nét về bản thân') ||
        qText.includes('giới thiệu về bản thân') ||
        qText.includes('khởi động') ||
        (t.evaluation && t.evaluation.includes('Icebreaker'))
      );
    };

    const technicalTurns = turns.filter(t => !isWarmupTurn(t));
    const warmupTurns = turns.filter(t => isWarmupTurn(t));

    // Update warmup turns in DB (excluded from technical scoring)
    for (const wt of warmupTurns) {
      await query(
        `UPDATE session_turns SET 
          score = 0,
          strengths = COALESCE(strengths, 'Khởi động / Giới thiệu làm quen'),
          improvements = COALESCE(improvements, '')
         WHERE id = $1`,
        [wt.id]
      );
    }

    // 4. Group technical turns into Base Question groups
    interface TechnicalGroup {
      baseTurn: typeof turns[0];
      followUpTurns: typeof turns;
    }

    const groups: TechnicalGroup[] = [];
    for (const turn of technicalTurns) {
      if (!turn.is_deep_dive || groups.length === 0) {
        groups.push({ baseTurn: turn, followUpTurns: [] });
      } else {
        groups[groups.length - 1].followUpTurns.push(turn);
      }
    }

    const totalBaseQuestions = Math.max(groups.length, 1);
    const answeredTechnicalTurns = technicalTurns.filter(t => t.answer && t.answer.trim().length > 0);

    if (answeredTechnicalTurns.length === 0) {
      // If no technical questions were answered, mark 0 points for all
      for (const t of technicalTurns) {
        await query(
          `UPDATE session_turns SET 
            score = 0,
            improvements = 'Ứng viên chưa trả lời câu hỏi này trong phiên phỏng vấn.'
           WHERE id = $1`,
          [t.id]
        );
      }

      await query(
        `UPDATE sessions SET 
          status = 'Completed', 
          overall_score = 0, 
          overall_feedback = 'Ứng viên chưa trả lời câu hỏi chuyên môn nào trong phiên phỏng vấn này.',
          hiring_recommendation = 'Strong No Hire'
         WHERE id = $1`,
        [id]
      );
      return NextResponse.json({ success: true, message: 'No technical questions answered' });
    }

    // 5. Send answered technical turns to matching-service for LLM evaluation
    const matchingServiceUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${matchingServiceUrl}/api/v2/assess-resume/evaluate-session`;

    const payload = {
      role_title: session.role_title || '',
      interview_type: session.interview_type || 'Technical',
      total_base_questions: totalBaseQuestions,
      turns: answeredTechnicalTurns.map(t => ({
        question: t.question || '',
        answer: t.answer || '',
        score: t.score || 0,
        is_deep_dive: Boolean(t.is_deep_dive),
        is_warmup: false
      }))
    };

    console.log(`[API Evaluate] Forwarding evaluation to matching-service: ${targetUrl} (totalBaseQuestions=${totalBaseQuestions})`);
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

    const evaluatedQuestions = evalResult.turns || evalResult.evaluatedQuestions || [];

    // Map evaluated scores back to answered turns
    for (let i = 0; i < answeredTechnicalTurns.length; i++) {
      const turnId = answeredTechnicalTurns[i].id;
      let turnScore = 0;
      let strengths = '';
      let improvements = '';
      let suggestedAnswer = '';

      if (i < evaluatedQuestions.length) {
        const eq = evaluatedQuestions[i];
        turnScore = typeof eq.score === 'number' ? eq.score : (parseInt(eq.score) || 0);
        if (turnScore > 0 && turnScore <= 10) {
          turnScore = Math.round(turnScore * 10);
        }
        strengths = eq.evaluation || eq.strengths || '';
        improvements = eq.improvements || '';
        suggestedAnswer = eq.suggested_answer || eq.suggestedAnswer || '';
      }

      answeredTechnicalTurns[i].score = turnScore;

      await query(
        `UPDATE session_turns SET 
          score = $1,
          strengths = $2,
          improvements = $3,
          suggested_answer = $4
         WHERE id = $5`,
        [turnScore, strengths, improvements, suggestedAnswer, turnId]
      );
    }

    // For unanswered technical turns: score = 0
    const unansweredTechnicalTurns = technicalTurns.filter(t => !t.answer || t.answer.trim().length === 0);
    for (const ut of unansweredTechnicalTurns) {
      ut.score = 0;
      await query(
        `UPDATE session_turns SET 
          score = 0,
          strengths = '',
          improvements = 'Ứng viên chưa trả lời câu hỏi này trong phiên phỏng vấn.'
         WHERE id = $1`,
        [ut.id]
      );
    }

    // 6. Deterministically calculate Question Score (averaging followups) and Overall Score
    let totalScoreSum = 0;
    for (const group of groups) {
      const isBaseAnswered = !!(group.baseTurn.answer && group.baseTurn.answer.trim().length > 0);
      if (!isBaseAnswered) {
        // Unanswered base question scores 0
        continue;
      }

      const turnsInGroup = [group.baseTurn, ...group.followUpTurns].filter(
        t => t.answer && t.answer.trim().length > 0
      );

      if (turnsInGroup.length > 0) {
        const groupSum = turnsInGroup.reduce((sum, t) => sum + (t.score || 0), 0);
        const groupAvg = Math.round(groupSum / turnsInGroup.length);
        totalScoreSum += groupAvg;
      }
    }

    const calculatedOverallScore = Math.round(totalScoreSum / totalBaseQuestions);

    let hiringRecommendation = 'Strong No Hire';
    if (calculatedOverallScore >= 90) {
      hiringRecommendation = 'Strong Hire';
    } else if (calculatedOverallScore >= 70) {
      hiringRecommendation = 'Hire';
    } else if (calculatedOverallScore >= 40) {
      hiringRecommendation = 'No Hire';
    }

    const overallFeedback = JSON.stringify({
      ...evalResult,
      overallScore: calculatedOverallScore,
      hiringRecommendation: hiringRecommendation
    });
    const strengthsList = evalResult.strengths || evalResult.strongAreas || [];
    const weaknessesList = evalResult.weaknesses || evalResult.gapAreas || [];
    const recommendationsList = evalResult.recommendations || evalResult.actionableSuggestions || [];

    // 7. Update Session table in PostgreSQL
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
        calculatedOverallScore,
        overallFeedback,
        JSON.stringify(strengthsList),
        JSON.stringify(weaknessesList),
        JSON.stringify(recommendationsList),
        hiringRecommendation,
        id
      ]
    );

    console.log(`[API Evaluate] Session ${id} successfully evaluated: overallScore=${calculatedOverallScore}/${totalBaseQuestions} base questions (${hiringRecommendation})`);
    return NextResponse.json({
      success: true,
      data: {
        ...evalResult,
        overallScore: calculatedOverallScore,
        hiringRecommendation: hiringRecommendation
      }
    });

  } catch (errorVal) { const error = errorVal as Error;
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
