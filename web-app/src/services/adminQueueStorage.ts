import axiosClient from '@/lib/axiosClient';
import type {
  AdminQueuePage, QueueJobStatus, QueueJobDetail, SkillGapJobItem, StorageCleanupResult, StorageOverviewData,
} from '@/components/features/admin/queue-storage/types';

const baseURL = '/';
const jobs = '/api/admin/queue/jobs';
const storage = '/api/admin/storage';

export interface QueueQuery {
  search: string;
  status: QueueJobStatus | '';
  page: number;
}

export const adminQueueStorage = {
  async page(query: QueueQuery, signal: AbortSignal) {
    return (await axiosClient.get<AdminQueuePage>(jobs, {
      baseURL, signal, params: { search: query.search.trim(), status: query.status || undefined, page: query.page },
    })).data;
  },
  async detail(id: string, signal: AbortSignal) {
    return (await axiosClient.get<QueueJobDetail>(jobs + '/' + id, { baseURL, signal })).data;
  },
  async act(job: SkillGapJobItem, action: 'release' | 'prioritize') {
    const payload = action === 'release' ? { claimToken: job.claimToken } : undefined;
    await axiosClient.post(jobs + '/' + job.id + '/' + action, payload, { baseURL });
  },
  async storage(signal: AbortSignal) {
    return (await axiosClient.get<StorageOverviewData>(storage, { baseURL, signal })).data;
  },
  async cleanup(ids: string[]) {
    return (await axiosClient.post<StorageCleanupResult>(storage + '/cleanup', { ids }, { baseURL })).data;
  },
};
