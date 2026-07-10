import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

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
    const resumeIdStr = formData.get('resumeId') as string | null;
    const jdIdStr = formData.get('jdId') as string | null;

    let finalResumeId: number | null = resumeIdStr ? parseInt(resumeIdStr, 10) : null;
    let finalJdId: number | null = jdIdStr ? parseInt(jdIdStr, 10) : null;

    // 1. If CV is uploaded newly, check for duplicate content first or save to Database
    if (!finalResumeId && cvFile) {
      const cvBuffer = Buffer.from(await cvFile.arrayBuffer());
      const existingCvRes = await query(
        'SELECT id FROM resumes WHERE file_name = $1 AND file_content = $2 LIMIT 1',
        [cvFile.name, cvBuffer]
      );
      if (existingCvRes.rows.length > 0) {
        console.log('[API Proxy Ingest] Reusing existing resume ID:', existingCvRes.rows[0].id);
        finalResumeId = existingCvRes.rows[0].id;
      } else {
        const insertResumeRes = await query(
          'INSERT INTO resumes (file_name, file_content) VALUES ($1, $2) RETURNING id',
          [cvFile.name, cvBuffer]
        );
        finalResumeId = insertResumeRes.rows[0].id;
      }
    }

    // 2. If JD is uploaded newly, check for duplicate content first or save to Database
    if (!finalJdId) {
      if (jdFile) {
        const jdBuffer = Buffer.from(await jdFile.arrayBuffer());
        const existingJdRes = await query(
          'SELECT id FROM job_descriptions WHERE title = $1 AND file_content = $2 LIMIT 1',
          [jdFile.name, jdBuffer]
        );
        if (existingJdRes.rows.length > 0) {
          console.log('[API Proxy Ingest] Reusing existing JD ID:', existingJdRes.rows[0].id);
          finalJdId = existingJdRes.rows[0].id;
        } else {
          const insertJdRes = await query(
            'INSERT INTO job_descriptions (title, file_content) VALUES ($1, $2) RETURNING id',
            [jdFile.name, jdBuffer]
          );
          finalJdId = insertJdRes.rows[0].id;
        }
      } else if (jdText && jdText.trim() !== '') {
        const existingJdRes = await query(
          'SELECT id FROM job_descriptions WHERE extracted_text = $1 LIMIT 1',
          [jdText]
        );
        if (existingJdRes.rows.length > 0) {
          console.log('[API Proxy Ingest] Reusing existing JD (text) ID:', existingJdRes.rows[0].id);
          finalJdId = existingJdRes.rows[0].id;
        } else {
          const insertJdRes = await query(
            'INSERT INTO job_descriptions (title, extracted_text) VALUES ($1, $2) RETURNING id',
            ['JD_Text_' + Date.now(), jdText]
          );
          finalJdId = insertJdRes.rows[0].id;
        }
      }
    }

    // 3. Resolve actual files/content to forward to Java backend
    let cvFileToSend: Blob | null = null;
    let cvFileName = '';

    if (finalResumeId) {
      const resumeRes = await query('SELECT file_name, file_content FROM resumes WHERE id = $1', [finalResumeId]);
      if (resumeRes.rows.length > 0) {
        const row = resumeRes.rows[0];
        cvFileName = row.file_name;
        if (row.file_content) {
          cvFileToSend = new Blob([row.file_content], { type: 'application/pdf' });
        }
      }
    }

    let jdFileToSend: Blob | null = null;
    let jdFileName = '';
    let jdTextToSend: string | null = null;

    if (finalJdId) {
      const jdRes = await query('SELECT title, file_content, extracted_text FROM job_descriptions WHERE id = $1', [finalJdId]);
      if (jdRes.rows.length > 0) {
        const row = jdRes.rows[0];
        jdFileName = row.title;
        if (row.file_content) {
          jdFileToSend = new Blob([row.file_content], { type: 'application/pdf' });
        } else {
          jdTextToSend = row.extracted_text;
        }
      }
    } else {
      jdTextToSend = jdText;
    }

    if (!cvFileToSend) {
      return NextResponse.json({ error: 'CV file is required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    
    // Reconstruct FormData for Spring Boot ingestion endpoint
    const backendFormData = new FormData();
    backendFormData.append('cvFile', cvFileToSend, cvFileName || 'cv.pdf');

    if (jdFileToSend && jdFileName) {
      backendFormData.append('jdFile', jdFileToSend, jdFileName);
    } else if (jdTextToSend) {
      backendFormData.append('jdText', jdTextToSend);
    }

    console.log(`[API Proxy Ingest] Forwarding to backend: ${backendUrl}/api/v1/ingest/${sessionId}`);
    
    const authHeader = request.headers.get('Authorization');
    const headers: Record<string, string> = {};
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const backendRes = await fetch(`${backendUrl}/api/v1/ingest/${sessionId}`, {
      method: 'POST',
      body: backendFormData,
      headers: headers,
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
      success: true,
      resumeId: finalResumeId,
      jdId: finalJdId
    });
  } catch (error: any) {
    console.error('[API Proxy Ingest] Error in proxy ingestion:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
