'use client';

import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { InterviewOutcome } from '@/components/features/interview/InterviewOutcome';
import { InterviewResultDashboard } from '@/components/features/interview/result/InterviewResultDashboard';
import { LegacyInterviewResult } from '@/components/features/interview/result/LegacyInterviewResult';
import { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { BrandLoading } from '@/components/common/BrandLoading';

export default function InterviewResultPage() {
  const { id } = useParams<{ id: string }>();
  return <InterviewResult sessionId={id} key={id} />;
}

function InterviewResult({ sessionId }: { sessionId: string }) {
  const { session, metadata, loading, error, reload } = useEvidenceInterview(sessionId, true);

  if (loading) return <main className="mx-auto max-w-6xl px-4 py-8">
    <BrandLoading label="Đang tải kết quả phỏng vấn…" description="Đang chuẩn bị báo cáo và nhận xét của bạn." />
  </main>;
  if (error) return (
    <div role="alert" className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 p-8">
      <p>{error}</p>
      <Button variant="outline" onClick={() => void reload()}>Thử lại</Button>
    </div>
  );
  if (!session) return <LegacyInterviewResult id={sessionId} />;
  if (!session.is_finished || !session.turns.length) return (
    <div className="mx-auto max-w-6xl p-6"><InterviewOutcome session={session} metadata={metadata} /></div>
  );
  return <InterviewResultDashboard session={session} metadata={metadata} />;
}
