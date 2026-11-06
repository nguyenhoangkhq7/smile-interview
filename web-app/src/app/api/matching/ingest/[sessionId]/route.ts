import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export const maxDuration = 300;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    const formData = await request.formData();

    const backendRes = await forwardToBackend(`/api/v1/sessions/${sessionId}/documents`, request, {
      method: 'POST',
      body: formData,
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      let detail = errText;
      try {
        const parsed = JSON.parse(errText);
        detail = parsed.message || parsed.error || errText;
      } catch {
        // use raw errText
      }
      return NextResponse.json({ error: detail }, { status: backendRes.status });
    }

    const result = await backendRes.json();

    return NextResponse.json({
      sessionId: result.sessionId || sessionId,
      success: true,
      cvFilename: result.cvFilename,
      jdFilename: result.jdFilename,
      cvTextLength: result.cvTextLength,
      jdTextLength: result.jdTextLength,
    });
  } catch (error) {
    const err = error as Error;
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
