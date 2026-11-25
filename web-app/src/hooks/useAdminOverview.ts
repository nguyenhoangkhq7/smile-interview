import { isAxiosError } from 'axios';
import { useEffect, useState } from 'react';
import type { AdminOverviewData, TimeRangeKey } from '@/components/features/admin/types';
import { getAdminOverview } from '@/services/adminOverview';

type OverviewResult = {
  key: string;
} & ({ data: AdminOverviewData; error?: never } | { data?: never; error: string });

export function useAdminOverview(range: TimeRangeKey) {
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState<OverviewResult>();
  const key = range + ':' + reload;

  useEffect(() => {
    const abort = new AbortController();
    getAdminOverview(range, abort.signal)
      .then((data) => {
        if (!abort.signal.aborted) setResult({ key, data });
      })
      .catch((error: unknown) => {
        if (abort.signal.aborted) return;
        const forbidden = isAxiosError(error) && error.response?.status === 403;
        setResult({ key, error: forbidden
          ? 'Bạn không có quyền xem số liệu quản trị.'
          : 'Không tải được dữ liệu tổng quan.' });
      });
    return () => abort.abort();
  }, [range, key]);

  return {
    result: result?.key === key ? result : undefined,
    retry: () => setReload((previous) => previous + 1),
  };
}
