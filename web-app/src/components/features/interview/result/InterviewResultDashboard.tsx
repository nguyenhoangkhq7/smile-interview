'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, BookOpen, CalendarDays, ChartNoAxesCombined, CircleCheck, Layers, MessageCircleQuestion, RotateCcw, TriangleAlert } from 'lucide-react';
import { formatProfileDate } from '@/components/features/applications/applicationUi';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { applicationProfiles } from '@/services/applicationProfiles';
import { interviewError, type EvidenceSession } from '@/services/evidenceInterview';
import type { SessionHistoryItem } from '@/services/historyService';
import { ResultFeedback, ResultQuestions, ResultSkills, ResultStudy, resultPanel, resultSection } from './ResultBreakdown';
import { buildResult, percent, resultReasons } from './resultData';
import { ResultNavigation } from './ResultNavigation';

const primary = 'rounded-full bg-[#b02700] text-white hover:bg-[#8c2100]';

function AttainmentGauge({ value, achieved, assessed }: { value: number | null; achieved: number; assessed: number }) {
  return (
    <div className="mx-auto flex w-full max-w-52 flex-col items-center gap-2 rounded-2xl border border-slate-200/70 bg-[#eef4ff] px-4 py-5 text-center">
      <div className="grid size-28 place-items-center rounded-full"
        style={{ background: `conic-gradient(#b02700 ${value ?? 0}%, #dce5f3 0)` }}>
        <div className="grid size-24 place-items-center rounded-full bg-white text-3xl font-extrabold tabular-nums">
          {value === null ? '—' : `${value}%`}
        </div>
      </div>
      <p className="text-sm font-bold">Nội dung đạt yêu cầu</p>
      <p className="text-xs text-muted-foreground">{value === null ? 'Chưa đủ cơ sở kết luận' : `${achieved}/${assessed} nội dung đã có kết luận`}</p>
    </div>
  );
}

