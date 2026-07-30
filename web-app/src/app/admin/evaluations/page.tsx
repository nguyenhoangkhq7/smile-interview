import React from 'react';
import {
  EvaluationStatsCards,
  AdminEvaluationTable,
  HrEvaluationAdminItem,
} from '@/components/features/admin/evaluations';
import { BarChart3, ShieldCheck } from 'lucide-react';

export const revalidate = 0; // Always fetch fresh evaluation results

async function fetchAdminEvaluations(): Promise<HrEvaluationAdminItem[]> {
  try {
    const backendUrl = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';
    const targetUrl = `${backendUrl}/api/v1/hr-evaluations/all`;

    console.log(`[Admin Evaluation Page] Fetching all HR evaluations from: ${targetUrl}`);
    const res = await fetch(targetUrl, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      console.warn(`[Admin Evaluation Page] Failed to fetch evaluations (${res.status}): ${res.statusText}`);
      return [];
    }

    return await res.json();
  } catch (error) {
    console.error('[Admin Evaluation Page] Error fetching evaluations:', error);
    return [];
  }
}

export default async function AdminEvaluationsPage() {
  const evaluations = await fetchAdminEvaluations();

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Thống kê & Kết quả Đánh giá Thực nghiệm (HR Validation)
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            Bảng tổng hợp điểm số đánh giá định lượng và nhận xét định tính từ chuyên viên HR về ngân hàng câu hỏi do AI tạo.
          </p>
        </div>

        <div className="flex items-center space-x-2 rounded-xl border border-white/10 bg-slate-900/80 px-3.5 py-2 text-xs text-slate-300">
          <ShieldCheck className="size-4 text-orange-400" />
          <span>Quyền Quản Trị Viên (Admin)</span>
        </div>
      </div>

      {/* 1. Evaluation Metric Cards */}
      <EvaluationStatsCards evaluations={evaluations} />

      {/* 2. Admin Evaluation Data Table */}
      <AdminEvaluationTable evaluations={evaluations} />
    </div>
  );
}
