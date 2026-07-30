import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { query } from '@/lib/db';
import { SessionHistoryItem } from '@/services/historyService';
import {
  AiContextBanner,
  QuestionCardList,
  HrEvaluationForm,
  QuestionBankData,
  CvJdMatchingView,
} from '@/components/features/hr';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ArrowLeft, FileCheck, ShieldAlert, FileText, HelpCircle } from 'lucide-react';

export const revalidate = 0; // Always fetch fresh data for evaluation

async function getQuestionBankData(sessionId: string): Promise<QuestionBankData | null> {
  try {
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/question-bank/session/${sessionId}`;

    console.log(`[HR Detail Page] Fetching question bank from: ${targetUrl}`);
    const res = await fetch(targetUrl, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });

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
    const res = await query('SELECT * FROM sessions WHERE id = $1', [sessionId]);
    if (res.rows.length === 0) return null;
    const sess = res.rows[0];

    const parseJsonField = (val: unknown) => {
      if (typeof val === 'string') {
        try {
          return JSON.parse(val);
        } catch {
          return val;
        }
      }
      return val;
    };

    return {
      id: sess.id,
      date: sess.date,
      interviewType: sess.interview_type,
      roleTitle: sess.role_title,
      cvFilename: sess.cv_filename,
      jdFilename: sess.jd_filename,
      overallScore: sess.overall_score !== null ? sess.overall_score : undefined,
      status: sess.status,
      questions: [],
      competencyFitScore: sess.competency_fit_score !== null ? sess.competency_fit_score : undefined,
      technicalDepthScore: sess.technical_depth_score !== null ? sess.technical_depth_score : undefined,
      matchLevel: sess.match_level || undefined,
      candidateLevel: sess.candidate_level || undefined,
      roleTypeDetected: sess.role_type_detected || undefined,
      strongAreas: parseJsonField(sess.strong_areas) || [],
      gapAreas: parseJsonField(sess.gap_areas) || [],
      criticalMissingSkills: parseJsonField(sess.critical_missing_skills) || [],
      hiringRecommendation: sess.hiring_recommendation || undefined,
      scoreBreakdown: parseJsonField(sess.score_breakdown) || null,
      eligibility: parseJsonField(sess.eligibility) || null,
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
          <Button variant="outline" size="sm" className="gap-1 text-slate-700">
            <Link href="/hr-dashboard" className="inline-flex items-center gap-1">
              <ArrowLeft className="size-4" /> Quay lại danh sách
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileCheck className="size-5 text-brand-orange" />
              Chi Tiết Đánh Giá Phỏng Vấn & So Khớp CV-JD
            </h1>
            <p className="text-xs text-slate-500 font-mono">
              Session ID: {sessionId}
            </p>
          </div>
        </div>
      </div>

      {/* If question bank data not found */}
      {!qbData ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-8 text-center space-y-3">
          <ShieldAlert className="mx-auto size-10 text-amber-600" />
          <h3 className="text-lg font-bold text-amber-900">
            Chưa Tìm Thấy Ngân Hàng Câu Hỏi AI Đã Sinh
          </h3>
          <p className="max-w-md mx-auto text-sm text-amber-800">
            Phiên phỏng vấn <strong>{sessionId}</strong> chưa được tạo ngân hàng câu hỏi AI thành công hoặc dữ liệu chưa sẵn sàng trên hệ thống backend.
          </p>
          <Button size="sm" variant="outline" className="mt-2 border-amber-300 text-amber-900">
            <Link href="/hr-dashboard">Quay Lại Dashboard HR</Link>
          </Button>
        </div>
      ) : (
        /* Assembled Tabbed Layout */
        <div className="space-y-8">
          {/* Tabs for Review: Matching vs Questions */}
          <Tabs defaultValue="matching" className="w-full space-y-6">
            <TabsList className="grid w-full grid-cols-2 bg-slate-200/80 p-1.5 rounded-xl border border-slate-300/60 shadow-inner">
              <TabsTrigger
                value="matching"
                className="font-bold gap-2 text-sm py-2.5 data-active:bg-white data-active:text-blue-700 data-active:shadow-sm transition-all cursor-pointer"
              >
                <FileText className="size-4 text-blue-600" />
                1. Đánh giá So khớp (Matching)
              </TabsTrigger>
              <TabsTrigger
                value="questions"
                className="font-bold gap-2 text-sm py-2.5 data-active:bg-white data-active:text-brand-orange data-active:shadow-sm transition-all cursor-pointer"
              >
                <HelpCircle className="size-4 text-brand-orange" />
                2. Đánh giá Câu hỏi (Questions)
              </TabsTrigger>
            </TabsList>

            {/* Tab 1: Matching Review */}
            <TabsContent value="matching" className="space-y-6 focus:outline-none">
              <CvJdMatchingView session={sessionData} />
            </TabsContent>

            {/* Tab 2: Question Bank Review */}
            <TabsContent value="questions" className="space-y-6 focus:outline-none">
              <AiContextBanner metadata={qbData.metadata} />
              <QuestionCardList questions={qbData.question_bank} />
            </TabsContent>
          </Tabs>

          {/* 3. HR Evaluation Form (Always visible below tabs) */}
          <div className="pt-6 border-t border-slate-200">
            <HrEvaluationForm sessionId={sessionId} />
          </div>
        </div>
      )}
    </div>
  );
}
