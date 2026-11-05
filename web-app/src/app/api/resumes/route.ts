import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

// GET: List all resumes
export async function GET(request: NextRequest) {
  try {
    const backendRes = await forwardToBackend('/api/v1/resumes', request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[API Resumes] Error fetching resumes:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}

// POST: Create/Upload a resume
export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';

    let backendRes: Response;
    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      backendRes = await forwardToBackend('/api/v1/resumes', request, {
        method: 'POST',
        body: formData,
      });
    } else {
      const body = await request.json();
      backendRes = await forwardToBackend('/api/v1/resumes', request, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    }

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const resume = await backendRes.json();
    return NextResponse.json({ success: true, resume });
  } catch (errorVal) {
    const error = errorVal as Error;
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

    const backendRes = await forwardToBackend(`/api/v1/resumes/${id}`, request, {
      method: 'DELETE',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    return NextResponse.json({ success: true });
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[API Resumes] Error deleting resume:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
