'use client';

import { useState, useEffect, useRef, useCallback, type ChangeEvent, type DragEvent } from 'react';
import { useRouter } from 'next/navigation';
import axiosClient from '@/lib/axiosClient';
import { cvJdMatchingService, type AnalyzeWithReportResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { applicationProfiles } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import { type ActiveSession, type SessionStage } from '@/components/features/interview/NewInterview/ActiveSessionsPanel';
import { useAuthStore } from '@/store/authStore';

export type CvSource = 'upload' | 'saved' | 'default';
export type JdSource = 'upload' | 'text' | 'saved';

interface DatabaseResume {
  id: string;
  file_name: string;
  created_at: string;
  file_url?: string;
}

interface DatabaseJd {
  id: string;
  title: string;
  created_at: string;
}

export function useNewInterview() {
  const router = useRouter();
  const { user, token } = useAuthStore();

  const [cvFile, setCvFile] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState('');
  const [jdTitle, setJdTitle] = useState('');
  const [cvSource, setCvSource] = useState<CvSource>('upload');
  const [jdSource, setJdSource] = useState<JdSource>('upload');
  const [savedResumes, setSavedResumes] = useState<DatabaseResume[]>([]);
  const [savedJds, setSavedJds] = useState<DatabaseJd[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null);
  const [selectedJdId, setSelectedJdId] = useState<string | null>(null);

  const [dragOverCv, setDragOverCv] = useState(false);
  const [dragOverJd, setDragOverJd] = useState(false);

  const [cvError, setCvError] = useState<string | null>(null);
  const [jdError, setJdError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isCloning, setIsCloning] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roleTitle, setRoleTitle] = useState('Software Engineer');
  const [profileTitle, setProfileTitle] = useState('');
  const [company, setCompany] = useState('');
  const [ingested, setIngested] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeWithReportResponse | null>(null);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);

  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerUrl, setViewerUrl] = useState('');
  const [viewerTitle, setViewerTitle] = useState('');

  const fileInputCvRef = useRef<HTMLInputElement>(null);
  const fileInputJdRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const sessions = await historyService.getHistory();
        if (!mounted) return;
        setActiveSessions(
          sessions
            .filter((s) => ['Not started', 'In progress'].includes(s.status))
            .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
            .map((s) => {
              const hasAssessment = Boolean(s.skillGapResults && s.skillGapReport);
              const questions = s.questions || [];
              const hasQuestions = questions.length > 0;
              const answeredCount = questions.filter((q) => q.answer && q.answer.trim() !== '').length;
              const totalQuestions = questions.length;

              let stage: SessionStage = 'UPLOADED';
              if (hasQuestions) {
                stage = 'INTERVIEWING';
              } else if (hasAssessment) {
                stage = 'ASSESSED';
              }

              return {
                sessionId: s.id,
                roleTitle: s.roleTitle,
                cvFilename: s.cvFilename,
                jdFilename: s.jdFilename,
                status: s.status,
                date: s.date,
                hasAssessment,
                hasQuestions,
                competencyFitScore: s.overallScore,
                stage,
                answeredCount,
                totalQuestions,
              };
            })
        );
      } catch (e) {
        console.error('[useNewInterview] sessions', e);
      }

      try {
        const [rRes, jRes] = await Promise.all([
          axiosClient.get<Array<{ id: string; fileName: string; createdAt: string; fileUrl?: string }>>('/api/v1/resumes'),
          axiosClient.get<Array<{ id: string; title: string; createdAt: string }>>('/api/v1/job-descriptions'),
        ]);
        if (mounted) {
          setSavedResumes(
            (rRes.data || []).map((r) => ({
              id: r.id,
              file_name: r.fileName,
              created_at: r.createdAt,
              file_url: r.fileUrl,
            }))
          );
          setSavedJds(
            (jRes.data || []).map((j) => ({
              id: j.id,
              title: j.title,
              created_at: j.createdAt,
            }))
          );
        }
      } catch (e) {
        console.error('[useNewInterview] entities', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [token]);

  const handleRunAssessment = useCallback(
    async (forceRefresh = false, overrideSessionId?: string | null) => {
      const targetSessionId = overrideSessionId || sessionId;
      if (!targetSessionId) return;
      setAnalyzing(true);
      setApiError(null);
      try {
        const result = await cvJdMatchingService.analyzeSkillGap(targetSessionId, forceRefresh);
        setAnalysis(result);
        setSessionId(targetSessionId);
      } catch (err) {
        const error = err as Error;
        console.error('[useNewInterview] analyzeSkillGap error:', error);
        setApiError('Không thể phân tích kỹ năng. Vui lòng thử lại.');
      } finally {
        setAnalyzing(false);
      }
    },
    [sessionId]
  );

  const handleViewAssessment = useCallback(
    async (id: string) => {
      try {
        const session = await historyService.getSessionById(id);
        if (!session) return;
        setSessionId(session.id);
        setRoleTitle(session.roleTitle);
        setProfileTitle(session.roleTitle);
        setIngested(true);
        if (session.skillGapResults && session.skillGapReport) {
          setAnalysis({
            analysis_id: session.id,
            skills: session.skillGapResults,
            report: session.skillGapReport,
          });
        } else {
          await handleRunAssessment(false, session.id);
        }
      } catch (e) {
        console.error('[useNewInterview] viewAssessment', e);
      }
    },
    [handleRunAssessment]
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const id = new URLSearchParams(window.location.search).get('sessionId');
    if (id) handleViewAssessment(id);
  }, [handleViewAssessment]);

  const validateFile = useCallback((file: File, zone: 'cv' | 'jd'): boolean => {
    const maxSize = 10 * 1024 * 1024;
    if (zone === 'cv') {
      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        setCvError('CV phải ở định dạng PDF (.pdf)');
        return false;
      }
      setCvError(null);
    } else {
      const ext = file.name.split('.').pop()?.toLowerCase();
      const allowed = ['application/pdf'];
      if (!allowed.includes(file.type) && ext !== 'pdf') {
        setJdError('JD phải ở định dạng PDF (.pdf)');
        return false;
      }
      setJdError(null);
    }
    if (file.size > maxSize) {
      if (zone === 'cv') setCvError('Kích thước CV không được vượt quá 10MB');
      else setJdError('Kích thước JD không được vượt quá 10MB');
      return false;
    }
    return true;
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    if (zone === 'cv') setDragOverCv(true);
    else setDragOverJd(true);
  }, []);

  const handleDragLeave = useCallback((zone: 'cv' | 'jd') => {
    if (zone === 'cv') setDragOverCv(false);
    else setDragOverJd(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
      e.preventDefault();
      handleDragLeave(zone);
      const file = e.dataTransfer.files[0];
      if (file && validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    },
    [handleDragLeave, validateFile]
  );

  const handleFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => {
      const file = e.target.files?.[0];
      if (file && validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    },
    [validateFile]
  );

  const triggerFileSelect = useCallback((zone: 'cv' | 'jd') => {
    if (zone === 'cv') fileInputCvRef.current?.click();
    else fileInputJdRef.current?.click();
  }, []);

  const handleResumeSession = useCallback(
    async (id: string) => {
      try {
        const session = await historyService.getSessionById(id);
        if (session) {
          if (session.applicationProfileId) {
            router.push(`/applications/${session.applicationProfileId}`);
            return;
          }
          const hasQ = session.questions && session.questions.length > 0;
          if (!hasQ) {
            await handleViewAssessment(id);
            return;
          }
          router.push(`/interview/session/${id}`);
          return;
        }
      } catch (e) {
        console.error('[useNewInterview] resume', e);
      }
      router.push(`/interview/session/${id}`);
    },
    [handleViewAssessment, router]
  );

  const handleRestart = useCallback(
    async (id: string) => {
      setIsCloning(id);
      try {
        const session = await historyService.getSessionById(id);
        if (session?.applicationProfileId) {
          router.push(`/applications/${session.applicationProfileId}`);
          return;
        }
        const newId = await historyService.cloneSession(id);
        router.push(`/interview/session/${newId}`);
      } catch (e) {
        console.error('[useNewInterview] restart', e);
      } finally {
        setIsCloning(null);
      }
    },
    [router]
  );

  const handleReset = useCallback(() => {
    setAnalysis(null);
    setCvFile(null);
    setJdFile(null);
    setJdText('');
    setJdTitle('');
    setSelectedResumeId(null);
    setSelectedJdId(null);
    setUploadProgress(0);
    setApiError(null);
    setIngested(false);
    setSessionId(null);
    setProfileTitle('');
    setCompany('');
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('sessionId');
      window.history.pushState({}, '', url.toString());
    }
  }, []);

  const handleStartInterview = useCallback(async () => {
    const targetSessionId = sessionId || analysis?.analysis_id;
    if (!targetSessionId) return;
    setGenerating(true);
    setApiError(null);
    try {
      const profile = await applicationProfiles.create(targetSessionId, profileTitle.trim() || roleTitle, company.trim());
      router.push(`/applications/${profile.id}`);
    } catch (cause) { setApiError(interviewError(cause)); }
    finally { setGenerating(false); }
  }, [analysis?.analysis_id, router, sessionId, profileTitle, company, roleTitle]);

  const handleUploadAndIngest = useCallback(async () => {
    if (cvSource === 'upload' && !cvFile) return;
    if ((cvSource === 'saved' || cvSource === 'default') && !selectedResumeId) return;
    if (jdSource === 'upload' && !jdFile) return;
    if (jdSource === 'text' && !jdText.trim()) return;
    if (jdSource === 'saved' && !selectedJdId) return;

    setUploading(true);
    setApiError(null);

    const trimmedJdTitle = jdTitle.trim();
    const displayCvName =
      cvSource === 'upload' && cvFile
        ? cvFile.name
        : savedResumes.find((r) => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf';
    const displayJdName =
      jdSource === 'upload' && jdFile
        ? (trimmedJdTitle ? `${trimmedJdTitle}.pdf` : jdFile.name)
        : jdSource === 'text'
        ? (trimmedJdTitle ? `${trimmedJdTitle}.txt` : 'JD_Pasted_Text.txt')
        : savedJds.find((j) => j.id === selectedJdId)?.title || 'Saved_JD.pdf';
    const initialRole =
      trimmedJdTitle ||
      (jdSource === 'saved' && selectedJdId
        ? savedJds.find((j) => j.id === selectedJdId)?.title || 'Software Engineer'
        : jdSource === 'upload' && jdFile
        ? jdFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
        : 'Software Engineer');

    const newSessionId = `session-${Date.now()}`;
    setRoleTitle(initialRole);
    setProfileTitle(initialRole);

    try {
      await historyService.saveSession({
        id: newSessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle: initialRole,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        status: 'In progress',
        questions: [],
        resumeId: cvSource !== 'upload' ? selectedResumeId || undefined : undefined,
        jdId: jdSource === 'saved' ? selectedJdId || undefined : undefined,
      });

      setUploading(false);
      setUploadProgress(100);
      setAnalyzing(true);

      await cvJdMatchingService.ingestCvJd(
        newSessionId,
        cvSource === 'upload' ? cvFile : null,
        jdSource === 'upload' ? jdFile : null,
        jdSource === 'text' ? jdText : null,
        cvSource !== 'upload' ? selectedResumeId : null,
        jdSource === 'saved' ? selectedJdId : null,
        initialRole
      );

      setSessionId(newSessionId);
      setIngested(true);

      await handleRunAssessment(false, newSessionId);
    } catch (err) {
      const error = err as Error;
      console.error('[useNewInterview] ingest error:', error);
      setApiError(error.message || 'Không thể xử lý tài liệu. Vui lòng thử lại.');
      setUploading(false);
    } finally {
      setAnalyzing(false);
    }
  }, [
    cvFile,
    cvSource,
    jdFile,
    jdSource,
    jdText,
    jdTitle,
    savedJds,
    savedResumes,
    selectedJdId,
    selectedResumeId,
    handleRunAssessment,
  ]);

  return {
    user,
    cvFile,
    setCvFile,
    jdFile,
    setJdFile,
    jdText,
    setJdText,
    jdTitle,
    setJdTitle,
    cvSource,
    setCvSource,
    jdSource,
    setJdSource,
    savedResumes,
    savedJds,
    selectedResumeId,
    setSelectedResumeId,
    selectedJdId,
    setSelectedJdId,
    dragOverCv,
    dragOverJd,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileChange,
    triggerFileSelect,
    fileInputCvRef,
    fileInputJdRef,
    cvError,
    jdError,
    uploading,
    analyzing,
    generating,
    uploadProgress,
    apiError,
    sessionId,
    roleTitle,
    profileTitle,
    setProfileTitle,
    company,
    setCompany,
    ingested,
    analysis,
    activeSessions,
    isCloning,
    viewerOpen,
    setViewerOpen,
    viewerUrl,
    setViewerUrl,
    viewerTitle,
    setViewerTitle,
    handleUploadAndIngest,
    handleRunAssessment,
    handleResumeSession,
    handleRestart,
    handleViewAssessment,
    handleReset,
    handleStartInterview,
  };
}
