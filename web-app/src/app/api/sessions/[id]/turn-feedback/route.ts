import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: sessionId } = await params;
    const body = await request.json();
    const { turnId, hrRating, hrFeedback } = body;

    if (!sessionId) {
      return NextResponse.json({ error: 'sessionId is required' }, { status: 400 });
    }
    if (!turnId) {
      return NextResponse.json({ error: 'turnId is required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend(`/api/v1/sessions/${sessionId}/turns/${turnId}/feedback`, request, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hrRating, hrFeedback }),
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    console.error('[API Turn Feedback] Error:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
