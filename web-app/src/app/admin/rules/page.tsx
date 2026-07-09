'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  adminService,
  JobCategoryDto,
  EvaluationCriteriaDto,
  CategoryCriteriaMappingDto,
  LevelDistributionRuleDto,
  SystemSettingDto,
} from '@/services/adminService';
import { ToastContainer } from '@/components/admin/Toast';
import JobCategoryTable from '@/components/admin/JobCategoryTable';
import EvaluationCriteriaTable from '@/components/admin/EvaluationCriteriaTable';
import WeightMappingTable from '@/components/admin/WeightMappingTable';
import LevelDistributionTable from '@/components/admin/LevelDistributionTable';
import SystemSettingTable from '@/components/admin/SystemSettingTable';

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  {
    id: 'rule-engine',
    label: 'Khung đánh giá',
    subtitle: 'Rule Engine',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z" /><path d="M7 7h.01" />
      </svg>
    ),
  },
  {
    id: 'weights',
    label: 'Trọng số',
    subtitle: 'Weight Mappings',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="14" x2="6" y2="20" /><line x1="18" y1="10" x2="18" y2="20" />
      </svg>
    ),
  },
  {
    id: 'distributions',
    label: 'Cấu trúc đề',
    subtitle: 'Distributions',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /><line x1="2" y1="12" x2="22" y2="12" />
      </svg>
    ),
  },
  {
    id: 'system',
    label: 'Hệ số lõi',
    subtitle: 'System Logic',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14" /><path d="M4.93 4.93a10 10 0 0 0 0 14.14" /><path d="M16.24 7.76a6 6 0 0 1 0 8.49" /><path d="M7.76 7.76a6 6 0 0 0 0 8.49" />
      </svg>
    ),
  },
] as const;

type TabId = typeof TABS[number]['id'];

// ── Data state ────────────────────────────────────────────────────────────────
interface AdminData {
  categories: JobCategoryDto[];
  criteria: EvaluationCriteriaDto[];
  mappings: CategoryCriteriaMappingDto[];
  levelRules: LevelDistributionRuleDto[];
  settings: SystemSettingDto[];
}

export default function AdminRulesPage() {
  const [activeTab, setActiveTab] = useState<TabId>('rule-engine');
  const [data, setData] = useState<AdminData>({
    categories: [],
    criteria: [],
    mappings: [],
    levelRules: [],
    settings: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [categories, criteria, mappings, levelRules, settings] = await Promise.all([
        adminService.getJobCategories(),
        adminService.getEvaluationCriteria(),
        adminService.getCategoryMappings(),
        adminService.getLevelDistributionRules(),
        adminService.getSystemSettings(),
      ]);
      setData({ categories, criteria, mappings, levelRules, settings });
    } catch (err) {
      setError('Không thể tải dữ liệu. Kiểm tra kết nối đến matching-service (port 8081).');
      console.error('[AdminRulesPage] Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ── Stats summary ─────────────────────────────────────────────────────────
  const stats = [
    { label: 'Danh mục', value: data.categories.length, color: 'text-orange-400' },
    { label: 'Tiêu chí', value: data.criteria.length, color: 'text-blue-400' },
    { label: 'Mappings', value: data.mappings.length, color: 'text-purple-400' },
    { label: 'Cấp bậc', value: data.levelRules.length, color: 'text-emerald-400' },
  ];

  return (
    <div className="max-w-7xl mx-auto">
      <ToastContainer />

      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Rule Engine Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">
              Quản lý tiêu chí đánh giá, trọng số và cấu hình hệ thống
            </p>
          </div>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 rounded-xl transition-colors disabled:opacity-50"
          >
            <svg className={loading ? 'animate-spin' : ''} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" /><path d="M16 21h5v-5" />
            </svg>
            Làm mới
          </button>
        </div>

        {/* Stats row */}
        {!loading && !error && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
            {stats.map((s) => (
              <div key={s.label} className="bg-slate-800/40 rounded-xl border border-slate-800 px-4 py-3">
                <p className={`text-2xl font-bold tabular-nums ${s.color}`}>{s.value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300">
          <svg className="flex-shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" />
          </svg>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-slate-800/30 animate-pulse" />
          ))}
        </div>
      )}

      {/* Tab navigation + content */}
      {!loading && !error && (
        <div className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden">
          {/* Tab bar */}
          <div className="flex overflow-x-auto border-b border-slate-800">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2.5 px-5 py-4 text-sm font-medium whitespace-nowrap border-b-2 transition-all duration-150 ${
                    isActive
                      ? 'border-orange-500 text-orange-400 bg-orange-950/20'
                      : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/30'
                  }`}
                >
                  <span className={isActive ? 'text-orange-400' : 'text-slate-600'}>{tab.icon}</span>
                  <div className="text-left">
                    <div>{tab.label}</div>
                    <div className={`text-xs font-normal ${isActive ? 'text-orange-500/70' : 'text-slate-600'}`}>{tab.subtitle}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Tab content */}
          <div className="p-6">
            {activeTab === 'rule-engine' && (
              <div className="space-y-10">
                <JobCategoryTable categories={data.categories} onRefresh={fetchAll} />
                <div className="border-t border-slate-800 pt-8">
                  <EvaluationCriteriaTable criteria={data.criteria} onRefresh={fetchAll} />
                </div>
              </div>
            )}

            {activeTab === 'weights' && (
              <WeightMappingTable
                mappings={data.mappings}
                categories={data.categories}
                criteria={data.criteria}
                onRefresh={fetchAll}
              />
            )}

            {activeTab === 'distributions' && (
              <LevelDistributionTable rules={data.levelRules} onRefresh={fetchAll} />
            )}

            {activeTab === 'system' && (
              <SystemSettingTable settings={data.settings} onRefresh={fetchAll} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
