'use client';

import { useState } from 'react';
import type { DistributionItem } from '../types';

const REASONS: Record<string, { label: string; color: string }> = {
  PLAN_COMPLETE: { label: 'Hoàn thành kế hoạch', color: '#1c7e3b' },
  USER_STOP: { label: 'Người dùng dừng sớm', color: '#ad2c00' },
  QUESTION_BUDGET: { label: 'Hết lượt câu hỏi', color: '#186392' },
  TIME_BUDGET: { label: 'Hết thời gian', color: '#907067' },
  OTHER: { label: 'Khác hoặc chưa rõ', color: '#68728a' },
};

const CIRCUMFERENCE = 2 * Math.PI * 14;
const formats = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export default function MethodTerminationCard({ segments }: { segments: DistributionItem[] }) {
  const [focusedCode, setFocusedCode] = useState<string | null>(null);
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  const visible = segments.filter((segment) => REASONS[segment.code] && (segment.count > 0 || segment.code !== 'OTHER'));
  const active = visible.find((segment) => segment.code === (focusedCode ?? 'PLAN_COMPLETE'));
  let drawn = 0;
  const arcs = visible.filter((segment) => segment.count > 0).map((segment) => {
    const length = segment.count * CIRCUMFERENCE / total;
    const offset = -drawn;
    drawn += length;
    return { segment, length, offset };
  });

  return (
    <section className="flex flex-col rounded-xl bg-white dark:bg-card p-6 shadow-xs lg:col-span-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-[#141b2c] dark:text-foreground">Trạng thái kết thúc phiên</h2>
        <p className="text-xs text-[#5c4039] dark:text-muted-foreground">Phân bố lý do kết thúc trong các phiên đã kết thúc</p>
      </div>
      {total === 0 ? (
        <p className="my-auto py-10 text-center text-sm text-[#5c4039] dark:text-muted-foreground">Chưa có phiên kết thúc trong kỳ này.</p>
      ) : (
        <div className="my-auto flex flex-col items-center gap-6 py-4 sm:flex-row lg:flex-col xl:flex-row">
          <div className="relative flex size-36 shrink-0 items-center justify-center">
            <svg className="size-full -rotate-90" viewBox="0 0 36 36" aria-hidden="true">
              <circle cx="18" cy="18" r="14" fill="none" stroke="#e9edff" strokeWidth="4.5" />
              {arcs.map(({ segment, length, offset }) => (
                <circle key={segment.code} cx="18" cy="18" r="14" fill="none"
                  stroke={REASONS[segment.code].color} strokeWidth={focusedCode === segment.code ? 5.4 : 4.5}
                  strokeDasharray={length + ' ' + CIRCUMFERENCE} strokeDashoffset={offset} />
              ))}
            </svg>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-5 text-center">
              <span className="text-xl font-bold text-[#141b2c] dark:text-foreground tabular-nums">{formats.format(active?.percentage ?? 0)}%</span>
              <span className="text-[10px] font-semibold text-[#5c4039] dark:text-muted-foreground">
                {active ? REASONS[active.code].label : 'Hoàn thành kế hoạch'}
              </span>
            </div>
          </div>
          <div className="w-full flex-1 space-y-1">
            {visible.map((segment) => (
              <button type="button" key={segment.code}
                className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-[#f1f3ff] dark:hover:bg-muted focus:bg-[#f1f3ff] dark:focus:bg-muted"
                onMouseEnter={() => setFocusedCode(segment.code)} onMouseLeave={() => setFocusedCode(null)}
                onFocus={() => setFocusedCode(segment.code)} onBlur={() => setFocusedCode(null)}
                onClick={() => setFocusedCode(segment.code)}>
                <span className="flex items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: REASONS[segment.code].color }} />
                  {REASONS[segment.code].label}
                </span>
                <strong className="font-mono tabular-nums">{formats.format(segment.percentage)}%</strong>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
