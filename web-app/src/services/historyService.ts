import type {
  SkillGapResult,
  StaticGapAuditReport,
  HITLReportResponse,
} from './cvJdMatching';
import { useAuthStore } from '@/store/authStore';

export interface QuestionFeedback {
  id?: string;
  question: string;
  answer: string;
  score: number;
  strengths: string;
  improvements: string;
  suggestedAnswer: string;
  topicTag: string;
  isDeepDive: boolean;
  hrRating?: number;
  hrFeedback?: string;
}

export interface SessionHistoryItem {
  id: string;
  userId?: string;
  date: string;
  interviewType: 'Technical' | 'Behavioural' | 'Live Coding' | 'Case Study' | 'System Design';
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  cvFileUrl?: string;
  jdFileUrl?: string;
  overallScore?: number;
  status: 'Completed' | 'In progress' | 'Not started';
  questions: QuestionFeedback[];
  overallFeedback?: string;
  resumeId?: string;
  jdId?: string;
  aiInterviewSessionId?: string | null;
  currentStage?: string;
  skillGapResults?: SkillGapResult[] | null;
  skillGapReport?: StaticGapAuditReport | null;
  interviewReport?: HITLReportResponse | null;
}

export interface SessionSavePayload extends SessionHistoryItem {
  replaceQuestions?: boolean;
}

function getFetchUrl(path: string): string {
  if (typeof window !== 'undefined') {
    return path;
  }
  const port = process.env.PORT || 3000;
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || `http://localhost:${port}`;
  return `${baseUrl}${path}`;
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (typeof window !== 'undefined') {
    const token = useAuthStore.getState().token;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

export const historyService = {
  async getHistory(): Promise<SessionHistoryItem[]> {
    try {
      const res = await fetch(getFetchUrl('/api/history'), {
        headers: getAuthHeaders(),
        cache: 'no-store',
      });
      if (!res.ok) {
        throw new Error(`Failed to fetch history: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.error('[historyService] Error loading history:', err);
      return [];
    }
  },

  async getSessionById(id: string): Promise<SessionHistoryItem | null> {
    try {
      const res = await fetch(getFetchUrl(`/api/history/${id}`), {
        headers: getAuthHeaders(),
        cache: 'no-store',
      });
      if (!res.ok) {
        if (res.status === 404) return null;
        throw new Error(`Failed to fetch session: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`[historyService] Error loading session ${id}:`, err);
      return null;
    }
  },

  async saveSession(session: SessionSavePayload): Promise<SessionHistoryItem> {
    try {
      const res = await fetch('/api/history', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(session),
      });

      if (!res.ok) {
        throw new Error(`Failed to save session: ${res.statusText}`);
      }

      const data = await res.json();
      return data.session;
    } catch (err) {
      console.error(`[historyService] Error saving session ${session.id}:`, err);
      throw err;
    }
  },

  async createSession(
    id: string,
    roleTitle: string,
    cvFilename: string,
    jdFilename: string,
    status: SessionHistoryItem['status'] = 'Not started'
  ): Promise<SessionHistoryItem> {
    const newSession: SessionSavePayload = {
      id,
      date: new Date().toISOString(),
      interviewType: 'Technical',
      roleTitle,
      cvFilename,
      jdFilename,
      status,
      questions: [],
      replaceQuestions: false,
    };

    return this.saveSession(newSession);
  },

  async cloneSession(sessionId: string): Promise<string> {
    const res = await fetch(`/api/history/${sessionId}/clone`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to clone session: ${res.statusText}`);
    }
    const data = await res.json();
    return data.newSessionId;
  },
};
