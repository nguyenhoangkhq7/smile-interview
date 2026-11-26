import axiosClient from '@/lib/axiosClient';
import { API_BASE_URL } from '@/lib/axiosClient';
import { expireSession, getTokenExpiresAt } from '@/lib/authSession';
import { useAuthStore } from '@/store/authStore';

export interface VoiceConfig {
  enabled: boolean; stt_model: string; tts_model: string; voice: string;
  format: 'pcm' | 'mp3'; sample_rate: number; language: string;
  avatar: { provider: 'simli'; configured: boolean; sample_rate: 16000 };
}
export interface VoiceTurn { turn_id: string; expected_state_version: number }
export interface RecognitionResult {
  text: string; phase: 'preview' | 'final'; alternative_text?: string;
  review_required: boolean; verification: 'not_requested' | 'agreed' | 'disagreed' | 'unavailable';
}
const path = (id: string) => `/api/v2/sessions/${encodeURIComponent(id)}/interview/voice`;

export const interviewVoice = {
  async config(id: string): Promise<VoiceConfig> {
    return (await axiosClient.get<VoiceConfig>(`${path(id)}/config`)).data;
  },
  async transcribe(id: string, turn: VoiceTurn, audio: string, signal: AbortSignal,
    phase: 'preview' | 'final' = 'final'): Promise<RecognitionResult> {
    const { data } = await axiosClient.post<RecognitionResult>(`${path(id)}/transcribe`,
      { ...turn, audio, phase }, { signal, timeout: 115000 });
    if (typeof data.text !== 'string' || data.phase !== phase || typeof data.review_required !== 'boolean') {
      throw new Error('Máy chủ trả về bản nhận diện không hợp lệ. Hãy cập nhật dịch vụ giọng nói.');
    }
    return data;
  },
  async avatarSession(id: string, turn: VoiceTurn, signal: AbortSignal): Promise<string> {
    const { data } = await axiosClient.post<{ session_token: string }>(`${path(id)}/avatar-session`, turn,
      { signal, timeout: 30000 });
    return data.session_token;
  },
  async speech(id: string, turn: VoiceTurn, signal: AbortSignal): Promise<Response> {
    const token = useAuthStore.getState().token;
    if (!token || (getTokenExpiresAt(token) ?? 0) <= Date.now()) {
      if (token) expireSession(token);
      throw new Error('Phiên đăng nhập đã hết hạn.');
    }
    const response = await fetch(`${API_BASE_URL}${path(id)}/speech`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(turn), signal, cache: 'no-store',
    });
    if (response.status === 401) expireSession(token);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || error.detail || 'Không thể phát câu hỏi. Hãy thử lại.');
    }
    return response;
  },
};
