import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

// GET: List all job descriptions
export async function GET() {
  try {
    const result = await query(
      'SELECT id, user_id, title, extracted_text, created_at FROM job_descriptions ORDER BY created_at DESC'
    );
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error('[API JDs] Error fetching JDs:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a job description
export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const file = formData.get('file') as File | null;
      const title = formData.get('title') as string | null;
      const text = formData.get('extracted_text') as string | null;
      const userId = formData.get('user_id') as string | null;

      if (!file && !text) {
        return NextResponse.json({ error: 'Either file or extracted_text is required' }, { status: 400 });
      }

      let fileBuffer = null;
      let finalTitle = title || '';
      
      if (file) {
        fileBuffer = Buffer.from(await file.arrayBuffer());
        if (!finalTitle) finalTitle = file.name;
      } else if (!finalTitle) {
        finalTitle = 'JD_' + Date.now();
      }

      const result = await query(
        'INSERT INTO job_descriptions (user_id, title, file_content, extracted_text) VALUES ($1, $2, $3, $4) RETURNING id, title, created_at',
        [userId || null, finalTitle, fileBuffer, text || null]
      );

      return NextResponse.json({ success: true, jd: result.rows[0] });
    } else {
      // JSON payload
      const body = await request.json();
      const { user_id, title, extracted_text, file_content } = body;

      if (!title && !extracted_text) {
        return NextResponse.json({ error: 'Either title or extracted_text is required' }, { status: 400 });
      }

      const finalTitle = title || 'JD_' + Date.now();
      const contentBuffer = file_content ? Buffer.from(file_content, 'base64') : null;
      const result = await query(
        'INSERT INTO job_descriptions (user_id, title, file_content, extracted_text) VALUES ($1, $2, $3, $4) RETURNING id, title, created_at',
        [user_id || null, finalTitle, contentBuffer, extracted_text || null]
      );

      return NextResponse.json({ success: true, jd: result.rows[0] });
    }
  } catch (error: any) {
    console.error('[API JDs] Error saving JD:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// DELETE: Remove a job description
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    await query('DELETE FROM job_descriptions WHERE id = $1', [parseInt(id, 10)]);
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[API JDs] Error deleting JD:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
