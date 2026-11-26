'use client';

import { useState } from 'react';
import type { DistributionItem } from '../types';

const LEVELS: Record<string, { title: string; color: string }> = {
  DEMONSTRATED_ABOVE_TARGET: { title: 'Vượt kỳ vọng', color: '#006b2f' },
  DEMONSTRATED_AT_TARGET: { title: 'Đạt chuẩn yêu cầu', color: '#186392' },
  DEMONSTRATED_BELOW_TARGET: { title: 'Dưới chuẩn yêu cầu', color: '#a65800' },
  NOT_DEMONSTRATED: { title: 'Chưa thể hiện được', color: '#ba1a1a' },
  INSUFFICIENT_EVIDENCE: { title: 'Chưa đủ bằng chứng', color: '#765a52' },
  NOT_ASSESSED: { title: 'Chưa được đánh giá', color: '#68728a' },
};
const numbers = new Intl.NumberFormat('vi-VN');
const percentages = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export default function AiEvaluationV2Section({ levels }: { levels: DistributionItem[] }) {
  const [active, setActive] = useState<string | null>(null);
  const total = levels.reduce((sum, level) => sum + level.count, 0);
  const visible = levels.filter((level) => LEVELS[level.code]);

  return (
    <section className="rounded-xl bg-white dark:bg-card p-6 shadow-xs">
      <h2 className="text-lg font-semibold tracking-tight text-[#141b2c] dark:text-foreground">Phân bố kết quả đánh giá năng lực AI</h2>
      <p className="text-xs text-[#5c4039] dark:text-muted-foreground">Thống kê mức năng lực theo từng mục tiêu trong báo cáo phỏng vấn</p>
      {total === 0 ? (
        <p className="mt-6 text-sm text-[#5c4039] dark:text-muted-foreground">Chưa có báo cáo đánh giá trong kỳ này.</p>
      ) : (
        <>
          <div className="mb-4 mt-4 flex h-3.5 overflow-hidden rounded-full bg-[#e9edff] dark:bg-secondary" aria-hidden="true">
            {visible.map((level) => (
              <span key={level.code} title={LEVELS[level.code].title}
                className={active && active !== level.code ? 'opacity-40' : ''}
                style={{ width: level.count * 100 / total + '%', backgroundColor: LEVELS[level.code].color }} />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            {visible.map((level) => {
              const display = LEVELS[level.code];
              return (
                <div key={level.code} onMouseEnter={() => setActive(level.code)} onMouseLeave={() => setActive(null)}
                  className="min-w-0 rounded-xl bg-[#f4f5ff] dark:bg-muted p-3 text-xs">
                  <div className="flex flex-wrap items-start justify-between gap-1 font-semibold">
                    <span>{display.title}</span>
                    <span style={{ color: display.color }}>{percentages.format(level.percentage)}%</span>
                  </div>
                  <div className="mt-2 text-[#5c4039] dark:text-muted-foreground">{numbers.format(level.count)} mục tiêu</div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-[#e9edff] dark:bg-secondary" aria-hidden="true">
                    <div className="h-full rounded-full" style={{ width: level.percentage + '%', backgroundColor: display.color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
