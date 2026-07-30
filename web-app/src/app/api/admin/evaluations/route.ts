import { NextRequest, NextResponse } from 'next/server';

/**
 * Proxy GET requests for all HR evaluations (Admin only) to matching-service backend.
 */
export async function GET(request: NextRequest) {
  try {
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/hr-evaluations/all`;

    console.log(`[API Proxy Admin Evaluations] Forwarding GET to: ${targetUrl}`);
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = {};
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const backendRes = await fetch(targetUrl, {
      method: 'GET',
      headers: headers,
      cache: 'no-store',
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Admin Evaluations] Backend error ${backendRes.status}:`, errText);
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
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy Admin Evaluations] Error in proxy:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
