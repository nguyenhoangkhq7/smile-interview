'use client';

import React, { useState } from 'react';
import { SessionHistoryItem, QuestionFeedback } from '@/services/historyService';
import {
  AiContextBanner,
  QuestionCardList,
  HrEvaluationForm,
  QuestionBankData,
  CvJdMatchingView,
  InterviewTranscriptView,
} from '@/components/features/hr';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ShieldAlert, FileText, HelpCircle, MessageSquare } from 'lucide-react';

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

  return (
    <div className="space-y-6">
      <Tabs
        defaultValue="matching"
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
            <span className="truncate">1. So Khớp CV & JD</span>
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
            <HrEvaluationForm sessionId={sessionId} activeTab="matching" />
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
            <HrEvaluationForm sessionId={sessionId} activeTab="questions" />
          </div>
        </TabsContent>

        {/* Tab 3: Transcript */}
        <TabsContent value="transcript" className="space-y-6 focus:outline-none">
          <InterviewTranscriptView questions={sessionData?.questions || []} sessionId={sessionId} />
        </TabsContent>
      </Tabs>
    </div>
  );
};
