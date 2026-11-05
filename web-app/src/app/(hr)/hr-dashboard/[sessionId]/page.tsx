import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { SessionHistoryItem, QuestionFeedback } from '@/services/historyService';
import { HrSessionDetailClient, QuestionBankData } from '@/components/features/hr';
import { Button } from '@/components/ui/button';
import { ArrowLeft, FileCheck } from 'lucide-react';

export const revalidate = 0;

async function getQuestionBankData(sessionId: string): Promise<QuestionBankData | null> {
  try {
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/question-bank/session/${sessionId}`;
    console.log(`[HR Detail Page] Fetching question bank from: ${targetUrl}`);
    const res = await fetch(targetUrl, { method: 'GET', headers: { 'Content-Type': 'application/json' }, cache: 'no-store' });
    if (!res.ok) {
      console.warn(`[HR Detail Page] Failed to fetch question bank (${res.status}): ${res.statusText}`);
      return null;
    }
    return await res.json();
  } catch (error) {
    console.error('[HR Detail Page] Error fetching question bank:', error);
    return null;
  }
}

async function getSessionData(sessionId: string): Promise<SessionHistoryItem | null> {
  try {
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/sessions/${sessionId}`;
    const res = await fetch(targetUrl, { cache: 'no-store' });
    if (!res.ok) {
      return null;
    }
    const sess = await res.json();

    const questionsList: QuestionFeedback[] = (sess.turns || []).map((t: {
      id?: string | number;
      question?: string;
      answer?: string;
      score?: number;
      strengths?: string;
      improvements?: string;
      suggestedAnswer?: string;
      topicTag?: string;
      isDeepDive?: boolean;
      hrRating?: number;
      hrFeedback?: string;
    }) => ({
      id: t.id ? String(t.id) : undefined,
      question: t.question || '',
      answer: t.answer || '',
      score: t.score !== null && t.score !== undefined ? Number(t.score) : 0,
      strengths: t.strengths || '',
      improvements: t.improvements || '',
      suggestedAnswer: t.suggestedAnswer || '',
      topicTag: t.topicTag || '',
      isDeepDive: Boolean(t.isDeepDive),
      hrRating: t.hrRating !== null && t.hrRating !== undefined ? Number(t.hrRating) : undefined,
      hrFeedback: t.hrFeedback || undefined,
    }));

    return {
      id: sess.id,
      date: sess.startedAt || sess.date || new Date().toISOString(),
      interviewType: sess.interviewType || 'Technical',
      roleTitle: sess.roleTitle || 'Candidate',
      cvFilename: sess.cvFilename || 'CV.pdf',
      jdFilename: sess.jdFilename || 'JD.pdf',
      cvFileUrl: sess.cvFileUrl,
      jdFileUrl: sess.jdFileUrl,
      overallScore: sess.overallScore,
      status: sess.status || 'In progress',
      questions: questionsList,
      competencyFitScore: sess.overallScore,
      technicalDepthScore: sess.overallScore,
      matchLevel: sess.overallScore >= 80 ? 'High' : (sess.overallScore >= 60 ? 'Moderate' : 'Low'),
      candidateLevel: 'N/A',
      roleTypeDetected: sess.roleTitle || 'N/A',
      strongAreas: [],
      gapAreas: [],
      criticalMissingSkills: [],
      hiringRecommendation: sess.overallScore >= 70 ? 'Hire' : 'No Hire',
      scoreBreakdown: null,
      eligibility: null,
    };
  } catch (error) {
    console.error('[HR Detail Page] Error querying session data:', error);
    return null;
  }
}

export default async function HrSessionDetailPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  if (!sessionId) {
    notFound();
  }

  const [qbData, sessionData] = await Promise.all([
    getQuestionBankData(sessionId),
    getSessionData(sessionId),
  ]);

  return (
    <div className="container mx-auto max-w-5xl px-4 space-y-6">
      {/* Header Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="flex items-center space-x-3">
          <Link href="/hr-dashboard">
            <Button variant="outline" size="sm" className="gap-1 text-slate-700 inline-flex items-center gap-1">
              <ArrowLeft className="size-4" /> Quay lại danh sách
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileCheck className="size-5 text-brand-orange" />
              {sessionData
                ? (() => {
                    // Derive candidate name from cvFilename
                    let name = (sessionData.cvFilename || '').replace(/\.[^.]+$/, '').replace(/^cv_/i, '').replace(/[_\s]+(test|upload|final|v\d+|\d{4}|draft|new|copy)$/i, '').replace(/[_-]+/g, ' ').trim();
                    const role = sessionData.roleTitle || sessionData.roleTypeDetected || 'Đang xác định vị trí';
                    return name ? `${name} — ${role}` : role;
                  })()
                : 'Chi Tiết Phỏng Vấn'}
            </h1>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">Session ID: {sessionId}</p>
          </div>
        </div>
      </div>

      {/* Client wrapper handles tabs + form */}
      <HrSessionDetailClient
        sessionId={sessionId}
        sessionData={sessionData}
        qbData={qbData}
      />
    </div>
  );
}
