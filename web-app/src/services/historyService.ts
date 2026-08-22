import type { ImprovementItem } from './cvJdMatching';
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
  cvExtractedText?: string;
  jdExtractedText?: string;
  overallScore?: number;
  status: 'Completed' | 'In progress' | 'Not started';
  questions: QuestionFeedback[];
  overallFeedback?: string;
  competencyFitScore?: number;
  skillsAnalysis?: {
    analysis?: string;
    criticalMissingSkills?: string[];
  };
  experienceEvaluation?: string;
  projectEvaluation?: string;
  technicalDepthScore?: number;
  matchLevel?: string;
  candidateLevel?: string;
  roleTypeDetected?: string;
  yearsOfExperienceEstimate?: string;
  strongAreas?: string[];
  gapAreas?: string[];
  criticalMissingSkills?: string[];
  sectionWiseFeedback?: Record<string, string>;
  actionableSuggestions?: string[];
  resumeId?: number;
  jdId?: number;
  gateEvidenceItems?: unknown[];
  mustHaveEvidenceItems?: unknown[];
  preferToHaveEvidenceItems?: unknown[];
  evidenceItems?: unknown[];
  additionalEvidenceItems?: unknown[];
  scoreBreakdown?: unknown;
  topPriorityImprovements?: unknown[];
  quickWins?: ImprovementItem[];
  skillGaps?: ImprovementItem[];
  hiringRecommendation?: string;
  eligibility?: SessionEligibility | string | null;
  currentStage?: 'CV_JD_MATCHED' | 'QUESTION_BANK_READY' | 'INTERVIEW_IN_PROGRESS' | 'COMPLETED' | string;
}

export interface SessionEligibility {
  status?: string;
  gate_checks?: {
    criteria_name?: string;
    status?: string;
    required_value?: string;
    actual_value?: string;
    passed?: boolean;
    description?: string;
    criterion?: string;
  }[];
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
    'Content-Type': 'application/json'
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
  /**
   * Fetch all past practice sessions
   */
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
      console.error('[historyService] Error loading history, falling back to empty list:', err);
      return [];
    }
  },

  /**
   * Fetch details of a specific session by ID
   */
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

  /**
   * Save or update an interview session in history
   */
  async saveSession(session: SessionSavePayload): Promise<SessionHistoryItem> {
    try {
      const res = await fetch('/api/history', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(session)
      });

      if (!res.ok) {
        throw new Error(`Failed to save session: ${res.statusText}`);
      }

      const data = await res.json();
      return data.session;
    } catch (err) {
      console.error(`[historyService] Error saving session ${session.id}:`, err);
      return session;
    }
  },

  /**
   * Create an initial blank session
   */
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
      replaceQuestions: false
    };

    return this.saveSession(newSession);
  },

  /**
   * Clone a session to restart interview
   */
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
  }
};
