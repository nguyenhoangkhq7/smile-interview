import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(request: NextRequest) {
  try {
    const { resumeId } = await request.json();
    if (!resumeId) {
      return NextResponse.json({ error: 'resumeId is required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend('/api/auth/profile', request, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ defaultResumeId: String(resumeId) }),
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    return NextResponse.json({ success: true, defaultResumeId: String(resumeId) });
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[API Set Default Resume] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
