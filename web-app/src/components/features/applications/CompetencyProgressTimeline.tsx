'use client';

import Link from 'next/link';
import { TrendingUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ProgressPoint } from '@/services/applicationProfiles';

const MIN_CHART_WIDTH = 288;

export function CompetencyProgressTimeline({ timeline }: { timeline: readonly ProgressPoint[] }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(440);
  const showChart = timeline.length >= 2;
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(MIN_CHART_WIDTH, Math.floor(entry.contentRect.width)));
    });
    observer.observe(chart);
    return () => observer.disconnect();
  }, [showChart]);

  if (!timeline.length) return null;
  const latest = timeline[timeline.length - 1];
  const first = timeline[0];
  const delta = timeline.length >= 2 ? latest.weightedReadinessPercent - first.weightedReadinessPercent : null;

  const labels = timeline.map(point => (
    point.kind === 'RECHECK' ? `KT #${point.attemptNumber}` : `Lượt ${point.attemptNumber}`
  ));
  const labelWidth = labels.reduce((widest, label) => Math.max(widest, label.length * 8), 0);
  const height = 128;
  const padX = Math.max(38, Math.ceil(labelWidth / 2) + 4);
  const padY = 22;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const lastIndex = timeline.length - 1;
  const labelStride = Math.max(1, Math.ceil((labelWidth + 16) * lastIndex / innerW));
  const coords = timeline.map((point, index) => {
    const x = lastIndex === 0 ? width / 2 : padX + (index / lastIndex) * innerW;
    const y = padY + innerH - (Math.min(100, Math.max(0, point.weightedReadinessPercent)) / 100) * innerH;
    return { x, y, point };
  });
  const polyline = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

  return (
    <section aria-label="Tiến bộ qua các lượt phỏng vấn" className="space-y-3 rounded-xl border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp size={16} className="text-brand-green" aria-hidden="true" />
          <h3 className="text-sm font-semibold">Tiến bộ mức độ sẵn sàng (có trọng số Core)</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold tabular-nums text-foreground">
            Hiện tại: {latest.weightedReadinessPercent}% ({latest.essentialCriteriaMet}/{latest.essentialCriteriaTotal} tiêu chí)
          </span>
          {delta !== null && (
            <span className={`rounded-full px-2 py-0.5 font-semibold tabular-nums ${
              delta > 0
                ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200'
                : delta < 0
                  ? 'bg-orange-100 text-orange-900 dark:bg-orange-500/20 dark:text-orange-200'
                  : 'bg-muted text-muted-foreground'
            }`}>
              {delta > 0 ? `+${delta}%` : `${delta}%`} so với lượt đầu
            </span>
          )}
        </div>
      </div>

      {showChart && (
        <div ref={chartRef} className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="block h-32 w-full"
            style={{ minWidth: MIN_CHART_WIDTH }}
            role="img"
            aria-label="Biểu đồ tiến bộ sẵn sàng qua từng lượt"
          >
            {[0, 50, 100].map(level => {
              const y = padY + innerH - (level / 100) * innerH;
              return (
                <g key={level}>
                  <line x1={padX} y1={y} x2={width - padX} y2={y} stroke="currentColor" strokeOpacity={0.12} strokeDasharray="3 3" />
                  <text x={4} y={y + 4} fontSize="11" fill="currentColor" fillOpacity={0.65}>{level}%</text>
                </g>
              );
            })}
            <polyline fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={polyline} />
            {coords.map(({ x, y, point }, index) => (
              <g key={point.sessionId}>
                <circle
                  cx={x}
                  cy={y}
                  r={point.kind === 'RECHECK' ? 4.5 : 5.5}
                  fill={point.kind === 'RECHECK' ? '#ea580c' : '#059669'}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                >
                  <title>{labels[index]} · {point.weightedReadinessPercent}%</title>
                </circle>
                {(index === 0 || index === lastIndex || (index % labelStride === 0 && lastIndex - index >= labelStride)) && (
                  <text x={x} y={height - 3} textAnchor="middle" fontSize="12" fill="currentColor" fillOpacity={0.75}>
                    {labels[index]}
                  </text>
                )}
              </g>
            ))}
          </svg>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {timeline.map(point => (
          <Link
            key={point.sessionId}
            prefetch={false}
            href={`/interview/session/${point.sessionId}/result`}
            className="inline-flex items-center gap-1.5 rounded-lg border bg-muted/30 px-2.5 py-1 text-xs transition hover:border-brand-green/50"
          >
            <span className={`size-2 rounded-full ${point.kind === 'RECHECK' ? 'bg-brand-orange' : 'bg-brand-green'}`} aria-hidden="true" />
            <span className="font-medium">
              {point.kind === 'RECHECK' ? `Kiểm chứng #${point.attemptNumber}` : `Lượt ${point.attemptNumber}`}
            </span>
            <span className="tabular-nums text-muted-foreground">{point.weightedReadinessPercent}%</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
