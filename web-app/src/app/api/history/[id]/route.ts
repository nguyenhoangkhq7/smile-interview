import { NextRequest, NextResponse } from 'next/server';
import { forwardToBackend } from '@/lib/backendClient';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    const backendRes = await forwardToBackend(`/api/v1/sessions/${id}`, request, {
      method: 'GET',
    });

    if (!backendRes.ok) {
      const err = await backendRes.text();
      return NextResponse.json({ error: err }, { status: backendRes.status });
    }

    const sess = await backendRes.json();

    const result = {
      id: sess.id,
      date: sess.startedAt || sess.date,
      interviewType: sess.interviewType,
      roleTitle: sess.roleTitle,
      cvFilename: sess.cvFilename,
      jdFilename: sess.jdFilename,
      cvFileUrl: sess.cvFileUrl,
      jdFileUrl: sess.jdFileUrl,
      resumeId: sess.resumeId,
      jdId: sess.jdId,
      overallScore: sess.overallScore,
      status: sess.status,
      overallFeedback: sess.overallFeedback,
      userRating: sess.userRating,
      userFeedbackText: sess.userFeedbackText,
      questions: (sess.turns || []).map((t: {
        question?: string;
        answer?: string;
        score?: number;
        strengths?: string;
        improvements?: string;
        suggestedAnswer?: string;
        topicTag?: string;
        isDeepDive?: boolean;
      }) => ({
        question: t.question,
        answer: t.answer,
        score: t.score,
        strengths: t.strengths,
        improvements: t.improvements,
        suggestedAnswer: t.suggestedAnswer,
        topicTag: t.topicTag,
        isDeepDive: t.isDeepDive,
      })),
    };

    return NextResponse.json(result);
  } catch (error) {
    const err = error as Error;
    console.error(`[API History Detail] Error fetching session detail:`, err);
    return NextResponse.json({ error: err.message || 'Internal server error' }, { status: 500 });
  }
}