export function InterviewResultDashboard({ session, metadata }: { session: EvidenceSession; metadata: SessionHistoryItem | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const data = buildResult(session);
  const profileId = metadata?.applicationProfileId;
  const encodedProfile = profileId && encodeURIComponent(profileId);
  const studyHref = encodedProfile ? `/practice/${encodedProfile}` : '/practice';
  const backHref = encodedProfile ? `/applications/${encodedProfile}#competency` : '/history';
  const attainment = percent(data.assessedCount ? data.achievedCount / data.assessedCount : null);
  const reason = session.report.termination_reason;
  const metrics = [
    { label: 'Kỹ năng đã phỏng vấn', value: data.skills.length, Icon: Layers, tone: 'bg-blue-50 text-blue-800' },
    { label: 'Đạt yêu cầu', value: data.skills.filter(skill => skill.status === 'strong').length, Icon: CircleCheck, tone: 'bg-emerald-50 text-emerald-800' },
    { label: 'Cần cải thiện', value: data.skills.filter(skill => skill.status === 'weak').length, Icon: TriangleAlert, tone: 'bg-orange-50 text-orange-800' },
    { label: 'Chưa đủ cơ sở kết luận', value: data.skills.filter(skill => skill.status === 'partial').length, Icon: MessageCircleQuestion, tone: 'bg-amber-50 text-amber-900' },
  ];

  async function retryInterview() {
    if (!profileId || busy) return;
    setBusy(true);
    setError('');
    try {
      const attempt = await applicationProfiles.newAttempt(profileId);
      router.push(`/interview/session/${encodeURIComponent(attempt.id)}`);
    } catch (cause) {
      setError(interviewError(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-w-0 bg-[#f4f7fc] text-slate-900">
      <ResultNavigation studyHref={studyHref} />
      <div className="mx-auto max-w-6xl space-y-6 px-4 pt-5 pb-10 sm:px-6">
        <Link href={backHref} className="inline-flex items-center gap-2 text-sm font-semibold text-[#a02707] hover:underline">
          <ArrowLeft size={16} aria-hidden="true" /> {profileId ? 'Về hồ sơ ứng tuyển' : 'Quay lại lịch sử'}
        </Link>
        <section id="overview" className={cn(resultPanel, 'scroll-mt-36 bg-gradient-to-br from-white via-white to-[#fff2ed] sm:p-7')}>
          <div className="grid items-center gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,.65fr)_minmax(0,1fr)]">
            <div className="space-y-3">
              <p className="inline-flex items-center gap-1.5 rounded-full bg-orange-100 px-2.5 py-1 text-xs font-bold text-orange-950"><ChartNoAxesCombined size={15} /> Kết quả phỏng vấn</p>
              <h1 className="text-2xl leading-tight font-extrabold tracking-tight wrap-anywhere sm:text-4xl">{metadata?.applicationProfileTitle || metadata?.roleTitle || 'Kết quả phỏng vấn'}</h1>
              {metadata?.roleTitle && metadata.roleTitle !== metadata.applicationProfileTitle && <p className="text-sm text-muted-foreground">{metadata.roleTitle}</p>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                {metadata?.attemptNumber && <span>Lượt {metadata.attemptNumber}</span>}
                {metadata?.date && <span className="inline-flex items-center gap-1"><CalendarDays size={14} /> {formatProfileDate(metadata.date, true)}</span>}
                <span>{session.turns.length} câu đã trả lời</span>
              </div>
            </div>
            <AttainmentGauge value={attainment} achieved={data.achievedCount} assessed={data.assessedCount} />
            <div className="space-y-3 rounded-xl border border-orange-100 bg-white/75 p-4">
              <h2 className="font-bold">Buổi phỏng vấn của bạn</h2>
              <p className="text-sm leading-relaxed text-slate-700">{reason ? resultReasons[reason] ?? 'Lượt phỏng vấn đã kết thúc.' : 'Lượt phỏng vấn đã kết thúc.'}</p>
              <p className="text-sm leading-relaxed text-slate-600">Bạn đã trả lời {data.questions.length} câu hỏi về {data.skills.length} kỹ năng. Kết quả chỉ phản ánh những nội dung đã phỏng vấn trong buổi này.</p>
              <Link href="#skills" className={cn(buttonVariants({ size: 'sm' }), primary)}>Xem kết quả kỹ năng <ArrowRight aria-hidden="true" /></Link>
            </div>
          </div>
        </section>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {metrics.map(({ label, value, Icon, tone }) => (
            <div key={label} className="min-w-0 rounded-xl border border-slate-200/70 bg-card p-3 shadow-xs">
              <span className={cn('mb-2 grid size-8 place-items-center rounded-lg', tone)}><Icon size={17} aria-hidden="true" /></span>
              <dt className="text-xs font-medium text-slate-600">{label}</dt>
              <dd className="mt-0.5 text-2xl font-extrabold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <ResultSkills skills={data.skills} />
        <ResultFeedback data={data} />
        <ResultQuestions questions={data.questions} />
        <ResultStudy data={data} studyHref={studyHref} />
        <section id="next" className={cn(resultPanel, resultSection, 'bg-orange-50/60')}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1"><h2 className="text-lg font-bold">Sẵn sàng cho buổi tiếp theo?</h2><p className="text-sm text-slate-600">Ôn lại phần cần cải thiện, sau đó phỏng vấn lại để theo dõi tiến bộ.</p></div>
            <div className="flex flex-wrap gap-2">
              <Link href={studyHref} className={cn(buttonVariants(), primary)}><BookOpen aria-hidden="true" />Mở kế hoạch ôn tập</Link>
              {profileId ? <Button variant="outline" disabled={busy} onClick={() => void retryInterview()}><RotateCcw aria-hidden="true" />{busy ? 'Đang tạo lượt…' : 'Phỏng vấn lượt mới'}</Button>
                : <Link href="/interview/new" className={buttonVariants({ variant: 'outline' })}><RotateCcw aria-hidden="true" />Phỏng vấn mới</Link>}
            </div>
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        </section>
      </div>
    </div>
  );
}
