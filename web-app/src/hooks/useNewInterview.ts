'use client';

import { useState, useEffect, useRef, useCallback, type ChangeEvent, type DragEvent } from 'react';
import { useRouter } from 'next/navigation';
import { cvJdMatchingService, type AssessmentResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { type ActiveSession } from '@/components/interview/ActiveSessionsList';
import { useAuthStore } from '@/store/authStore';

export type CvSource  = 'upload' | 'saved' | 'default';
export type JdSource  = 'upload' | 'text' | 'saved';
export type CriteriaFilter = 'all' | 'matched' | 'weak' | 'missing';
export type ActiveView = 'ai-cards' | 'visual-match';


const ROLE_MAP: Record<string, string> = {
  BACKEND: 'Backend Engineer',  FRONTEND: 'Frontend Engineer',
  FULLSTACK: 'Fullstack Engineer', DEVOPS: 'DevOps Engineer',
  DATA_ENGINEERING: 'Data Engineer', ML_ENGINEERING: 'ML Engineer',
  MOBILE: 'Mobile Developer', SECURITY: 'Security Engineer',
  QA: 'QA/QC Engineer', OTHER: 'Software Engineer',
};

export function getDisplayRoleTitle(raw?: string | null): string {
  if (!raw) return 'Software Engineer';
  return ROLE_MAP[raw.toUpperCase()] ?? raw;
}


const DESCRIPTOR_WORDS = new Set([
  'fundamentals', 'fundamental', 'practices', 'practice', 'ecosystem', 'architecture',
  'design', 'management', 'principles', 'principle', 'concepts', 'concept', 'techniques',
  'technique', 'methodology', 'methodologies', 'basics', 'advanced', 'modern', 'best',
  'patterns', 'pattern', 'tools', 'tool', 'skills', 'skill', 'knowledge', 'experience',
  'proficiency', 'understanding', 'overview', 'development', 'implementation', 'integration',
  'systems', 'system', 'and', 'or', 'the', 'for', 'with', 'using', 'via',
  'trong', 'tại', 'ở', 'cho', 'với', 'như', 'các', 'những', 'của', 'và', 'hoặc',
]);

export function splitCriteriaName(name: string): string[] {
  if (!name) return [];
  const tokens: string[] = [];
  const parenMatches = name.match(/\(([^)]+)\)/g) || [];
  for (const p of parenMatches) {
    p.replace(/[()]/g, '').split(/[&/|,\s]+/).forEach((t) => tokens.push(t.trim()));
  }
  name.replace(/\([^)]*\)/g, ' ').split(/[&/|,]+/).forEach((seg) =>
    seg.split(/\s+/).forEach((w) => tokens.push(w.trim()))
  );
  return tokens
    .map((t) => t.replace(/[^a-zA-Z0-9#+.]/g, '').trim())
    .filter((t) => t.length >= 2)
    .filter((t) => !DESCRIPTOR_WORDS.has(t.toLowerCase()));
}

interface KeywordMetadata {
  matching_skills?: string[];
  variation_skills?: string[];
  missing_skills?: string[];
  matchingSkills?: string[];
  variationSkills?: string[];
  missingSkills?: string[];
  [key: string]: unknown;
}

interface KeywordEvidenceItem {
  criteria_name?: string;
  status?: string;
}



interface DatabaseResume {
  id: number;
  file_name: string;
  created_at: string;
  file_url?: string;
}

interface DatabaseJd {
  id: number;
  title: string;
  created_at: string;
}

interface QuestionBankItem {
  question?: string;
  topic?: string;
  good_answer_signals?: string[];
  goodAnswerSignals?: string[];
}

export function extractKeywordsFromEvaluation(evidenceItems: unknown[], additionalEvidenceItems: unknown[]) {
  const matching: string[] = [], variation: string[] = [], missing: string[] = [];
  const items = [...(evidenceItems || []), ...(additionalEvidenceItems || [])] as KeywordEvidenceItem[];
  for (const item of items) {
    const tokens = splitCriteriaName(item.criteria_name || '');
    const s = (item.status || '').toLowerCase();
    if (s === 'matched') matching.push(...tokens);
    else if (s === 'weak')    variation.push(...tokens);
    else if (s === 'missing') missing.push(...tokens);
  }
  const dedupe = (a: string[]) => [...new Set(a)];
  return { matchingSkills: dedupe(matching), variationSkills: dedupe(variation), missingSkills: dedupe(missing) };
}


export function useNewInterview() {
  const router = useRouter();
  const { user } = useAuthStore();

  
  const [cvFile,          setCvFile]          = useState<File | null>(null);
  const [jdFile,          setJdFile]          = useState<File | null>(null);
  const [jdText,          setJdText]          = useState('');
  const [cvSource,        setCvSource]        = useState<CvSource>('upload');
  const [jdSource,        setJdSource]        = useState<JdSource>('upload');
  const [savedResumes,    setSavedResumes]    = useState<DatabaseResume[]>([]);
  const [savedJds,        setSavedJds]        = useState<DatabaseJd[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedJdId,    setSelectedJdId]    = useState<number | null>(null);

  
  const [dragOverCv, setDragOverCv] = useState(false);
  const [dragOverJd, setDragOverJd] = useState(false);

  
  const [cvError,    setCvError]    = useState<string | null>(null);
  const [jdError,    setJdError]    = useState<string | null>(null);
  const [uploading,  setUploading]  = useState(false);
  const [analyzing,  setAnalyzing]  = useState(false);
  const [generating, setGenerating] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [apiError,   setApiError]   = useState<string | null>(null);
  const [isCloning,  setIsCloning]  = useState<string | null>(null);

  
  const [sessionId,  setSessionId]  = useState<string | null>(null);
  const [roleTitle,  setRoleTitle]  = useState('React Frontend Engineer');
  const [ingested,   setIngested]   = useState(false);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);

  
  const [keywordMetadata,  setKeywordMetadata]  = useState<KeywordMetadata | null>(null);
  const [rawCvText,        setRawCvText]        = useState<string | null>(null);
  const [rawJdText,        setRawJdText]        = useState<string | null>(null);
  const [cvDisplayName,    setCvDisplayName]    = useState('CV');
  const [jdDisplayName,    setJdDisplayName]    = useState('JD');
  const [activeResumeId,   setActiveResumeId]   = useState<number | null>(null);
  const [activeJdId,       setActiveJdId]       = useState<number | null>(null);
  const [criteriaFilter,   setCriteriaFilter]   = useState<CriteriaFilter>('all');
  const [activeView,       setActiveView]       = useState<ActiveView>('ai-cards');

  
  const [viewerOpen,  setViewerOpen]  = useState(false);
  const [viewerUrl,   setViewerUrl]   = useState('');
  const [viewerTitle, setViewerTitle] = useState('');

  const fileInputCvRef = useRef<HTMLInputElement>(null);
  const fileInputJdRef = useRef<HTMLInputElement>(null);

  // ── Load active sessions & saved entities ─────────────────
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const sessions = await historyService.getHistory();
        if (!mounted) return;
        setActiveSessions(
          sessions
            .filter((s) => s.status !== 'Completed')
            .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
            .map((s) => ({
              sessionId: s.id, roleTitle: s.roleTitle, cvFilename: s.cvFilename,
              jdFilename: s.jdFilename, status: s.status, date: s.date,
              hasAssessment: s.competencyFitScore !== undefined,
            }))
        );
      } catch (e) { console.error('[useNewInterview] sessions', e); }

      try {
        const [rRes, jRes] = await Promise.all([fetch('/api/resumes'), fetch('/api/jds')]);
        if (rRes.ok && mounted) setSavedResumes(await rRes.json());
        if (jRes.ok && mounted) setSavedJds(await jRes.json());
      } catch (e) { console.error('[useNewInterview] entities', e); }
    })();
    return () => { mounted = false; };
  }, []);

  
  useEffect(() => {
    if (!sessionId) { setKeywordMetadata(null); setRawCvText(null); setRawJdText(null); return; }
    try {
      const raw = sessionStorage.getItem(`keyword_data_${sessionId}`);
      if (raw) {
        const p = JSON.parse(raw);
        setKeywordMetadata(p.keywordMetadata ?? null);
        setRawCvText(p.rawCvText ?? null);
        setRawJdText(p.rawJdText ?? null);
        return;
      }
    } catch {}
    if (!activeResumeId && !activeJdId) return;
    const params = new URLSearchParams();
    if (activeResumeId) params.set('resumeId', String(activeResumeId));
    if (activeJdId)     params.set('jdId', String(activeJdId));
    fetch(`/api/matching/raw-texts?${params}`)
      .then((r) => r.json())
      .then((d) => {
        setKeywordMetadata(null);
        setRawCvText(d.rawCvText ?? null);
        setRawJdText(d.rawJdText ?? null);
        if (d.cvFilename) setCvDisplayName(d.cvFilename);
        if (d.jdFilename) setJdDisplayName(d.jdFilename);
      })
      .catch((e) => console.error('[useNewInterview] raw-texts', e));
  }, [sessionId, activeResumeId, activeJdId]);

  
  const handleViewAssessment = useCallback(async (id: string) => {
    try {
      const session = await historyService.getSessionById(id);
      if (!session) return;
      setAssessment({
        id: '', sessionId: session.id,
        competencyFitScore: session.competencyFitScore || 0,
        technicalDepthScore: session.technicalDepthScore || 0,
        matchLevel: session.matchLevel || '',
        candidateLevel: session.candidateLevel || '',
        roleTypeDetected: session.roleTypeDetected || '',
        yearsOfExperienceEstimate: session.yearsOfExperienceEstimate || '',
        strongAreas: session.strongAreas || [],
        gapAreas: session.gapAreas || [],
        criticalMissingSkills: session.criticalMissingSkills || [],
        sectionWiseFeedback: session.sectionWiseFeedback || {},
        actionableImprovementSuggestions: session.actionableSuggestions || [],
        cached: true, createdAt: session.date,
        evidenceItems: session.evidenceItems || [],
        additionalEvidenceItems: session.additionalEvidenceItems || [],
        scoreBreakdown: session.scoreBreakdown || null,
        topPriorityImprovements: session.topPriorityImprovements || [],
      });
      setSessionId(session.id);
      setRoleTitle(session.roleTitle);
      setIngested(true);
      if (session.resumeId) setActiveResumeId(session.resumeId);
      if (session.jdId)     setActiveJdId(session.jdId);
      if (session.cvFilename) setCvDisplayName(session.cvFilename);
      if (session.jdFilename) setJdDisplayName(session.jdFilename);
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.searchParams.set('sessionId', id);
        window.history.pushState({}, '', url.toString());
      }
    } catch (e) { console.error('[useNewInterview] viewAssessment', e); }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const id = new URLSearchParams(window.location.search).get('sessionId');
    if (id) handleViewAssessment(id);
  }, [handleViewAssessment]);

  
  const validateFile = useCallback((file: File, zone: 'cv' | 'jd'): boolean => {
    const maxSize = 10 * 1024 * 1024;
    if (zone === 'cv') {
      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        setCvError('CV phải ở định dạng PDF (.pdf)'); return false;
      }
      setCvError(null);
    } else {
      const ext = file.name.split('.').pop()?.toLowerCase();
      const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'];
      if (!allowed.includes(file.type) && ext !== 'pdf' && ext !== 'docx' && ext !== 'doc') {
        setJdError('JD phải ở định dạng PDF (.pdf) hoặc Word (.docx, .doc)'); return false;
      }
      setJdError(null);
    }
    if (file.size > maxSize) {
      if (zone === 'cv') setCvError('Kích thước CV không được vượt quá 10MB');
      else               setJdError('Kích thước JD không được vượt quá 10MB');
      return false;
    }
    return true;
  }, []);

  const handleDragOver  = useCallback((e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    if (zone === 'cv') setDragOverCv(true); else setDragOverJd(true);
  }, []);

  const handleDragLeave = useCallback((zone: 'cv' | 'jd') => {
    if (zone === 'cv') setDragOverCv(false); else setDragOverJd(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    handleDragLeave(zone);
    const file = e.dataTransfer.files[0];
    if (file && validateFile(file, zone)) {
      if (zone === 'cv') setCvFile(file); else setJdFile(file);
    }
  }, [handleDragLeave, validateFile]);

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => {
    const file = e.target.files?.[0];
    if (file && validateFile(file, zone)) {
      if (zone === 'cv') setCvFile(file); else setJdFile(file);
    }
  }, [validateFile]);

  const triggerFileSelect = useCallback((zone: 'cv' | 'jd') => {
    if (zone === 'cv') fileInputCvRef.current?.click(); else fileInputJdRef.current?.click();
  }, []);

  
  const handleResumeSession = useCallback(async (id: string) => {
    try {
      const session = await historyService.getSessionById(id);
      if (session) {
        const hasQ = session.questions?.length > 0;
        if (session.competencyFitScore === undefined && !hasQ) {
          setSessionId(session.id); setRoleTitle(session.roleTitle);
          setIngested(true); setAssessment(null); return;
        }
        if (session.competencyFitScore !== undefined && !hasQ) {
          await handleViewAssessment(id); return;
        }
      }
    } catch (e) { console.error('[useNewInterview] resume', e); }
    router.push(`/interview/session/${id}`);
  }, [handleViewAssessment, router]);

  
  const handleRestart = useCallback(async (id: string) => {
    setIsCloning(id);
    try {
      const newId = await historyService.cloneSession(id);
      router.push(`/interview/session/${newId}`);
    } catch (e) {
      console.error('[useNewInterview] restart', e);
    } finally {
      setIsCloning(null);
    }
  }, [router]);

  
  const handleReset = useCallback(() => {
    setAssessment(null);
    setCvFile(null);
    setJdFile(null);
    setJdText('');
    setSelectedResumeId(null);
    setSelectedJdId(null);
    setUploadProgress(0);
    setApiError(null);
    setIngested(false);
    setSessionId(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('sessionId');
      window.history.pushState({}, '', url.toString());
    }
  }, []);

  // ── Continue to Interview Room & Gen Questions ─────────────
  const handleContinueToSelection = useCallback(async () => {
    if (!assessment || !sessionId) return;
    setGenerating(true);
    setApiError(null);
    try {
      const displayCvName = cvSource === 'upload' && cvFile
        ? cvFile.name
        : (savedResumes.find((r) => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');

      const displayJdName = jdSource === 'upload' && jdFile
        ? jdFile.name
        : (jdSource === 'text'
          ? 'JD_Pasted_Text.txt'
          : (savedJds.find((j) => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const qbRes = await fetch('/api/question-banks', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          sessionId: assessment.sessionId,
          questionConfig: { behavioural: 1, technical: 3, coding: 1, systemDesign: 0 },
        }),
      });

      if (!qbRes.ok) throw new Error('Failed to generate question bank');
      const qbData = await qbRes.json();

      const questionsToSave = (qbData.questionBank || qbData.question_bank || []).map((q: QuestionBankItem) => ({
        question: q.question || '',
        answer: '',
        score: 0,
        strengths: '',
        improvements: '',
        suggestedAnswer: '',
        topicTag: q.topic || '',
        isDeepDive: false,
        goodAnswerSignals: q.good_answer_signals || q.goodAnswerSignals || [],
      }));

      const finalRole = assessment.roleTypeDetected
        ? getDisplayRoleTitle(assessment.roleTypeDetected)
        : roleTitle;

      await historyService.saveSession({
        id: assessment.sessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle: finalRole,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined,
        jdId: selectedJdId || undefined,
        status: 'In progress',
        questions: questionsToSave,
        replaceQuestions: true,
        competencyFitScore: assessment.competencyFitScore,
        technicalDepthScore: assessment.technicalDepthScore,
        matchLevel: assessment.matchLevel,
        candidateLevel: assessment.candidateLevel,
        roleTypeDetected: assessment.roleTypeDetected,
        yearsOfExperienceEstimate: assessment.yearsOfExperienceEstimate,
        strongAreas: assessment.strongAreas,
        gapAreas: assessment.gapAreas,
        criticalMissingSkills: assessment.criticalMissingSkills,
        sectionWiseFeedback: assessment.sectionWiseFeedback,
        actionableSuggestions: assessment.actionableImprovementSuggestions || [],
        evidenceItems: assessment.evidenceItems,
        additionalEvidenceItems: assessment.additionalEvidenceItems,
        scoreBreakdown: assessment.scoreBreakdown,
        topPriorityImprovements: assessment.topPriorityImprovements,
        eligibility: assessment.eligibility,
      });

      router.push(`/interview/session/${assessment.sessionId}`);
    } catch (err) {
      console.error('[useNewInterview] continue to selection error:', err);
      setApiError('Đã xảy ra lỗi khi tạo ngân hàng câu hỏi. Vui lòng thử lại sau.');
      setGenerating(false);
    }
  }, [assessment, sessionId, cvFile, cvSource, jdFile, jdSource, savedJds, savedResumes, selectedJdId, selectedResumeId, roleTitle, router]);

  
  const handleUploadAndIngest = useCallback(async () => {
    if (cvSource === 'upload' && !cvFile) return;
    if ((cvSource === 'saved' || cvSource === 'default') && !selectedResumeId) return;
    if (jdSource === 'upload' && !jdFile) return;
    if (jdSource === 'text'   && !jdText.trim()) return;
    if (jdSource === 'saved'  && !selectedJdId) return;

    setUploading(true);
    setApiError(null);

    const tick = setInterval(() => {
      setUploadProgress((p) => {
        if (p >= 80) { clearInterval(tick); return p; }
        return p + 20;
      });
    }, 100);

    const displayCvName = cvSource === 'upload' && cvFile
      ? cvFile.name
      : (savedResumes.find((r) => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
    const displayJdName = jdSource === 'upload' && jdFile
      ? jdFile.name
      : jdSource === 'text'
      ? 'JD_Pasted_Text.txt'
      : (savedJds.find((j) => j.id === selectedJdId)?.title || 'Saved_JD.pdf');
    const initialRole = jdSource === 'saved' && selectedJdId
      ? (savedJds.find((j) => j.id === selectedJdId)?.title || 'Software Engineer')
      : jdSource === 'upload' && jdFile
      ? jdFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
      : 'Software Engineer';

    const newSessionId = `session-${Date.now()}`;
    setRoleTitle(initialRole);

    try {
      await historyService.saveSession({
        id: newSessionId, date: new Date().toISOString(),
        interviewType: 'Technical', roleTitle: initialRole,
        cvFilename: displayCvName, jdFilename: displayJdName,
        status: 'In progress', questions: [],
        resumeId: cvSource !== 'upload' ? selectedResumeId || undefined : undefined,
        jdId: jdSource === 'saved' ? selectedJdId || undefined : undefined,
      });

      setUploading(false);
      setUploadProgress(100);
      setAnalyzing(true);

      const ingestRes = await cvJdMatchingService.ingestCvJd(
        newSessionId,
        cvSource === 'upload' ? cvFile : null,
        jdSource === 'upload' ? jdFile : null,
        jdSource === 'text'   ? jdText : null,
        cvSource !== 'upload' ? selectedResumeId : null,
        jdSource === 'saved'  ? selectedJdId : null,
      );

      if (ingestRes.resumeId) setSelectedResumeId(ingestRes.resumeId);
      if (ingestRes.jdId)     setSelectedJdId(ingestRes.jdId);

      if (ingestRes.keywordMetadata || ingestRes.rawCvText || ingestRes.rawJdText) {
        try {
          sessionStorage.setItem(`keyword_data_${newSessionId}`, JSON.stringify({
            keywordMetadata: ingestRes.keywordMetadata ?? { matching_skills: [], missing_skills: [] },
            rawCvText: ingestRes.rawCvText ?? null,
            rawJdText: ingestRes.rawJdText ?? null,
          }));
        } catch {}
      }

      setSessionId(newSessionId);
      setIngested(true);
      if (ingestRes.resumeId) setActiveResumeId(ingestRes.resumeId);
      if (ingestRes.jdId)     setActiveJdId(ingestRes.jdId);
      setCvDisplayName(displayCvName);
      setJdDisplayName(displayJdName);
      if (ingestRes.rawCvText) setRawCvText(ingestRes.rawCvText);
      if (ingestRes.rawJdText) setRawJdText(ingestRes.rawJdText);
    } catch (err) {
      const error = err as Error;
      console.error('[useNewInterview] ingest error:', error);
      setApiError('Đã xảy ra lỗi khi tải lên và xử lý tài liệu. Vui lòng thử lại sau.');
      setUploading(false);
    } finally {
      setAnalyzing(false);
      clearInterval(tick);
    }
  }, [cvFile, cvSource, jdFile, jdSource, jdText, savedJds, savedResumes, selectedJdId, selectedResumeId]);

  
  const handleRunAssessment = useCallback(async (forceRefresh = false) => {
    if (!sessionId) return;
    setAnalyzing(true);
    setApiError(null);
    try {
      const result = await cvJdMatchingService.getAssessment(sessionId, forceRefresh, selectedResumeId, selectedJdId);
      setAssessment(result);

      const displayCvName = cvSource === 'upload' && cvFile
        ? cvFile.name : (savedResumes.find((r) => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
      const displayJdName = jdSource === 'upload' && jdFile
        ? jdFile.name : jdSource === 'text' ? 'JD_Pasted_Text.txt'
        : (savedJds.find((j) => j.id === selectedJdId)?.title || 'Saved_JD.pdf');
      const finalRole = result.roleTypeDetected
        ? getDisplayRoleTitle(result.roleTypeDetected)
        : initialRoleTitle({ jdSource, selectedJdId, savedJds, jdFile });

      setRoleTitle(finalRole);
      await historyService.saveSession({
        id: result.sessionId || sessionId!, date: new Date().toISOString(),
        interviewType: 'Technical', roleTitle: finalRole,
        cvFilename: displayCvName, jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined, jdId: selectedJdId || undefined,
        status: 'In progress', questions: [], replaceQuestions: false,
        competencyFitScore: result.competencyFitScore,
        technicalDepthScore: result.technicalDepthScore,
        matchLevel: result.matchLevel, candidateLevel: result.candidateLevel,
        roleTypeDetected: result.roleTypeDetected,
        yearsOfExperienceEstimate: result.yearsOfExperienceEstimate,
        strongAreas: result.strongAreas, gapAreas: result.gapAreas,
        criticalMissingSkills: result.criticalMissingSkills,
        sectionWiseFeedback: result.sectionWiseFeedback,
        actionableSuggestions: result.actionableImprovementSuggestions,
        evidenceItems: result.evidenceItems,
        additionalEvidenceItems: result.additionalEvidenceItems,
        scoreBreakdown: result.scoreBreakdown,
        topPriorityImprovements: result.topPriorityImprovements,
        eligibility: result.eligibility,
      });
    } catch (err) {
      const error = err as Error;
      console.error('[useNewInterview] assessment error:', error);
      setApiError('Đã xảy ra lỗi khi kết nối với máy chủ AI. Vui lòng thử lại sau.');
    } finally {
      setAnalyzing(false);
    }
  }, [cvFile, cvSource, jdFile, jdSource, savedJds, savedResumes, selectedJdId, selectedResumeId, sessionId]);

  return {
    user,
    
    cvFile, setCvFile, jdFile, setJdFile, jdText, setJdText,
    cvSource, setCvSource, jdSource, setJdSource,
    savedResumes, savedJds,
    selectedResumeId, setSelectedResumeId,
    selectedJdId, setSelectedJdId,
    
    dragOverCv, dragOverJd,
    handleDragOver, handleDragLeave, handleDrop, handleFileChange, triggerFileSelect,
    fileInputCvRef, fileInputJdRef,
    
    cvError, jdError, uploading, analyzing, generating, uploadProgress, apiError,
    
    sessionId, roleTitle, ingested, assessment, activeSessions, isCloning,
    
    keywordMetadata, rawCvText, rawJdText,
    cvDisplayName, jdDisplayName,
    criteriaFilter, setCriteriaFilter,
    activeView, setActiveView,
    
    viewerOpen, setViewerOpen, viewerUrl, setViewerUrl, viewerTitle, setViewerTitle,
    
    handleUploadAndIngest, handleRunAssessment,
    handleResumeSession, handleRestart, handleViewAssessment, handleReset, handleContinueToSelection,
  };
}


function initialRoleTitle({ jdSource, selectedJdId, savedJds, jdFile }: {
  jdSource: JdSource; selectedJdId: number | null; savedJds: DatabaseJd[]; jdFile: File | null;
}): string {
  if (jdSource === 'saved' && selectedJdId)
    return savedJds.find((j) => j.id === selectedJdId)?.title || 'Software Engineer';
  if (jdSource === 'upload' && jdFile)
    return jdFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
  return 'Software Engineer';
}
