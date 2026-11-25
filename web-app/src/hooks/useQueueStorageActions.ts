import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { queueStorageError } from '@/hooks/useAdminQueueStorage';
import { adminQueueStorage } from '@/services/adminQueueStorage';
import type { SkillGapJobItem, StorageOverviewData } from '@/components/features/admin/queue-storage/types';

interface RefreshActions {
  refreshQueue: () => void;
  refreshStorage: () => void;
  refreshDetail: () => void;
}

const success = {
  release: 'Đã giải phóng lease và đưa job về hàng chờ.',
  prioritize: 'Đã ưu tiên job.',
};

export function useQueueStorageActions({ refreshQueue, refreshStorage, refreshDetail }: RefreshActions) {
  const [queueBusy, setQueueBusy] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const queueLock = useRef(false);
  const cleanupLock = useRef(false);

  async function queueAction(action: () => Promise<void>) {
    if (queueLock.current) return;
    queueLock.current = true;
    setQueueBusy(true);
    try {
      await action();
    } catch (error) {
      toast.error(queueStorageError(error, 'Không thực hiện được thao tác với hàng đợi.'));
    } finally {
      queueLock.current = false;
      setQueueBusy(false);
      refreshQueue();
      refreshDetail();
    }
  }

  function act(job: SkillGapJobItem, action: keyof typeof success) {
    void queueAction(async () => {
      await adminQueueStorage.act(job, action);
      toast.success(success[action]);
    });
  }

  async function cleanup(storage: StorageOverviewData) {
    if (cleanupLock.current || !storage.orphans?.ids.length) return;
    cleanupLock.current = true;
    setCleaning(true);
    const ids = storage.orphans.ids;
    const totals = { deleted: 0, skipped: 0, failed: 0 };
    try {
      for (let offset = 0; offset < ids.length; offset += storage.cleanupBatchSize) {
        const result = await adminQueueStorage.cleanup(ids.slice(offset, offset + storage.cleanupBatchSize));
        totals.deleted += result.deleted;
        totals.skipped += result.skipped;
        totals.failed += result.failed;
      }
      const message = 'Đã xóa ' + totals.deleted + ' tệp, bỏ qua ' + totals.skipped + ', lỗi ' + totals.failed + '.';
      if (totals.failed) toast.warning(message);
      else toast.success(message);
    } catch (error) {
      toast.error(queueStorageError(error, 'Dọn dẹp bị gián đoạn. Đã xác nhận xóa ' + totals.deleted + ' tệp.'));
    } finally {
      cleanupLock.current = false;
      setCleaning(false);
      refreshStorage();
    }
  }

  return { queueBusy, cleaning, act, clean: (storage: StorageOverviewData) => void cleanup(storage) };
}
