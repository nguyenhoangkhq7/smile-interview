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
const path = (id: string) => `/api/v2/sessions/${encodeURIComponent(id)}/interview/voice`;

export const interviewVoice = {
  async config(id: string): Promise<VoiceConfig> {
    return (await axiosClient.get<VoiceConfig>(`${path(id)}/config`)).data;
  },
  async transcribe(id: string, turn: VoiceTurn, audio: string, signal: AbortSignal): Promise<string> {
    const { data } = await axiosClient.post<{ text: string }>(`${path(id)}/transcribe`,
      { ...turn, audio }, { signal, timeout: 60000 });
    return data.text;
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
