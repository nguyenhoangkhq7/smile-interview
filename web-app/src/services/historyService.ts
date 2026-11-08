import axios from 'axios';
import axiosClient, { API_BASE_URL } from '@/lib/axiosClient';
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
  applicationProfileId?: string;
  applicationProfileTitle?: string;
  attemptNumber?: number;
  userId?: string;
  date: string;
  interviewType: 'Technical' | 'Behavioural' | 'Live Coding' | 'Case Study' | 'System Design';
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  cvFileUrl?: string;
  jdFileUrl?: string;
  overallScore?: number;
  status: import('./applicationProfiles').AttemptStatus;
  questions: QuestionFeedback[];
  overallFeedback?: string;
  userRating?: number;
  userFeedbackText?: string;
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

interface BackendSessionTurnDto {
  id?: number | string;
  question?: string;
  answer?: string;
  score?: number;
  strengths?: string;
  improvements?: string;
  suggestedAnswer?: string;
  topicTag?: string;
  isDeepDive?: boolean;
  hrRating?: number;
  hrFeedback?: string;
}

interface BackendSessionResponse {
  id: string;
  applicationProfileId?: string;
  applicationProfileTitle?: string;
  attemptNumber?: number;
  userId?: string;
  resumeId?: string;
  resumeFileName?: string;
  cvFilename?: string;
  cvFileUrl?: string;
  jdId?: string;
  jdTitle?: string;
  jdFilename?: string;
  jdFileUrl?: string;
  status?: SessionHistoryItem['status'];
  interviewType?: SessionHistoryItem['interviewType'];
  roleTitle?: string;
  overallScore?: number;
  overallFeedback?: string;
  userRating?: number;
  userFeedbackText?: string;
  skillGapJson?: string | null;
  gapReportJson?: string | null;
  aiInterviewSessionId?: string | null;
  interviewReportJson?: string | null;
  startedAt?: string;
  date?: string;
  turns?: BackendSessionTurnDto[];
}

function parseJsonSafe<T>(raw?: string | null): T | null {
  if (!raw) return null;
  try {
    return (typeof raw === 'string' ? JSON.parse(raw) : raw) as T;
  } catch {
    return null;
  }
}

export function mapBackendSessionToHistoryItem(sess: BackendSessionResponse): SessionHistoryItem {
  const questions: QuestionFeedback[] = (sess.turns || []).map((t) => ({
    id: t.id != null ? String(t.id) : undefined,
    question: t.question || '',
    answer: t.answer || '',
    score: t.score != null ? Number(t.score) : 0,
    strengths: t.strengths || '',
    improvements: t.improvements || '',
    suggestedAnswer: t.suggestedAnswer || '',
    topicTag: t.topicTag || '',
    isDeepDive: Boolean(t.isDeepDive),
    hrRating: t.hrRating != null ? Number(t.hrRating) : undefined,
    hrFeedback: t.hrFeedback || undefined,
  }));

  return {
    id: sess.id,
    applicationProfileId: sess.applicationProfileId,
    applicationProfileTitle: sess.applicationProfileTitle,
    attemptNumber: sess.attemptNumber,
    userId: sess.userId,
    date: sess.startedAt || sess.date || new Date().toISOString(),
    interviewType: sess.interviewType || 'Technical',
    roleTitle: sess.roleTitle || 'Software Engineer',
    cvFilename: sess.resumeFileName || sess.cvFilename || 'CV.pdf',
    jdFilename: sess.jdTitle || sess.jdFilename || 'JD.pdf',
    cvFileUrl: sess.cvFileUrl,
    jdFileUrl: sess.jdFileUrl,
    resumeId: sess.resumeId ? String(sess.resumeId) : undefined,
    jdId: sess.jdId ? String(sess.jdId) : undefined,
    overallScore: sess.overallScore,
    status: sess.status || 'In progress',
    overallFeedback: sess.overallFeedback,
    userRating: sess.userRating,
    userFeedbackText: sess.userFeedbackText,
    aiInterviewSessionId: sess.aiInterviewSessionId,
    skillGapResults: parseJsonSafe<SkillGapResult[]>(sess.skillGapJson),
    skillGapReport: parseJsonSafe<StaticGapAuditReport>(sess.gapReportJson),
    interviewReport: parseJsonSafe<HITLReportResponse>(sess.interviewReportJson),
    questions,
  };
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return useAuthStore.getState().token;
}

export const historyService = {
  async getHistory(allUsers = false): Promise<SessionHistoryItem[]> {
    try {
      const token = getToken();
      const endpoint = !allUsers && token ? '/api/v1/sessions/user' : '/api/v1/sessions';
      const { data } = await axiosClient.get<BackendSessionResponse[]>(endpoint, {
        baseURL: API_BASE_URL,
      });
      return (data || []).map(mapBackendSessionToHistoryItem);
    } catch (err) {
      console.error('[historyService] Error loading history:', err);
      return [];
    }
  },

  async getSessionById(id: string): Promise<SessionHistoryItem | null> {
    try {
      const { data } = await axiosClient.get<BackendSessionResponse>(
        `/api/v1/sessions/${encodeURIComponent(id)}`,
        { baseURL: API_BASE_URL }
      );
      return mapBackendSessionToHistoryItem(data);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 404) {
        return null;
      }
      console.error(`[historyService] Error loading session ${id}:`, err);
      return null;
    }
  },

  async saveSession(session: SessionSavePayload): Promise<SessionHistoryItem> {
    try {
      const { data } = await axiosClient.post<BackendSessionResponse>(
        '/api/v1/sessions',
        session,
        { baseURL: API_BASE_URL }
      );
      return mapBackendSessionToHistoryItem(data);
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
    const { data } = await axiosClient.post<{ newSessionId: string }>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/clone`,
      null,
      { baseURL: API_BASE_URL }
    );
    return data.newSessionId;
  },
};
