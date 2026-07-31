'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Toaster } from '@/components/ui/sonner';
import { useAdminRules } from '@/hooks/useAdminRules';
import JobCategoryTable from '@/components/admin/JobCategoryTable';
import EvaluationCriteriaTable from '@/components/admin/EvaluationCriteriaTable';
import WeightMappingTable from '@/components/admin/WeightMappingTable';
import LevelDistributionTable from '@/components/admin/LevelDistributionTable';
import SystemSettingTable from '@/components/admin/SystemSettingTable';
import StatCards from '@/components/admin/rule-dashboard/StatCards';
import { IconRefresh, IconChevronLeft, IconX } from '@/components/ui/icons';

export default function AdminRulesPage() {
  const { data, loading, error, fetchAll, stats } = useAdminRules();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) =>
      setSidebarCollapsed((e as CustomEvent<boolean>).detail);
    window.addEventListener('admin-sidebar-collapsed', handler);
    return () => window.removeEventListener('admin-sidebar-collapsed', handler);
  }, []);

  return (
    <div className="w-full max-w-7xl mx-auto space-y-8 p-6 md:p-8">
      <Toaster />

      {/* Page header */}
      <div className="rounded-3xl border border-white/6 bg-slate-950/45 px-6 py-6 shadow-[0_18px_60px_rgba(2,6,23,0.18)] backdrop-blur-sm sm:px-8 sm:py-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Rule Engine Dashboard</p>
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="icon"
                onClick={() => window.dispatchEvent(new Event('toggle-admin-sidebar'))}
                aria-label={sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
                className="border-slate-700 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:text-white"
              >
                <IconChevronLeft size={16} className={`transition-transform duration-200 ${sidebarCollapsed ? 'rotate-180' : ''}`} />
              </Button>
              <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Quản lý tiêu chí, trọng số và cấu hình hệ thống
              </h1>
            </div>
          </div>

          <Button
            variant="outline"
            onClick={fetchAll}
            disabled={loading}
            className="self-center border-slate-700 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:text-white disabled:opacity-40"
          >
            <IconRefresh size={14} className={loading ? 'animate-spin' : ''} />
            Làm mới
          </Button>
        </div>

        {!loading && !error && (
          <div className="mt-8">
            <StatCards items={stats} />
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-300">
          <IconX size={16} className="mt-0.5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl bg-slate-800/30" />)}
        </div>
      )}

      {/* Tabs */}
      {!loading && !error && (
        <Tabs defaultValue="categories" className="rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden">
          <TabsList className="w-full justify-start overflow-x-auto rounded-none border-b border-slate-800 bg-slate-950/20 h-auto p-0">
            {(['categories', 'criteria', 'weights', 'distributions', 'system'] as const).map((tab) => {
              const labels: Record<string, string> = {
                categories: 'Danh mục', criteria: 'Tiêu chí',
                weights: 'Trọng số', distributions: 'Cấu trúc đề', system: 'Hệ số lõi',
              };
              return (
                <TabsTrigger
                  key={tab} value={tab}
                  className="min-w-[140px] rounded-none border-b-2 border-transparent px-6 py-4 text-slate-400 data-[state=active]:border-orange-500 data-[state=active]:bg-orange-950/20 data-[state=active]:text-orange-400"
                >
                  {labels[tab]}
                </TabsTrigger>
              );
            })}
          </TabsList>

          <div className="p-8">
            <TabsContent value="categories" className="mt-0">
              <JobCategoryTable categories={data.categories} onRefresh={fetchAll} />
            </TabsContent>
            <TabsContent value="criteria" className="mt-0">
              <EvaluationCriteriaTable criteria={data.criteria} categories={data.categories} mappings={data.mappings} onRefresh={fetchAll} />
            </TabsContent>
            <TabsContent value="weights" className="mt-0">
              <WeightMappingTable mappings={data.mappings} categories={data.categories} criteria={data.criteria} onRefresh={fetchAll} />
            </TabsContent>
            <TabsContent value="distributions" className="mt-0">
              <LevelDistributionTable rules={data.levelRules} onRefresh={fetchAll} />
            </TabsContent>
            <TabsContent value="system" className="mt-0">
              <SystemSettingTable settings={data.settings} onRefresh={fetchAll} />
            </TabsContent>
          </div>
        </Tabs>
      )}
    </div>
  );
}
