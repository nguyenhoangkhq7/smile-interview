'use client';

import React, { useEffect, useState } from 'react';
import { AiEvalLevelItem } from '../types';

interface AiEvaluationV2SectionProps {
  levels: AiEvalLevelItem[];
}

export default function AiEvaluationV2Section({
  levels,
}: AiEvaluationV2SectionProps) {
  const [animated, setAnimated] = useState(false);
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 200);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="space-y-4 rounded-xl bg-white p-6 shadow-xs">
      {/* Header */}
      <div className="space-y-0.5">
        <h2 className="text-lg font-semibold tracking-tight text-[#141b2c]">
          Phân bổ kết quả đánh giá năng lực AI
        </h2>
        <p className="text-xs text-[#5c4039]">
          Thống kê 6 mức độ chuẩn hóa năng lực dựa trên bằng chứng phỏng vấn
        </p>
      </div>

      {/* Cumulative Stacked Ribbon */}
      <div className="flex h-3.5 w-full overflow-hidden rounded-full bg-[#e9edff] shadow-inner">
        {levels.map((level) => {
          const isHovered = hoveredCode === level.code;
          return (
            <div
              key={level.code}
              onMouseEnter={() => setHoveredCode(level.code)}
              onMouseLeave={() => setHoveredCode(null)}
              className={`${level.ribbonColorClass} h-full cursor-pointer transition-all duration-700 ease-out ${
                isHovered ? 'brightness-110' : ''
              }`}
              style={{ width: animated ? `${level.percentage}%` : '0%' }}
              title={`${level.title}: ${level.percentage}%`}
            />
          );
        })}
      </div>

      {/* 6 Compact Level Cards Grid */}
      <div className="grid grid-cols-2 gap-3 pt-1 md:grid-cols-3 lg:grid-cols-6">
        {levels.map((level) => {
          const isHighlighted = hoveredCode === level.code;
          return (
            <div
              key={level.code}
              onMouseEnter={() => setHoveredCode(level.code)}
              onMouseLeave={() => setHoveredCode(null)}
              className={`flex flex-col justify-between rounded-xl p-3.5 transition-all duration-200 ${
                isHighlighted
                  ? 'bg-[#e9edff] ring-1 ring-[#186392]/25 shadow-2xs'
                  : 'bg-[#f1f3ff]/60 hover:bg-[#f1f3ff]'
              }`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="truncate text-xs font-semibold text-[#141b2c]">
                  {level.title}
                </span>
                <span className={`font-mono text-xs font-bold ${level.percentTextClass}`}>
                  {level.percentage.toFixed(1)}%
                </span>
              </div>

              <div className="mt-1.5 text-[11px] text-[#5c4039] tabular-nums">
                {level.evaluationsCount.toLocaleString('en-US')} lượt
              </div>

              <div className="mt-2.5 h-1 w-full overflow-hidden rounded-full bg-[#e9edff]">
                <div
                  className={`${level.barColorClass} h-full rounded-full transition-all duration-700 ease-out`}
                  style={{ width: animated ? `${level.percentage}%` : '0%' }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
