import Link from 'next/link';
import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  FileText,
  Info,
  ListChecks,
  Mic,
} from 'lucide-react';
import { formatProfileDate } from '@/components/features/applications/applicationUi';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { practiceStatuses, type PracticePlan, type PracticeStatus } from './practicePlans';
import { formatStudyPercent } from './studyPlan';

const statusTones: Record<PracticeStatus, string> = {
  'no-result': 'bg-(--practice-blue) text-(--practice-muted)',
  'has-result': 'bg-(--practice-green-bg) text-(--practice-green)',
};

interface PlanHeadingProps {
  plan: PracticePlan;
}

function PlanHeading({ plan }: PlanHeadingProps) {
  const status = practiceStatuses.find(({ value }) => value === plan.status)?.label;

  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
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
      <span className={cn('rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide', statusTones[plan.status])}>
        {status}
      </span>
    </div>
  );
}

interface PlanDocumentsProps {
  plan: PracticePlan;
}

function PlanDocuments({ plan }: PlanDocumentsProps) {
  const items = [
    { Icon: FileText, text: plan.cvFilename, tone: 'text-(--practice-primary)' },
    { Icon: ListChecks, text: `${plan.skillCount} kỹ năng theo JD`, tone: '' },
    { Icon: Mic, text: `${plan.interviewCount} lượt phỏng vấn`, tone: '' },
  ];

  return (
    <ul aria-label="Thông tin hồ sơ" className="flex flex-wrap gap-1.5">
      {items.map(({ Icon, text, tone }) => (
        <li key={text} className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-(--practice-pale) px-2 py-1 text-xs text-(--practice-muted)">
          <Icon size={14} className={cn('shrink-0', tone)} aria-hidden="true" />
          <span className="[overflow-wrap:anywhere]">{text}</span>
        </li>
      ))}
    </ul>
  );
}

interface InterviewSummaryProps {
  plan: PracticePlan;
}

function InterviewSummary({ plan }: InterviewSummaryProps) {
  const hasResult = plan.status === 'has-result';

  return (
    <section className="space-y-2 rounded-xl bg-(--practice-pale) p-3 sm:p-4">
      <h3 className="text-[11px] font-bold uppercase tracking-wide text-(--practice-muted)">Đánh giá phỏng vấn</h3>
      <div className="flex items-center gap-2.5 rounded-lg bg-card p-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-(--practice-blue) text-(--practice-muted)">
          <Info size={15} aria-hidden="true" />
        </span>
        <div className="space-y-0.5">
          <p className="text-xs font-semibold">
            {hasResult ? 'Đã có kết quả phỏng vấn' : 'Chưa có dữ liệu đánh giá'}
          </p>
          {hasResult ? (
            <Link href={`/applications/${plan.id}#competency`} className="text-xs text-(--practice-primary) hover:underline">
              Xem đánh giá trong hồ sơ ứng tuyển
            </Link>
          ) : (
            <p className="text-xs leading-5 text-(--practice-muted)">Kết quả sẽ có sau khi bạn hoàn thành một lượt phỏng vấn có câu trả lời.</p>
          )}
        </div>
      </div>
    </section>
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
      <InterviewSummary plan={plan} />
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
