'use client';

import React, { useEffect, useState } from 'react';
import { TerminationSegment } from '../types';

interface MethodTerminationCardProps {
  segments: TerminationSegment[];
}

export default function MethodTerminationCard({
  segments,
}: MethodTerminationCardProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [ringAnimated, setRingAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setRingAnimated(true), 150);
    return () => clearTimeout(timer);
  }, []);

  const activeSegment = segments.find((s) => s.id === hoveredId) ?? segments[0];
  const circumference = 88;

  const donutArcs = segments.reduce<
    {
      segment: TerminationSegment;
      dashLength: number;
      dashOffset: number;
    }[]
  >((acc, segment) => {
    const previousTotalLength = acc.reduce((sum, item) => sum + item.dashLength, 0);
    const dashLength = (segment.percentage / 100) * circumference;
    acc.push({
      segment,
      dashLength,
      dashOffset: -previousTotalLength,
    });
    return acc;
  }, []);

  return (
    <div className="flex flex-col justify-between rounded-xl bg-white p-6 shadow-xs lg:col-span-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-[#141b2c]">
          Trạng thái kết thúc phiên
        </h2>
        <p className="text-xs text-[#5c4039]">Tỷ lệ hoàn tất và nguyên nhân dừng phiên</p>
      </div>

      {/* Donut & Legend */}
      <div className="my-auto flex flex-col items-center justify-center gap-6 py-4 sm:flex-row">
        <div className="relative flex size-36 shrink-0 items-center justify-center">
          <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 36 36">
            <circle
              cx="18"
              cy="18"
              fill="transparent"
              r="14"
              stroke="#e9edff"
              strokeWidth="4.5"
            />
            {donutArcs.map(({ segment, dashLength, dashOffset }) => {
              const isHighlighted = hoveredId === segment.id;
              return (
                <circle
                  key={segment.id}
                  cx="18"
                  cy="18"
                  fill="transparent"
                  r="14"
                  stroke={segment.color}
                  strokeDasharray={`${ringAnimated ? dashLength : 0} 100`}
                  strokeDashoffset={dashOffset}
                  strokeWidth={isHighlighted ? '5.4' : '4.5'}
                  className="cursor-pointer transition-all duration-700 ease-out"
                  onMouseEnter={() => setHoveredId(segment.id)}
                  onMouseLeave={() => setHoveredId(null)}
                />
              );
            })}
          </svg>

          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
            <span className="text-[22px] font-bold leading-none text-[#141b2c] tabular-nums">
              {activeSegment ? `${activeSegment.percentage}%` : '85%'}
            </span>
            <span className="mt-1 line-clamp-1 text-[10px] font-semibold uppercase text-[#5c4039]">
              {hoveredId ? activeSegment.label : 'Hoàn tất'}
            </span>
          </div>
        </div>

        <div className="w-full flex-1 space-y-2 text-xs">
          {segments.map((seg) => {
            const isHovered = hoveredId === seg.id;
            return (
              <div
                key={seg.id}
                onMouseEnter={() => setHoveredId(seg.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`flex cursor-pointer items-center justify-between rounded-lg px-2.5 py-1.5 transition-colors ${
                  isHovered ? 'bg-[#f1f3ff]' : 'hover:bg-[#f1f3ff]/60'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className={`size-2.5 rounded-full ${seg.dotColorClass}`} />
                  <span className="font-medium text-[#141b2c]">{seg.label}</span>
                </span>
                <span className="font-mono font-semibold text-[#141b2c] tabular-nums">
                  {seg.percentage.toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
