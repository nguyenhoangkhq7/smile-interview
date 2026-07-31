import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import cloudinary from '@/lib/cloudinary';

// GET: List all resumes
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
        console.error('[API Resumes] Error decoding JWT:', e);
      }
    }

    let result;
    if (authUserId) {
      result = await query(
        'SELECT id, user_id, file_name, file_url, cloudinary_id, extracted_text, created_at FROM resumes WHERE user_id = $1 ORDER BY created_at DESC',
        [authUserId]
      );
    } else {
      result = await query(
        'SELECT id, user_id, file_name, file_url, cloudinary_id, extracted_text, created_at FROM resumes ORDER BY created_at DESC'
      );
    }
    return NextResponse.json(result.rows);
  } catch (errorVal) { const error = errorVal as Error;
    console.error('[API Resumes] Error fetching resumes:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a resume
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
        console.error('[API Resumes] Error decoding JWT:', e);
      }
    }

    const contentType = request.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const file = formData.get('file') as File | null;
      const userId = formData.get('user_id') as string | null;
      const extractedText = formData.get('extracted_text') as string | null;

      if (!file) {
        return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
      }

      let uploadRes;
      try {
        if (!process.env.CLOUDINARY_API_KEY) {
          console.warn('[API Resumes] CLOUDINARY_API_KEY is not set, using mock upload.');
          uploadRes = {
            secure_url: `https://example.com/resumes/${encodeURIComponent(file.name)}`,
            public_id: `mock_cv_${Date.now()}_${encodeURIComponent(file.name)}`,
          };
        } else {
          const fileBuffer = Buffer.from(await file.arrayBuffer());
          const base64Data = `data:${file.type || 'application/octet-stream'};base64,${fileBuffer.toString('base64')}`;
          uploadRes = await cloudinary.uploader.upload(base64Data, {
            resource_type: 'raw',
            public_id: file.name,
            use_filename: true,
            unique_filename: true,
          });
        }
      } catch (uploadErrorVal) { const uploadError = uploadErrorVal as Error;
        console.error('[API Resumes] Cloudinary upload failed:', uploadError);
        return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
      }

      const result = await query(
        'INSERT INTO resumes (user_id, file_name, file_url, cloudinary_id, extracted_text) VALUES ($1, $2, $3, $4, $5) RETURNING id, file_name, file_url, cloudinary_id, created_at',
        [userId || authUserId || null, file.name, uploadRes.secure_url, uploadRes.public_id, extractedText || null]
      );

      return NextResponse.json({ success: true, resume: result.rows[0] });
    } else {
      // JSON payload
      const body = await request.json();
      const { user_id, file_name, extracted_text, file_content } = body;

      if (!file_name) {
        return NextResponse.json({ error: 'file_name is required' }, { status: 400 });
      }

      let fileUrl = null;
      let cloudinaryId = null;

      if (file_content) {
        try {
          if (!process.env.CLOUDINARY_API_KEY) {
            console.warn('[API Resumes] CLOUDINARY_API_KEY is not set, using mock upload for file content.');
            fileUrl = `https://example.com/resumes/${encodeURIComponent(file_name)}`;
            cloudinaryId = `mock_cv_${Date.now()}_${encodeURIComponent(file_name)}`;
          } else {
            const contentBuffer = Buffer.from(file_content, 'base64');
            const base64Data = `data:application/octet-stream;base64,${contentBuffer.toString('base64')}`;
            const uploadRes = await cloudinary.uploader.upload(base64Data, {
              resource_type: 'raw',
              public_id: file_name,
              use_filename: true,
              unique_filename: true,
            });
            fileUrl = uploadRes.secure_url;
            cloudinaryId = uploadRes.public_id;
          }
        } catch (uploadErrorVal) { const uploadError = uploadErrorVal as Error;
          console.error('[API Resumes] Cloudinary upload failed:', uploadError);
          return NextResponse.json({ error: `Cloudinary upload failed: ${uploadError.message || uploadError}` }, { status: 500 });
        }
      }

      const result = await query(
        'INSERT INTO resumes (user_id, file_name, file_url, cloudinary_id, extracted_text) VALUES ($1, $2, $3, $4, $5) RETURNING id, file_name, file_url, cloudinary_id, created_at',
        [user_id || authUserId || null, file_name, fileUrl, cloudinaryId, extracted_text || null]
      );

      return NextResponse.json({ success: true, resume: result.rows[0] });
    }
  } catch (errorVal) { const error = errorVal as Error;
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

    await query('DELETE FROM resumes WHERE id = $1', [id]);
    return NextResponse.json({ success: true });
  } catch (errorVal) { const error = errorVal as Error;
    console.error('[API Resumes] Error deleting resume:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
