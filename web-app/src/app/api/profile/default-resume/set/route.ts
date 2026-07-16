import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

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
        console.error('[API Set Default Resume] Error decoding JWT:', e);
      }
    }

    if (!authUserId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { resumeId } = await request.json();
    if (!resumeId) {
      return NextResponse.json({ error: 'resumeId is required' }, { status: 400 });
    }

    // Update the database users table default_resume_id
    await query(
      'UPDATE users SET default_resume_id = $1 WHERE id = $2',
      [String(resumeId), authUserId]
    );

    return NextResponse.json({ success: true, defaultResumeId: String(resumeId) });
  } catch (error: any) {
    console.error('[API Set Default Resume] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
