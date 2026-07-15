import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import cloudinary from '@/lib/cloudinary';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    const formData = await request.formData();
    
    let authUserId: string | null = null;
    const authHeader = request.headers.get('Authorization');
    if (authHeader && authHeader.startsWith('Bearer ')) {
      try {
        const token = authHeader.substring(7);
        const parts = token.split('.');
        if (parts.length === 3) {
          const payload = Buffer.from(parts[1], 'base64').toString('utf-8');
          const claims = JSON.parse(payload);
          authUserId = claims.id || null;
        }
      } catch (e) {
        console.error('[API Proxy Ingest] Error decoding JWT:', e);
      }
    }
    
    const cvFile = formData.get('cvFile') as File | null;
    const jdFile = formData.get('jdFile') as File | null;
    const jdText = formData.get('jdText') as string | null;
    const resumeIdStr = formData.get('resumeId') as string | null;
    const jdIdStr = formData.get('jdId') as string | null;

    let finalResumeId: number | null = resumeIdStr ? parseInt(resumeIdStr, 10) : null;
    let finalJdId: number | null = jdIdStr ? parseInt(jdIdStr, 10) : null;

    // 1. If CV is uploaded newly, upload to Cloudinary and save to Database
    if (!finalResumeId && cvFile) {
      let uploadRes;
      try {
        const cvBuffer = Buffer.from(await cvFile.arrayBuffer());
        const base64Data = `data:${cvFile.type || 'application/octet-stream'};base64,${cvBuffer.toString('base64')}`;
        uploadRes = await cloudinary.uploader.upload(base64Data, {
          resource_type: 'raw',
          public_id: cvFile.name,
          use_filename: true,
          unique_filename: true,
        });
      } catch (uploadError: any) {
        console.error('[API Proxy Ingest] Cloudinary upload failed for CV:', uploadError);
        return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
      }

      const insertResumeRes = await query(
        'INSERT INTO resumes (user_id, file_name, file_url, cloudinary_id) VALUES ($1, $2, $3, $4) RETURNING id',
        [authUserId, cvFile.name, uploadRes.secure_url, uploadRes.public_id]
      );
      finalResumeId = insertResumeRes.rows[0].id;
    }

    // 2. If JD is uploaded newly, upload to Cloudinary and save to Database
    if (!finalJdId) {
      if (jdFile) {
        let uploadRes;
        try {
          const jdBuffer = Buffer.from(await jdFile.arrayBuffer());
          const base64Data = `data:${jdFile.type || 'application/octet-stream'};base64,${jdBuffer.toString('base64')}`;
          uploadRes = await cloudinary.uploader.upload(base64Data, {
            resource_type: 'raw',
            public_id: jdFile.name,
            use_filename: true,
            unique_filename: true,
          });
        } catch (uploadError: any) {
          console.error('[API Proxy Ingest] Cloudinary upload failed for JD:', uploadError);
          return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
        }

        const insertJdRes = await query(
          'INSERT INTO job_descriptions (user_id, title, file_url, cloudinary_id) VALUES ($1, $2, $3, $4) RETURNING id',
          [authUserId, jdFile.name, uploadRes.secure_url, uploadRes.public_id]
        );
        finalJdId = insertJdRes.rows[0].id;
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
            'INSERT INTO job_descriptions (user_id, title, extracted_text) VALUES ($1, $2, $3) RETURNING id',
            [authUserId, 'JD_Text_' + Date.now(), jdText]
          );
          finalJdId = insertJdRes.rows[0].id;
        }
      }
    }

    // 3. Resolve actual files/content to forward to Java backend
    let cvMarkdownToSend: string | null = null;
    let cvFileToSend: Blob | null = null;
    let cvFileName = '';

    if (finalResumeId) {
      const resumeRes = await query('SELECT file_name, file_url, extracted_text FROM resumes WHERE id = $1', [finalResumeId]);
      if (resumeRes.rows.length > 0) {
        const row = resumeRes.rows[0];
        cvFileName = row.file_name;
        if (row.extracted_text) {
          cvMarkdownToSend = row.extracted_text;
        } else if (row.file_url) {
          try {
            const fileRes = await fetch(row.file_url);
            if (fileRes.ok) {
              const arrayBuffer = await fileRes.arrayBuffer();
              cvFileToSend = new Blob([arrayBuffer], { type: 'application/pdf' });
            } else {
              console.error(`[API Proxy Ingest] Failed to fetch CV from URL ${row.file_url}:`, fileRes.statusText);
            }
          } catch (fetchError) {
            console.error('[API Proxy Ingest] Error fetching CV from URL:', fetchError);
          }
        }
      }
    }

    let jdMarkdownToSend: string | null = null;
    let jdFileToSend: Blob | null = null;
    let jdFileName = '';
    let jdTextToSend: string | null = null;

    if (finalJdId) {
      const jdRes = await query('SELECT title, file_url, extracted_text FROM job_descriptions WHERE id = $1', [finalJdId]);
      if (jdRes.rows.length > 0) {
        const row = jdRes.rows[0];
        jdFileName = row.title;
        if (row.file_url) {
          if (row.extracted_text) {
            jdMarkdownToSend = row.extracted_text;
          } else {
            try {
              const fileRes = await fetch(row.file_url);
              if (fileRes.ok) {
                const arrayBuffer = await fileRes.arrayBuffer();
                jdFileToSend = new Blob([arrayBuffer], { type: 'application/pdf' });
              } else {
                console.error(`[API Proxy Ingest] Failed to fetch JD from URL ${row.file_url}:`, fileRes.statusText);
              }
            } catch (fetchError) {
              console.error('[API Proxy Ingest] Error fetching JD from URL:', fetchError);
            }
          }
        } else {
          jdTextToSend = row.extracted_text;
        }
      }
    } else {
      jdTextToSend = jdText;
    }

    if (!cvFileToSend && !cvMarkdownToSend) {
      return NextResponse.json({ error: 'CV file or CV Markdown is required' }, { status: 400 });
    }

    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    
    // Reconstruct FormData for Spring Boot ingestion endpoint
    const backendFormData = new FormData();
    if (cvFileToSend) {
      backendFormData.append('cvFile', cvFileToSend, cvFileName || 'cv.pdf');
    }
    if (cvMarkdownToSend) {
      backendFormData.append('resumeMarkdown', cvMarkdownToSend);
    }

    if (jdFileToSend && jdFileName) {
      backendFormData.append('jdFile', jdFileToSend, jdFileName);
    } else if (jdMarkdownToSend) {
      backendFormData.append('jdMarkdown', jdMarkdownToSend);
    } else if (jdTextToSend) {
      backendFormData.append('jdText', jdTextToSend);
    }

    console.log(`[API Proxy Ingest] Forwarding to backend: ${backendUrl}/api/v1/ingest/${sessionId}`);
    
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

    // Cache newly generated Markdowns in PostgreSQL
    if (result.cvMarkdown && finalResumeId && !cvMarkdownToSend) {
      try {
        await query('UPDATE resumes SET extracted_text = $1 WHERE id = $2', [result.cvMarkdown, finalResumeId]);
        console.log(`[API Proxy Ingest] Successfully cached CV Markdown for resume ID: ${finalResumeId}`);
      } catch (dbError) {
        console.error(`[API Proxy Ingest] Failed to cache CV Markdown for resume ID ${finalResumeId}:`, dbError);
      }
    }

    if (result.jdMarkdown && finalJdId && !jdMarkdownToSend) {
      try {
        await query('UPDATE job_descriptions SET extracted_text = $1 WHERE id = $2', [result.jdMarkdown, finalJdId]);
        console.log(`[API Proxy Ingest] Successfully cached JD Markdown for job description ID: ${finalJdId}`);
      } catch (dbError) {
        console.error(`[API Proxy Ingest] Failed to cache JD Markdown for job description ID ${finalJdId}:`, dbError);
      }
    }

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
