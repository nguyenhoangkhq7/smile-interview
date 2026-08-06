import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: sessionId } = await params;
    const body = await request.json();
    const { turnId, turnIndex, hrRating, hrFeedback } = body;

    if (!sessionId) {
      return NextResponse.json({ error: 'sessionId is required' }, { status: 400 });
    }

    if (turnId) {
      await query(
        `UPDATE session_turns SET hr_rating = $1, hr_feedback = $2 WHERE id::text = $3 AND session_id = $4`,
        [hrRating, hrFeedback || null, turnId, sessionId]
      );
    } else if (turnIndex !== undefined) {
      await query(
        `UPDATE session_turns SET hr_rating = $1, hr_feedback = $2 WHERE session_id = $3 AND turn_number = $4`,
        [hrRating, hrFeedback || null, sessionId, turnIndex + 1]
      );
    } else {
      return NextResponse.json({ error: 'turnId or turnIndex is required' }, { status: 400 });
    }

    return NextResponse.json({ success: true, message: 'Turn evaluation saved successfully' });
  } catch (error) {
    const err = error as Error;
    console.error('[API Turn Feedback] Error:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
