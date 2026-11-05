import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

// GET: List all job descriptions
export async function GET(request: NextRequest) {
  try {
    const backendRes = await forwardToBackend('/api/v1/job-descriptions', request, {
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
    console.error('[API JDs] Error fetching JDs:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a job description
export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';

    let backendRes: Response;
    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      backendRes = await forwardToBackend('/api/v1/job-descriptions', request, {
        method: 'POST',
        body: formData,
      });
    } else {
      const body = await request.json();
      backendRes = await forwardToBackend('/api/v1/job-descriptions', request, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    }

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const jd = await backendRes.json();
    return NextResponse.json({ success: true, jd });
  } catch (error) {
    const err = error as Error;
    console.error('[API JDs] Error saving JD:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
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

    const backendRes = await forwardToBackend(`/api/v1/job-descriptions/${id}`, request, {
      method: 'DELETE',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    const err = error as Error;
    console.error('[API JDs] Error deleting JD:', err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
