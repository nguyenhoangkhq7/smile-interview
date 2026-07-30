import React from 'react';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { HrSessionTable } from '@/components/features/hr';
import { ShieldCheck, Sparkles, Users } from 'lucide-react';

export const revalidate = 0; // Always fetch fresh history data

export default async function HrDashboardPage() {
  let sessions: SessionHistoryItem[] = [];

  try {
    sessions = await historyService.getHistory();
  } catch (error) {
    console.error('[HrDashboardPage] Failed to load interview history:', error);
  }

  return (
    <div className="container mx-auto max-w-7xl px-4 space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight sm:text-3xl">
              Cổng Đánh Giá HR (HR Evaluation Portal)
            </h1>
            <span className="inline-flex items-center rounded-full bg-brand-orange/10 px-2.5 py-0.5 text-xs font-bold text-brand-orange border border-brand-orange/20">
              <Sparkles className="mr-1 size-3" /> HR Validation
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Quản lý danh sách các phiên phỏng vấn, kiểm tra chất lượng ngân hàng câu hỏi AI và đóng góp đánh giá chuyên môn HR.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs text-slate-600 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex size-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <Users className="size-5" />
          </div>
          <div>
            <p className="font-bold text-slate-800">Dành cho Chuyên Viên HR</p>
            <p className="text-slate-500">Validation & Model Feedback</p>
          </div>
        </div>
      </div>

      {/* Main Sessions Table */}
      <HrSessionTable sessions={sessions} />
    </div>
  );
}
