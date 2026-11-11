'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, BookOpen, CalendarDays, ChartNoAxesCombined, CircleCheck, ClipboardList, Gauge, Layers, RotateCcw, Target, TriangleAlert } from 'lucide-react';
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

function AttainmentGauge({ value }: { value: number | null }) {
  return (
    <div className="mx-auto flex w-full max-w-52 flex-col items-center gap-2 rounded-2xl border border-slate-200/70 bg-[#eef4ff] px-4 py-5 text-center">
      <div className="grid size-28 place-items-center rounded-full"
        style={{ background: `conic-gradient(#b02700 ${value ?? 0}%, #dce5f3 0)` }}>
        <div className="grid size-24 place-items-center rounded-full bg-white text-3xl font-extrabold tabular-nums">
          {value === null ? '—' : `${value}%`}
        </div>
      </div>
      <p className="text-sm font-bold">Tỷ lệ đạt mục tiêu</p>
      <p className="text-xs text-muted-foreground">{value === null ? 'Chưa đủ dữ liệu' : 'Trong các mục tiêu đã được đánh giá'}</p>
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
  const attainment = percent(session.report.target_attainment);
  const coverage = percent(session.report.evidence_coverage);
  const reason = session.report.termination_reason;
  const metrics = [
    { label: 'Bao phủ bằng chứng', value: coverage === null ? '—' : `${coverage}%`, Icon: Gauge, tone: 'bg-blue-50 text-blue-800' },
    { label: 'Kỹ năng đã kiểm tra', value: data.skills.filter(skill => skill.checked > 0).length, Icon: Layers, tone: 'bg-violet-50 text-violet-800' },
    { label: 'Kỹ năng cần cải thiện', value: data.skills.filter(skill => skill.status === 'weak').length, Icon: TriangleAlert, tone: 'bg-orange-50 text-orange-800' },
    { label: 'Kỹ năng chưa kiểm tra', value: data.skills.filter(skill => skill.status === 'unchecked').length, Icon: Target, tone: 'bg-amber-50 text-amber-900' },
    { label: 'Câu có bằng chứng đạt', value: data.questions.filter(question => question.status === 'strong').length, Icon: CircleCheck, tone: 'bg-emerald-50 text-emerald-800' },
    { label: 'Câu cần cải thiện', value: data.questions.filter(question => question.status === 'weak').length, Icon: ClipboardList, tone: 'bg-rose-50 text-rose-800' },
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
      <div className="mx-auto max-w-7xl space-y-7 px-4 pt-5 pb-10 sm:px-6">
        <Link href={backHref} className="inline-flex items-center gap-2 text-sm font-semibold text-[#a02707] hover:underline">
          <ArrowLeft size={16} aria-hidden="true" /> {profileId ? 'Về hồ sơ ứng tuyển' : 'Quay lại lịch sử'}
        </Link>
        <section id="overview" className={cn(resultPanel, 'scroll-mt-36 bg-gradient-to-br from-white via-white to-[#fff2ed] sm:p-7')}>
          <div className="grid items-center gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,.65fr)_minmax(0,1fr)]">
            <div className="space-y-3">
              <p className="inline-flex items-center gap-1.5 rounded-full bg-orange-100 px-2.5 py-1 text-xs font-bold text-orange-950"><ChartNoAxesCombined size={15} /> Kết quả phỏng vấn theo bằng chứng</p>
              <h1 className="text-2xl leading-tight font-extrabold tracking-tight wrap-anywhere sm:text-4xl">{metadata?.applicationProfileTitle || metadata?.roleTitle || 'Kết quả phỏng vấn'}</h1>
              {metadata?.roleTitle && metadata.roleTitle !== metadata.applicationProfileTitle && <p className="text-sm text-muted-foreground">{metadata.roleTitle}</p>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                {metadata?.attemptNumber && <span>Lượt {metadata.attemptNumber}</span>}
                {metadata?.date && <span className="inline-flex items-center gap-1"><CalendarDays size={14} /> {formatProfileDate(metadata.date, true)}</span>}
                <span>{session.turns.length} câu đã trả lời</span>
              </div>
            </div>
            <AttainmentGauge value={attainment} />
            <div className="space-y-3 rounded-xl border border-orange-100 bg-white/75 p-4">
              <h2 className="font-bold">Tổng kết phiên</h2>
              <p className="text-sm leading-relaxed text-slate-700">{reason ? resultReasons[reason] ?? reason : 'Lượt phỏng vấn đã kết thúc.'}</p>
              <p className="text-sm text-slate-600">Độ bao phủ bằng chứng {coverage === null ? 'chưa xác định' : `${coverage}%`}. Kết luận áp dụng cho phần đã kiểm tra.</p>
              <Link href="#feedback" className={cn(buttonVariants({ size: 'sm' }), primary)}>Xem nhận xét AI <ArrowRight aria-hidden="true" /></Link>
            </div>
          </div>
        </section>
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {metrics.map(({ label, value, Icon, tone }) => (
            <div key={label} className="min-w-0 rounded-xl border border-slate-200/70 bg-card p-3 shadow-xs">
              <span className={cn('mb-2 grid size-8 place-items-center rounded-lg', tone)}><Icon size={17} aria-hidden="true" /></span>
              <dt className="text-xs font-medium text-slate-600">{label}</dt>
              <dd className="mt-0.5 text-2xl font-extrabold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <ResultFeedback data={data} studyHref={studyHref} />
        <ResultSkills skills={data.skills} />
        <ResultQuestions questions={data.questions} />
        <ResultStudy data={data} studyHref={studyHref} />
        <section id="next" className={resultSection}>
          <h2 className="text-xl font-bold">Tiếp theo bạn nên làm gì?</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-3 rounded-2xl bg-[#a92705] p-5 text-white shadow-sm">
              <BookOpen aria-hidden="true" /><h3 className="font-bold">Lập kế hoạch tự ôn tập</h3>
              <p className="text-sm text-orange-50">Xem các kỹ năng cần cải thiện và sắp xếp đầu việc luyện tập.</p>
              <Link href={studyHref} className={cn(buttonVariants({ variant: 'outline' }), 'rounded-full border-white bg-white text-[#8c2100] hover:bg-orange-50')}>Mở kế hoạch <ArrowRight aria-hidden="true" /></Link>
            </div>
            <div className={cn(resultPanel, 'space-y-3')}>
              <RotateCcw className="text-orange-800" aria-hidden="true" /><h3 className="font-bold">Luyện tập phỏng vấn lại</h3>
              <p className="text-sm text-muted-foreground">Bắt đầu một lượt mới để kiểm tra phần đã ôn.</p>
              {profileId ? <Button variant="outline" disabled={busy} onClick={() => void retryInterview()}>{busy ? 'Đang tạo lượt…' : 'Phỏng vấn lượt mới'}</Button>
                : <Link href="/interview/new" className={buttonVariants({ variant: 'outline' })}>Phỏng vấn mới</Link>}
              {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            </div>
            <div className={cn(resultPanel, 'space-y-3')}>
              <ClipboardList className="text-blue-800" aria-hidden="true" /><h3 className="font-bold">{profileId ? 'Theo dõi năng lực' : 'Xem lịch sử phỏng vấn'}</h3>
              <p className="text-sm text-muted-foreground">{profileId ? 'Xem kết quả đánh giá tích lũy theo hồ sơ.' : 'Mở các lượt phỏng vấn đã lưu.'}</p>
              <Link href={backHref} className={buttonVariants({ variant: 'outline' })}>{profileId ? 'Mở hồ sơ ứng tuyển' : 'Mở lịch sử'}</Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
