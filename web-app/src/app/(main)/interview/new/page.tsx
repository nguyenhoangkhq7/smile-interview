'use client';

import React, { useEffect, useState, useRef, DragEvent, ChangeEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cvJdMatchingService, AssessmentResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { Calendar, FileText, UploadCloud, FolderOpen, Briefcase, CheckCircle, XCircle, Brain, Lightbulb, X, AlertTriangle, Check, AlertCircle, TrendingUp, UserCheck, Award, ShieldCheck, RefreshCw } from 'lucide-react';
import styles from './new.module.css';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { ActiveSessionsList, type ActiveSession } from '@/components/interview/ActiveSessionsList';
import { useAuthStore } from '@/store/authStore';

export default function NewInterviewPage() {
  const router = useRouter();
  const [roleTitle, setRoleTitle] = useState('React Frontend Engineer');

  // Files & Sources
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState('');
  const [jdInputType, setJdInputType] = useState<'file' | 'text'>('file'); // Note: we'll use jdSource for detailed tabs, keeping this for backward compatibility

  // Saved database entities
  const [savedResumes, setSavedResumes] = useState<any[]>([]);
  const [savedJds, setSavedJds] = useState<any[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedJdId, setSelectedJdId] = useState<number | null>(null);
  const [cvSource, setCvSource] = useState<'upload' | 'saved'>('upload');
  const [jdSource, setJdSource] = useState<'upload' | 'text' | 'saved'>('upload');

  // Drag states
  const [dragOverCv, setDragOverCv] = useState(false);
  const [dragOverJd, setDragOverJd] = useState(false);

  // Error and UI states
  const [cvError, setCvError] = useState<string | null>(null);
  const [jdError, setJdError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [isCloning, setIsCloning] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // Result state
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [criteriaFilter, setCriteriaFilter] = useState<'all' | 'matched' | 'weak' | 'missing'>('all');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ingested, setIngested] = useState(false);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);

  const fileInputCvRef = useRef<HTMLInputElement>(null);
  const fileInputJdRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let mounted = true;

    async function loadActiveSessions() {
      try {
        const sessions = await historyService.getHistory();
        if (!mounted) return;

        const inProgressSessions = sessions
          .filter((item) => item.status !== 'Completed')
          .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .map((item) => ({
            sessionId: item.id,
            roleTitle: item.roleTitle,
            cvFilename: item.cvFilename,
            jdFilename: item.jdFilename,
            status: item.status,
            date: item.date,
            hasAssessment: item.competencyFitScore !== undefined
          }));

        setActiveSessions(inProgressSessions);
      } catch (error) {
        console.error('[NewInterviewPage] Failed to load active sessions:', error);
      }
    }

    async function loadSavedEntities() {
      try {
        const resumesRes = await fetch('/api/resumes');
        if (resumesRes.ok && mounted) {
          const resumes = await resumesRes.json();
          setSavedResumes(resumes);
        }
        const jdsRes = await fetch('/api/jds');
        if (jdsRes.ok && mounted) {
          const jds = await jdsRes.json();
          setSavedJds(jds);
        }
      } catch (error) {
        console.error('[NewInterviewPage] Failed to load saved resumes/JDs:', error);
      }
    }

    loadActiveSessions();
    loadSavedEntities();

    return () => {
      mounted = false;
    };
  }, []);

  // ── Drag & Drop Handlers ──
  const handleDragOver = (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    if (zone === 'cv') setDragOverCv(true);
    else setDragOverJd(true);
  };

  const handleDragLeave = (zone: 'cv' | 'jd') => {
    if (zone === 'cv') setDragOverCv(false);
    else setDragOverJd(false);
  };

  const validateFile = (file: File, zone: 'cv' | 'jd'): boolean => {
    const isCv = zone === 'cv';
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (isCv) {
      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        setCvError('CV phải ở định dạng PDF (.pdf)');
        return false;
      }
      setCvError(null);
    } else {
      const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!allowedTypes.includes(file.type) && ext !== 'pdf' && ext !== 'docx' && ext !== 'doc') {
        setJdError('JD phải ở định dạng PDF (.pdf) hoặc Word (.docx, .doc)');
        return false;
      }
      setJdError(null);
    }

    if (file.size > maxSize) {
      if (isCv) setCvError('Kích thước tệp tin CV không được vượt quá 10MB');
      else setJdError('Kích thước tệp tin JD không được vượt quá 10MB');
      return false;
    }

    return true;
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => {
    e.preventDefault();
    handleDragLeave(zone);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (validateFile(file, zone)) {
        if (zone === 'cv') setCvFile(file);
        else setJdFile(file);
      }
    }
  };

  const triggerFileSelect = (zone: 'cv' | 'jd') => {
    if (zone === 'cv') fileInputCvRef.current?.click();
    else fileInputJdRef.current?.click();
  };

  const handleResumeSession = async (resumeSessionId: string) => {
    try {
      const session = await historyService.getSessionById(resumeSessionId);
      if (session) {
        const hasQuestions = session.questions && session.questions.length > 0;
        const hasQuestionsGenerated = session.actionableSuggestions && session.actionableSuggestions.length > 0;

        // Case 1: CV & JD were uploaded/ingested, but CV assessment hasn't run yet
        if (session.competencyFitScore === undefined && !hasQuestions) {
          setSessionId(session.id);
          setRoleTitle(session.roleTitle);
          setIngested(true);
          setAssessment(null);
          return;
        }

        // Case 2: CV assessment is done, but Question Bank hasn't been generated yet
        if (session.competencyFitScore !== undefined && !hasQuestions && !hasQuestionsGenerated) {
          setAssessment({
            id: '',
            sessionId: session.id,
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
            cached: true,
            createdAt: session.date,
            evidenceItems: session.evidenceItems || [],
            additionalEvidenceItems: session.additionalEvidenceItems || [],
            scoreBreakdown: session.scoreBreakdown || null,
            topPriorityImprovements: session.topPriorityImprovements || []
          });
          setSessionId(session.id);
          setRoleTitle(session.roleTitle);
          setIngested(true);
          return;
        }
      }
    } catch (err) {
      console.error('Error resuming session:', err);
    }
    router.push(`/interview/session/${resumeSessionId}`);
  };

  const handleViewAssessment = async (resumeSessionId: string) => {
    try {
      const session = await historyService.getSessionById(resumeSessionId);
      if (session) {
        setAssessment({
          id: '',
          sessionId: session.id,
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
          cached: true,
          createdAt: session.date,
          evidenceItems: session.evidenceItems || [],
          additionalEvidenceItems: session.additionalEvidenceItems || [],
          scoreBreakdown: session.scoreBreakdown || null,
          topPriorityImprovements: session.topPriorityImprovements || []
        });
        setSessionId(session.id);
        setRoleTitle(session.roleTitle);
        setIngested(true);

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          url.searchParams.set('sessionId', resumeSessionId);
          window.history.pushState({}, '', url.toString());
        }
      }
    } catch (err) {
      console.error('Error loading assessment:', err);
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const urlSessionId = params.get('sessionId');
    if (urlSessionId) {
      handleViewAssessment(urlSessionId);
    }
  }, []);

  const handleUploadAndIngest = async () => {
    // Validate CV selection
    if (cvSource === 'upload' && !cvFile) return;
    if (cvSource === 'saved' && !selectedResumeId) return;

    // Validate JD selection
    if (jdSource === 'upload' && !jdFile) return;
    if (jdSource === 'text' && !jdText.trim()) return;
    if (jdSource === 'saved' && !selectedJdId) return;

    setUploading(true);
    setApiError(null);

    // Simulate upload progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += 20;
      if (progress >= 100) {
        clearInterval(interval);
        setUploadProgress(100);

        // Start API pipeline
        setTimeout(async () => {
          setUploading(false);
          setAnalyzing(true);
          const newSessionId = `session-${Date.now()}`;
          try {
            const displayCvName = cvSource === 'upload' && cvFile 
              ? cvFile.name 
              : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
            
            const displayJdName = jdSource === 'upload' && jdFile 
              ? jdFile.name 
              : (jdSource === 'text' 
                  ? 'JD_Pasted_Text.txt' 
                  : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

            await historyService.saveSession({
              id: newSessionId,
              date: new Date().toISOString(),
              interviewType: 'Technical',
              roleTitle,
              cvFilename: displayCvName,
              jdFilename: displayJdName,
              status: 'In progress',
              questions: [],
              resumeId: cvSource === 'saved' ? (selectedResumeId || undefined) : undefined,
              jdId: jdSource === 'saved' ? (selectedJdId || undefined) : undefined
            });

            // Step 1: Ingestion
            const ingestRes = await cvJdMatchingService.ingestCvJd(
              newSessionId,
              cvSource === 'upload' ? cvFile : null,
              jdSource === 'upload' ? jdFile : null,
              jdSource === 'text' ? jdText : null,
              cvSource === 'saved' ? selectedResumeId : null,
              jdSource === 'saved' ? selectedJdId : null
            );
            
            // If new files were uploaded and saved, update the IDs
            if (ingestRes.resumeId) setSelectedResumeId(ingestRes.resumeId);
            if (ingestRes.jdId) setSelectedJdId(ingestRes.jdId);

            setSessionId(newSessionId);
            setIngested(true);
          } catch (err: any) {
            console.error('Ingestion error:', err);
            setApiError('Đã xảy ra lỗi khi tải lên và xử lý tài liệu. Vui lòng thử lại sau.');
          } finally {
            setAnalyzing(false);
          }
        }, 300);
      } else {
        setUploadProgress(progress);
      }
    }, 100);
  };

  const handleRunAssessment = async () => {
    if (!sessionId) return;
    setAnalyzing(true);
    setApiError(null);
    try {
      const result = await cvJdMatchingService.getAssessment(sessionId);
      setAssessment(result);

      // Save CV match results to database immediately so history is preserved
      const displayCvName = cvSource === 'upload' && cvFile 
        ? cvFile.name 
        : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
      
      const displayJdName = jdSource === 'upload' && jdFile 
        ? jdFile.name 
        : (jdSource === 'text' 
            ? 'JD_Pasted_Text.txt' 
            : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      await historyService.saveSession({
        id: result.sessionId || sessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined,
        jdId: selectedJdId || undefined,
        status: 'In progress',
        questions: [],
        replaceQuestions: false,
        competencyFitScore: result.competencyFitScore,
        technicalDepthScore: result.technicalDepthScore,
        matchLevel: result.matchLevel,
        candidateLevel: result.candidateLevel,
        roleTypeDetected: result.roleTypeDetected,
        yearsOfExperienceEstimate: result.yearsOfExperienceEstimate,
        strongAreas: result.strongAreas,
        gapAreas: result.gapAreas,
        criticalMissingSkills: result.criticalMissingSkills,
        sectionWiseFeedback: result.sectionWiseFeedback,
        evidenceItems: result.evidenceItems,
        additionalEvidenceItems: result.additionalEvidenceItems,
        scoreBreakdown: result.scoreBreakdown,
        topPriorityImprovements: result.topPriorityImprovements
      });
    } catch (err: any) {
      console.error('Assessment error:', err);
      setApiError('Đã xảy ra lỗi khi kết nối với máy chủ AI. Vui lòng thử lại sau.');
    } finally {
      setAnalyzing(false);
    }
  };

  const [generating, setGenerating] = useState(false);

  const handleContinueToSelection = async () => {
    if (!assessment || !sessionId) return;
    setGenerating(true);
    setApiError(null);
    try {
      const displayCvName = cvSource === 'upload' && cvFile 
        ? cvFile.name 
        : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
      
      const displayJdName = jdSource === 'upload' && jdFile 
        ? jdFile.name 
        : (jdSource === 'text' 
            ? 'JD_Pasted_Text.txt' 
            : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      // Generate Question Bank
      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const qbRes = await fetch('/api/question-banks', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          sessionId: assessment.sessionId,
          questionConfig: {
            behavioural: 1,
            technical: 3,
            coding: 1,
            systemDesign: 0
          }
        })
      });

      if (!qbRes.ok) {
        throw new Error('Failed to generate question bank');
      }

      const qbData = await qbRes.json();

      // Persist the assessment result and generated questions (including follow-ups) to the existing session draft
      await historyService.saveSession({
        id: assessment.sessionId,
        date: new Date().toISOString(),
        interviewType: 'Technical',
        roleTitle,
        cvFilename: displayCvName,
        jdFilename: displayJdName,
        resumeId: selectedResumeId || undefined,
        jdId: selectedJdId || undefined,
        status: 'In progress',
        questions: [],
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
        actionableSuggestions: qbData.question_bank || [],
        evidenceItems: assessment.evidenceItems,
        additionalEvidenceItems: assessment.additionalEvidenceItems,
        scoreBreakdown: assessment.scoreBreakdown,
        topPriorityImprovements: assessment.topPriorityImprovements
      });

      // Navigate directly to the interview session room
      router.push(`/interview/session/${assessment.sessionId}`);
    } catch (err) {
      console.error('Error creating interview session:', err);
      setApiError('Đã xảy ra lỗi khi tạo ngân hàng câu hỏi. Vui lòng thử lại sau.');
      setGenerating(false);
    }
  };

  const handleRestart = async (id: string) => {
    try {
      setIsCloning(id);
      const newSessionId = await historyService.cloneSession(id);
      router.push(`/interview/session/${newSessionId}`);
    } catch (err) {
      console.error('Lỗi khi thực hiện lại phiên:', err);
      alert('Không thể thực hiện lại phiên này. Vui lòng thử lại sau.');
      setIsCloning(null);
    }
  };

  const handleReset = () => {
    if (assessment) {
      setAssessment(null);
    }
    setCvFile(null);
    setJdFile(null);
    setJdText('');
    setSelectedResumeId(null);
    setSelectedJdId(null);
    setUploadProgress(0);
    setApiError(null);
    setIngested(false);
    setSessionId(null);

    // Also remove the search parameter from the URL
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('sessionId');
      window.history.pushState({}, '', url.toString());
    }
  };

  // SVG Circular progress values
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = assessment
    ? circumference - (assessment.competencyFitScore / 100) * circumference
    : circumference;
  const depthStrokeDashoffset = assessment
    ? circumference - (assessment.technicalDepthScore / 100) * circumference
    : circumference;

  const renderFeedbackValue = (val: any) => {
    if (val && typeof val === 'object') {
      return val.analysis || JSON.stringify(val);
    }
    return String(val || '');
  };

  const getSectionName = (key: string) => {
    const SECTION_NAMES: Record<string, string> = {
      cs_fundamentals: "Kiến thức Khoa học Máy tính cốt lõi (CS Fundamentals)",
      tech_stack_alignment: "Mức độ tương thích Tech Stack",
      project_technical_depth: "Chiều sâu kỹ thuật trong các dự án",
      engineering_practices: "Quy trình và Thực hành Kỹ nghệ",
      experience_evaluation: "Đánh giá kinh nghiệm làm việc",
      education_and_certifications: "Đánh giá học vấn & chứng chỉ"
    };
    return SECTION_NAMES[key] || key.replace(/_/g, ' ').toUpperCase();
  };

  return (
    <ProtectedRoute>
    <div className={styles.container}>

      {/* Main Content */}
      <main className={styles.content}>
        <div className={styles.titleSection}>
          <h1>Khởi tạo phỏng vấn</h1>
          <p className={styles.subtitle}>Tải lên CV và Mô tả công việc (JD) để AI phân tích mức độ tương thích</p>
        </div>

        {/* Active Sessions — rendered only when not in a result/loading state */}
        {!assessment && !uploading && !analyzing && (
          <ActiveSessionsList
            sessions={activeSessions}
            cloningId={isCloning}
            onResume={handleResumeSession}
            onRestart={handleRestart}
            onViewAssessment={handleViewAssessment}
          />
        )}

        {apiError && (
          <div className={styles.errorBanner}>
            <span>⚠️ {apiError}</span>
            <button onClick={handleReset}>Thử lại</button>
          </div>
        )}

        {/* ── State 1: Ready to Upload ── */}
        {!uploading && !analyzing && !assessment && !ingested && (
          <div className={styles.formSection}>
            <div className={styles.inputGroup}>
              <label htmlFor="roleTitle">Vị trí phỏng vấn mong muốn</label>
              <input
                id="roleTitle"
                type="text"
                className={styles.textInput}
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="Ví dụ: React Frontend Engineer, Java Backend Developer..."
              />
            </div>

            <div className={styles.uploadGrid}>
              {/* CV Upload */}
              <div className={styles.uploadCol}>
                <label className={styles.uploadLabel}>Hồ sơ cá nhân (CV)</label>
                 <div className={styles.tabButtons} style={{ marginBottom: '1rem' }}>
                  <button
                    type="button"
                    className={`${styles.tabButton} ${cvSource === 'upload' ? styles.tabButtonActive : ''}`}
                    onClick={() => setCvSource('upload')}
                  >
                    Tải CV mới
                  </button>
                  <button
                    type="button"
                    className={`${styles.tabButton} ${cvSource === 'saved' ? styles.tabButtonActive : ''}`}
                    onClick={() => setCvSource('saved')}
                  >
                    Chọn CV đã lưu
                  </button>
                </div>

                {cvSource === 'upload' ? (
                  !cvFile ? (
                    <div
                      className={`${styles.dropzone} ${dragOverCv ? styles.dropzoneActive : ''}`}
                      onDragOver={(e) => handleDragOver(e, 'cv')}
                      onDragLeave={() => handleDragLeave('cv')}
                      onDrop={(e) => handleDrop(e, 'cv')}
                      onClick={() => triggerFileSelect('cv')}
                    >
                      <FolderOpen size={48} className={styles.uploadIcon} />
                      <p className={styles.dropzoneText}>
                        Kéo thả CV hoặc <span className={styles.browseLink}>chọn tệp</span>
                      </p>
                      <p className={styles.dropzoneHint}>Hỗ trợ định dạng PDF. Tối đa 10MB.</p>
                      <input
                        ref={fileInputCvRef}
                        type="file"
                        style={{ display: 'none' }}
                        accept=".pdf"
                        onChange={(e) => handleFileChange(e, 'cv')}
                      />
                    </div>
                  ) : (
                    <div className={styles.fileCard}>
                      <div className={styles.fileInfo}>
                        <FileText size={24} className={styles.fileIcon} />
                        <div>
                          <p className={styles.fileName}>{cvFile.name}</p>
                          <p className={styles.fileSize}>{(cvFile.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                      </div>
                      <button className={styles.removeBtn} onClick={() => setCvFile(null)}><X size={14} /></button>
                    </div>
                  )
                ) : (
                  <div className="flex flex-col gap-2">
                    <select
                      className={styles.textInput}
                      style={{ width: '100%', cursor: 'pointer' }}
                      value={selectedResumeId || ''}
                      onChange={(e) => setSelectedResumeId(e.target.value ? parseInt(e.target.value, 10) : null)}
                    >
                      <option value="">-- Chọn CV trong danh sách --</option>
                      {savedResumes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.file_name} ({new Date(r.created_at).toLocaleDateString('vi-VN')})
                        </option>
                      ))}
                    </select>
                    {savedResumes.length === 0 && (
                      <p className="text-xs text-slate-400 mt-1">Không có CV nào được lưu trước đó.</p>
                    )}
                  </div>
                )}
                {cvError && (
                  <span className={styles.errorText} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                    <AlertTriangle size={12} /> {cvError}
                  </span>
                )}
              </div>

              {/* JD Upload / Text Area */}
              <div className={styles.uploadCol}>
                <label className={styles.uploadLabel}>Mô tả công việc (JD)</label>
                <div className={styles.jdTabContainer}>
                  <div className={styles.tabButtons}>
                    <button
                      className={`${styles.tabButton} ${jdSource === 'upload' ? styles.tabButtonActive : ''}`}
                      onClick={() => setJdSource('upload')}
                    >
                      Tải tệp JD
                    </button>
                    <button
                      className={`${styles.tabButton} ${jdSource === 'text' ? styles.tabButtonActive : ''}`}
                      onClick={() => setJdSource('text')}
                    >
                      Dán văn bản
                    </button>
                    <button
                      className={`${styles.tabButton} ${jdSource === 'saved' ? styles.tabButtonActive : ''}`}
                      onClick={() => setJdSource('saved')}
                    >
                      Chọn JD đã lưu
                    </button>
                  </div>

                  {jdSource === 'upload' ? (
                    !jdFile ? (
                      <div
                        className={`${styles.dropzone} ${dragOverJd ? styles.dropzoneActive : ''}`}
                        onDragOver={(e) => handleDragOver(e, 'jd')}
                        onDragLeave={() => handleDragLeave('jd')}
                        onDrop={(e) => handleDrop(e, 'jd')}
                        onClick={() => triggerFileSelect('jd')}
                      >
                        <Briefcase size={48} className={styles.uploadIcon} />
                        <p className={styles.dropzoneText}>
                          Kéo thả JD hoặc <span className={styles.browseLink}>chọn tệp</span>
                        </p>
                        <p className={styles.dropzoneHint}>Hỗ trợ PDF, DOCX, DOC. Tối đa 10MB.</p>
                        <input
                          ref={fileInputJdRef}
                          type="file"
                          style={{ display: 'none' }}
                          accept=".pdf,.docx,.doc"
                          onChange={(e) => handleFileChange(e, 'jd')}
                        />
                      </div>
                    ) : (
                      <div className={styles.fileCard}>
                        <div className={styles.fileInfo}>
                          <FileText size={24} className={styles.fileIcon} />
                          <div>
                            <p className={styles.fileName}>{jdFile.name}</p>
                            <p className={styles.fileSize}>{(jdFile.size / 1024 / 1024).toFixed(2)} MB</p>
                          </div>
                        </div>
                        <button className={styles.removeBtn} onClick={() => setJdFile(null)}><X size={14} /></button>
                      </div>
                    )
                  ) : jdSource === 'text' ? (
                    <textarea
                      className={styles.textAreaJd}
                      value={jdText}
                      onChange={(e) => setJdText(e.target.value)}
                      placeholder="Dán toàn bộ nội dung bản mô tả công việc (JD) vào đây..."
                    />
                  ) : (
                    <div className="flex flex-col gap-2 mt-2">
                      <select
                        className={styles.textInput}
                        style={{ width: '100%', cursor: 'pointer' }}
                        value={selectedJdId || ''}
                        onChange={(e) => setSelectedJdId(e.target.value ? parseInt(e.target.value, 10) : null)}
                      >
                        <option value="">-- Chọn JD trong danh sách --</option>
                        {savedJds.map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.title} ({new Date(j.created_at).toLocaleDateString('vi-VN')})
                          </option>
                        ))}
                      </select>
                      {savedJds.length === 0 && (
                        <p className="text-xs text-slate-400 mt-1">Không có JD nào được lưu trước đó.</p>
                      )}
                    </div>
                  )}
                  {jdError && (
                    <span className={styles.errorText} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      <AlertTriangle size={12} /> {jdError}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className={styles.formActions}>
              <Link href="/" className={styles.secondaryButton}>
                Hủy bỏ
              </Link>
              <button
                className={styles.primaryButton}
                disabled={
                  (cvSource === 'upload' && !cvFile) ||
                  (cvSource === 'saved' && !selectedResumeId) ||
                  (jdSource === 'upload' && !jdFile) ||
                  (jdSource === 'text' && !jdText.trim()) ||
                  (jdSource === 'saved' && !selectedJdId)
                }
                onClick={handleUploadAndIngest}
              >
                Tải lên CV &amp; JD
              </button>
            </div>
          </div>
        )}

        {/* ── State 2: Uploading ── */}
        {uploading && (
          <div className={styles.loadingOverlay}>
            <div className={styles.spinner} />
            <div>
              <h3>Đang tải tài liệu lên...</h3>
              <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>Hồ sơ của bạn đang được truyền tải an toàn</p>
            </div>
            <div className={styles.progressContainer}>
              <div className={styles.progressBar} style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}

        {/* ── State 3: AI Analyzing (Ingesting or Assessing) ── */}
        {analyzing && (
          <div className={styles.loadingOverlay}>
            <div className={styles.spinner} style={{ borderTopColor: '#8b5cf6' }} />
            <div>
              <h3>AI đang xử lý tài liệu của bạn...</h3>
              <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>Quá trình này có thể mất tới 10-35 giây đối với tài liệu mới</p>
            </div>
            <div className={styles.loadingSteps}>
              {!ingested ? (
                <>
                  <p>✓ Trích xuất nội dung văn bản từ PDF...</p>
                  <p>➜ Chuẩn hóa định dạng tài liệu...</p>
                </>
              ) : (
                <p>➜ Đối chiếu và chấm điểm mức độ tương thích kỹ năng...</p>
              )}
            </div>
          </div>
        )}

        {/* ── State 3.5: Ingested Successfully, Ready for Assessment ── */}
        {ingested && !analyzing && !assessment && (
          <div className={styles.formSection} style={{ textAlign: 'center', padding: '3rem' }}>
            <CheckCircle size={64} style={{ color: '#10b981', margin: '0 auto 1.5rem auto' }} />
            <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: '#1e293b', marginBottom: '0.5rem' }}>Tải lên thành công!</h2>
            <p style={{ color: '#64748b', marginBottom: '2rem' }}>
              Tài liệu của bạn đã được chuẩn hóa và lưu trữ. Hệ thống đã sẵn sàng để phân tích độ tương thích.
            </p>
            <div className={styles.formActions} style={{ justifyContent: 'center' }}>
              <button className={styles.secondaryButton} onClick={handleReset}>
                Tải lại tài liệu khác
              </button>
              <button className={styles.primaryButton} onClick={handleRunAssessment}>
                Tiến hành Đánh giá (Assessment)
              </button>
            </div>
          </div>
        )}

        {/* ── State 4: Display Assessment Result ── */}
        {assessment && (
          <div className={styles.resultSection}>
            
            {/* Title & Cache Meta */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                  Kết quả phân tích độ tương thích
                </h2>
                <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '0.25rem 0 0 0' }}>
                  Dành cho vị trí <strong>{roleTitle}</strong>
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', padding: '0.35rem 0.75rem', borderRadius: '0.5rem', backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0', color: '#475569' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: assessment.cached ? '#10b981' : '#f59e0b' }}></span>
                {assessment.cached ? 'Kết quả từ Cache' : 'Phân tích mới'}
              </div>
            </div>

            {/* Dashboard: Circular rings & Badges panel */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
              
              {/* Ring 1: Competency Fit */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Tương thích Năng lực</span>
                <div className={styles.scoreRing}>
                  <svg width="110" height="110" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r={radius} fill="transparent" stroke="#e2e8f0" strokeWidth="8" />
                    <circle
                      cx="60"
                      cy="60"
                      r={radius}
                      fill="transparent"
                      stroke="#4f46e5"
                      strokeWidth="8"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                      transform="rotate(-90 60 60)"
                    />
                  </svg>
                  <span className={styles.scoreVal}>{assessment.competencyFitScore}%</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '1rem', maxWidth: '200px', marginInline: 'auto' }}>Độ khớp tổng quan của CV ứng viên với JD yêu cầu</p>
              </div>

              {/* Ring 2: Technical Depth */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0ea5e9', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Chiều sâu Kỹ thuật</span>
                <div className={styles.scoreRing}>
                  <svg width="110" height="110" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r={radius} fill="transparent" stroke="#e2e8f0" strokeWidth="8" />
                    <circle
                      cx="60"
                      cy="60"
                      r={radius}
                      fill="transparent"
                      stroke="#0ea5e9"
                      strokeWidth="8"
                      strokeDasharray={circumference}
                      strokeDashoffset={depthStrokeDashoffset}
                      strokeLinecap="round"
                      transform="rotate(-90 60 60)"
                    />
                  </svg>
                  <span className={styles.scoreVal} style={{ color: '#0ea5e9' }}>{assessment.technicalDepthScore}%</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '1rem', maxWidth: '200px', marginInline: 'auto' }}>Độ sâu kinh nghiệm và khả năng làm chủ công nghệ cốt lõi</p>
              </div>

              {/* Classifications Badges Panel */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', justifyContent: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.25rem' }}>Phân loại Ứng viên</span>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <TrendingUp size={13} style={{ color: '#4f46e5' }} /> Mức độ khớp:
                  </span>
                  <span style={{
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.5rem',
                    borderRadius: '0.25rem',
                    backgroundColor: assessment.matchLevel?.toLowerCase().includes('high') || assessment.matchLevel?.toLowerCase().includes('rất tốt') ? '#ecfdf5' : assessment.matchLevel?.toLowerCase().includes('moderate') || assessment.matchLevel?.toLowerCase().includes('khớp') ? '#f0f9ff' : '#fffbeb',
                    color: assessment.matchLevel?.toLowerCase().includes('high') || assessment.matchLevel?.toLowerCase().includes('rất tốt') ? '#047857' : assessment.matchLevel?.toLowerCase().includes('moderate') || assessment.matchLevel?.toLowerCase().includes('khớp') ? '#0369a1' : '#b45309',
                    border: '1px solid currentColor'
                  }}>
                    {assessment.matchLevel || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Award size={13} style={{ color: '#8b5cf6' }} /> Định hướng:
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f5f3ff', color: '#6d28d9' }}>
                    {assessment.roleTypeDetected || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <UserCheck size={13} style={{ color: '#0ea5e9' }} /> Cấp bậc:
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f1f5f9', color: '#334155' }}>
                    {assessment.candidateLevel || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <ShieldCheck size={13} style={{ color: '#10b981' }} /> Kinh nghiệm:
                  </span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>
                    {assessment.yearsOfExperienceEstimate || 'N/A'}
                  </span>
                </div>

              </div>

            </div>

            {/* Removed tag badges alignment matrix based on user feedback */}

            {/* Detailed Criteria Alignment Matrix */}
            <div className={styles.evaluationBox} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '1rem', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', flexWrap: 'wrap', gap: '1rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Award size={18} style={{ color: '#4f46e5' }} />
                  <span>Chi tiết đối chiếu tiêu chí (CV vs JD)</span>
                </h3>
                
                {/* Tabs */}
                <div style={{ display: 'flex', gap: '0.25rem', padding: '0.2rem', backgroundColor: '#f1f5f9', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
                  {(['all', 'matched', 'weak', 'missing'] as const).map((tab) => {
                    const labelMap = { all: 'Tất cả', matched: 'Khớp', weak: 'Yếu', missing: 'Thiếu' };
                    const count = [
                      ...(assessment.evidenceItems || []),
                      ...(assessment.additionalEvidenceItems || [])
                    ].filter(item => tab === 'all' || item.status === tab).length;
                    
                    const isActive = criteriaFilter === tab;
                    return (
                      <button
                        key={tab}
                        onClick={() => setCriteriaFilter(tab)}
                        style={{
                          border: 'none',
                          padding: '0.3rem 0.65rem',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          borderRadius: '0.35rem',
                          cursor: 'pointer',
                          backgroundColor: isActive ? '#ffffff' : 'transparent',
                          color: isActive ? '#0f172a' : '#64748b',
                          boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {labelMap[tab]} ({count})
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Score Breakdown if present */}
              {assessment.scoreBreakdown && (
                <div style={{
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  fontSize: '0.82rem',
                  color: '#334155'
                }}>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <TrendingUp size={14} style={{ color: '#10b981' }} />
                    <span>Chi tiết tính điểm (Score Breakdown)</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '0.25rem' }}>
                    <div>
                      <div>• Tổng điểm trọng số tích lũy: <strong style={{ color: '#4f46e5' }}>{assessment.scoreBreakdown.weighted_points_sum}</strong></div>
                      <div>• Tổng trọng số các tiêu chí: <strong style={{ color: '#0f172a' }}>{assessment.scoreBreakdown.total_weight_used}</strong></div>
                    </div>
                    <div>
                      <div>• Công thức tính: <code style={{ backgroundColor: '#e2e8f0', padding: '0.1rem 0.3rem', borderRadius: '0.25rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>SUM(weight * points) / SUM(weight) * 100</code></div>
                      <div>• Chi tiết phép tính: <strong style={{ color: '#ea580c' }}>({assessment.scoreBreakdown.weighted_points_sum} / {assessment.scoreBreakdown.total_weight_used}) * 100 = {assessment.competencyFitScore}%</strong></div>
                    </div>
                  </div>
                  <div style={{ borderTop: '1px solid #e2e8f0', marginTop: '0.75rem', paddingTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
                    <span>Quy đổi trạng thái:</span>
                    <span>Khớp (Matched) = <strong>{assessment.scoreBreakdown.points_config?.matched || 1.0}</strong></span>
                    <span>Yếu (Weak) = <strong>{assessment.scoreBreakdown.points_config?.weak || 0.3}</strong></span>
                    <span>Thiếu (Missing) = <strong>{assessment.scoreBreakdown.points_config?.missing || 0.0}</strong></span>
                  </div>
                </div>
              )}

              {/* Criteria List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {[
                  ...(assessment.evidenceItems || []),
                  ...(assessment.additionalEvidenceItems || [])
                ]
                  .filter(item => criteriaFilter === 'all' || item.status === criteriaFilter)
                  .map((item, idx) => {
                    const statusConfig = {
                      matched: { bg: '#ecfdf5', color: '#047857', border: '#a7f3d0', label: 'Khớp (Matched)', icon: CheckCircle },
                      weak: { bg: '#fffbeb', color: '#b45309', border: '#fde68a', label: 'Cần cải thiện (Weak)', icon: AlertCircle },
                      missing: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5', label: 'Thiếu hụt (Missing)', icon: XCircle }
                    }[item.status as 'matched' | 'weak' | 'missing'] || { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1', label: item.status, icon: AlertCircle };
                    
                    const StatusIcon = statusConfig.icon;

                    return (
                      <div
                        key={idx}
                        style={{
                          border: `1px solid ${statusConfig.border}`,
                          borderRadius: '0.5rem',
                          backgroundColor: '#ffffff',
                          overflow: 'hidden',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.01)'
                        }}
                      >
                        {/* Criterion Header */}
                        <div style={{
                          backgroundColor: statusConfig.bg,
                          padding: '0.6rem 0.85rem',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                          borderBottom: `1px solid ${statusConfig.border}`
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <StatusIcon size={15} style={{ color: statusConfig.color }} />
                            <strong style={{ fontSize: '0.85rem', color: '#0f172a' }}>{item.criteria_name}</strong>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            {item.weight_used !== undefined && (
                              <span style={{ fontSize: '0.72rem', color: '#475569', backgroundColor: 'rgba(255,255,255,0.6)', padding: '0.15rem 0.4rem', borderRadius: '0.25rem', border: '1px solid rgba(0,0,0,0.05)' }}>
                                Trọng số: <strong>{item.weight_used}</strong>
                                {item.score_contribution !== undefined && <> | Điểm đóng góp: <strong>{item.score_contribution}</strong></>}
                              </span>
                            )}
                            <span style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              padding: '0.15rem 0.45rem',
                              borderRadius: '0.25rem',
                              backgroundColor: '#ffffff',
                              color: statusConfig.color,
                              border: `1px solid ${statusConfig.color}`
                            }}>
                              {statusConfig.label}
                            </span>
                          </div>
                        </div>

                        {/* Criterion Details */}
                        <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.8rem' }}>
                          {item.jd_requirement && (
                            <div>
                              <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Yêu cầu tuyển dụng (JD):</div>
                              <div style={{ color: '#0f172a', backgroundColor: '#f8fafc', padding: '0.4rem 0.65rem', borderRadius: '0.25rem', border: '1px solid #f1f5f9' }}>
                                {item.jd_requirement}
                              </div>
                            </div>
                          )}
                          {item.cv_evidence && (
                            <div>
                              <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Minh chứng trong CV:</div>
                              <div style={{ color: '#0f172a', backgroundColor: '#f8fafc', padding: '0.4rem 0.65rem', borderRadius: '0.25rem', border: '1px solid #f1f5f9' }}>
                                {item.cv_evidence}
                              </div>
                            </div>
                          )}
                          {item.reasoning && (
                            <div>
                              <div style={{ fontWeight: 700, color: '#475569', marginBottom: '0.15rem' }}>Phân tích &amp; Đánh giá của AI:</div>
                              <div style={{ color: '#334155', fontStyle: 'italic', paddingLeft: '0.65rem', borderLeft: `3px solid ${statusConfig.color}` }}>
                                {item.reasoning}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* In-depth AI Evaluation Feedbacks */}
            {assessment.sectionWiseFeedback && Object.keys(assessment.sectionWiseFeedback).length > 0 && (
              <div className={styles.evaluationBox} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: 0 }}>
                  <Brain size={18} style={{ color: '#4f46e5' }} />
                  <span>Phân tích chi tiết từ AI</span>
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {Object.entries(assessment.sectionWiseFeedback).map(([section, feedback], idx) => {
                    const cleanText = renderFeedbackValue(feedback);
                    if (!cleanText) return null;
                    return (
                      <div key={idx} style={{ borderLeft: '3px solid #818cf8', paddingLeft: '1rem' }}>
                        <h4 style={{ fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', margin: '0 0 0.25rem 0' }}>
                          {getSectionName(section)}
                        </h4>
                        <p style={{ margin: 0, fontSize: '0.88rem', color: '#334155', lineHeight: '1.5' }}>
                          {cleanText}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Actionable Suggestions */}
            <div className={styles.evaluationBox}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem', fontWeight: 700, color: '#1e293b', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: '0 0 1rem 0' }}>
                <Lightbulb size={18} style={{ color: '#eab308' }} />
                <span>Lời khuyên chuẩn bị phỏng vấn</span>
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {assessment.topPriorityImprovements && assessment.topPriorityImprovements.length > 0 ? (
                  assessment.topPriorityImprovements.map((item: any, index: number) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        gap: '1rem',
                        alignItems: 'flex-start',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.5rem',
                        padding: '1rem',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
                      }}
                    >
                      {/* Priority Bubble */}
                      <div
                        style={{
                          backgroundColor: '#fff7ed',
                          border: '1.5px solid #fdba74',
                          color: '#ea580c',
                          width: '30px',
                          height: '30px',
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 800,
                          fontSize: '0.85rem',
                          flexShrink: 0
                        }}
                      >
                        {item.priority_rank || index + 1}
                      </div>

                      {/* Content */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#1e293b' }}>
                            {item.criteria_name || 'Đề xuất'}
                          </span>
                          <span style={{
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            padding: '0.1rem 0.35rem',
                            borderRadius: '0.25rem',
                            backgroundColor: '#ffedd5',
                            color: '#c2410c'
                          }}>
                            Ưu tiên {item.priority_rank || index + 1}
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.8rem', color: '#475569', lineHeight: '1.5' }}>
                          {item.suggestion}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (assessment.actionableImprovementSuggestions || []).length > 0 ? (
                  (assessment.actionableImprovementSuggestions || []).map((suggestion, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        gap: '0.75rem',
                        alignItems: 'flex-start',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '0.5rem',
                        padding: '0.85rem 1rem',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
                      }}
                    >
                      <span style={{ color: '#ea580c', fontWeight: 'bold', fontSize: '1rem', lineHeight: '1.2' }}>➔</span>
                      <span style={{ fontSize: '#0.8rem', color: '#475569', lineHeight: '1.5' }}>{suggestion}</span>
                    </div>
                  ))
                ) : (
                  <p style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', margin: 0 }}>Không có đề xuất thêm.</p>
                )}
              </div>
            </div>

            {/* Navigation buttons */}
            <div className={styles.formActions} style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1.5rem', margin: 0 }}>
              <button className={styles.secondaryButton} onClick={handleReset}>
                Quay lại
              </button>
              <button className={styles.primaryButton} onClick={handleContinueToSelection}>
                Tiếp tục phỏng vấn ➔
              </button>
            </div>

          </div>
        )}
        {/* ── State 5: Generating Question Bank ── */}
        {generating && (
          <div className={styles.loadingOverlay}>
            <div className={styles.spinner} style={{ borderTopColor: '#f59e0b' }} />
            <div>
              <h3>Đang tạo bộ câu hỏi phỏng vấn...</h3>
              <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>AI đang thiết kế câu hỏi dựa trên CV và JD của bạn</p>
            </div>
            <div className={styles.loadingSteps}>
              <p>➜ Phân tích kỹ năng cốt lõi...</p>
              <p>➜ Lên danh sách câu hỏi phù hợp...</p>
            </div>
          </div>
        )}
      </main>

    </div>
    </ProtectedRoute>
  );
}
