import type { EvidenceSession } from '@/services/evidenceInterview';
import { Button } from '@/components/ui/button';

export function InterviewSubmissionStatus({ submission, busy, retry, stop }: {
  submission: NonNullable<EvidenceSession['submission']>;
  busy?: boolean;
  retry?: () => void;
  stop?: () => void;
}) {
  if (submission.status === 'QUEUED') return null;

  return <section className="space-y-3 rounded-xl border bg-card p-5">
    <p role="status" className="font-semibold">{submission.status === 'FAILED'
      ? 'Bài đã được lưu. Chấm điểm tạm thời gián đoạn.' : 'Bài đã nộp và chưa được chấm.'}</p>
    {submission.status === 'FAILED' && <div className="flex gap-2">
      {retry && <Button disabled={busy} onClick={retry}>Chấm lại bài đã nộp</Button>}
      {stop && <Button variant="outline" disabled={busy} onClick={stop}>Kết thúc phiên</Button>}
    </div>}
  </section>;
}
