import React from 'react';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { HrSessionTable } from '@/components/features/hr';

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
      <div className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight sm:text-3xl">
          Cổng Đánh Giá HR
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Quản lý danh sách phiên phỏng vấn, kiểm tra chất lượng ngân hàng câu hỏi AI và gửi đánh giá chuyên môn.
        </p>
      </div>

      {/* Main Sessions Table */}
      <HrSessionTable sessions={sessions} />
    </div>
  );
}
