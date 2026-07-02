/**
 * CV & JD Matching Service
 * 
 * Initiates the CV-JD analysis and fetches results.
 * Communicates with the local Next.js proxy API routes to bypass CORS and hide internal ports.
 */

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

    const res = await fetch(`${getBaseUrl()}/ingest/${sessionId}`, {
      method: 'POST',
      body: formData,
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
    const res = await fetch(url);

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Assessment request failed: ${res.statusText} - ${errorText}`);
    }

    return await res.json();
  }
};
