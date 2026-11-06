import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    const backendFormData = new FormData();
    backendFormData.append('file', file);

    const backendRes = await forwardToBackend('/api/auth/avatar', request, {
      method: 'POST',
      body: backendFormData,
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const user = await backendRes.json();
    return NextResponse.json({ avatarUrl: user.avatarUrl });
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[API Avatar] Error uploading avatar:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
