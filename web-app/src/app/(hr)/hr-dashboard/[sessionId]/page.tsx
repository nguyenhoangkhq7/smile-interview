import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { query } from '@/lib/db';
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
    const sql = `
      SELECT DISTINCT ON (s.id)
        s.*,
        r.file_url AS cv_file_url,
        COALESCE(r.raw_text, r.parsed_content) AS cv_extracted_text,
        j.file_url AS jd_file_url,
        COALESCE(j.raw_text, j.parsed_content) AS jd_extracted_text
      FROM sessions s
      LEFT JOIN resumes r ON (s.resume_id = r.id OR (s.resume_id IS NULL AND s.cv_filename = r.file_name))
      LEFT JOIN job_descriptions j ON (s.jd_id = j.id OR (s.jd_id IS NULL AND s.jd_filename = j.title))
      WHERE s.id = $1
      ORDER BY s.id, s.date DESC
    `;
    const res = await query(sql, [sessionId]);
    const sess = res.rows[0];

    if (!sess) {
      try {
        const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
        const assessUrl = `${backendUrl}/api/v2/assess-resume?sessionId=${sessionId}&forceRefresh=false`;
        const assessRes = await fetch(assessUrl, { cache: 'no-store' });
        if (assessRes.ok) {
          const data = await assessRes.json();
          const overallScore = data.overall_match_score ?? data.score_breakdown?.final_score ?? undefined;
          return {
            id: sessionId,
            date: data.created_at || new Date().toISOString(),
            interviewType: 'Technical',
            roleTitle: data.job_category || 'Software Engineer',
            cvFilename: 'Uploaded_CV.pdf',
            jdFilename: 'Uploaded_JD.pdf',
            overallScore,
            status: 'In progress',
            questions: [],
            competencyFitScore: overallScore,
            matchLevel: overallScore >= 80 ? 'High (Rất tốt)' : (overallScore >= 60 ? 'Moderate (Khớp)' : 'Low (Cần cải thiện)'),
            candidateLevel: data.seniority_level || 'N/A',
            roleTypeDetected: data.job_category || 'N/A',
            strongAreas: [],
            gapAreas: [],
            criticalMissingSkills: [],
            mustHaveEvidenceItems: data.must_have_evidence_items || [],
            preferToHaveEvidenceItems: data.prefer_to_have_evidence_items || [],
            gateEvidenceItems: data.gate_evidence_items || [],
            scoreBreakdown: data.score_breakdown || null,
            eligibility: data.eligibility || null,
          };
        }
      } catch (fErr) {
        console.warn('[HR Detail Page] Fallback assessment fetch failed:', fErr);
      }
      return null;
    }

    const parseJsonField = (val: unknown) => {
      if (typeof val === 'string') {
        try { return JSON.parse(val); } catch { return val; }
      }
      return val;
    };

    let questionsList: QuestionFeedback[] = [];
    try {
      const turnsRes = await query(
        'SELECT * FROM session_turns WHERE session_id = $1 ORDER BY turn_number ASC, created_at ASC',
        [sessionId]
      );
      questionsList = turnsRes.rows.map((t) => ({
        id: t.id,
        question: t.dynamic_question_text || t.question || '',
        answer: t.answer || '',
        score: t.score !== null && t.score !== undefined ? Number(t.score) : 0,
        strengths: t.strengths || '',
        improvements: t.improvements || '',
        suggestedAnswer: t.suggested_answer || '',
        topicTag: t.topic_tag || '',
        isDeepDive: Boolean(t.is_deep_dive),
        hrRating: t.hr_rating !== null && t.hr_rating !== undefined ? Number(t.hr_rating) : undefined,
        hrFeedback: t.hr_feedback || undefined,
      }));
    } catch (turnsErr) {
      console.warn('[HR Detail Page] Could not fetch session_turns:', turnsErr);
    }

    return {
      id: sess.id,
      date: sess.date,
      interviewType: sess.interview_type,
      roleTitle: sess.role_title,
      cvFilename: sess.cv_filename,
      jdFilename: sess.jd_filename,
      cvFileUrl: sess.cv_file_url || undefined,
      jdFileUrl: sess.jd_file_url || undefined,
      cvExtractedText: sess.cv_extracted_text || undefined,
      jdExtractedText: sess.jd_extracted_text || undefined,
      overallScore: sess.overall_score !== null ? sess.overall_score : undefined,
      status: sess.status,
      questions: questionsList,
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
