'use client';

import { useAdminOverview } from '@/hooks/useAdminOverview';
import { TIME_RANGE_OPTIONS } from '../data/dashboardOptions';
import type { TimeRangeKey } from '../types';
import AiEvaluationV2Section from './AiEvaluationV2Section';
import DashboardHeader from './DashboardHeader';
import KpiGrid from './KpiGrid';
import MethodTerminationCard from './MethodTerminationCard';
import SkillGapInsightsSection from './SkillGapInsightsSection';
import VolumeTelemetryChart from './VolumeTelemetryChart';

interface AdminOverviewPanelProps {
  range: TimeRangeKey;
  onSelectRange: (range: TimeRangeKey) => void;
}

export default function AdminOverviewPanel({ range, onSelectRange }: AdminOverviewPanelProps) {
  const { result, retry } = useAdminOverview(range);
  const data = result?.data;
  const rangeLabel = TIME_RANGE_OPTIONS.find((option) => option.key === range)?.label.toLowerCase() ?? '';

  return (
    <div className="flex w-full flex-col gap-6 pb-8">
      <DashboardHeader selectedRange={range} onSelectRange={onSelectRange} />
      {!result && (
        <p role="status" className="rounded-xl bg-white dark:bg-card p-6 text-sm text-[#5c4039] dark:text-muted-foreground">
          Đang tải số liệu tổng quan…
        </p>
      )}
      {result?.error && (
        <div role="alert" className="flex items-center gap-4 rounded-xl bg-white dark:bg-card p-6 text-sm">
          <span>{result.error}</span>
          <button type="button" onClick={retry} className="font-semibold text-[#ad2c00] dark:text-orange-300 underline">
            Thử lại
          </button>
        </div>
      )}
      {data && (
        <>
          <KpiGrid metrics={data.kpis} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <VolumeTelemetryChart points={data.telemetry} rangeLabel={rangeLabel} />
            <MethodTerminationCard segments={data.termination} />
          </div>
          <AiEvaluationV2Section levels={data.assessments} />
          <SkillGapInsightsSection knowledgeGaps={data.knowledgeGaps} popularRoles={data.popularRoles} />
        </>
      )}
    </div>
  );
}
