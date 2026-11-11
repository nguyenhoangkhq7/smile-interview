'use client';

import Link from 'next/link';
import { FolderOpen } from 'lucide-react';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { usePracticePlanDetail, usePracticeProfiles, usePracticeRequest } from '@/hooks/usePracticeProfiles';
import { studyPlans } from '@/services/studyPlans';
import { PracticeStats } from './PracticeOverview';
import { PracticePlanBoard } from './PracticePlanBoard';
import { PracticePlanList } from './PracticePlanList';
import { toPracticePlan } from './practicePlans';

type ProfileStatusProps =
  | { loadingLabel: string; message?: never; onRetry?: never }
  | { loadingLabel?: never; message: string; onRetry: () => void };

function ProfileStatus({ loadingLabel, message, onRetry }: ProfileStatusProps) {
  if (onRetry) {
    return (
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-card p-4 text-sm">
        <p>{message}</p>
        <Button type="button" variant="outline" onClick={onRetry}>Thử lại</Button>
      </div>
    );
  }

  return <p role="status" className="rounded-xl border border-slate-100 bg-card p-5 text-sm text-(--practice-muted)">{loadingLabel}</p>;
}

function NoPracticeProfiles() {
  return (
    <section className="flex flex-col items-center gap-3 rounded-2xl border border-slate-100 bg-card p-8 text-center">
      <FolderOpen size={24} className="text-(--practice-primary)" aria-hidden="true" />
      <h2 className="font-semibold">Bạn chưa có hồ sơ ứng tuyển</h2>
      <p className="text-sm text-(--practice-muted)">Hồ sơ bạn tạo sẽ tự xuất hiện trong danh sách ôn tập.</p>
      <Link href="/applications" className={cn(buttonVariants({ variant: 'outline' }), 'rounded-full')}>
        Đến Hồ sơ ứng tuyển
      </Link>
    </section>
  );
}

export function PracticeProfilesContent() {
  const { state, retry } = usePracticeProfiles();
  const progress = usePracticeRequest(studyPlans.listProgress);
  if (state.status === 'loading') return <ProfileStatus loadingLabel="Đang tải hồ sơ ứng tuyển…" />;
  if (state.status === 'error') return <ProfileStatus message={state.message} onRetry={retry} />;
  const progressByProfile = new Map(progress.state.status === 'ready'
    ? progress.state.data.map((item) => [item.applicationProfileId, item.progress]) : []);
  const plans = state.data.map((profile) => toPracticePlan(profile, progressByProfile.get(profile.id), progress.state.status));

  return (
    <>
      <PracticeStats plans={plans} />
      {progress.state.status === 'error' && <ProfileStatus message="Không tải được tiến độ ôn tập." onRetry={progress.retry} />}
      {plans.length ? <PracticePlanList plans={plans} /> : <NoPracticeProfiles />}
    </>
  );
}

export function PracticePlanDetail({ profileId }: { profileId: string }) {
  const { state, retry } = usePracticePlanDetail(profileId);
  if (state.status === 'loading') return <ProfileStatus loadingLabel="Đang tải kế hoạch ôn tập…" />;
  if (state.status === 'error') return <ProfileStatus message={state.message} onRetry={retry} />;
  return <PracticePlanBoard profile={state.data.profile} initialPlan={state.data.plan} />;
}
