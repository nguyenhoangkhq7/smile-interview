import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export const maxDuration = 300;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { searchParams } = new URL(request.url);
    const forceRefresh = searchParams.get('forceRefresh') === 'true';

    const backendRes = await forwardToBackend(
      `/api/v1/sessions/${id}/analyze-gap?forceRefresh=${forceRefresh}`,
      request,
      { method: 'POST' }
    );

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      return NextResponse.json({ error: errText }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
