import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    if (!id) {
      return NextResponse.json({ error: 'Session ID is required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend(`/api/v1/sessions/${id}/clone`, request, {
      method: 'POST',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    console.error('[API History Clone] Error:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
