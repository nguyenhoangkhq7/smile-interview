import { FolderX, HardDrive, RefreshCw } from 'lucide-react';
import type { StorageOverviewData } from './types';
import { queueTime, storageBytes } from './queueStorageFormat';

const segments: Record<string, { label: string; color: string }> = {
  cv: { label: 'Tài liệu CV trên S3', color: '#ad2c00' },
  jd: { label: 'Mô tả công việc trên S3', color: '#186392' },
  avatars: { label: 'Ảnh đại diện trên máy chủ', color: '#8dcbfa' },
  postgres: { label: 'Cơ sở dữ liệu PostgreSQL', color: '#006b2f' },
};

export default function StorageAllocationSection({ storage, busy, onRefresh, onCleanOrphans }: {
  storage: StorageOverviewData; busy: boolean; onRefresh: () => void; onCleanOrphans: () => void;
}) {
  const quota = storage.complete ? storage.quotaBytes : null;
  const scale = Math.max(quota ?? 0, storage.totalBytes, 1);
  const orphans = storage.orphans;
  const count = orphans?.ids.length ?? 0;

  return (
    <section className="space-y-4 rounded-xl bg-white dark:bg-card p-5 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-lg bg-[#e0e8ff] dark:bg-secondary text-[#186392] dark:text-sky-300"><HardDrive className="size-5" /></span>
          <div>
            <h2 className="font-semibold">Tổng quan lưu trữ</h2>
            <p className="text-xs text-[#5c4039] dark:text-muted-foreground">Cập nhật {queueTime(storage.measuredAt)}</p>
          </div>
        </div>
        <button type="button" className="rounded-lg bg-[#f1f3ff] dark:bg-muted p-2" onClick={onRefresh} disabled={busy} aria-label="Đo lại dung lượng">
          <RefreshCw className="size-4" />
        </button>
      </div>
      <div className="rounded-xl bg-[#f1f3ff] dark:bg-muted p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-1 text-sm">
          <span>Đã đo <strong className="text-xl">{storageBytes(storage.totalBytes)}</strong>{quota && ' / ' + storageBytes(quota)}</span>
          {quota && <span className="font-semibold text-[#186392] dark:text-sky-300">{(100 * storage.totalBytes / quota).toFixed(1)}%</span>}
        </div>
        <div className="my-3 flex h-2.5 overflow-hidden rounded-full bg-[#e0e8ff] dark:bg-secondary" aria-hidden="true">
          {storage.segments.map(segment => <div key={segment.code} style={{
            width: 100 * segment.bytes / scale + '%', backgroundColor: segments[segment.code]?.color,
          }} />)}
        </div>
        <ul className="grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
          {storage.segments.map(segment => (
            <li key={segment.code} className="flex items-center gap-2">
              <span className="size-2.5 rounded-sm" style={{ backgroundColor: segments[segment.code]?.color }} />
              <span>{segments[segment.code]?.label ?? segment.code}<strong className="block text-sm">{storageBytes(segment.bytes)}</strong></span>
            </li>
          ))}
        </ul>
        {!storage.complete && <p role="status" className="mt-3 text-xs text-[#5c4039] dark:text-muted-foreground">
          {storage.s3Available ? 'Dung lượng hiển thị có thể thiếu ảnh đại diện.' : 'S3 chưa phản hồi số liệu. Dung lượng hiển thị chỉ gồm nguồn đã đo được.'}
        </p>}
      </div>
      <div className={'flex flex-wrap items-center justify-between gap-3 rounded-xl p-4 ' + (count ? 'bg-[#fff1ef] dark:bg-red-950/55' : 'bg-[#f7f8ff] dark:bg-background')}>
        <div className="flex items-center gap-3">
          <FolderX className="size-5 shrink-0 text-[#ad2c00] dark:text-orange-300" />
          <div>
            <strong className="text-sm">{!orphans ? 'Chưa kiểm tra được CV mồ côi' : count
              ? 'Phát hiện ' + count.toLocaleString('vi-VN') + ' CV mồ côi (' + storageBytes(orphans.bytes) + ')'
              : 'Không có CV mồ côi đủ điều kiện dọn'}</strong>
            {orphans && <p className="text-xs text-[#5c4039] dark:text-muted-foreground">CV do hệ thống theo dõi, đã tải lên ít nhất {orphans.minimumAgeHours} giờ.</p>}
          </div>
        </div>
        <button type="button" disabled={busy || !count} onClick={onCleanOrphans}
          className="rounded-lg bg-[#ba1a1a] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
          {busy ? 'Đang dọn dẹp…' : 'Dọn dẹp tệp mồ côi'}
        </button>
      </div>
    </section>
  );
}
