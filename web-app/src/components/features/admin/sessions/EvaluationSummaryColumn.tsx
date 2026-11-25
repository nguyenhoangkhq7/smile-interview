'use client';

import React from 'react';
import {
  AlertCircle,
  Award,
  Check,
  Zap,
} from 'lucide-react';
import { InspectedSessionData } from './types';

interface EvaluationSummaryColumnProps {
  session: InspectedSessionData;
}

export default function EvaluationSummaryColumn({
  session,
}: EvaluationSummaryColumnProps) {
  return (
    <div className="space-y-4 lg:col-span-4">
      {/* Single Clean Competency Evaluation Summary Card */}
      <div className="space-y-4 rounded-xl bg-white p-5 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Award className="size-5 text-[#ad2c00]" />
            <h3 className="text-base font-semibold text-[#141b2c]">Kết quả đánh giá năng lực</h3>
          </div>
          <span className="rounded-full bg-[#e9edff] px-2.5 py-0.5 font-mono text-xs font-bold text-[#006b2f]">
            4/5 Đạt chuẩn
          </span>
        </div>

        {/* Metric Distribution Bar */}
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[#e9edff]">
          <div
            className="h-full bg-[#1f8642]"
            style={{ width: '20%' }}
            title="Vượt kỳ vọng: 1"
          />
          <div
            className="h-full bg-[#006b2f]"
            style={{ width: '60%' }}
            title="Đạt chuẩn: 3"
          />
          <div
            className="h-full bg-[#ba1a1a]"
            style={{ width: '20%' }}
            title="Dưới chuẩn: 1"
          />
        </div>

        {/* 3 Demonstrated Competency Groups */}
        <div className="space-y-2.5">
          {/* Group 1: Above Target */}
          <div className="space-y-1.5 rounded-lg bg-[#f1f3ff] p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[#006b2f]">
                <span className="size-2 rounded-full bg-[#1f8642]" />
                Vượt kỳ vọng
              </span>
              <span className="font-mono text-xs font-bold text-[#006b2f]">1 kỹ năng</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <span className="flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs text-[#141b2c] shadow-2xs">
                <Zap className="size-3.5 text-[#006b2f]" />
                Go Concurrency & Channels
              </span>
            </div>
          </div>

          {/* Group 2: At Target */}
          <div className="space-y-1.5 rounded-lg bg-[#f1f3ff] p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[#006b2f]">
                <span className="size-2 rounded-full bg-[#006b2f]" />
                Đạt chuẩn yêu cầu
              </span>
              <span className="font-mono text-xs font-bold text-[#141b2c]">3 kỹ năng</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <span className="flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs text-[#141b2c] shadow-2xs">
                <Check className="size-3.5 text-[#006b2f]" />
                SQL Query Optimization
              </span>
              <span className="flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs text-[#141b2c] shadow-2xs">
                <Check className="size-3.5 text-[#006b2f]" />
                Distributed Locking (Redis)
              </span>
              <span className="flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs text-[#141b2c] shadow-2xs">
                <Check className="size-3.5 text-[#006b2f]" />
                Docker Container Lifecycle
              </span>
            </div>
          </div>

          {/* Group 3: Below Target */}
          <div className="space-y-1.5 rounded-lg bg-[#f1f3ff] p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[#ba1a1a]">
                <span className="size-2 rounded-full bg-[#ba1a1a]" />
                Dưới chuẩn yêu cầu
              </span>
              <span className="font-mono text-xs font-bold text-[#ba1a1a]">1 kỹ năng</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <span className="flex items-center gap-1 rounded bg-white px-2.5 py-1 text-xs text-[#141b2c] shadow-2xs">
                <AlertCircle className="size-3.5 text-[#ba1a1a]" />
                Raft Consensus Algorithm
              </span>
            </div>
          </div>
        </div>

        {/* Concise Session Summary Footer */}
        <div className="space-y-2 border-t border-[#e9edff] pt-3 text-xs">
          <div className="flex justify-between gap-2">
            <span className="text-[#5c4039]">Độ khớp CV–JD:</span>
            <span className="font-mono font-bold text-[#186392]">
              {session.matchingScorePct}%
            </span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-[#5c4039]">Trạng thái kết thúc:</span>
            <span className="font-semibold text-[#006b2f]">Hoàn thành kế hoạch</span>
          </div>
        </div>
      </div>
    </div>
  );
}
