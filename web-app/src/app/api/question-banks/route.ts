import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, questionConfig } = body;

    if (!sessionId || !questionConfig) {
      return NextResponse.json({ error: 'sessionId and questionConfig are required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/question-bank/generate`;

    console.log(`[API Proxy QuestionBank] Forwarding to backend: ${targetUrl}`);
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    // Calculate total questions and distribution from categories
    const behavioural = questionConfig.behavioural || 0;
    const technical = questionConfig.technical || 0;
    const coding = questionConfig.coding || 0;
    const systemDesign = questionConfig.systemDesign || 0;
    const total = behavioural + technical + coding + systemDesign || 5;

    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        sessionId: sessionId,
        questionConfig: {
          total: total,
          mode: questionConfig.mode || 'SCREENING',
          interview_channel: questionConfig.interviewChannel || questionConfig.interview_channel || 'VOICE',
          distribution: {
            behavioral: behavioural,
            technical: technical,
            coding: coding,
            system_design: systemDesign
          }
        }
      })
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy QuestionBank] Backend error status ${backendRes.status}:`, errText);
      let detail = errText;
      try {
        const parsed = JSON.parse(errText);
        detail = parsed.message || parsed.error || errText;
      } catch {
        // use raw errText
      }
      const errorMessage = detail
        ? `Backend error (${backendRes.status}): ${detail}`
        : `Backend error: ${backendRes.status} ${backendRes.statusText}`.trim();
      return NextResponse.json({ error: errorMessage }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (errorVal) { const error = errorVal as Error;
    console.error('[API Proxy QuestionBank] Error in proxy:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
