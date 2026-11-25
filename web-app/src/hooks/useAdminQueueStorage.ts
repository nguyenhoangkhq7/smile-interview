import { isAxiosError } from 'axios';
import { useDeferredValue, useEffect, useState } from 'react';
import type { AdminQueuePage, QueueJobDetail, StorageOverviewData } from '@/components/features/admin/queue-storage/types';
import { adminQueueStorage, type QueueQuery } from '@/services/adminQueueStorage';

type Resource<T> = { key: string; data: T; error?: never } | { key: string; error: string; data?: never };

const refreshInterval = 5000;
const initialQuery: QueueQuery = { search: '', status: '', page: 1 };

export function queueStorageError(error: unknown, fallback: string) {
  if (isAxiosError<{ message?: string }>(error) && error.response && error.response.status < 500) {
    return error.response.data?.message || fallback;
  }
  return fallback;
}

export function useAdminQueue() {
  const [query, setQuery] = useState(initialQuery);
  const deferred = useDeferredValue(query);
  const [revision, setRevision] = useState(0);
  const [value, setValue] = useState<Resource<AdminQueuePage>>();
  const key = JSON.stringify(deferred);

  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const data = await adminQueueStorage.page(deferred, abort.signal);
        if (!abort.signal.aborted) setValue({ key, data });
      } catch (error) {
        if (!abort.signal.aborted) setValue({ key, error: queueStorageError(error, 'Không tải được hàng đợi.') });
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(() => void load(), refreshInterval);
      }
    }
    void load();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [deferred, key, revision]);

  return {
    query, setQuery,
    result: query === deferred && value?.key === key ? value : undefined,
    refresh: () => setRevision(current => current + 1),
  };
}

export function useAdminJobDetail(id: string | null) {
  const [value, setValue] = useState<Resource<QueueJobDetail>>();
  const [revision, setRevision] = useState(0);
  const key = JSON.stringify([id, revision]);

  useEffect(() => {
    if (!id) return;
    const abort = new AbortController();
    adminQueueStorage.detail(id, abort.signal).then(data => {
      if (!abort.signal.aborted) setValue({ key, data });
    }).catch(error => {
      if (!abort.signal.aborted) setValue({ key, error: queueStorageError(error, 'Không tải được chi tiết job.') });
    });
    return () => abort.abort();
  }, [id, key]);

  return { result: id && value?.key === key ? value : undefined, refresh: () => setRevision(n => n + 1) };
}

export function useAdminStorage() {
  const [value, setValue] = useState<Resource<StorageOverviewData>>();
  const [revision, setRevision] = useState(0);
  const key = String(revision);
  useEffect(() => {
    const abort = new AbortController();
    adminQueueStorage.storage(abort.signal).then(data => {
      if (!abort.signal.aborted) setValue({ key, data });
    }).catch(error => {
      if (!abort.signal.aborted) setValue({ key, error: queueStorageError(error, 'Không đo được dung lượng lưu trữ.') });
    });
    return () => abort.abort();
  }, [key]);

  return { result: value?.key === key ? value : undefined, refresh: () => setRevision(n => n + 1) };
}
