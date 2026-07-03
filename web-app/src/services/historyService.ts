/**
 * Interview Session History Service
 * 
 * Exposes an asynchronous interface to persist and retrieve interview session records.
 * Integrates with PostgreSQL database via server-side Next.js route handlers.
 */

export interface QuestionFeedback {
  question: string;
  answer: string;
  score: number;
  strengths: string;
  improvements: string;
  suggestedAnswer: string;
  topicTag: string;
  isDeepDive: boolean;
}

export interface SessionHistoryItem {
  id: string;
  date: string;
  interviewType: 'Technical' | 'Behavioural' | 'Live Coding' | 'Case Study' | 'System Design';
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
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
}

export interface SessionSavePayload extends SessionHistoryItem {
  replaceQuestions?: boolean;
}

export const historyService = {
  /**
   * Fetch all past practice sessions
   */
  async getHistory(): Promise<SessionHistoryItem[]> {
    try {
      const res = await fetch('/api/history');
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
      const res = await fetch(`/api/history/${id}`);
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
        headers: {
          'Content-Type': 'application/json'
        },
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
    });
    if (!res.ok) {
      throw new Error(`Failed to clone session: ${res.statusText}`);
    }
    const data = await res.json();
    return data.newSessionId;
  }
};
