'use client';

import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp, AudioWaveform, BadgeCheck, Check, Cpu, FileText, Mic, Users } from 'lucide-react';
import type { KpiMetricsData } from '../types';

const numbers = new Intl.NumberFormat('vi-VN');
const decimals = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });

function percent(value: number | null) {
  return value === null ? '—' : decimals.format(value) + '%';
}

function Trend({ value, unit = '%' }: { value: number | null; unit?: string }) {
  if (value === null) return null;
  const Icon = value < 0 ? ArrowDown : ArrowUp;
  const color = value < 0 ? 'bg-[#ffdbd1] dark:bg-orange-950 text-[#ad2c00] dark:text-orange-300' : 'bg-[#1f8642]/10 text-[#006b2f] dark:text-emerald-300';
  return (
    <span title="So với kỳ trước" className={'inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ' + color}>
      {value !== 0 && <Icon className="size-3" />}
      {value > 0 ? '+' : ''}{decimals.format(value)}{unit}
    </span>
  );
}

function KpiCard({ title, icon, badge, value, footer }: {
  title: string; icon: ReactNode; badge?: ReactNode; value: ReactNode; footer: ReactNode;
}) {
  return (
    <div className="flex flex-col rounded-xl bg-white dark:bg-card p-4 shadow-xs transition-shadow hover:shadow-md">
      <div className="flex h-9 items-center justify-between gap-1">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#f1f3ff] dark:bg-muted text-[#186392] dark:text-sky-300">
          {icon}
        </span>
        {badge}
      </div>
      <h2 className="mt-3.5 text-[11px] font-semibold uppercase tracking-wide text-[#5c4039] dark:text-muted-foreground">{title}</h2>
      <div className="mt-1 min-h-8 text-2xl font-bold leading-none text-[#141b2c] dark:text-foreground tabular-nums">{value}</div>
      <div className="mt-2.5 flex min-h-5 items-center text-xs text-[#5c4039] dark:text-muted-foreground">{footer}</div>
    </div>
  );
}

function ModeBreakdown({ text, voice }: { text: number; voice: number }) {
  const total = text + voice;
  if (total === 0) return <span>Chưa có phiên theo chế độ</span>;
  const textShare = Math.round(text * 100 / total);

  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[#e9edff] dark:bg-secondary">
      <div className="bg-[#141b2c]" style={{ width: textShare + '%' }} title={'Text: ' + numbers.format(text)} />
      <div className="bg-[#186392]" style={{ width: (100 - textShare) + '%' }} title={'Voice: ' + numbers.format(voice)} />
    </div>
  );
}

export default function KpiGrid({ metrics }: { metrics: KpiMetricsData }) {
  const modeTotal = metrics.textInterviews + metrics.voiceInterviews;
  const textShare = modeTotal === 0 ? null : Math.round(metrics.textInterviews * 100 / modeTotal);
  const voiceShare = textShare === null ? null : 100 - textShare;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard title="Người dùng" icon={<Users className="size-4.5" />} badge={<Trend value={metrics.usersGrowth} />}
        value={numbers.format(metrics.users)} footer="Tài khoản đăng ký" />
      <KpiCard title="Hồ sơ ứng tuyển" icon={<FileText className="size-4.5" />} badge={<Trend value={metrics.applicationProfilesGrowth} />}
        value={numbers.format(metrics.applicationProfiles)} footer="Hồ sơ đã lưu" />
      <KpiCard title="Phiên phỏng vấn" icon={<Mic className="size-4.5 text-[#ad2c00] dark:text-orange-300" />} badge={<Trend value={metrics.interviewsGrowth} />}
        value={numbers.format(metrics.interviews)}
        footer={<span>Hoàn thành <strong>{numbers.format(metrics.completedInterviews)}</strong></span>} />
      <KpiCard title="Tỷ lệ hoàn thành" icon={<BadgeCheck className="size-4.5 text-[#006b2f] dark:text-emerald-300" />}
        badge={<Trend value={metrics.completionRateChange} unit=" đpt" />}
        value={<span className="text-[#006b2f] dark:text-emerald-300">{percent(metrics.completionRate)}</span>}
        footer={<div className="h-1.5 w-full overflow-hidden rounded-full bg-[#e9edff] dark:bg-secondary">
          <div className="h-full rounded-full bg-[#006b2f]" style={{ width: (metrics.completionRate ?? 0) + '%' }} />
        </div>} />
      <KpiCard title="Skill Gap Jobs" icon={<Cpu className="size-4.5" />}
        badge={metrics.skillGapSuccessRate !== null && (
          <span className="inline-flex items-center gap-0.5 rounded-full bg-[#cce5ff] dark:bg-sky-950 px-2 py-0.5 text-[11px] font-semibold text-[#001e31] dark:text-sky-200">
            <Check className="size-3" />{percent(metrics.skillGapSuccessRate)}
          </span>
        )}
        value={numbers.format(metrics.skillGapJobs)}
        footer={<span>Thành công <strong className="text-[#006b2f] dark:text-emerald-300">{numbers.format(metrics.successfulSkillGapJobs)}</strong></span>} />
      <KpiCard title="Chế độ phỏng vấn" icon={<AudioWaveform className="size-4.5" />}
        badge={<span className="rounded-full bg-[#e9edff] dark:bg-secondary px-2 py-0.5 text-[11px] font-semibold text-[#5c4039] dark:text-muted-foreground">Text / Voice</span>}
        value={textShare === null ? '—' : <span className="whitespace-nowrap">{percent(textShare)} <span className="text-base text-[#907067] dark:text-muted-foreground">/</span> <span className="text-[#186392] dark:text-sky-300">{percent(voiceShare)}</span></span>}
        footer={<ModeBreakdown text={metrics.textInterviews} voice={metrics.voiceInterviews} />} />
    </div>
  );
}
