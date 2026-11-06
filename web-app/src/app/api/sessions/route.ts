import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

// GET: List all sessions
export async function GET(request: NextRequest) {
  try {
    const authHeader = request.headers.get('Authorization');
    const endpoint = authHeader ? '/api/v1/sessions/user' : '/api/v1/sessions';
    const backendRes = await forwardToBackend(endpoint, request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error) {
    const err = error as Error;
    console.error('[API Sessions] Error fetching sessions:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Save/Upsert a session
export async function POST(request: NextRequest) {
  try {
    const session = await request.json();
    if (!session || !session.id) {
      return NextResponse.json({ error: 'Session details with id are required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend('/api/v1/sessions', request, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(session),
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json({ success: true, session: data });
  } catch (error) {
    const err = error as Error;
    console.error('[API Sessions] Error saving session:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}

// DELETE: Delete a session
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend(`/api/v1/sessions/${id}`, request, {
      method: 'DELETE',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    const err = error as Error;
    console.error('[API Sessions] Error deleting session:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
