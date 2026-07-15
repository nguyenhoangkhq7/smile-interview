import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import cloudinary from '@/lib/cloudinary';

// GET: List all job descriptions
export async function GET(request: NextRequest) {
  try {
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
        console.error('[API JDs] Error decoding JWT:', e);
      }
    }

    let result;
    if (authUserId) {
      result = await query(
        'SELECT id, user_id, title, file_url, cloudinary_id, extracted_text, created_at FROM job_descriptions WHERE user_id = $1 ORDER BY created_at DESC',
        [authUserId]
      );
    } else {
      result = await query(
        'SELECT id, user_id, title, file_url, cloudinary_id, extracted_text, created_at FROM job_descriptions ORDER BY created_at DESC'
      );
    }
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error('[API JDs] Error fetching JDs:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a job description
export async function POST(request: NextRequest) {
  try {
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
        console.error('[API JDs] Error decoding JWT:', e);
      }
    }

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

      let fileUrl = null;
      let cloudinaryId = null;
      let finalTitle = title || '';
      
      if (file) {
        try {
          const fileBuffer = Buffer.from(await file.arrayBuffer());
          const base64Data = `data:${file.type || 'application/octet-stream'};base64,${fileBuffer.toString('base64')}`;
          const uploadRes = await cloudinary.uploader.upload(base64Data, {
            resource_type: 'raw',
            public_id: file.name,
            use_filename: true,
            unique_filename: true,
          });
          fileUrl = uploadRes.secure_url;
          cloudinaryId = uploadRes.public_id;
        } catch (uploadError: any) {
          console.error('[API JDs] Cloudinary upload failed:', uploadError);
          return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
        }
        if (!finalTitle) finalTitle = file.name;
      } else if (!finalTitle) {
        finalTitle = 'JD_' + Date.now();
      }

      const result = await query(
        'INSERT INTO job_descriptions (user_id, title, file_url, cloudinary_id, extracted_text) VALUES ($1, $2, $3, $4, $5) RETURNING id, title, file_url, cloudinary_id, created_at',
        [userId || authUserId || null, finalTitle, fileUrl, cloudinaryId, text || null]
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
      let fileUrl = null;
      let cloudinaryId = null;

      if (file_content) {
        try {
          const contentBuffer = Buffer.from(file_content, 'base64');
          const base64Data = `data:application/octet-stream;base64,${contentBuffer.toString('base64')}`;
          const uploadRes = await cloudinary.uploader.upload(base64Data, {
            resource_type: 'raw',
            public_id: finalTitle,
            use_filename: true,
            unique_filename: true,
          });
          fileUrl = uploadRes.secure_url;
          cloudinaryId = uploadRes.public_id;
        } catch (uploadError: any) {
          console.error('[API JDs] Cloudinary upload failed:', uploadError);
          return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
        }
      }

      const result = await query(
        'INSERT INTO job_descriptions (user_id, title, file_url, cloudinary_id, extracted_text) VALUES ($1, $2, $3, $4, $5) RETURNING id, title, file_url, cloudinary_id, created_at',
        [user_id || authUserId || null, finalTitle, fileUrl, cloudinaryId, extracted_text || null]
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
