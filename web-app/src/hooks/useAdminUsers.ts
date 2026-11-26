import { isAxiosError } from 'axios';
import { useDeferredValue, useEffect, useState } from 'react';
import type { AdminUserDetail, AdminUserPage, UserCatalogFilter } from '@/components/features/admin/users/types';
import { adminUsers } from '@/services/adminUsers';

const emptyFilter: UserCatalogFilter = { search: '', role: '', status: '' };

export function adminUsersError(error: unknown, fallback: string) {
  if (!isAxiosError<{ message?: string }>(error)) return fallback;
  const message = error.response?.data?.message;
  return typeof message === 'string' && error.response?.status !== 502 ? message : fallback;
}

type Result<T> = { key: string } & ({ data: T; error?: never } | { data?: never; error: string });

export function useAdminUsers() {
  const [filter, setFilter] = useState(emptyFilter);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const currentFilter = useDeferredValue(filter);
  const [value, setValue] = useState<Result<AdminUserPage>>();
  const key = JSON.stringify([currentFilter, page, revision]);

  useEffect(() => {
    const abort = new AbortController();
    adminUsers.list(currentFilter, page, abort.signal)
      .then(data => {
        if (!abort.signal.aborted) setValue({ key, data });
      })
      .catch(error => {
        if (!abort.signal.aborted) setValue({ key, error: adminUsersError(error, 'Không tải được danh sách.') });
      });
    return () => abort.abort();
  }, [currentFilter, page, key]);

  return {
    filter, setPage, revision,
    result: filter === currentFilter && value?.key === key ? value : undefined,
    changeFilter: (next: UserCatalogFilter) => { setFilter(next); setPage(1); },
    reset: () => { setFilter(emptyFilter); setPage(1); },
    refresh: () => setRevision(previous => previous + 1),
  };
}

export function useAdminUserDetail(id: string | null, revision: number) {
  const [value, setValue] = useState<Result<AdminUserDetail>>();
  const key = JSON.stringify([id, revision]);

  useEffect(() => {
    if (!id) return;
    const abort = new AbortController();
    adminUsers.detail(id, abort.signal)
      .then(data => {
        if (!abort.signal.aborted) setValue({ key, data });
      })
      .catch(error => {
        if (!abort.signal.aborted) setValue({ key, error: adminUsersError(error, 'Không tải được chi tiết.') });
      });
    return () => abort.abort();
  }, [id, key]);

  return id && value?.key === key ? value : undefined;
}
