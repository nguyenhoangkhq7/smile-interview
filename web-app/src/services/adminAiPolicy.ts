import axios from 'axios';
import axiosClient from '@/lib/axiosClient';
import type { AdaptivePolicyConfig } from '@/components/features/admin/ai-policy/types';

const path = '/api/admin/ai-policy';
const config = { baseURL: '/' };

export interface AiModels {
  interviewModel: string;
  fastModel: string;
  matchingModel: string;
  verifierModel: string;
  skillGapModel: string;
  embeddingModel: string;
  embeddingRevision: string;
  sttModel: string;
  ttsModel: string;
  ttsVoice: string;
  ttsFormat: string;
  ttsSampleRate: number;
  simliFaceId: string;
}

export interface AiSettings {
  models: AiModels;
  policy: AdaptivePolicyConfig;
}

export interface AiCredentials {
  openRouterKey: string;
  simliKey: string;
  resetOpenRouterKey: boolean;
  resetSimliKey: boolean;
}

export const unchangedCredentials: AiCredentials = {
  openRouterKey: '', simliKey: '', resetOpenRouterKey: false, resetSimliKey: false,
};

export interface AiConfiguration {
  revision: number;
  settings: AiSettings;
  overridden: boolean;
  openRouterConfigured: boolean;
  simliConfigured: boolean;
  openRouterOverridden: boolean;
  simliOverridden: boolean;
  embeddingDimension: number | null;
  skillGapParameters: { key: string; value: number }[];
}

export interface AiServiceCheck {
  id: string;
  status: 'UP' | 'DOWN' | 'CONFIGURED' | 'DISABLED' | 'UNKNOWN' | 'DEGRADED';
  latencyMs: number | null;
  detail: string;
}

export const adminAiPolicy = {
  async configuration(signal?: AbortSignal) {
    return (await axiosClient.get<AiConfiguration>(path, { ...config, signal })).data;
  },
  async health(signal?: AbortSignal) {
    return (await axiosClient.get<AiServiceCheck[]>(path + '/health', { ...config, signal })).data;
  },
  async measureHealth(signal?: AbortSignal) {
    return (await axiosClient.post<AiServiceCheck[]>(path + '/health', undefined, { ...config, signal })).data;
  },
  async save(revision: number, settings: AiSettings, credentials: AiCredentials) {
    await axiosClient.put(path, { revision, settings, credentials }, config);
  },
  async reset(revision: number) {
    await axiosClient.post(path + '/reset', { revision }, config);
  },
};

export function aiHealthError(error: unknown, measuring: boolean) {
  if (axios.isAxiosError(error) && error.response?.status === 429) {
    return 'Đang có một lượt đo phản hồi. Vui lòng thử lại sau.';
  }
  return measuring ? 'Không thể đo phản hồi dịch vụ. Vui lòng thử lại.' : 'Không thể kiểm tra trạng thái dịch vụ.';
}

export function aiPolicyError(error: unknown) {
  if (axios.isAxiosError(error)) {
    const code = error.response?.status;
    if (code === 409) return 'Cấu hình vừa được thay đổi. Tải lại trước khi lưu.';
    if (code === 400) return 'Kiểm tra ID model, giới hạn phiên và định dạng PCM khi bật Simli.';
    if (code === 403) return 'Bạn cần quyền quản trị để truy cập cấu hình AI.';
  }
  return 'Không thể kết nối hoặc tải cấu hình AI. Vui lòng thử lại.';
}
