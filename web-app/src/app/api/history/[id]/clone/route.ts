import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const resolvedParams = await params;
    const oldSessionId = resolvedParams.id;
    if (!oldSessionId) {
      return NextResponse.json({ error: 'Session ID is required' }, { status: 400 });
    }

    // 1. Fetch the old session
    const sessionRes = await query('SELECT * FROM sessions WHERE id = $1', [oldSessionId]);
    if (sessionRes.rows.length === 0) {
      return NextResponse.json({ error: 'Session not found' }, { status: 404 });
    }
    const oldSession = sessionRes.rows[0];

    // 2. Fetch the old turns
    const turnsRes = await query('SELECT * FROM session_turns WHERE session_id = $1 ORDER BY id ASC', [oldSessionId]);
    const oldTurns = turnsRes.rows;

    // 3. Create a new session ID
    const newSessionId = 'session-' + Date.now();
    const currentDate = new Date().toISOString();

    // 4. Insert new session (only copying initial setup data and base questions)
    const insertSessionSql = `
      INSERT INTO sessions (
        id, date, interview_type, role_title, cv_filename, jd_filename,
        resume_id, jd_id, status, actionable_suggestions
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    `;
    await query(insertSessionSql, [
      newSessionId,
      currentDate,
      oldSession.interview_type,
      oldSession.role_title,
      oldSession.cv_filename,
      oldSession.jd_filename,
      oldSession.resume_id,
      oldSession.jd_id,
      'In progress',
      oldSession.actionable_suggestions 
        ? (typeof oldSession.actionable_suggestions === 'string' ? oldSession.actionable_suggestions : JSON.stringify(oldSession.actionable_suggestions))
        : null
    ]);

    return NextResponse.json({ success: true, newSessionId });
  } catch (error: any) {
    console.error('[API History Clone] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
