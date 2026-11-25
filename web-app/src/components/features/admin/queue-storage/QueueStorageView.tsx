'use client';

import { useState } from 'react';
import { useAdminJobDetail, useAdminQueue, useAdminStorage } from '@/hooks/useAdminQueueStorage';
import { useQueueStorageActions } from '@/hooks/useQueueStorageActions';
import type { StorageOverviewData } from './types';
import { storageBytes } from './queueStorageFormat';
import QueueFilterActionBar from './QueueFilterActionBar';
import QueueJobDetailDialog from './QueueJobDetailDialog';
import QueueKpiBento from './QueueKpiBento';
import QueueStorageHeader from './QueueStorageHeader';
import SkillGapQueueTable from './SkillGapQueueTable';
import StorageAllocationSection from './StorageAllocationSection';

function StatusPanel({ error, pending, onRetry }: { error?: string; pending: string; onRetry: () => void }) {
  return (
    <div className="rounded-xl bg-white dark:bg-card p-5 text-sm text-[#5c4039] dark:text-muted-foreground" role={error ? 'alert' : 'status'}>
      {error ?? pending}
      {error && <button type="button" className="ml-3 font-semibold underline" onClick={onRetry}>Thử lại</button>}
    </div>
  );
}

function ConfirmCleanup({ snapshot, onCancel, onConfirm }: {
  snapshot: NonNullable<StorageOverviewData['orphans']>; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="queue-cleanup-title">
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-card p-6 shadow-lg">
        <h2 id="queue-cleanup-title" className="text-lg font-semibold">Dọn dẹp CV mồ côi</h2>
        <p className="mt-3 text-sm">Xác nhận xóa {snapshot.ids.length.toLocaleString('vi-VN')} CV ({storageBytes(snapshot.bytes)}) khỏi S3.</p>
        <div className="mt-5 flex justify-end gap-3 text-sm">
          <button type="button" onClick={onCancel}>Hủy</button>
          <button type="button" className="rounded-lg bg-[#ba1a1a] px-4 py-2 font-semibold text-white" onClick={onConfirm}>Xóa CV mồ côi</button>
        </div>
      </div>
    </div>
  );
}

export default function QueueStorageView() {
  const queue = useAdminQueue();
  const storage = useAdminStorage();
  const [selected, setSelected] = useState<string | null>(null);
  const [cleanup, setCleanup] = useState<StorageOverviewData>();
  const detail = useAdminJobDetail(selected);
  const actions = useQueueStorageActions({ refreshQueue: queue.refresh, refreshStorage: storage.refresh, refreshDetail: detail.refresh });
  const page = queue.result?.data;
  const inventory = storage.result?.data;

  return (
    <div className="flex w-full flex-col gap-5 pb-8">
      <QueueStorageHeader />
      {page && <QueueKpiBento stats={page.stats} />}
      <QueueFilterActionBar
        jobSearch={queue.query.search} onJobSearchChange={search => queue.setQuery({ ...queue.query, search, page: 1 })}
        statusFilter={queue.query.status} onStatusFilterChange={status => queue.setQuery({ ...queue.query, status, page: 1 })}
      />
      {page ? (
        <SkillGapQueueTable data={page} busy={actions.queueBusy} onInspect={setSelected} onAction={actions.act}
          onPageChange={number => queue.setQuery({ ...queue.query, page: number })} onRefresh={queue.refresh} />
      ) : (
        <StatusPanel error={queue.result?.error} pending="Đang tải hàng đợi…" onRetry={queue.refresh} />
      )}
      {inventory ? (
        <StorageAllocationSection storage={inventory} busy={actions.cleaning}
          onRefresh={storage.refresh} onCleanOrphans={() => setCleanup(inventory)} />
      ) : (
        <StatusPanel error={storage.result?.error} pending="Đang đo dung lượng lưu trữ…" onRetry={storage.refresh} />
      )}
      {selected && <QueueJobDetailDialog detail={detail.result?.data} error={detail.result?.error}
        onRefresh={detail.refresh} onClose={() => setSelected(null)} />}
      {cleanup?.orphans && <ConfirmCleanup snapshot={cleanup.orphans} onCancel={() => setCleanup(undefined)} onConfirm={() => {
        actions.clean(cleanup);
        setCleanup(undefined);
      }} />}
    </div>
  );
}
