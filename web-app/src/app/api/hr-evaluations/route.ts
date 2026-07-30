import { NextRequest, NextResponse } from 'next/server';

/**
 * Proxy POST requests for HR evaluations to matching-service backend.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/hr-evaluations`;

    console.log(`[API Proxy HR Evaluation] Forwarding POST to: ${targetUrl}`);
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body),
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy HR Evaluation] Backend error status ${backendRes.status}:`, errText);
      let detail = errText;
      try {
        const parsed = JSON.parse(errText);
        detail = parsed.detail || parsed.message || parsed.error || errText;
      } catch {
        // use raw errText
      }
      return NextResponse.json({ error: detail }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy HR Evaluation] Error in proxy:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
