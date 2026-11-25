'use client';

import React, { useEffect, useState } from 'react';
import { TelemetryDataPoint } from '../types';

interface VolumeTelemetryChartProps {
  points: TelemetryDataPoint[];
  rangeLabel: string;
}

export default function VolumeTelemetryChart({
  points,
  rangeLabel,
}: VolumeTelemetryChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number>(4);
  const [chartMounted, setChartMounted] = useState<boolean>(false);

  useEffect(() => {
    const timer = setTimeout(() => setChartMounted(true), 120);
    return () => clearTimeout(timer);
  }, []);

  const activePoint = points[hoveredIdx] ?? points[points.length - 1];

  return (
    <div className="flex flex-col justify-between rounded-xl bg-white p-6 shadow-xs lg:col-span-7">
      <div className="flex flex-col justify-between gap-2 pb-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-[#141b2c]">
            Lưu lượng phân tích CV–JD & Phiên phỏng vấn
          </h2>
          <p className="text-xs text-[#5c4039]">
            Thống kê đối sánh hồ sơ và phiên hoàn thành trong {rangeLabel}
          </p>
        </div>

        <div className="flex items-center gap-4 text-[11px] font-semibold">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-xs bg-[#ad2c00]" />
            <span className="text-[#5c4039]">Khớp nối CV–JD</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-xs bg-[#186392]" />
            <span className="text-[#5c4039]">Phiên hoàn thành</span>
          </span>
        </div>
      </div>

      {/* Area Chart SVG Container with Interactive Hover Tooltip */}
      <div className="relative h-64 w-full pt-4">
        {activePoint && (
          <div
            style={{
              left: `${Math.min(Math.max((activePoint.x / 700) * 100, 12), 88)}%`,
            }}
            className="pointer-events-none absolute top-1 z-10 -translate-x-1/2 rounded-lg border border-[#e0e8ff] bg-white/95 px-3 py-1.5 text-xs shadow-md backdrop-blur-xs transition-all duration-200"
          >
            <div className="font-mono text-[11px] font-bold text-[#141b2c]">
              {activePoint.label}
            </div>
            <div className="mt-0.5 flex items-center gap-3 whitespace-nowrap">
              <span className="flex items-center gap-1 font-semibold text-[#ad2c00]">
                <span className="size-2 rounded-full bg-[#ad2c00]" />
                CV–JD: {activePoint.cvJdValue}
              </span>
              <span className="flex items-center gap-1 font-semibold text-[#186392]">
                <span className="size-2 rounded-full bg-[#186392]" />
                Hoàn thành: {activePoint.completedValue}
              </span>
            </div>
          </div>
        )}

        <svg
          className="h-full w-full overflow-visible"
          preserveAspectRatio="none"
          viewBox="0 0 700 240"
        >
          <defs>
            <linearGradient id="gradPrimary" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#ad2c00" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#ad2c00" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="gradSecondary" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#186392" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#186392" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          <line stroke="#f1f3ff" strokeWidth="1" x1="0" x2="700" y1="40" y2="40" />
          <line stroke="#f1f3ff" strokeWidth="1" x1="0" x2="700" y1="100" y2="100" />
          <line stroke="#f1f3ff" strokeWidth="1" x1="0" x2="700" y1="160" y2="160" />
          <line stroke="#e9edff" strokeWidth="1" x1="0" x2="700" y1="220" y2="220" />

          <path
            d="M 0,180 Q 70,140 140,110 T 280,70 T 420,95 T 560,45 T 700,30 L 700,220 L 0,220 Z"
            fill="url(#gradPrimary)"
            className="transition-opacity duration-700 ease-out"
            style={{ opacity: chartMounted ? 1 : 0 }}
          />
          <path
            d="M 0,180 Q 70,140 140,110 T 280,70 T 420,95 T 560,45 T 700,30"
            fill="none"
            stroke="#ad2c00"
            strokeLinecap="round"
            strokeWidth="2.5"
            strokeDasharray="1000"
            strokeDashoffset={chartMounted ? 0 : 1000}
            className="transition-all duration-1000 ease-out"
          />

          <path
            d="M 0,200 Q 70,180 140,160 T 280,130 T 420,120 T 560,90 T 700,75 L 700,220 L 0,220 Z"
            fill="url(#gradSecondary)"
            className="transition-opacity duration-700 delay-150 ease-out"
            style={{ opacity: chartMounted ? 1 : 0 }}
          />
          <path
            d="M 0,200 Q 70,180 140,160 T 280,130 T 420,120 T 560,90 T 700,75"
            fill="none"
            stroke="#186392"
            strokeDasharray="4 2"
            strokeLinecap="round"
            strokeWidth="2"
            className="transition-opacity duration-700 delay-100"
            style={{ opacity: chartMounted ? 1 : 0 }}
          />

          {activePoint && (
            <g className="transition-all duration-200">
              <line
                stroke="#907067"
                strokeDasharray="2 2"
                strokeWidth="1"
                x1={activePoint.x}
                x2={activePoint.x}
                y1="20"
                y2="220"
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.cvJdY}
                fill="#ad2c00"
                r="5"
                stroke="#ffffff"
                strokeWidth="2"
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.completedY}
                fill="#186392"
                r="5"
                stroke="#ffffff"
                strokeWidth="2"
              />
            </g>
          )}

          {points.map((pt, index) => {
            const colWidth = 700 / points.length;
            const startX = Math.max(0, pt.x - colWidth / 2);
            return (
              <rect
                key={pt.label}
                x={startX}
                y={0}
                width={colWidth}
                height={230}
                fill="transparent"
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIdx(index)}
              />
            );
          })}
        </svg>

        <div className="flex justify-between pt-2 font-mono text-xs font-medium text-[#5c4039]">
          {points.map((pt, index) => (
            <button
              key={pt.label}
              type="button"
              onMouseEnter={() => setHoveredIdx(index)}
              onClick={() => setHoveredIdx(index)}
              className={`rounded px-1.5 py-0.5 transition-colors cursor-pointer ${
                hoveredIdx === index
                  ? 'bg-[#e9edff] font-bold text-[#141b2c]'
                  : 'hover:text-[#141b2c]'
              }`}
            >
              {pt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
