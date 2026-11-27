import axiosClient from '@/lib/axiosClient';
import type {
  AiQualityReview, InterviewDetail, InterviewDocument, InterviewDocumentKind, InterviewFilter, InterviewMatchingDetail, InterviewPage,
} from '@/components/features/admin/sessions/types';

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
  async quality(id: string, signal: AbortSignal) {
    return (await axiosClient.get<AiQualityReview>(path + '/quality', { baseURL, params: { id }, signal })).data;
  },
  async matching(id: string, signal: AbortSignal) {
    return (await axiosClient.get<InterviewMatchingDetail>(path + '/matching', { baseURL, params: { id }, signal })).data;
  },
  async document(id: string, kind: InterviewDocumentKind, preview: boolean, signal: AbortSignal) {
    const params = { id, kind, preview };
    return (await axiosClient.get<InterviewDocument>(path + '/document', { baseURL, params, signal })).data;
  },
  async original(id: string, kind: InterviewDocumentKind) {
    const response = await axiosClient.get<Blob>(path + '/document-file', {
      baseURL, params: { id, kind }, responseType: 'blob',
    });
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(String(response.headers['content-disposition']))?.[1];
    return { blob: response.data, name: encoded ? decodeURIComponent(encoded) : kind };
  },
};
