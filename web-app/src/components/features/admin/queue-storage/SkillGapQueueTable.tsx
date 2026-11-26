import { ChevronLeft, ChevronRight, Eye, ListVideo, RefreshCw, Unplug, Zap } from 'lucide-react';
import type { AdminQueuePage, QueueJobStatus, SkillGapJobItem } from './types';
import { queueFailure, queueTime } from './queueStorageFormat';

const badges: Record<QueueJobStatus, string> = {
  FAILED: 'bg-[#ffdad6] dark:bg-red-950 text-[#93000a] dark:text-red-200',
  RUNNING: 'bg-[#cce5ff] dark:bg-sky-950 text-[#186392] dark:text-sky-300',
  SUCCEEDED: 'bg-[#daf8e0] dark:bg-emerald-950 text-[#006b2f] dark:text-emerald-300',
  PENDING: 'bg-[#e0e8ff] dark:bg-secondary text-[#293041] dark:text-foreground',
};
const columns = ['Mã job', 'Ứng viên / Vị trí', 'Trạng thái', 'Lần thử', 'Tạo lúc', 'Thao tác'];
const actionClass = 'inline-flex items-center gap-1 rounded-md bg-[#f1f3ff] dark:bg-muted px-2 py-1.5 text-xs font-semibold disabled:opacity-50';
const pagingClass = 'grid size-8 place-items-center rounded-lg bg-white dark:bg-card disabled:opacity-45';

interface SkillGapQueueTableProps {
  data: AdminQueuePage;
  busy: boolean;
  onInspect: (id: string) => void;
  onAction: (job: SkillGapJobItem, action: 'release' | 'prioritize') => void;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

function JobActions({ job, busy, onInspect, onAction }: Pick<SkillGapQueueTableProps, 'busy' | 'onInspect' | 'onAction'> & { job: SkillGapJobItem }) {
  if (job.status === 'RUNNING' && job.claimToken) {
    return <button type="button" className={actionClass + ' text-[#186392] dark:text-sky-300'} disabled={busy}
      onClick={() => onAction(job, 'release')}><Unplug className="size-3.5" /> Giải phóng</button>;
  }
  if (job.status === 'PENDING' && !job.prioritized) {
    return <button type="button" className={actionClass + ' text-[#ad2c00] dark:text-orange-300'} disabled={busy}
      onClick={() => onAction(job, 'prioritize')}><Zap className="size-3.5" /> Ưu tiên</button>;
  }
  return <button type="button" className={actionClass} onClick={() => onInspect(job.id)}><Eye className="size-3.5" /> Chi tiết</button>;
}

function JobState({ job }: { job: SkillGapJobItem }) {
  return (
    <>
      <span className={'inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ' + badges[job.status]}>{job.status}</span>
      {job.status === 'RUNNING' && job.leaseUntil && <p className="mt-1 text-xs text-[#186392] dark:text-sky-300">Lease đến {queueTime(job.leaseUntil)}</p>}
      {job.status === 'FAILED' && <p className="mt-1 text-xs text-[#93000a] dark:text-red-200">{queueFailure(job.failureCode) ?? 'Chưa ghi nhận nguyên nhân'}</p>}
      {job.status === 'PENDING' && job.prioritized && <p className="mt-1 text-xs text-[#ad2c00] dark:text-orange-300">Đã ưu tiên</p>}
    </>
  );
}

export default function SkillGapQueueTable({ data, busy, onInspect, onAction, onPageChange, onRefresh }: SkillGapQueueTableProps) {
  const first = data.jobs.length ? (data.page - 1) * data.size + 1 : 0;
  const last = data.jobs.length ? first + data.jobs.length - 1 : 0;
  const pageCount = Math.max(1, Math.ceil(data.total / data.size));

  return (
    <section className="overflow-hidden rounded-xl bg-white dark:bg-card shadow-xs">
      <header className="flex items-center justify-between gap-2 px-5 py-4">
        <h2 className="flex items-center gap-2 font-semibold"><ListVideo className="size-5 text-[#ad2c00] dark:text-orange-300" />Danh sách tiến trình phân tích</h2>
        <button type="button" className={actionClass} onClick={onRefresh} aria-label="Làm mới hàng đợi"><RefreshCw className="size-4" /></button>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-205 text-left text-sm">
          <thead className="bg-[#f1f3ff] dark:bg-muted text-xs uppercase text-[#5c4039] dark:text-muted-foreground">
            <tr>{columns.map((column, index) => <th scope="col" key={column} className={'px-5 py-3 ' + (index === 5 ? 'text-right' : '')}>{column}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-[#e9edff]">
            {!data.jobs.length && <tr><td colSpan={6} className="p-8 text-center text-[#5c4039] dark:text-muted-foreground">Không tìm thấy job phù hợp.</td></tr>}
            {data.jobs.map(job => (
              <tr key={job.id} className={job.status === 'RUNNING' ? 'bg-[#f3f8fd] dark:bg-muted' : ''}>
                <td className="px-5 py-3">
                  <button type="button" className="font-mono text-xs font-semibold text-[#186392] dark:text-sky-300 underline"
                    title={job.id} onClick={() => onInspect(job.id)}>#{job.id.slice(0, 8)}</button>
                </td>
                <td className="px-5 py-3"><strong>{job.candidateName}</strong><p className="text-xs text-[#5c4039] dark:text-muted-foreground">{job.roleTitle ?? '—'}</p></td>
                <td className="px-5 py-3"><JobState job={job} /></td>
                <td className="px-5 py-3 font-mono text-xs">{job.attempts}/{data.maxAttempts}</td>
                <td className="px-5 py-3 text-xs text-[#5c4039] dark:text-muted-foreground">{queueTime(job.createdAt)}</td>
                <td className="px-5 py-3 text-right"><JobActions job={job} busy={busy} onInspect={onInspect} onAction={onAction} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-3 bg-[#f1f3ff] dark:bg-muted px-5 py-3 text-xs">
        <span>Hiển thị {first}–{last} / {data.total.toLocaleString('vi-VN')} jobs</span>
        <nav aria-label="Trang hàng đợi" className="flex items-center gap-2">
          <button type="button" className={pagingClass} disabled={data.page <= 1} onClick={() => onPageChange(data.page - 1)} aria-label="Trang trước"><ChevronLeft className="size-4" /></button>
          <span>{data.page} / {pageCount}</span>
          <button type="button" className={pagingClass} disabled={data.page >= pageCount} onClick={() => onPageChange(data.page + 1)} aria-label="Trang tiếp"><ChevronRight className="size-4" /></button>
        </nav>
      </footer>
    </section>
  );
}
