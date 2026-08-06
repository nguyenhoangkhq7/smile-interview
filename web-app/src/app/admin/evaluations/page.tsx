'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  EvaluationStatsCards,
  AdminEvaluationTable,
  HrEvaluationAdminItem,
} from '@/components/features/admin/evaluations';
import { adminService } from '@/services/adminService';
import { ShieldCheck, RefreshCw, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export default function AdminEvaluationsPage() {
  const [evaluations, setEvaluations] = useState<HrEvaluationAdminItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvaluations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminService.getHrEvaluations();
      setEvaluations(data || []);
    } catch (err) {
      console.error('[Admin Evaluation Page] Error fetching evaluations:', err);
      const message = err instanceof Error ? err.message : 'Không thể tải danh sách đánh giá từ HR';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvaluations();
  }, [fetchEvaluations]);

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

        <div className="flex items-center space-x-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchEvaluations}
            disabled={loading}
            className="border-slate-700 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:text-white disabled:opacity-40 gap-1.5 text-xs font-semibold"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
            Làm mới
          </Button>

          <div className="flex items-center space-x-2 rounded-xl border border-white/10 bg-slate-900/80 px-3.5 py-2 text-xs text-slate-300">
            <ShieldCheck className="size-4 text-orange-400" />
            <span>Quyền Quản Trị Viên (Admin)</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-800/60 bg-rose-950/40 p-4 text-xs text-rose-300">
          <AlertTriangle className="size-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl bg-slate-900/60 border border-white/5" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-2xl bg-slate-900/60 border border-white/5" />
        </div>
      ) : (
        <>
          {/* 1. Evaluation Metric Cards */}
          <EvaluationStatsCards evaluations={evaluations} />

          {/* 2. Admin Evaluation Data Table */}
          <AdminEvaluationTable evaluations={evaluations} />
        </>
      )}
    </div>
  );
}
