'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, CalendarDays, CheckCircle2 } from 'lucide-react';
import { formatProfileDate } from '@/components/features/applications/applicationUi';
import { cn } from '@/lib/utils';
import { applicationProfiles } from '@/services/applicationProfiles';
import { interviewError, type EvidenceSession } from '@/services/evidenceInterview';
import type { SessionHistoryItem } from '@/services/historyService';
import { ResultCoachingSummary, ResultFeedback, ResultQuestions, ResultSkills, ResultStudy, resultPanel } from './ResultBreakdown';
import { assessmentLabels, buildResult, percent, resultReasons } from './resultData';
import { ResultNavigation } from './ResultNavigation';

function SkillSummaryCard({ data, reason }: { data: ReturnType<typeof buildResult>; reason: string | null }) {
  const totalSkills = data.skills.length;
  const allConclusive = totalSkills > 0 && data.partialSkillCount === 0;
  const attainment = data.weightedReadiness.hasCoreWeight && data.weightedReadiness.percent !== null
    ? data.weightedReadiness.percent
    : percent(data.assessedCount ? data.achievedCount / data.assessedCount : null);
  const ringPercent = allConclusive
    ? (attainment ?? 0)
    : data.weightedReadiness.hasCoreWeight && data.weightedReadiness.percent !== null
      ? data.weightedReadiness.percent
      : totalSkills > 0 ? Math.round((data.strongSkillCount / totalSkills) * 100) : 0;

  return (
    <div className="flex flex-col justify-between gap-4 rounded-xl border border-slate-200/70 dark:border-border/70 bg-slate-50/70 p-4">
      <div className="flex items-center gap-4">
        <div className="grid size-24 shrink-0 place-items-center rounded-full"
          style={{ background: `conic-gradient(#059669 ${ringPercent}%, #e2e8f0 0)` }}>
          <div className="grid size-19 place-items-center rounded-full bg-white dark:bg-card text-center">
            {allConclusive || data.weightedReadiness.hasCoreWeight ? (
              <span className="text-xl font-extrabold tabular-nums text-slate-900 dark:text-foreground">{attainment === null ? '—' : `${attainment}%`}</span>
            ) : (
              <span className="text-xl font-extrabold tabular-nums text-slate-900 dark:text-foreground">{data.strongSkillCount}/{totalSkills}</span>
            )}
          </div>
        </div>
        <div className="min-w-0 space-y-1.5">
          <p className="text-sm font-bold text-slate-900 dark:text-foreground">
            {data.weightedReadiness.hasCoreWeight
              ? 'Mức độ sẵn sàng (có trọng số Core)'
              : allConclusive ? 'Tỷ lệ nội dung đạt yêu cầu' : 'Kỹ năng đạt yêu cầu'}
          </p>
          {data.weightedReadiness.coreTotal > 0 && (
            <p className="text-xs font-medium text-slate-700 dark:text-muted-foreground">
              Kỹ năng cốt lõi đạt: <strong className="text-foreground">{data.weightedReadiness.coreMet}/{data.weightedReadiness.coreTotal}</strong>
            </p>
          )}
          {data.coverage && <p className="text-xs text-slate-700 dark:text-muted-foreground">
            Đã kiểm tra {data.coverage.checked}/{data.coverage.total} tiêu chí bắt buộc
            {data.coverage.checked > 0 && ` · Đạt ${data.coverage.passed}/${data.coverage.checked} tiêu chí đã kiểm tra`}
          </p>}
          <div className="flex flex-wrap gap-1.5 text-xs">
            <span className="rounded-full bg-emerald-100/80 px-2.5 py-0.5 font-semibold text-emerald-900">
              Đạt: {data.strongSkillCount}
            </span>
            {data.weakSkillCount > 0 && (
              <span className="rounded-full bg-orange-100/80 px-2.5 py-0.5 font-semibold text-orange-900">
                Cần cải thiện: {data.weakSkillCount}
              </span>
            )}
            {data.partialSkillCount > 0 && (
              <span className="rounded-full bg-amber-100/80 px-2.5 py-0.5 font-semibold text-amber-900">
                Chưa đủ cơ sở: {data.partialSkillCount}
              </span>
            )}
          </div>
        </div>
      </div>
      <p className="flex items-center gap-1.5 border-t border-slate-200/70 dark:border-border/70 pt-2.5 text-xs text-slate-600 dark:text-muted-foreground">
        <CheckCircle2 size={14} className="shrink-0 text-slate-500 dark:text-muted-foreground" />
        <span>{reason ? resultReasons[reason] ?? 'Lượt phỏng vấn đã kết thúc.' : 'Lượt phỏng vấn đã kết thúc.'}</span>
      </p>
    </div>
  );
}

