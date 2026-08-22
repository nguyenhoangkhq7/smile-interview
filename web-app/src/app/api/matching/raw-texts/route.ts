import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

/**
 * GET /api/matching/raw-texts?resumeId=X&jdId=Y
 *
 * Lightweight endpoint that retrieves pre-parsed raw text (plain-text,
 * pre-LLM) stored in the `resumes.raw_text` and `job_descriptions.raw_text`
 * columns for the Jobscan visual keyword highlighter.
 *
 * Returns:
 *   rawCvText  – plain text of the CV  (null if not yet cached)
 *   rawJdText  – plain text of the JD  (null if not yet cached)
 *   cvFilename – original file name of the resume
 *   jdFilename – title / file name of the job description
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const resumeIdStr = searchParams.get('resumeId');
    const jdIdStr = searchParams.get('jdId');

    if (!resumeIdStr && !jdIdStr) {
      return NextResponse.json(
        { error: 'At least one of resumeId or jdId is required' },
        { status: 400 }
      );
    }

    let rawCvText: string | null = null;
    let cvFilename: string | null = null;

    if (resumeIdStr) {
      const res = await query(
        'SELECT file_name, COALESCE(raw_text, parsed_content) as raw_text FROM resumes WHERE id = $1',
        [resumeIdStr]
      );
      if (res.rows.length > 0) {
        rawCvText = res.rows[0].raw_text || null;
        cvFilename = res.rows[0].file_name || null;
      }
    }

    let rawJdText: string | null = null;
    let jdFilename: string | null = null;

    if (jdIdStr) {
      const res = await query(
        'SELECT title, COALESCE(raw_text, parsed_content) as raw_text FROM job_descriptions WHERE id = $1',
        [jdIdStr]
      );
      if (res.rows.length > 0) {
        rawJdText = res.rows[0].raw_text || null;
        jdFilename = res.rows[0].title || null;
      }
    }

    return NextResponse.json({
      rawCvText,
      rawJdText,
      cvFilename,
      jdFilename,
    });
  } catch (errorVal) { const error = errorVal as Error;
    console.error('[raw-texts] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
