import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import cloudinary from '@/lib/cloudinary';

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
        console.error('[API Default Resume] Error decoding JWT:', e);
      }
    }

    if (!authUserId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    // Convert file to base64 for Cloudinary
    const buffer = Buffer.from(await file.arrayBuffer());
    const base64Data = `data:${file.type};base64,${buffer.toString('base64')}`;

    console.log(`[API Default Resume] Uploading default CV to Cloudinary for user ${authUserId}...`);
    const uploadRes = await cloudinary.uploader.upload(base64Data, {
      folder: 'smile-interview/resumes',
      resource_type: 'raw', // Support PDF/Docx raw upload
    });

    const fileUrl = uploadRes.secure_url;
    const cloudinaryId = uploadRes.public_id;
    const fileName = file.name;

    console.log(`[API Default Resume] Cloudinary upload success. URL: ${fileUrl}`);

    // Insert CV into resumes table
    const resumeInsertRes = await query(
      'INSERT INTO resumes (user_id, file_name, file_url, cloudinary_id) VALUES ($1, $2, $3, $4) RETURNING id, file_name, file_url, cloudinary_id, created_at',
      [authUserId, fileName, fileUrl, cloudinaryId]
    );
    const newResume = resumeInsertRes.rows[0];

    // Update users table default_resume_id to the new resume's ID
    await query(
      'UPDATE users SET default_resume_id = $1 WHERE id = $2',
      [String(newResume.id), authUserId]
    );

    return NextResponse.json({
      success: true,
      defaultResumeId: String(newResume.id),
      resume: newResume,
    });
  } catch (error: any) {
    console.error('[API Default Resume] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
