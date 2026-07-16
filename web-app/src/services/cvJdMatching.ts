import { useAuthStore } from '@/store/authStore';

export interface SkillEntry {
  id: string;
  keyword: string;
  category: 'hard' | 'soft';
  variants?: string[];
}

export interface KeywordMetadata {
  matching_skills: SkillEntry[];
  missing_skills: SkillEntry[];
}

export interface IngestResponse {
  sessionId: string;
  totalChunksCount: number;
  success: boolean;
  resumeId?: number;
  jdId?: number;
  /** Jobscan-style keyword match metadata from matchKeywords.ts */
  keywordMetadata?: KeywordMetadata;
  /** Pre-LLM raw text extracted from CV PDF */
  rawCvText?: string | null;
  /** Pre-LLM raw text extracted from JD PDF */
  rawJdText?: string | null;
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
  evidenceItems?: any[];
  additionalEvidenceItems?: any[];
  scoreBreakdown?: any;
  topPriorityImprovements?: any[];
  eligibility?: any;
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
  async getAssessment(
    sessionId: string,
    forceRefresh = false,
    resumeId?: number | null,
    jdId?: number | null
  ): Promise<AssessmentResponse> {
    let url = `${getBaseUrl()}/assess?sessionId=${sessionId}&forceRefresh=${forceRefresh}`;
    if (resumeId) {
      url += `&resumeId=${resumeId}`;
    }
    if (jdId) {
      url += `&jdId=${jdId}`;
    }
    
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
