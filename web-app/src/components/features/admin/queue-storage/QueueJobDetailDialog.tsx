import { X } from 'lucide-react';
import type { QueueJobDetail } from './types';
import { queueFailure, queueTime } from './queueStorageFormat';

export default function QueueJobDetailDialog({ detail, error, onRefresh, onClose }: {
  detail?: QueueJobDetail; error?: string; onRefresh: () => void; onClose: () => void;
}) {
  const job = detail?.job;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="queue-detail-title">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white dark:bg-card p-6 shadow-lg">
        <header className="flex items-start justify-between gap-4">
          <h2 id="queue-detail-title" className="text-lg font-semibold">Chi tiết tiến trình phân tích</h2>
          <button type="button" onClick={onClose} aria-label="Đóng"><X className="size-5" /></button>
        </header>
        {!job ? <p className="mt-4 text-sm" role={error ? 'alert' : 'status'}>{error ?? 'Đang tải chi tiết job…'}</p> : (
          <dl className="mt-4 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
            <dt>Mã job</dt><dd className="break-all font-mono text-xs">{job.id}</dd>
            <dt>Phiên</dt><dd className="break-all font-mono text-xs">{job.sessionId}</dd>
            <dt>Ứng viên</dt><dd>{job.candidateName}</dd>
            <dt>Vị trí</dt><dd>{job.roleTitle ?? '—'}</dd>
            <dt>Trạng thái</dt><dd>{job.status}</dd>
            <dt>Số lần thử</dt><dd>{job.attempts}</dd>
            <dt>Tạo lúc</dt><dd>{queueTime(job.createdAt)}</dd>
            <dt>Có thể chạy từ</dt><dd>{queueTime(job.availableAt)}</dd>
            <dt>Nhận lease</dt><dd>{queueTime(job.claimedAt)}</dd>
            <dt>Hết hạn lease</dt><dd>{queueTime(job.leaseUntil)}</dd>
            <dt>Kết thúc</dt><dd>{queueTime(job.finishedAt)}</dd>
            {job.failureCode && <><dt>Lỗi gần nhất</dt><dd>{queueFailure(job.failureCode)}</dd></>}
            {detail.skillCount !== null && <><dt>Kỹ năng phân tích</dt><dd>{detail.skillCount}</dd></>}
            {detail.matchingScore !== null && <><dt>Điểm đối sánh</dt><dd>{detail.matchingScore.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}</dd></>}
            {detail.degraded && <><dt>Chất lượng</dt><dd>Kết quả có bước phân tích dự phòng</dd></>}
          </dl>
        )}
        <div className="mt-5 flex justify-end"><button type="button" onClick={onRefresh} className="rounded-lg bg-[#f1f3ff] dark:bg-muted px-3 py-2 text-sm">Làm mới</button></div>
      </div>
    </div>
  );
}
