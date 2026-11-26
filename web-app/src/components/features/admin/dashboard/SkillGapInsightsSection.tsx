import type { ReactNode } from 'react';
import { Brain, Briefcase } from 'lucide-react';
import type { KnowledgeGapItem, PopularRoleItem } from '../types';

const numbers = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });
const gapColors = ['#ad2c00', '#d83900', '#186392', '#5088b7', '#68728a'];

function InsightsCard({ title, subtitle, icon, className, children }: {
  title: string; subtitle: string; icon: ReactNode; className: string; children: ReactNode;
}) {
  return (
    <section className={'rounded-xl bg-white dark:bg-card p-6 shadow-xs ' + className}>
      <div className="flex items-start justify-between gap-2 pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-[#141b2c] dark:text-foreground">{title}</h2>
          <p className="text-xs text-[#5c4039] dark:text-muted-foreground">{subtitle}</p>
        </div>
        <span className="rounded-lg bg-[#f1f3ff] dark:bg-muted p-2">{icon}</span>
      </div>
      {children}
    </section>
  );
}

function KnowledgeGaps({ gaps }: { gaps: KnowledgeGapItem[] }) {
  if (!gaps.length) return <p className="text-sm text-[#5c4039] dark:text-muted-foreground">Chưa ghi nhận lỗ hổng trong kỳ này.</p>;
  return (
    <ol className="space-y-3.5">
      {gaps.map((gap, index) => {
        const color = gapColors[index % gapColors.length];
        return (
          <li key={gap.title + ':' + index}>
            <div className="mb-1.5 flex items-start justify-between gap-2 text-xs font-medium">
              <span className="flex items-start gap-2">
                <strong className="font-mono" style={{ color }}>#{index + 1}</strong>
                {gap.title}
              </span>
              <span className="shrink-0 font-mono tabular-nums">
                <strong>{numbers.format(gap.percentage)}%</strong> ({numbers.format(gap.candidates)})
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[#e9edff] dark:bg-secondary" aria-hidden="true">
              <div className="h-full rounded-full" style={{ width: gap.percentage + '%', backgroundColor: color }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function PopularRoles({ roles }: { roles: PopularRoleItem[] }) {
  if (!roles.length) return <p className="text-sm text-[#5c4039] dark:text-muted-foreground">Chưa có vị trí phỏng vấn trong kỳ này.</p>;
  return (
    <ul className="space-y-1.5">
      {roles.map((role) => (
        <li key={role.title} className="flex items-center justify-between gap-2 rounded-lg p-2">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-[#e0e8ff] dark:bg-secondary font-mono text-xs font-bold text-[#186392] dark:text-sky-300" aria-hidden="true">
              {role.title.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join('').toUpperCase()}
            </span>
            <span className="break-words text-sm font-semibold text-[#141b2c] dark:text-foreground">{role.title}</span>
          </div>
          <div className="shrink-0 text-right text-sm">
            <strong>{numbers.format(role.interviews)}</strong>
            {role.growth !== null && (
              <div className={role.growth < 0 ? 'text-[11px] text-[#ad2c00] dark:text-orange-300' : 'text-[11px] text-[#006b2f] dark:text-emerald-300'} title="So với kỳ trước">
                {role.growth > 0 ? '+' : ''}{numbers.format(role.growth)}%
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function SkillGapInsightsSection({ knowledgeGaps, popularRoles }: {
  knowledgeGaps: KnowledgeGapItem[]; popularRoles: PopularRoleItem[];
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <InsightsCard title="Top 5 lỗ hổng kiến thức phổ biến"
        subtitle="Tỷ lệ ứng viên có lỗ hổng trong kết quả đối sánh CV–JD hoặc phỏng vấn"
        icon={<Brain className="size-4.5 text-[#ad2c00] dark:text-orange-300" />} className="lg:col-span-7">
        <KnowledgeGaps gaps={knowledgeGaps} />
      </InsightsCard>
      <InsightsCard title="Vị trí phỏng vấn phổ biến" subtitle="Xếp theo số phiên của từng vị trí"
        icon={<Briefcase className="size-4.5 text-[#186392] dark:text-sky-300" />} className="lg:col-span-5">
        <PopularRoles roles={popularRoles} />
      </InsightsCard>
    </div>
  );
}
