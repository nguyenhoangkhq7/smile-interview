import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

// GET: List all resumes
export async function GET() {
  try {
    const result = await query(
      'SELECT id, user_id, file_name, extracted_text, created_at FROM resumes ORDER BY created_at DESC'
    );
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error('[API Resumes] Error fetching resumes:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a resume
export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const file = formData.get('file') as File | null;
      const userId = formData.get('user_id') as string | null;
      const extractedText = formData.get('extracted_text') as string | null;

      if (!file) {
        return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
      }

      const fileBuffer = Buffer.from(await file.arrayBuffer());
      const result = await query(
        'INSERT INTO resumes (user_id, file_name, file_content, extracted_text) VALUES ($1, $2, $3, $4) RETURNING id, file_name, created_at',
        [userId || null, file.name, fileBuffer, extractedText || null]
      );

      return NextResponse.json({ success: true, resume: result.rows[0] });
    } else {
      // JSON payload
      const body = await request.json();
      const { user_id, file_name, extracted_text, file_content } = body;

      if (!file_name) {
        return NextResponse.json({ error: 'file_name is required' }, { status: 400 });
      }

      const contentBuffer = file_content ? Buffer.from(file_content, 'base64') : null;
      const result = await query(
        'INSERT INTO resumes (user_id, file_name, file_content, extracted_text) VALUES ($1, $2, $3, $4) RETURNING id, file_name, created_at',
        [user_id || null, file_name, contentBuffer, extracted_text || null]
      );

      return NextResponse.json({ success: true, resume: result.rows[0] });
    }
  } catch (error: any) {
    console.error('[API Resumes] Error saving resume:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// DELETE: Remove a resume
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    await query('DELETE FROM resumes WHERE id = $1', [parseInt(id, 10)]);
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[API Resumes] Error deleting resume:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
