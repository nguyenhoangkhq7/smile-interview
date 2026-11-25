import axiosClient from '@/lib/axiosClient';
import type { InterviewDetail, InterviewFilter, InterviewPage } from '@/components/features/admin/sessions/types';

const baseURL = '/';
const path = '/api/admin/interview-sessions';

export const adminInterviews = {
  async list(search: string, status: InterviewFilter, page: number, signal: AbortSignal) {
    const params = { search: search.trim() || undefined, status: status === 'all' ? undefined : status, page };
    return (await axiosClient.get<InterviewPage>(path, { baseURL, params, signal })).data;
  },
  async detail(id: string, signal: AbortSignal) {
    return (await axiosClient.get<InterviewDetail>(path + '/detail', { baseURL, params: { id }, signal })).data;
  },
};
