'use client';

import React, { useEffect, useState } from 'react';
import {
  ArrowUp,
  AudioWaveform,
  BadgeCheck,
  Check,
  Cpu,
  FileText,
  Mic,
  Users,
} from 'lucide-react';
import { useCountUp } from '../hooks/useCountUp';
import { KpiMetricsData } from '../types';

interface KpiGridProps {
  metrics: KpiMetricsData;
}

export default function KpiGrid({ metrics }: KpiGridProps) {
  const [barsAnimated, setBarsAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setBarsAnimated(true), 80);
    return () => clearTimeout(timer);
  }, []);

  const totalUsersStr = useCountUp(metrics.totalUsers);
  const usersOnlineStr = useCountUp(metrics.usersOnline);
  const resumesTrackedStr = useCountUp(metrics.resumesTracked);
  const interviewsCountStr = useCountUp(metrics.interviewsCount);
  const interviewsCompletedStr = useCountUp(metrics.interviewsCompleted);
  const completionRateStr = useCountUp(metrics.completionRate, { decimals: 1 });
  const skillGapJobsStr = useCountUp(metrics.skillGapJobs);
  const skillGapSuccessStr = useCountUp(metrics.skillGapSuccessCount);
  const textModePctStr = useCountUp(metrics.textModePct);
  const voiceModePctStr = useCountUp(metrics.voiceModePct);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {/* Card 1: Total Users */}
      <div
        style={{ animationDelay: '0ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#186392]">
            <Users className="size-4.5" />
          </span>
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#1f8642]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
            <ArrowUp className="size-3" />
            {metrics.usersGrowth}
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Tổng người dùng
        </span>

        <div className="mt-1 flex h-8 items-baseline">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {totalUsersStr}
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center truncate text-xs text-[#5c4039]">
          <span>
            Online: <strong className="font-semibold text-[#006b2f]">{usersOnlineStr}</strong>
          </span>
        </div>
      </div>

      {/* Card 2: Resumes Tracked */}
      <div
        style={{ animationDelay: '70ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#186392]">
            <FileText className="size-4.5" />
          </span>
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#1f8642]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
            <ArrowUp className="size-3" />
            {metrics.resumesGrowth}
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Hồ sơ ứng tuyển
        </span>

        <div className="mt-1 flex h-8 items-baseline">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {resumesTrackedStr}
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center truncate text-xs text-[#5c4039]">
          <span>Đồng bộ phân tích CV–JD</span>
        </div>
      </div>

      {/* Card 3: Interviews Count */}
      <div
        style={{ animationDelay: '140ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#ffdbd1] text-[#ad2c00]">
            <Mic className="size-4.5" />
          </span>
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#1f8642]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
            <ArrowUp className="size-3" />
            {metrics.interviewsGrowth}
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Phiên phỏng vấn
        </span>

        <div className="mt-1 flex h-8 items-baseline">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {interviewsCountStr}
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center truncate text-xs text-[#5c4039]">
          <span>
            Hoàn thành:{' '}
            <strong className="font-semibold text-[#141b2c]">{interviewsCompletedStr}</strong>
          </span>
        </div>
      </div>

      {/* Card 4: Completion Rate */}
      <div
        style={{ animationDelay: '210ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#006b2f]">
            <BadgeCheck className="size-4.5" />
          </span>
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#1f8642]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
            <ArrowUp className="size-3" />
            {metrics.completionRateGrowth}
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Tỷ lệ hoàn thành
        </span>

        <div className="mt-1 flex h-8 items-baseline">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#006b2f] tabular-nums">
            {completionRateStr}%
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#e9edff]">
            <div
              className="h-full rounded-full bg-[#006b2f] transition-all duration-700 ease-out"
              style={{ width: barsAnimated ? `${metrics.completionRate}%` : '0%' }}
            />
          </div>
        </div>
      </div>

      {/* Card 5: Skill Gap Jobs */}
      <div
        style={{ animationDelay: '280ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#186392]">
            <Cpu className="size-4.5" />
          </span>
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#cce5ff] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#001e31]">
            <Check className="size-3" />
            {metrics.skillGapSuccessRate}
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Skill Gap Jobs
        </span>

        <div className="mt-1 flex h-8 items-baseline">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {skillGapJobsStr}
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center truncate text-xs text-[#5c4039]">
          <span>
            Thành công:{' '}
            <strong className="font-semibold text-[#006b2f]">{skillGapSuccessStr}</strong>
          </span>
        </div>
      </div>

      {/* Card 6: Text vs Voice Modes */}
      <div
        style={{ animationDelay: '350ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-9 items-center justify-between">
          <span className="flex size-9 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#141b2c]">
            <AudioWaveform className="size-4.5" />
          </span>
          <span className="rounded-full bg-[#e9edff] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#5c4039]">
            Text / Voice
          </span>
        </div>

        <span className="mt-3.5 truncate text-[11px] font-semibold uppercase tracking-wide text-[#5c4039]">
          Chế độ phỏng vấn
        </span>

        <div className="mt-1 flex h-8 items-baseline gap-1 whitespace-nowrap">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {textModePctStr}%
          </span>
          <span className="text-base font-medium text-[#907067]">/</span>
          <span className="text-2xl font-bold leading-none tracking-tight text-[#186392] tabular-nums">
            {voiceModePctStr}%
          </span>
        </div>

        <div className="mt-2.5 flex h-5 items-center">
          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[#e9edff]">
            <div
              className="h-full bg-[#141b2c] transition-all duration-700 ease-out"
              style={{ width: barsAnimated ? `${metrics.textModePct}%` : '50%' }}
              title={`Text: ${metrics.textModeCount.toLocaleString('en-US')}`}
            />
            <div
              className="h-full bg-[#186392] transition-all duration-700 ease-out"
              style={{ width: barsAnimated ? `${metrics.voiceModePct}%` : '50%' }}
              title={`Voice: ${metrics.voiceModeCount.toLocaleString('en-US')}`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
