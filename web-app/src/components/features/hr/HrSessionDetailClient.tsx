'use client';

import React, { useState } from 'react';
import { SessionHistoryItem } from '@/services/historyService';
import {
  AiContextBanner,
  QuestionCardList,
  HrEvaluationForm,
  QuestionBankData,
  CvJdMatchingView,
  InterviewTranscriptView,
} from '@/components/features/hr';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/authStore';
import {
  ShieldAlert,
  FileText,
  HelpCircle,
  MessageSquare,
  Send,
  CheckCircle2,
  Lock,
  User,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';

interface HrSessionDetailClientProps {
  sessionId: string;
  sessionData: SessionHistoryItem | null;
  qbData: QuestionBankData | null;
}

export const HrSessionDetailClient: React.FC<HrSessionDetailClientProps> = ({
  sessionId,
  sessionData,
  qbData,
}) => {
  const [activeTab, setActiveTab] = useState<'matching' | 'questions' | 'transcript'>('matching');

  // ── Shared evaluation state (persists across tab switches) ─────────────────
  const [ratingMatchingAccuracy, setRatingMatchingAccuracy] = useState<number>(5);
  const [ratingAiRationale, setRatingAiRationale] = useState<number>(5);
  const [ratingQuestionQuality, setRatingQuestionQuality] = useState<number>(5);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Fixed bottom bar: collapsed by default
  const [footerExpanded, setFooterExpanded] = useState(false);

  // Auto-fill evaluator from auth
  const { user, token } = useAuthStore();
  const evaluatorName = user?.username || 'HR Specialist';

  // Track which criteria have been deliberately touched (moved off default)
  const [touchedMatching, setTouchedMatching] = useState(false);
  const [touchedRationale, setTouchedRationale] = useState(false);
  const [touchedQuality, setTouchedQuality] = useState(false);

  const ratedCount = [touchedMatching, touchedRationale, touchedQuality].filter(Boolean).length;
  const totalCriteria = 3;

  const handleRatingMatchingChange = (v: number) => {
    setRatingMatchingAccuracy(v);
    setTouchedMatching(true);
  };
  const handleRatingRationaleChange = (v: number) => {
    setRatingAiRationale(v);
    setTouchedRationale(true);
  };
  const handleRatingQualityChange = (v: number) => {
    setRatingQuestionQuality(v);
    setTouchedQuality(true);
  };

  // ── Single submit for all ratings ──────────────────────────────────────────
  const handleSubmitAll = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!sessionId) {
      toast.error('Lỗi: Không tìm thấy mã phiên phỏng vấn (Session ID).');
      return;
    }

    setIsSubmitting(true);
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const payload = {
        session_id: sessionId,
        evaluator_name: evaluatorName,
        rating_matching_accuracy: ratingMatchingAccuracy,
        rating_ai_rationale: ratingAiRationale,
        rating_question_quality: ratingQuestionQuality,
        feedback_notes: feedbackNotes.trim() || undefined,
      };

      const res = await fetch('/api/hr-evaluations', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.message || 'Gửi đánh giá thất bại');

      setIsSubmitted(true);
      setFooterExpanded(false);
      toast.success('Đã gửi đánh giá HR thành công!');
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Đã có lỗi xảy ra khi gửi đánh giá');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/*
       * Main scrollable content.
       * pb-[72px] reserves space for the fixed bottom bar (collapsed ~56px + 16px gap).
       * When bar is expanded we add more space via pb-[220px] — both values are safe
       * because content simply scrolls above the bar, never hidden behind it.
       */}
      <div className={`space-y-6 transition-[padding] duration-300 ${footerExpanded ? 'pb-[220px]' : 'pb-[72px]'}`}>
        <Tabs
          value={activeTab}
          onValueChange={(val) => setActiveTab(val as 'matching' | 'questions' | 'transcript')}
          className="w-full space-y-6"
        >
          {/* Tab Triggers */}
          <TabsList className="flex w-full bg-slate-200/80 p-1 rounded-xl border border-slate-300/60 shadow-inner gap-1 overflow-x-auto">
            <TabsTrigger
              value="matching"
              className="flex-1 min-w-0 flex items-center justify-center gap-1.5 text-xs font-bold py-2 px-2 rounded-lg data-[state=active]:bg-white data-[state=active]:text-blue-700 data-[state=active]:shadow-sm transition-all cursor-pointer whitespace-nowrap"
            >
              <FileText className="size-3.5 text-blue-600 shrink-0" />
              <span className="truncate">1. So Khớp CV &amp; JD</span>
            </TabsTrigger>
            <TabsTrigger
              value="questions"
              className="flex-1 min-w-0 flex items-center justify-center gap-1.5 text-xs font-bold py-2 px-2 rounded-lg data-[state=active]:bg-white data-[state=active]:text-brand-orange data-[state=active]:shadow-sm transition-all cursor-pointer whitespace-nowrap"
            >
              <HelpCircle className="size-3.5 text-brand-orange shrink-0" />
              <span className="truncate">2. Ngân Hàng Câu Hỏi</span>
            </TabsTrigger>
            <TabsTrigger
              value="transcript"
              className="flex-1 min-w-0 flex items-center justify-center gap-1.5 text-xs font-bold py-2 px-2 rounded-lg data-[state=active]:bg-white data-[state=active]:text-indigo-700 data-[state=active]:shadow-sm transition-all cursor-pointer whitespace-nowrap"
            >
              <MessageSquare className="size-3.5 text-indigo-600 shrink-0" />
              <span className="truncate">3. Nhật Ký ({sessionData?.questions?.length || 0})</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Matching */}
          <TabsContent value="matching" className="space-y-6 focus:outline-none">
            <CvJdMatchingView session={sessionData} />
            <div className="pt-4 border-t border-slate-200">
              <HrEvaluationForm
                activeTab="matching"
                ratingMatchingAccuracy={ratingMatchingAccuracy}
                ratingAiRationale={ratingAiRationale}
                ratingQuestionQuality={ratingQuestionQuality}
                onRatingMatchingAccuracyChange={handleRatingMatchingChange}
                onRatingAiRationaleChange={handleRatingRationaleChange}
                onRatingQuestionQualityChange={handleRatingQualityChange}
                isSubmitted={isSubmitted}
              />
            </div>
          </TabsContent>

          {/* Tab 2: Question Bank */}
          <TabsContent value="questions" className="space-y-6 focus:outline-none">
            {qbData ? (
              <>
                <AiContextBanner metadata={qbData.metadata} />
                <QuestionCardList questions={qbData.question_bank} />
              </>
            ) : (
              <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-8 text-center space-y-3">
                <ShieldAlert className="mx-auto size-10 text-amber-600" />
                <h3 className="text-lg font-bold text-amber-900">
                  Chưa Tìm Thấy Ngân Hàng Câu Hỏi AI Đã Sinh
                </h3>
                <p className="max-w-md mx-auto text-sm text-amber-800">
                  Phiên phỏng vấn <strong>{sessionId}</strong> chưa được tạo ngân hàng câu hỏi AI thành công hoặc ứng viên mới dừng ở bước đánh giá So khớp CV-JD.
                </p>
              </div>
            )}
            <div className="pt-4 border-t border-slate-200">
              <HrEvaluationForm
                activeTab="questions"
                ratingMatchingAccuracy={ratingMatchingAccuracy}
                ratingAiRationale={ratingAiRationale}
                ratingQuestionQuality={ratingQuestionQuality}
                onRatingMatchingAccuracyChange={handleRatingMatchingChange}
                onRatingAiRationaleChange={handleRatingRationaleChange}
                onRatingQuestionQualityChange={handleRatingQualityChange}
                isSubmitted={isSubmitted}
              />
            </div>
          </TabsContent>

          {/* Tab 3: Transcript */}
          <TabsContent value="transcript" className="space-y-6 focus:outline-none">
            <InterviewTranscriptView questions={sessionData?.questions || []} sessionId={sessionId} />
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Fixed bottom evaluation bar ────────────────────────────────────────
          Docked to viewport bottom. Never overlaps content — content has pb to
          compensate. Collapsed by default (~56px); expand to show notes + detail.
      ─────────────────────────────────────────────────────────────────────── */}
      <div className="fixed bottom-0 left-0 right-0 z-50">
        {/* Submitted state — slim green confirmation bar */}
        {isSubmitted ? (
          <div className="mx-auto max-w-5xl px-4">
            <div className="border border-emerald-200 bg-emerald-50 shadow-lg rounded-t-xl flex items-center justify-between px-4 h-14 gap-3">
              <div className="flex items-center gap-2">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                </div>
                <span className="text-sm font-bold text-emerald-900">Đánh Giá HR Đã Được Lưu Thành Công!</span>
              </div>
              <div className="flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-md shrink-0">
                <Lock className="size-3 mr-0.5" /> Đã khóa
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl px-4">
            <div className="border border-slate-200 bg-white shadow-[0_-4px_16px_rgba(0,0,0,0.08)] rounded-t-xl overflow-hidden">

              {/* ── Collapsed bar (always visible) ── */}
              <div className="flex items-center justify-between px-4 h-14 gap-3">
                {/* Left: evaluator + progress summary */}
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-xs text-slate-600 shrink-0">
                    <User className="size-3.5 text-slate-400" />
                    <span className="font-semibold text-slate-900">{evaluatorName}</span>
                  </div>
                  <span className="text-slate-300 text-xs">·</span>
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="h-1.5 w-20 rounded-full bg-slate-200 overflow-hidden shrink-0 hidden sm:block">
                      <div
                        className="h-full rounded-full bg-brand-orange transition-all duration-300"
                        style={{ width: `${(ratedCount / totalCriteria) * 100}%` }}
                      />
                    </div>
                    <span className={`text-xs font-bold shrink-0 ${ratedCount === totalCriteria ? 'text-emerald-600' : 'text-brand-orange'}`}>
                      {ratedCount}/{totalCriteria} tiêu chí đã đánh giá
                    </span>
                  </div>
                </div>

                {/* Right: submit + expand toggle */}
                <div className="flex items-center gap-2 shrink-0">
                  <form onSubmit={handleSubmitAll}>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isSubmitting}
                      className="bg-brand-orange text-white hover:bg-brand-orange-hover font-bold shadow-sm gap-1.5 text-xs h-8 px-3"
                    >
                      {isSubmitting ? (
                        <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      ) : (
                        <Send className="size-3.5" />
                      )}
                      <span className="hidden sm:inline">Gửi Đánh Giá HR</span>
                      <span className="sm:hidden">Gửi</span>
                    </Button>
                  </form>

                  <button
                    type="button"
                    onClick={() => setFooterExpanded(!footerExpanded)}
                    aria-label={footerExpanded ? 'Thu gọn panel đánh giá' : 'Mở rộng panel đánh giá'}
                    className="flex size-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors shrink-0"
                  >
                    {footerExpanded ? (
                      <ChevronDown className="size-4" />
                    ) : (
                      <ChevronUp className="size-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* ── Expanded panel (notes textarea + criterion detail) ── */}
              {footerExpanded && (
                <div className="border-t border-slate-100 px-4 pb-4 pt-3 space-y-3 bg-slate-50/60">
                  <p className="text-[11px] text-slate-500">
                    Tiêu chí 1 (So Khớp CV-JD)
                    {touchedMatching ? <span className="ml-1 text-emerald-600 font-semibold">✓</span> : <span className="ml-1 text-slate-300">○</span>}
                    {' · '}
                    Tiêu chí 2 (Lập Luận AI)
                    {touchedRationale ? <span className="ml-1 text-emerald-600 font-semibold">✓</span> : <span className="ml-1 text-slate-300">○</span>}
                    {' · '}
                    Tiêu chí 3 (Chất Lượng Câu Hỏi)
                    {touchedQuality ? <span className="ml-1 text-emerald-600 font-semibold">✓</span> : <span className="ml-1 text-slate-300">○</span>}
                  </p>

                  <form onSubmit={handleSubmitAll} className="space-y-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="feedbackNotes" className="text-xs font-semibold text-slate-700">
                        Ghi Chú &amp; Nhận Xét Bổ Sung (tuỳ chọn)
                      </Label>
                      <Textarea
                        id="feedbackNotes"
                        rows={2}
                        placeholder="Nhập góp ý hoặc ghi chú bổ sung về ngân hàng câu hỏi..."
                        value={feedbackNotes}
                        onChange={(e) => setFeedbackNotes(e.target.value)}
                        disabled={isSubmitting}
                        className="bg-white text-xs resize-none"
                      />
                    </div>

                    <Button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full bg-brand-orange text-white hover:bg-brand-orange-hover font-bold py-2 shadow-sm gap-2 h-9"
                    >
                      {isSubmitting ? (
                        <>
                          <span className="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                          <span>Đang gửi đánh giá...</span>
                        </>
                      ) : (
                        <>
                          <Send className="size-4" />
                          <span>Gửi Đánh Giá HR ({ratedCount}/{totalCriteria} tiêu chí)</span>
                        </>
                      )}
                    </Button>
                  </form>
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    </>
  );
};
