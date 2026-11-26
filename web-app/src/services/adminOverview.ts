import type { AdminOverviewData, TimeRangeKey } from '@/components/features/admin/types';
import axiosClient from '@/lib/axiosClient';

export async function getAdminOverview(range: TimeRangeKey, signal: AbortSignal) {
  const { data } = await axiosClient.get<AdminOverviewData>('/api/admin/overview', {
    baseURL: '/',
    params: { range },
    signal,
  });
  return data;
}
