import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    // 1. Get session info from Spring Boot backend
    const sessionRes = await forwardToBackend(`/api/v1/sessions/${id}`, request, {
      method: 'GET',
    });
    if (!sessionRes.ok) {
      return NextResponse.json({ error: 'Session not found' }, { status: 404 });
    }
    const session = await sessionRes.json();

    // 1a. Idempotency guard: skip re-evaluation if already completed
    const alreadyEvaluated =
      session.overallScore !== null &&
      session.overallScore !== undefined &&
      session.overallScore > 0 &&
      session.overallFeedback !== null &&
      session.overallFeedback !== '';
    if (alreadyEvaluated) {
      console.log(`[API Evaluate] Session ${id} already evaluated (score=${session.overallScore}). Skipping LLM call.`);
      return NextResponse.json({
        success: true,
        cached: true,
        data: {
          overallScore: session.overallScore,
          hiringRecommendation: session.overallFeedback?.hiringRecommendation || 'Hire',
        },
      });
    }

    // 2. Fetch turns from session
    const turns = session.turns || [];
    if (turns.length === 0) {
      await forwardToBackend(`/api/v1/sessions/${id}`, request, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'Completed',
          overallScore: 0,
          overallFeedback: 'Không có câu hỏi nào trong phiên phỏng vấn này.',
        }),
      });
      return NextResponse.json({ success: true, message: 'No questions found' });
    }

    // 3. Helper to detect warmup introduction turn
    const isWarmupTurn = (t: { topicTag?: string; question?: string }) => {
      const qText = (t.question || '').toLowerCase();
      return (
        t.topicTag === 'Warmup' ||
        t.topicTag === 'Khởi động' ||
        qText.includes('giới thiệu đôi nét về bản thân') ||
        qText.includes('giới thiệu về bản thân') ||
        qText.includes('khởi động')
      );
    };

    const technicalTurns = turns.filter((t: { topicTag?: string; question?: string }) => !isWarmupTurn(t));
    const answeredTechnicalTurns = technicalTurns.filter((t: { answer?: string }) => t.answer && t.answer.trim().length > 0);

    if (answeredTechnicalTurns.length === 0) {
      await forwardToBackend(`/api/v1/sessions/${id}`, request, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'Completed',
          overallScore: 0,
          overallFeedback: 'Ứng viên chưa trả lời câu hỏi chuyên môn nào trong phiên phỏng vấn này.',
        }),
      });
      return NextResponse.json({ success: true, message: 'No technical questions answered' });
    }

    // 4. Send answered technical turns to Spring Boot AI evaluation endpoint
    const payload = {
      role_title: session.roleTitle || '',
      interview_type: session.interviewType || 'Technical',
      total_base_questions: Math.max(technicalTurns.length, 1),
      turns: answeredTechnicalTurns.map((t: { question?: string; answer?: string; score?: number; isDeepDive?: boolean }) => ({
        question: t.question || '',
        answer: t.answer || '',
        score: t.score || 0,
        is_deep_dive: Boolean(t.isDeepDive),
        is_warmup: false,
      })),
    };

    console.log(`[API Evaluate] Forwarding evaluation to Spring Boot backend: /api/v2/assess-resume/evaluate-session`);
    const evalRes = await forwardToBackend('/api/v2/assess-resume/evaluate-session', request, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!evalRes.ok) {
      const errText = await evalRes.text();
      throw new Error(`Spring Boot backend evaluation failed: ${evalRes.status} ${errText}`);
    }

    const evalResult = await evalRes.json();
    const overallScore = evalResult.overallScore ?? 75;

    let hiringRecommendation = 'No Hire';
    if (overallScore >= 90) hiringRecommendation = 'Strong Hire';
    else if (overallScore >= 70) hiringRecommendation = 'Hire';
    else if (overallScore < 40) hiringRecommendation = 'Strong No Hire';

    const feedbackPayload = JSON.stringify({
      ...evalResult,
      overallScore,
      hiringRecommendation,
    });

    // 5. Update Session status and score in Spring Boot
    await forwardToBackend(`/api/v1/sessions/${id}`, request, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'Completed',
        overallScore,
        overallFeedback: feedbackPayload,
      }),
    });

    console.log(`[API Evaluate] Session ${id} successfully evaluated: score=${overallScore}`);
    return NextResponse.json({
      success: true,
      data: {
        ...evalResult,
        overallScore,
        hiringRecommendation,
      },
    });
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error(`[API Evaluate] Error evaluating session:`, error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