export function InterviewResultDashboard({
  session,
  metadata,
  hasNavbar = false,
}: {
  session: EvidenceSession;
  metadata: SessionHistoryItem | null;
  hasNavbar?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const data = buildResult(session);
  const profileId = metadata?.applicationProfileId;
  const encodedProfile = profileId && encodeURIComponent(profileId);
  const studyHref = encodedProfile ? `/practice/${encodedProfile}` : '/practice';
  const backHref = encodedProfile ? `/applications/${encodedProfile}#competency` : '/history';

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
    <div className="min-w-0 bg-[#f4f7fc] dark:bg-background text-slate-900 dark:text-foreground">
      <ResultNavigation studyHref={studyHref} hasNavbar={hasNavbar} />
      <div className="mx-auto max-w-5xl space-y-6 px-4 pt-5 pb-12 sm:px-6">
        <div className="space-y-1.5">
          <Link href={backHref} className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#a02707] dark:text-orange-300 hover:underline">
            <ArrowLeft size={15} aria-hidden="true" /> {profileId ? 'Về hồ sơ ứng tuyển' : 'Quay lại lịch sử'}
          </Link>
          {session.config.recheck && encodedProfile && <Link className="block font-medium text-brand-green"
            href={`/practice/${encodedProfile}?task=${session.config.recheck.taskId}#checklist-${session.config.recheck.checklistItemId}`}>Về đầu việc</Link>}
          <h1 className="text-2xl font-extrabold tracking-tight wrap-anywhere sm:text-3xl">
            {metadata?.applicationProfileTitle || metadata?.roleTitle || 'Kết quả phỏng vấn'}
          </h1>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600 dark:text-muted-foreground">
            {metadata?.attemptNumber && <span className="font-semibold text-slate-800 dark:text-foreground">Lượt {metadata.attemptNumber}</span>}
            {metadata?.date && (
              <span className="inline-flex items-center gap-1">
                <CalendarDays size={13} /> {formatProfileDate(metadata.date, true)}
              </span>
            )}
            <span>{session.turns.length} câu đã trả lời</span>
            <span>{data.skills.length} kỹ năng</span>
            {session.config.session_purpose === 'PRACTICE' && (
              <span className="rounded-full bg-brand-green/10 px-2 py-0.5 font-semibold text-brand-green">
                Chế độ Luyện tập (không ảnh hưởng hồ sơ năng lực chính thức)
              </span>
            )}
          </div>
        </div>

        <section id="overview" className={cn(resultPanel, 'scroll-mt-(--result-scroll-mt,5rem) space-y-4')}>
          <div className={cn('grid gap-4', data.coaching?.overall_summary && 'lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.35fr)]')}>
            {session.report.recheck_criterion ? <div className="rounded-xl border p-4">
              <h2 className="text-sm font-semibold">Tiêu chí kiểm chứng</h2>
              <p className="my-2 text-lg">{session.report.recheck_criterion.description}</p>
              <p className="font-semibold">{assessmentLabels[session.report.recheck_criterion.assessment]}</p>
            </div> : <SkillSummaryCard data={data} reason={session.report.termination_reason} />}
            {data.coaching?.overall_summary && (
              <ResultCoachingSummary
                summary={data.coaching.overall_summary}
                introFeedback={data.coaching.introduction_feedback}
              />
            )}
          </div>
          <ResultFeedback data={data} />
        </section>

        <ResultSkills skills={data.skills} />
        <ResultQuestions questions={data.questions} />
        <ResultStudy
          data={data}
          studyHref={studyHref}
          profileId={profileId}
          busy={busy}
          error={error}
          onRetry={() => void retryInterview()}
        />
      </div>
    </div>
  );
}
