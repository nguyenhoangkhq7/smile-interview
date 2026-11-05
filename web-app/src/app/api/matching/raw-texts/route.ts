import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const resumeId = searchParams.get('resumeId') || '';
    const jdId = searchParams.get('jdId') || '';

    if (!resumeId && !jdId) {
      return NextResponse.json(
        { error: 'At least one of resumeId or jdId is required' },
        { status: 400 }
      );
    }

    const backendRes = await forwardToBackend(`/api/v1/sessions/raw-texts?resumeId=${resumeId}&jdId=${jdId}`, request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[raw-texts] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
