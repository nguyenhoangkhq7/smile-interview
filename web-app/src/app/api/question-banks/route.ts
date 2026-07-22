import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, questionConfig } = body;

    if (!sessionId || !questionConfig) {
      return NextResponse.json({ error: 'sessionId and questionConfig are required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/question-banks/generate`;

    console.log(`[API Proxy QuestionBank] Forwarding to backend: ${targetUrl}`);
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    // Calculate total questions requested from categories
    const totalQuestions =
      (questionConfig.behavioural || 0) +
      (questionConfig.technical || 0) +
      (questionConfig.coding || 0) +
      (questionConfig.systemDesign || 0) ||
      5;

    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        session_id: sessionId,
        question_config: {
          totalQuestions: totalQuestions,
          total_questions: totalQuestions
        }
      })
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy QuestionBank] Backend error status ${backendRes.status}:`, errText);
      return NextResponse.json({ error: `Backend error: ${backendRes.statusText}` }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (errorVal) { const error = errorVal as Error;
    console.error('[API Proxy QuestionBank] Error in proxy:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
