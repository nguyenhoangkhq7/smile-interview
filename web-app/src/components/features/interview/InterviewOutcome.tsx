'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button, buttonVariants } from '@/components/ui/button';
import { EvidenceSession, interviewError } from '@/services/evidenceInterview';
import type { SessionHistoryItem } from '@/services/historyService';
import { applicationProfiles } from '@/services/applicationProfiles';

export function InterviewOutcome({ session, metadata }: { session: EvidenceSession; metadata: SessionHistoryItem | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function newAttempt() {
    if (!metadata?.applicationProfileId || busy) return;
    setBusy(true); setError('');
    try {
      const attempt = await applicationProfiles.newAttempt(metadata.applicationProfileId);
      router.push(`/interview/session/${attempt.id}`);
    } catch (cause) { setError(interviewError(cause)); }
    finally { setBusy(false); }
  }
  return <div className="space-y-6">
    {!session.is_finished ? <div className="rounded-xl border p-5"><h1 className="text-xl font-semibold">Lượt phỏng vấn đang diễn ra</h1><Link className={`${buttonVariants()} mt-4`} href={`/interview/session/${session.session_id}`}>Tiếp tục phỏng vấn</Link></div>
      : <section className="space-y-3 rounded-xl border bg-muted/20 p-6"><h1 className="text-2xl font-semibold">Lượt phỏng vấn đã kết thúc</h1><p>Bạn chưa gửi câu trả lời nào. Chưa có dữ liệu để đánh giá năng lực.</p></section>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    <div className="flex flex-wrap gap-3 border-t pt-5">
      {metadata?.applicationProfileId ? <><Link className={buttonVariants({ variant: 'outline' })} href={`/applications/${metadata.applicationProfileId}#competency`}>Về hồ sơ ứng tuyển</Link>{session.is_finished && <Button disabled={busy} onClick={() => void newAttempt()}>{busy ? 'Đang tạo lượt…' : 'Phỏng vấn lượt mới'}</Button>}</>
        : <Link className={buttonVariants({ variant: 'outline' })} href="/history">Về lịch sử</Link>}
    </div>
  </div>;
}
