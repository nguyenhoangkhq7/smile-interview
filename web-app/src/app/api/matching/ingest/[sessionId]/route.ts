import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';
import { matchKeywords, KeywordMatchResult } from '@/lib/matchKeywords';

// Allow route handler to run up to 5 minutes (300 seconds) for heavy LLM ingestion pipeline
export const maxDuration = 300;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    const formData = await request.formData();

    console.log(`[API Proxy Ingest] Forwarding ingestion to Spring Boot backend for sessionId=${sessionId}`);
    const backendRes = await forwardToBackend(`/api/v1/ingest/${sessionId}`, request, {
      method: 'POST',
      body: formData,
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Ingest] Backend returned error status ${backendRes.status}:`, errText);
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

    let keywordMetadata: KeywordMatchResult = { matching_skills: [], missing_skills: [] };
    if (result.rawCvText && result.rawJdText) {
      try {
        keywordMetadata = await matchKeywords(result.rawCvText, result.rawJdText);
      } catch (kwErr) {
        console.warn('[API Proxy Ingest] Error running matchKeywords:', kwErr);
      }
    }

    return NextResponse.json({
      sessionId: result.sessionId || sessionId,
      success: true,
      cvMarkdown: result.cvMarkdown,
      jdMarkdown: result.jdMarkdown,
      rawCvText: result.rawCvText || null,
      rawJdText: result.rawJdText || null,
      keywordMetadata,
    });
  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy Ingest] Error in proxy ingestion:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
