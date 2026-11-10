import { useMemo } from 'react';
import Link from 'next/link';
import { CheckCircle2, ClipboardList, FolderOpen, Mic } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PracticePlan } from './practicePlans';

export function PracticeHeading() {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Kế hoạch ôn tập</h1>
        <p className="max-w-xl text-sm leading-6 text-(--practice-muted) sm:text-base">
          Xem kế hoạch ôn tập theo từng hồ sơ ứng tuyển bạn đã tạo.
        </p>
      </div>
      <Link
        href="/applications"
        className={cn(buttonVariants({ variant: 'outline' }), 'h-10 self-start rounded-full bg-card px-4 shadow-xs md:self-end')}
      >
        <FolderOpen size={18} className="text-(--practice-primary)" aria-hidden="true" />
        Xem hồ sơ ứng tuyển
      </Link>
    </div>
  );
}

export interface PracticeStatsProps {
  plans: readonly PracticePlan[];
}

export function PracticeStats({ plans }: PracticeStatsProps) {
  const metrics = useMemo(() => {
    const assessed = plans.filter((plan) => plan.status === 'has-result').length;
    const interviewCount = plans.reduce((sum, plan) => sum + plan.interviewCount, 0);

    return [
      {
        label: 'Tổng số hồ sơ ôn tập',
        value: plans.length,
        hint: 'hồ sơ liên kết',
        Icon: ClipboardList,
        tone: 'bg-(--practice-orange) text-(--practice-primary)',
      },
      {
        label: 'Hồ sơ đã có kết quả',
        value: assessed,
        hint: 'hồ sơ',
        Icon: CheckCircle2,
        tone: 'bg-(--practice-green-bg) text-(--practice-green)',
      },
      {
        label: 'Lượt phỏng vấn',
        value: interviewCount,
        hint: 'lượt đã tạo',
        Icon: Mic,
        tone: 'bg-(--practice-blue) text-(--practice-muted)',
      },
    ];
  }, [plans]);

  return (
    <dl aria-label="Tổng quan ôn tập" className="grid gap-3 sm:grid-cols-3 sm:gap-4">
      {metrics.map(({ label, value, hint, Icon, tone }) => (
        <div key={label} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-card p-4 shadow-xs sm:p-5">
          <span className={cn('grid size-11 shrink-0 place-items-center rounded-xl', tone)}>
            <Icon size={21} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <dt className="text-xs font-semibold uppercase tracking-wide text-(--practice-muted)">{label}</dt>
            <dd className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-2xl font-bold tabular-nums">{value}</span>
              <span className="text-xs text-(--practice-muted)">{hint}</span>
            </dd>
          </div>
        </div>
      ))}
    </dl>
  );
}
