'use client';

import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Hourglass,
  RefreshCw,
} from 'lucide-react';
import { useCountUp } from '../hooks/useCountUp';
import { QueueKpiStats } from './types';

interface QueueKpiBentoProps {
  stats: QueueKpiStats;
}

export default function QueueKpiBento({ stats }: QueueKpiBentoProps) {
  const pendingStr = useCountUp(stats.pendingCount);
  const runningStr = useCountUp(stats.runningCount);
  const succeededStr = useCountUp(stats.succeededCount);
  const failedStr = useCountUp(stats.failedCount);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Card 1: Pending */}
      <div
        style={{ animationDelay: '0ms', animationFillMode: 'both' }}
        className="animate-fade-up flex items-center justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="min-w-0 flex-1 pr-3">
          <div className="flex h-5 items-center">
            <span className="truncate text-xs font-semibold uppercase tracking-wide text-[#5c4039]">
              Đang chờ
            </span>
          </div>
          <div className="mt-1.5 flex h-9 items-baseline">
            <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
              {pendingStr}
            </span>
          </div>
        </div>

        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#f1f3ff] text-[#5c4039]">
          <Hourglass className="size-5" />
        </div>
      </div>

      {/* Card 2: Running */}
      <div
        style={{ animationDelay: '70ms', animationFillMode: 'both' }}
        className="animate-fade-up flex items-center justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="min-w-0 flex-1 pr-3">
          <div className="flex h-5 items-center gap-2">
            <span className="truncate text-xs font-semibold uppercase tracking-wide text-[#186392]">
              Đang chạy
            </span>
            <span className="relative flex size-2 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#186392] opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-[#186392]" />
            </span>
          </div>
          <div className="mt-1.5 flex h-9 items-baseline">
            <span className="text-2xl font-bold leading-none tracking-tight text-[#186392] tabular-nums">
              {runningStr}
            </span>
          </div>
        </div>

        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#cce5ff]/45 text-[#186392]">
          <RefreshCw className="size-5 animate-spin [animation-duration:6s]" />
        </div>
      </div>

      {/* Card 3: Succeeded */}
      <div
        style={{ animationDelay: '140ms', animationFillMode: 'both' }}
        className="animate-fade-up flex items-center justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="min-w-0 flex-1 pr-3">
          <div className="flex h-5 items-center">
            <span className="truncate text-xs font-semibold uppercase tracking-wide text-[#006b2f]">
              Thành công
            </span>
          </div>
          <div className="mt-1.5 flex h-9 items-baseline">
            <span className="text-2xl font-bold leading-none tracking-tight text-[#006b2f] tabular-nums">
              {succeededStr}
            </span>
          </div>
        </div>

        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#95f8a7]/35 text-[#006b2f]">
          <CheckCircle2 className="size-5" />
        </div>
      </div>

      {/* Card 4: Failed */}
      <div
        style={{ animationDelay: '210ms', animationFillMode: 'both' }}
        className="animate-fade-up flex items-center justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="min-w-0 flex-1 pr-3">
          <div className="flex h-5 items-center">
            <span className="truncate text-xs font-semibold uppercase tracking-wide text-[#ba1a1a]">
              Thất bại
            </span>
          </div>
          <div className="mt-1.5 flex h-9 items-baseline">
            <span className="text-2xl font-bold leading-none tracking-tight text-[#ba1a1a] tabular-nums">
              {failedStr}
            </span>
          </div>
        </div>

        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#ffdad6]/55 text-[#ba1a1a]">
          <AlertCircle className="size-5" />
        </div>
      </div>
    </div>
  );
}
