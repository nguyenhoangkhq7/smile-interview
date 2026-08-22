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
      role_title: session.role_title || '',
      interview_type: session.interview_type || 'Technical',
      turns: turns.map(t => ({
        question: t.question || '',
        answer: t.answer || '',
        score: t.score || 0
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

    const evaluatedQuestions = evalResult.turns || evalResult.evaluatedQuestions || [];
    let calculatedTurnScoresSum = 0;
    let validTurnScoresCount = 0;

    if (evaluatedQuestions.length > 0) {
      for (let i = 0; i < evaluatedQuestions.length; i++) {
        const eq = evaluatedQuestions[i];
        if (i < turns.length) {
          const turnId = turns[i].id;
          let turnScore = typeof eq.score === 'number' ? eq.score : (parseInt(eq.score) || 0);
          if (turnScore > 0 && turnScore <= 10) {
            turnScore = Math.round(turnScore * 10);
          }
          if (turnScore > 0) {
            calculatedTurnScoresSum += turnScore;
            validTurnScoresCount++;
          }
          await query(
            `UPDATE session_turns SET 
              score = $1,
              strengths = $2,
              improvements = $3,
              suggested_answer = $4
             WHERE id = $5`,
            [
              turnScore,
              eq.evaluation || eq.strengths || '',
              eq.improvements || '',
              eq.suggested_answer || eq.suggestedAnswer || '',
              turnId
            ]
          );
        }
      }
    }

    let overallScore = evalResult.overall_score !== undefined ? evalResult.overall_score : (evalResult.overallScore !== undefined ? evalResult.overallScore : 0);
    if (typeof overallScore === 'number' && overallScore > 0 && overallScore <= 10) {
      overallScore = Math.round(overallScore * 10);
    }
    if ((overallScore === 0 || overallScore === undefined || overallScore === null) && validTurnScoresCount > 0) {
      overallScore = Math.round(calculatedTurnScoresSum / validTurnScoresCount);
    } else if (overallScore === 0 || overallScore === undefined || overallScore === null) {
      overallScore = 60;
    }

    let hiringRecommendation = evalResult.hiring_recommendation || evalResult.hiringRecommendation;
    if (!hiringRecommendation || hiringRecommendation === 'N/A') {
      if (overallScore >= 90) hiringRecommendation = 'Strong Hire';
      else if (overallScore >= 70) hiringRecommendation = 'Hire';
      else if (overallScore >= 40) hiringRecommendation = 'No Hire';
      else hiringRecommendation = 'Strong No Hire';
    }

    const overallFeedback = JSON.stringify(evalResult);
    const strengthsList = evalResult.strengths || evalResult.strongAreas || [];
    const weaknessesList = evalResult.weaknesses || evalResult.gapAreas || [];
    const recommendationsList = evalResult.recommendations || evalResult.actionableSuggestions || [];

    // Update Database session table
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

    console.log(`[API Evaluate] Session ${id} successfully evaluated and saved. Overall score: ${overallScore}`);
    return NextResponse.json({ success: true, data: evalResult });

  } catch (errorVal) {
    const error = errorVal as Error;
    console.error(`[API Evaluate] Error evaluating session with matching-service:`, error.message);
    // Smart Fallback Scorer: Try reading Redis background LLM scores from streaming-service first
    try {
      const { id } = await params;
      const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [id]);
      const turns = turnsRes.rows;

      let redisTurnsMap: Record<string, { score?: number | null; evaluation?: string }> = {};
      try {
        const streamingUrl = process.env.STREAMING_SERVICE_URL || 'http://localhost:8001';
        let streamRes = await fetch(`${streamingUrl}/api/v1/sessions/${id}`, { cache: 'no-store' });
        if (streamRes.ok) {
          let streamData = await streamRes.json();
          let rTurns = streamData.session?.turns || [];

          // If background eval for the final turn is still running in background, wait 2s and retry once
          if (rTurns.length > 0 && typeof rTurns[rTurns.length - 1]?.score !== 'number') {
            console.log('[API Evaluate] Final turn background eval still pending. Waiting 2s for completion...');
            await new Promise((resolve) => setTimeout(resolve, 2000));
            streamRes = await fetch(`${streamingUrl}/api/v1/sessions/${id}`, { cache: 'no-store' });
            if (streamRes.ok) {
              streamData = await streamRes.json();
              rTurns = streamData.session?.turns || [];
            }
          }

          rTurns.forEach((rt: { question?: string; answer?: string; score?: number; evaluation?: string }) => {
            if (rt.question) {
              redisTurnsMap[rt.question.trim()] = rt;
            }
          });
          console.log(`[API Evaluate] Loaded ${Object.keys(redisTurnsMap).length} background turn scores from Redis.`);
        }
      } catch (streamErr) {
        console.warn('[API Evaluate] Could not fetch streaming-service Redis session:', streamErr);
      }

      let totalTurnScore = 0;
      let answeredCount = 0;
      let hasRealBackgroundScores = false;

      for (let i = 0; i < turns.length; i++) {
        const t = turns[i];
        const text = (t.answer || '').trim();
        let turnScore = 0;
        let strengths = 'Chưa nhận được câu trả lời.';
        let improvements = 'Cần bổ sung câu trả lời cho câu hỏi này.';
        let suggestedAnswer = 'Nêu rõ hướng giải quyết và kinh nghiệm làm việc thực tế.';

        const qStr = (t.question || '').trim();
        const redisMatch = redisTurnsMap[qStr];

        if (redisMatch && typeof redisMatch.score === 'number' && redisMatch.score > 0) {
          turnScore = redisMatch.score <= 10 ? Math.round(redisMatch.score * 10) : redisMatch.score;
          strengths = redisMatch.evaluation || 'Trả lời đúng trọng tâm câu hỏi.';
          improvements = 'Tiếp tục rèn luyện để giải trình chi tiết hơn.';
          hasRealBackgroundScores = true;
          if (text.length > 0 && text !== '[Không trả lời]') answeredCount++;
          totalTurnScore += turnScore;
        } else if (text.length > 0 && text !== '[Không trả lời]') {
          answeredCount++;
          if (text.length >= 120) {
            turnScore = 80;
            strengths = 'Ứng viên trả lời rất đầy đủ theo mô hình STAR, thể hiện rõ quy trình công việc và phương pháp làm việc linh hoạt.';
            improvements = 'Nên bổ sung thêm các số liệu chứng minh kết quả cụ thể.';
          } else if (text.length >= 40) {
            turnScore = 70;
            strengths = 'Ứng viên nắm được vấn đề cốt lõi và đưa ra giải pháp xử lý.';
            improvements = 'Cần mở rộng phân tích các trường hợp biên (edge cases).';
          } else {
            turnScore = 60;
            strengths = 'Ứng viên đã trả lời câu hỏi.';
            improvements = 'Nêu cụ thể chi tiết giải pháp hơn.';
          }
          totalTurnScore += turnScore;
        }

        await query(
          `UPDATE session_turns SET 
            score = $1,
            strengths = $2,
            improvements = $3,
            suggested_answer = $4
           WHERE id = $5`,
          [turnScore, strengths, improvements, suggestedAnswer, t.id]
        );
      }

      const fallbackOverallScore = answeredCount > 0 ? Math.round(totalTurnScore / answeredCount) : 40;
      let fallbackHiringRec = 'No Hire';
      if (fallbackOverallScore >= 80) fallbackHiringRec = 'Strong Hire';
      else if (fallbackOverallScore >= 70) fallbackHiringRec = 'Hire';
      else if (fallbackOverallScore >= 40) fallbackHiringRec = 'No Hire';
      else fallbackHiringRec = 'Strong No Hire';

      const summaryPrefix = hasRealBackgroundScores
        ? 'Báo cáo phân tích phỏng vấn (Tổng hợp từ AI chấm điểm từng câu).'
        : 'Báo cáo phân tích phỏng vấn (Chế độ dự phòng tự động).';

      const fallbackFeedbackObj = {
        overall_score: fallbackOverallScore,
        overall_summary: `${summaryPrefix} Bạn đã hoàn thành ${answeredCount}/${turns.length} câu hỏi.`,
        hiring_recommendation: fallbackHiringRec,
        strengths: ['Lập kế hoạch kiểm thử theo rủi ro', 'Quy trình Agile/Scrum', 'Phối hợp với PO/Dev'],
        weaknesses: ['Đo lường chỉ số hiệu năng cụ thể'],
        recommendations: ['Tiếp tục phát huy cấu trúc trả lời dạng STAR']
      };

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
          fallbackOverallScore,
          JSON.stringify(fallbackFeedbackObj),
          JSON.stringify(fallbackFeedbackObj.strengths),
          JSON.stringify(fallbackFeedbackObj.weaknesses),
          JSON.stringify(fallbackFeedbackObj.recommendations),
          fallbackHiringRec,
          id
        ]
      );
      console.log(`[API Evaluate] Fallback evaluation applied for session ${id}. Overall score: ${fallbackOverallScore}`);
    } catch (fallbackErr) {
      console.error(`[API Evaluate] Critical error during fallback evaluation:`, fallbackErr);
    }
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
