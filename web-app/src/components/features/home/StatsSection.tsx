import { IconFile, IconUsers, IconTrend, IconStar } from '@/components/ui/icons';
import type { ReactNode } from 'react';

interface StatItem {
  icon: ReactNode;
  value: string;
  label: string;
  accent: 'orange' | 'green';
}

const STATS: StatItem[] = [
  { icon: <IconFile size={22} />, value: '10,000+', label: 'CV đã phân tích', accent: 'orange' },
  { icon: <IconUsers size={22} />, value: '2,500+', label: 'Người dùng tin tưởng', accent: 'green' },
  { icon: <IconTrend size={22} />, value: '87%', label: 'Cải thiện sau 3 buổi', accent: 'orange' },
  { icon: <IconStar size={22} />, value: '4.9 ★', label: 'Đánh giá trung bình', accent: 'green' },
];

export function StatsSection() {
  return (
    <section className="border-y border-border bg-card/60 py-14">
      <div className="mx-auto max-w-5xl px-6">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {STATS.map(({ icon, value, label, accent }) => (
            <div key={label} className="flex flex-col items-center gap-2 text-center">
              <span className={accent === 'orange' ? 'text-brand-orange' : 'text-brand-green'}>
                {icon}
              </span>
              <span className={`text-2xl font-extrabold ${accent === 'orange' ? 'text-brand-orange' : 'text-brand-green'}`}>
                {value}
              </span>
              <span className="text-xs font-medium text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
