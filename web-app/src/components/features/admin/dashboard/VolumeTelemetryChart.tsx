'use client';

import { useState } from 'react';
import type { TelemetryDataPoint } from '../types';

const WIDTH = 700;
const BASELINE = 220;
const dates = new Intl.DateTimeFormat('vi-VN', { day: 'numeric', month: 'numeric', timeZone: 'UTC' });
const detailedDates = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeZone: 'UTC' });
const count = new Intl.NumberFormat('vi-VN');

function formatDate(day: string, formatter = dates) {
  return formatter.format(new Date(day + 'T00:00:00Z'));
}

interface ChartPoint {
  x: number;
  analysesY: number;
  completedY: number;
}

function line(points: ChartPoint[], key: 'analysesY' | 'completedY') {
  return points.map((point, index) => {
    if (index === 0) return ['M', point.x, point[key]].join(' ');
    const previous = points[index - 1];
    const middleX = (point.x + previous.x) / 2;
    return ['C', middleX, previous[key], middleX, point[key], point.x, point[key]].join(' ');
  }).join(' ');
}

function Series({ points, dataKey, color, gradient }: {
  points: ChartPoint[]; dataKey: 'analysesY' | 'completedY'; color: string; gradient: string;
}) {
  if (!points.length) return null;
  const path = line(points, dataKey);
  const area = path + ' L ' + points[points.length - 1].x + ' ' + BASELINE + ' L ' + points[0].x + ' ' + BASELINE + ' Z';

  return (
    <>
      <path d={area} fill={'url(#' + gradient + ')'} />
      <path d={path} fill="none" stroke={color} strokeLinecap="round" strokeWidth="2.5" />
    </>
  );
}

export default function VolumeTelemetryChart({ points, rangeLabel }: {
  points: TelemetryDataPoint[]; rangeLabel: string;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((point) => Math.max(point.analyses, point.completedInterviews)));
  const chart = points.map((point, index) => ({
    x: points.length === 1 ? WIDTH / 2 : index * WIDTH / (points.length - 1),
    analysesY: BASELINE - point.analyses * 170 / max,
    completedY: BASELINE - point.completedInterviews * 170 / max,
  }));
  const active = activeIndex === null ? undefined : chart[activeIndex];
  const data = activeIndex === null ? undefined : points[activeIndex];
  const hasActivity = points.some((point) => point.analyses > 0 || point.completedInterviews > 0);

  return (
    <section className="rounded-xl bg-white dark:bg-card p-6 shadow-xs lg:col-span-7">
      <h2 className="text-lg font-semibold tracking-tight text-[#141b2c] dark:text-foreground">Lưu lượng phân tích CV–JD & Phiên phỏng vấn</h2>
      <p className="text-xs text-[#5c4039] dark:text-muted-foreground">
        {rangeLabel === 'toàn thời gian' ? 'Toàn thời gian' : rangeLabel + ' gần nhất'}. Phân tích thành công tính theo ngày tiếp nhận.
      </p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-semibold text-[#5c4039] dark:text-muted-foreground">
        <span><span className="mr-1.5 inline-block size-2.5 rounded-xs bg-[#ad2c00]" />Phân tích thành công</span>
        <span><span className="mr-1.5 inline-block size-2.5 rounded-xs bg-[#186392]" />Phiên hoàn thành</span>
      </div>
      {!hasActivity ? (
        <p className="grid h-56 place-content-center text-center text-sm text-[#5c4039] dark:text-muted-foreground">Chưa có hoạt động trong kỳ này.</p>
      ) : (
        <>
          <div className="relative mt-3 h-56">
            {active && data && (
              <div className="pointer-events-none absolute top-1 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-white dark:bg-card px-3 py-1.5 text-xs shadow-md"
                style={{ left: Math.min(84, Math.max(16, active.x * 100 / WIDTH)) + '%' }}>
                <strong>{formatDate(data.from, detailedDates)}{data.from !== data.through && ' – ' + formatDate(data.through, detailedDates)}</strong>
                <div>CV–JD {count.format(data.analyses)} · Phiên {count.format(data.completedInterviews)}</div>
              </div>
            )}
            <svg className="h-full w-full" viewBox="0 0 700 240" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="admin-overview-analyses" x1="0" x2="0" y1="0" y2="1" gradientUnits="objectBoundingBox">
                  <stop offset="0%" stopColor="#ad2c00" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#ad2c00" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="admin-overview-interviews" x1="0" x2="0" y1="0" y2="1" gradientUnits="objectBoundingBox">
                  <stop offset="0%" stopColor="#186392" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#186392" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[40, 100, 160, BASELINE].map((y) => <line key={y} stroke="#e9edff" x1="0" x2={WIDTH} y1={y} y2={y} />)}
              <Series points={chart} dataKey="analysesY" color="#ad2c00" gradient="admin-overview-analyses" />
              <Series points={chart} dataKey="completedY" color="#186392" gradient="admin-overview-interviews" />
              {active && <line stroke="#907067" strokeDasharray="3 3" x1={active.x} x2={active.x} y1="30" y2={BASELINE} />}
              {chart.map((point, index) => (
                <g key={points[index].from}>
                  <circle cx={point.x} cy={point.analysesY} r="4" fill="#ad2c00" />
                  <circle cx={point.x} cy={point.completedY} r="4" fill="#186392" />
                </g>
              ))}
            </svg>
            <div className="absolute inset-0 flex" aria-hidden="true" onMouseLeave={() => setActiveIndex(null)}>
              {points.map((point, index) => <div key={point.from} className="flex-1" onMouseEnter={() => setActiveIndex(index)} />)}
            </div>
          </div>
          <div className="flex justify-between gap-1">
            {points.map((point, index) => (
              <button type="button" key={point.from} className="rounded px-1 py-0.5 text-[11px] text-[#5c4039] dark:text-muted-foreground hover:bg-[#e9edff] dark:hover:bg-secondary focus:bg-[#e9edff] dark:focus:bg-secondary"
                aria-label={formatDate(point.from, detailedDates) + ' đến ' + formatDate(point.through, detailedDates) + ', phân tích ' + count.format(point.analyses) + ', phiên hoàn thành ' + count.format(point.completedInterviews)}
                onFocus={() => setActiveIndex(index)} onBlur={() => setActiveIndex(null)} onClick={() => setActiveIndex(index)}>
                {formatDate(point.through)}
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
