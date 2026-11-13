import Link from 'next/link';
import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  FileText,
} from 'lucide-react';
import { formatProfileDate } from '@/components/features/applications/applicationUi';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PracticePlan } from './practicePlans';
import { formatStudyPercent } from './studyPlan';

interface PlanHeadingProps {
  plan: PracticePlan;
}

function PlanHeading({ plan }: PlanHeadingProps) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-(--practice-orange) text-(--practice-primary)">
        <BriefcaseBusiness size={21} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <h2 className="text-base font-bold leading-snug [overflow-wrap:anywhere]">{plan.title}</h2>
        <p className={cn('mt-1 flex items-center gap-1 text-xs text-(--practice-muted)', !plan.company && 'italic')}>
          <Building2 size={13} className="shrink-0" aria-hidden="true" />
          {plan.company ?? 'Chưa thêm công ty'}
        </p>
      </div>
    </div>
  );
}

interface PlanDocumentsProps {
  plan: PracticePlan;
}

function PlanDocuments({ plan }: PlanDocumentsProps) {
  return (
    <div className="inline-flex max-w-full w-fit items-center gap-1.5 rounded-md bg-(--practice-pale) px-2.5 py-1 text-xs text-(--practice-muted)">
      <FileText size={14} className="shrink-0 text-(--practice-primary)" aria-hidden="true" />
      <span className="[overflow-wrap:anywhere]">{plan.cvFilename}</span>
    </div>
  );
}

export interface PracticePlanCardProps {
  plan: PracticePlan;
}

export function PracticePlanCard({ plan }: PracticePlanCardProps) {
  return (
    <article className="flex min-w-0 flex-col gap-4 rounded-2xl border border-slate-100 bg-card p-5 shadow-xs sm:p-6">
      <PlanHeading plan={plan} />
      <PlanDocuments plan={plan} />
      <p className="flex flex-wrap items-center justify-between gap-2 text-xs text-(--practice-muted)">
        <span>Tiến độ ôn tập</span>
        <span>{plan.progress?.percent != null
          ? `${formatStudyPercent(plan.progress.percent)} · ${plan.progress.done}/${plan.progress.total} đầu việc`
          : { loading: 'Đang tải…', ready: 'Chưa theo dõi', error: 'Chưa tải được' }[plan.progressStatus]}</span>
      </p>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-2">
        <span className="flex items-center gap-1.5 text-xs text-(--practice-muted)">
          <CalendarDays size={14} aria-hidden="true" />
          Tạo {formatProfileDate(plan.createdAt)}
        </span>
        <Link
          href={`/practice/${plan.id}`}
          aria-label={`Mở kế hoạch ôn tập: ${plan.title}`}
          className={cn(buttonVariants(), 'h-9 rounded-full bg-(--practice-primary) px-4 font-semibold hover:bg-(--practice-primary-hover)')}
        >
          Mở kế hoạch ôn tập <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}

