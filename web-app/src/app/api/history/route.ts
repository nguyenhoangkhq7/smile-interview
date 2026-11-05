import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function GET(request: NextRequest) {
  try {
    const authHeader = request.headers.get('Authorization');
    const endpoint = authHeader ? '/api/v1/sessions/user' : '/api/v1/sessions';
    const backendRes = await forwardToBackend(endpoint, request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    console.error('[API History] Error fetching history:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await request.json();
    const backendRes = await forwardToBackend('/api/v1/sessions', request, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(session),
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json({ success: true, session: data });
  } catch (error) {
    const err = error as Error;
    console.error('[API History] Error saving history:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
