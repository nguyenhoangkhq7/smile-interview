import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    // 1. Upload to resumes API
    const uploadFormData = new FormData();
    uploadFormData.append('file', file);

    const uploadRes = await forwardToBackend('/api/v1/resumes', request, {
      method: 'POST',
      body: uploadFormData,
    });

    if (!uploadRes.ok) {
      const err = await uploadRes.text();
      return NextResponse.json({ error: err }, { status: uploadRes.status });
    }

    const newResume = await uploadRes.json();
    const resumeId = String(newResume.id);

    // 2. Set default resume on user profile
    await forwardToBackend('/api/auth/profile', request, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ defaultResumeId: resumeId }),
    });

    return NextResponse.json({
      success: true,
      defaultResumeId: resumeId,
      resume: newResume,
    });
  } catch (errorVal) {
    const error = errorVal as Error;
    console.error('[API Default Resume] Error:', error);
    return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
  }
}
