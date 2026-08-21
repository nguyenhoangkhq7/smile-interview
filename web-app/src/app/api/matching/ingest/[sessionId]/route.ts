import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import cloudinary from '@/lib/cloudinary';
import { matchKeywords, KeywordMatchResult } from '@/lib/matchKeywords';
import { customFetch } from '@/lib/customFetch';

// Allow route handler to run up to 5 minutes (300 seconds) for heavy LLM ingestion pipeline
export const maxDuration = 300;

// ─── JWT helper ───────────────────────────────────────────────────────────────
function extractUserId(request: NextRequest): string | null {
  const authHeader = request.headers.get('Authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    try {
      const token = authHeader.substring(7);
      const parts = token.split('.');
      if (parts.length === 3) {
        const payload = Buffer.from(parts[1], 'base64').toString('utf-8');
        const claims = JSON.parse(payload);
        return claims.id || null;
      }
    } catch (e) {
      console.error('[API Proxy Ingest] Error decoding JWT:', e);
    }
  }
  return null;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;
    const formData = await request.formData();

    const authUserId = extractUserId(request);
    const authHeader = request.headers.get('Authorization');

    const cvFile = formData.get('cvFile') as File | null;
    const jdFile = formData.get('jdFile') as File | null;
    const jdText = formData.get('jdText') as string | null;
    const resumeIdStr = formData.get('resumeId') as string | null;
    const jdIdStr = formData.get('jdId') as string | null;
    const roleTitle = formData.get('roleTitle') as string | null;
    const interviewType = formData.get('interviewType') as string | null;

    if (jdText && jdText.trim().startsWith('%PDF-')) {
      return NextResponse.json({ 
        error: 'Nội dung mô tả công việc (JD Text) không hợp lệ vì chứa mã nguồn của file PDF. Vui lòng chuyển sang tab "Tải tệp JD" để upload file PDF thay vì dán nội dung.' 
      }, { status: 400 });
    }

    let finalResumeId: string | null = resumeIdStr || null;
    let finalJdId: string | null = jdIdStr || null;

    // ── 1. Upload new CV to Cloudinary + DB if no resumeId provided ──────────
    if (!finalResumeId && cvFile) {
      let uploadRes;
      try {
        if (!process.env.CLOUDINARY_API_KEY) {
          console.warn('[API Proxy Ingest] CLOUDINARY_API_KEY is not set, using mock upload for CV.');
          uploadRes = {
            secure_url: `https://example.com/resumes/${encodeURIComponent(cvFile.name)}`,
            public_id: `mock_cv_${Date.now()}_${encodeURIComponent(cvFile.name)}`,
          };
        } else {
          const cvBuffer = Buffer.from(await cvFile.arrayBuffer());
          const base64Data = `data:${cvFile.type || 'application/octet-stream'};base64,${cvBuffer.toString('base64')}`;
          uploadRes = await cloudinary.uploader.upload(base64Data, {
            resource_type: 'raw',
            public_id: cvFile.name,
            use_filename: true,
            unique_filename: true,
          });
        }
      } catch (uploadError) {
        const uErr = uploadError as Error;
        console.error('[API Proxy Ingest] Cloudinary upload failed for CV:', uErr);
        return NextResponse.json({ error: `Cloudinary upload failed: ${uErr.message || uErr}` }, { status: 500 });
      }

      const insertResumeRes = await query(
        'INSERT INTO resumes (user_id, file_name, file_url, cloudinary_id) VALUES ($1, $2, $3, $4) RETURNING id',
        [authUserId, cvFile.name, uploadRes.secure_url, uploadRes.public_id]
      );
      finalResumeId = insertResumeRes.rows[0].id;
    }

    // ── 2. Upload new JD to Cloudinary + DB if no jdId provided ─────────────
    if (!finalJdId) {
      if (jdFile) {
        let uploadRes;
        try {
          if (!process.env.CLOUDINARY_API_KEY) {
            console.warn('[API Proxy Ingest] CLOUDINARY_API_KEY is not set, using mock upload for JD.');
            uploadRes = {
              secure_url: `https://example.com/jds/${encodeURIComponent(jdFile.name)}`,
              public_id: `mock_jd_${Date.now()}_${encodeURIComponent(jdFile.name)}`,
            };
          } else {
            const jdBuffer = Buffer.from(await jdFile.arrayBuffer());
            const base64Data = `data:${jdFile.type || 'application/octet-stream'};base64,${jdBuffer.toString('base64')}`;
            uploadRes = await cloudinary.uploader.upload(base64Data, {
              resource_type: 'raw',
              public_id: jdFile.name,
              use_filename: true,
              unique_filename: true,
            });
          }
        } catch (uploadError) {
          const uErr = uploadError as Error;
          console.error('[API Proxy Ingest] Cloudinary upload failed for JD:', uErr);
          return NextResponse.json({ error: `Cloudinary upload failed: ${uErr.message || uErr}` }, { status: 500 });
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

    // ── 3. Fetch cached data: extracted_text (markdown) AND raw_text ──────────
    // extracted_text → used to decide whether to call Java (Groq LLM bypass)
    // raw_text       → used for visual keyword matching (pre-LLM plain text)
    let cvMarkdownToSend: string | null = null;
    let cvFileToSend: Blob | null = null;
    let cvFileName = '';
    let cachedRawCvText: string | null = null;

    if (finalResumeId) {
      const resumeRes = await query(
        'SELECT file_name, file_url, extracted_text, raw_text FROM resumes WHERE id = $1',
        [finalResumeId]
      );
      if (resumeRes.rows.length > 0) {
        const row = resumeRes.rows[0];
        cvFileName = row.file_name;
        cachedRawCvText = row.raw_text || null;

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
    let cachedRawJdText: string | null = null;

    if (finalJdId) {
      const jdRes = await query(
        'SELECT title, file_url, extracted_text, raw_text FROM job_descriptions WHERE id = $1',
        [finalJdId]
      );
      if (jdRes.rows.length > 0) {
        const row = jdRes.rows[0];
        jdFileName = row.title;
        cachedRawJdText = row.raw_text || null;

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

    // ── 4. Check if we have a FULL MARKDOWN CACHE HIT (skip Java entirely) ────
    // When both documents have cached Markdown AND cached raw_text, we can:
    //   - Bypass Java ingestion completely
    //   - Run keyword matching directly using the cached raw texts
    // Note: LLM call in matchKeywords takes ~1-3s. This is acceptable.
    const isFullCacheHit = !!(cvMarkdownToSend && jdMarkdownToSend && cachedRawCvText && cachedRawJdText);

    let keywordMetadata: KeywordMatchResult = { matching_skills: [], missing_skills: [] };
    let rawCvText: string | null = cachedRawCvText;
    let rawJdText: string | null = cachedRawJdText;
    let totalChunksCount = 0;

    if (isFullCacheHit) {
      // ── FULL CACHE HIT: Bypass Java, run keyword matching directly ──────────
      console.log(`[API Proxy Ingest] Full cache hit (markdown + raw_text). Skipping Java ingestion.`);

      // Still call Java to register the session (needed for question generation etc.)
      // But we can do it fire-and-forget style, or still wait if needed.
      // For now: call Java with cached markdown only (fast path, no LLM in Java).
      const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
      const backendFormData = new FormData();
      backendFormData.append('resumeMarkdown', cvMarkdownToSend!);
      if (jdMarkdownToSend) backendFormData.append('jdMarkdown', jdMarkdownToSend);

      const headers: Record<string, string> = {};
      if (authHeader) headers['Authorization'] = authHeader;

      console.log(`[API Proxy Ingest] Forwarding cached markdown to backend (no LLM): ${backendUrl}/api/v1/ingest/${sessionId}`);
      const backendRes = await customFetch(`${backendUrl}/api/v1/ingest/${sessionId}`, {
        method: 'POST',
        body: backendFormData,
        headers,
      });

      if (backendRes.ok) {
        const result = await backendRes.json();
        totalChunksCount = result.totalChunksCount || 0;
      } else {
        const errText = await backendRes.text();
        console.error(`[API Proxy Ingest] Backend returned error on cache-hit path ${backendRes.status}:`, errText);
      }

      // Run keyword matching with the cached raw texts (LLM call ~1-3s)
      console.log('[API Proxy Ingest] Running keyword matching on cached raw texts...');
      keywordMetadata = await matchKeywords(cachedRawCvText!, cachedRawJdText!);

    } else {
      // ── CACHE MISS: Forward to Java for PDF parsing + Groq LLM ──────────────
      const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
      const backendFormData = new FormData();

      if (cvFile) {
        backendFormData.append('cvFile', cvFile);
      } else if (cvFileToSend) {
        backendFormData.append('cvFile', cvFileToSend, cvFileName || 'cv.pdf');
      }
      if (cvMarkdownToSend) {
        backendFormData.append('resumeMarkdown', cvMarkdownToSend);
      }
      if (jdFile) {
        backendFormData.append('jdFile', jdFile);
      } else if (jdFileToSend && jdFileName) {
        backendFormData.append('jdFile', jdFileToSend, jdFileName);
      } else if (jdMarkdownToSend) {
        backendFormData.append('jdMarkdown', jdMarkdownToSend);
      } else if (jdTextToSend) {
        backendFormData.append('jdText', jdTextToSend);
      }
      if (roleTitle) {
        backendFormData.append('roleTitle', roleTitle);
      }
      if (interviewType) {
        backendFormData.append('interviewType', interviewType);
      }

      const headers: Record<string, string> = {};
      if (authHeader) headers['Authorization'] = authHeader;

      console.log(`[API Proxy Ingest] Forwarding to backend: ${backendUrl}/api/v1/ingest/${sessionId}`);
      const backendRes = await customFetch(`${backendUrl}/api/v1/ingest/${sessionId}`, {
        method: 'POST',
        body: backendFormData,
        headers,
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
        const errorMessage = detail
          ? `Backend error (${backendRes.status}): ${detail}`
          : `Backend error: ${backendRes.status} ${backendRes.statusText}`.trim();
        return NextResponse.json({ error: errorMessage }, { status: backendRes.status });
      }

      const result = await backendRes.json();
      totalChunksCount = result.totalChunksCount || 0;

      // ── 5a. Cache newly generated Markdowns ────────────────────────────────
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

      // ── 5b. Cache newly extracted raw texts ────────────────────────────────
      // rawCvText / rawJdText are populated by Java only on cache-miss PDF parsing.
      rawCvText = result.rawCvText || cachedRawCvText;
      rawJdText = result.rawJdText || cachedRawJdText;

      if (result.rawCvText && finalResumeId && !cachedRawCvText) {
        try {
          await query('UPDATE resumes SET raw_text = $1 WHERE id = $2', [result.rawCvText, finalResumeId]);
          console.log(`[API Proxy Ingest] Successfully cached raw CV text for resume ID: ${finalResumeId}`);
        } catch (dbError) {
          console.error(`[API Proxy Ingest] Failed to cache raw CV text for resume ID ${finalResumeId}:`, dbError);
        }
      }

      if (result.rawJdText && finalJdId && !cachedRawJdText) {
        try {
          await query('UPDATE job_descriptions SET raw_text = $1 WHERE id = $2', [result.rawJdText, finalJdId]);
          console.log(`[API Proxy Ingest] Successfully cached raw JD text for job description ID: ${finalJdId}`);
        } catch (dbError) {
          console.error(`[API Proxy Ingest] Failed to cache raw JD text for job description ID ${finalJdId}:`, dbError);
        }
      }

      // ── 5c. Run keyword matching if we have raw texts ─────────────────────
      // Note: LLM call takes ~1-3 seconds on a cache-miss path. Acceptable.
      if (rawCvText && rawJdText) {
        console.log('[API Proxy Ingest] Running keyword matching on freshly extracted raw texts...');
        keywordMetadata = await matchKeywords(rawCvText, rawJdText);
      } else {
        console.warn('[API Proxy Ingest] Skipping keyword matching — raw texts not available.');
      }
    }

    return NextResponse.json({
      sessionId,
      totalChunksCount,
      success: true,
      resumeId: finalResumeId,
      jdId: finalJdId,
      // Keyword metadata for Jobscan-style visual highlighting
      keywordMetadata,
      // Raw pre-LLM texts for client-side highlight rendering
      rawCvText: rawCvText || null,
      rawJdText: rawJdText || null,
    });
  } catch (error) {
    const err = error as Error;
    console.error('[API Proxy Ingest] Error in proxy ingestion:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
