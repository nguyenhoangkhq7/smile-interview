import { NextRequest, NextResponse } from 'next/server';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    const formData = await request.formData();
    
    const cvFile = formData.get('cvFile') as File | null;
    const jdFile = formData.get('jdFile') as File | null;
    const jdText = formData.get('jdText') as string | null;

    if (!cvFile) {
      return NextResponse.json({ error: 'cvFile is required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    
    // Reconstruct FormData for Spring Boot ingestion endpoint
    const backendFormData = new FormData();
    // Use Blobs to reconstruct files cleanly
    const cvBlob = new Blob([await cvFile.arrayBuffer()], { type: cvFile.type });
    backendFormData.append('cvFile', cvBlob, cvFile.name);

    if (jdFile) {
      const jdBlob = new Blob([await jdFile.arrayBuffer()], { type: jdFile.type });
      backendFormData.append('jdFile', jdBlob, jdFile.name);
    }
    
    if (jdText) {
      backendFormData.append('jdText', jdText);
    }

    console.log(`[API Proxy Ingest] Forwarding to backend: ${backendUrl}/api/v1/ingest/${sessionId}`);
    
    const backendRes = await fetch(`${backendUrl}/api/v1/ingest/${sessionId}`, {
      method: 'POST',
      body: backendFormData,
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error(`[API Proxy Ingest] Backend returned error status ${backendRes.status}:`, errText);
      return NextResponse.json({ error: `Backend error: ${backendRes.statusText}` }, { status: backendRes.status });
    }

    const result = await backendRes.json();
    return NextResponse.json({
      sessionId,
      totalChunksCount: result.totalChunksCount || 0,
      success: true
    });
  } catch (error: any) {
    console.error('[API Proxy Ingest] Error in proxy ingestion:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
