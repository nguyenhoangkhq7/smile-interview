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
        console.error('[API Avatar] Error decoding JWT:', e);
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

    console.log(`[API Avatar] Uploading avatar to Cloudinary for user ${authUserId}...`);
    const uploadRes = await cloudinary.uploader.upload(base64Data, {
      folder: 'smile-interview/avatars',
    });

    const avatarUrl = uploadRes.secure_url;
    console.log(`[API Avatar] Cloudinary upload success. URL: ${avatarUrl}`);

    // Update the database users table
    await query(
      'UPDATE users SET avatar_url = $1 WHERE id = $2',
      [avatarUrl, authUserId]
    );

    return NextResponse.json({ avatarUrl });
  } catch (error: any) {
    console.error('[API Avatar] Error uploading avatar:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
