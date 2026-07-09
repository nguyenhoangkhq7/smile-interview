import { useAuthStore } from '@/store/authStore';

export interface IngestResponse {
  sessionId: string;
  totalChunksCount: number;
  success: boolean;
  resumeId?: number;
  jdId?: number;
}

export interface AssessmentResponse {
  id: string;
  sessionId: string;
  competencyFitScore: number;
  technicalDepthScore: number;
  matchLevel: string;
  candidateLevel: string;
  roleTypeDetected: string;
  yearsOfExperienceEstimate: string;
  strongAreas: string[];
  gapAreas: string[];
  criticalMissingSkills: string[];
  sectionWiseFeedback: Record<string, string>;
  actionableImprovementSuggestions: string[];
  cached: boolean;
  createdAt: string;
}

const getBaseUrl = () => {
  // Client-side call to Next.js API route
  return '/api/matching';
};

export const cvJdMatchingService = {
  /**
   * Ingest CV (PDF) and JD (PDF or raw text) for a given session
   */
  async ingestCvJd(
    sessionId: string,
    cvFile: File | null,
    jdFile: File | null,
    jdText: string | null,
    resumeId?: number | null,
    jdId?: number | null
  ): Promise<IngestResponse> {
    const formData = new FormData();
    if (cvFile) {
      formData.append('cvFile', cvFile);
    }
    if (jdFile) {
      formData.append('jdFile', jdFile);
    }
    if (jdText) {
      formData.append('jdText', jdText);
    }
    if (resumeId) {
      formData.append('resumeId', String(resumeId));
    }
    if (jdId) {
      formData.append('jdId', String(jdId));
    }

    const headers: Record<string, string> = {};
    const token = useAuthStore.getState().token;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${getBaseUrl()}/ingest/${sessionId}`, {
      method: 'POST',
      body: formData,
      headers: headers,
    });

    if (!res.ok) {
      throw new Error(`Ingest request failed: ${res.statusText}`);
    }

    return await res.json();
  },

  /**
   * Fetch matching assessment details
   */
  async getAssessment(sessionId: string, forceRefresh = false): Promise<AssessmentResponse> {
    const url = `${getBaseUrl()}/assess?sessionId=${sessionId}&forceRefresh=${forceRefresh}`;
    
    const headers: Record<string, string> = {};
    const token = useAuthStore.getState().token;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(url, {
      headers: headers
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Assessment request failed: ${res.statusText} - ${errorText}`);
    }

    return await res.json();
  }
};
