'use client';

import React, { useEffect, useState, useRef, DragEvent, ChangeEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cvJdMatchingService, AssessmentResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { FolderOpen, FileText, Briefcase, CheckCircle, XCircle, Brain, Lightbulb, X, AlertTriangle, Check, AlertCircle, TrendingUp, UserCheck, Award, ShieldCheck } from 'lucide-react';
import styles from './new.module.css';

type ActiveSessionState = {
  sessionId: string;
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  status: string;
  date: string;
};

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
  const [apiError, setApiError] = useState<string | null>(null);

  // Result state
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ingested, setIngested] = useState(false);
  const [activeSessions, setActiveSessions] = useState<ActiveSessionState[]>([]);

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
            date: item.date
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

  const handleResumeSession = (resumeSessionId: string) => {
    router.push(`/interview/session/${resumeSessionId}`);
  };

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
    } catch (err: any) {
      console.error('Assessment error:', err);
      setApiError('Đã xảy ra lỗi khi kết nối với máy chủ AI. Vui lòng thử lại sau.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleContinueToSelection = async () => {
    if (!assessment) return;
    try {
      const displayCvName = cvSource === 'upload' && cvFile 
        ? cvFile.name 
        : (savedResumes.find(r => r.id === selectedResumeId)?.file_name || 'Saved_CV.pdf');
      
      const displayJdName = jdSource === 'upload' && jdFile 
        ? jdFile.name 
        : (jdSource === 'text' 
            ? 'JD_Pasted_Text.txt' 
            : (savedJds.find(j => j.id === selectedJdId)?.title || 'Saved_JD.pdf'));

      // Persist the assessment result to the existing session draft
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
        actionableSuggestions: assessment.actionableImprovementSuggestions
      });

      router.push(`/interview/new/type?sessionId=${assessment.sessionId}`);
    } catch (err) {
      console.error('Error creating interview session:', err);
    }
  };

  const handleReset = () => {
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
    <div className={styles.container}>
      <header className={styles.header}>
        <Link href="/history" className={styles.logo}>
          <img src="/logo.png" alt="Smile Interview Logo" className={styles.logoImg} />
        </Link>
        <nav className={styles.navLinks}>
          <Link href="/history" className={styles.navLink}>
            Lịch sử
          </Link>
          <span className={`${styles.navLink} ${styles.browseLink}`} style={{ cursor: 'default' }}>
            Phỏng vấn mới
          </span>
        </nav>
      </header>

      {/* Main Content */}
      <main className={styles.content}>
        <div className={styles.titleSection}>
          <h1>Khởi tạo phỏng vấn</h1>
          <p className={styles.subtitle}>Tải lên CV và Mô tả công việc (JD) để AI phân tích mức độ tương thích</p>
        </div>

        {activeSessions.length > 0 && !assessment && !uploading && !analyzing && (
          <section className={styles.formSection} style={{ marginBottom: '1.5rem' }}>
            <div className={styles.titleSection} style={{ marginBottom: '1rem' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Phiên đang thực hiện</h2>
                <p className={styles.subtitle} style={{ marginTop: '0.35rem' }}>
                  Các phiên này đang được quản lý trong PostgreSQL, bạn có thể tiếp tục ngay từ đây.
                </p>
              </div>
              <Link href="/history" className={styles.secondaryButton}>
                Mở toàn bộ lịch sử
              </Link>
            </div>

            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {activeSessions.slice(0, 3).map((session) => (
                <div
                  key={session.sessionId}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    padding: '1rem 1.1rem',
                    borderRadius: '0.9rem',
                    background: 'linear-gradient(135deg, rgba(79,70,229,0.06), rgba(14,165,233,0.04))',
                    border: '1px solid rgba(99,102,241,0.12)'
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                      <strong style={{ color: '#0f172a' }}>{session.roleTitle}</strong>
                      <span style={{ fontSize: '0.72rem', padding: '0.18rem 0.45rem', borderRadius: '999px', backgroundColor: '#e0e7ff', color: '#3730a3', fontWeight: 700 }}>
                        {session.status}
                      </span>
                    </div>
                    <p style={{ margin: '0.35rem 0 0', fontSize: '0.86rem', color: '#64748b' }}>
                      {session.cvFilename} • {session.jdFilename}
                    </p>
                    <p style={{ margin: '0.25rem 0 0', fontSize: '0.78rem', color: '#94a3b8' }}>
                      Cập nhật: {new Date(session.date).toLocaleString('vi-VN')}
                    </p>
                  </div>

                  <button className={styles.primaryButton} onClick={() => handleResumeSession(session.sessionId)}>
                    Tiếp tục phiên này
                  </button>
                </div>
              ))}
            </div>
          </section>
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
                      <FolderOpen size={48} className={styles.uploadIcon} style={{ color: '#6366f1', marginBottom: '1rem' }} />
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
                        <FileText size={24} className={styles.fileIcon} style={{ color: '#6366f1', marginRight: '8px' }} />
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
                        <Briefcase size={48} className={styles.uploadIcon} style={{ color: '#6366f1', marginBottom: '1rem' }} />
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
                          <FileText size={24} className={styles.fileIcon} style={{ color: '#3b82f6', marginRight: '8px' }} />
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
              <Link href="/history" className={styles.secondaryButton}>
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

            {/* Skills & Gaps Alignment Matrix */}
            <div className={styles.skillsSection}>
              
              {/* Strong Areas */}
              <div style={{ padding: '1.25rem', border: '1px solid #a7f3d0', backgroundColor: 'rgba(236, 253, 245, 0.4)', borderRadius: '0.5rem' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#047857', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem' }}>
                  <CheckCircle size={16} />
                  <span>Điểm mạnh nổi bật</span>
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(assessment.strongAreas || []).length > 0 ? (
                    (assessment.strongAreas || []).map((skill, index) => (
                      <span key={index} className={`${styles.skillBadge} ${styles.skillMatched}`}>
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: '#64748b', fontSize: '0.85rem', fontStyle: 'italic' }}>Không tìm thấy thế mạnh nổi bật.</span>
                  )}
                </div>
              </div>

              {/* Missing & Gaps */}
              <div style={{ padding: '1.25rem', border: '1px solid #fde68a', backgroundColor: 'rgba(255, 251, 235, 0.4)', borderRadius: '0.5rem' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#b45309', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem' }}>
                  <AlertCircle size={16} />
                  <span>Điểm cần cải thiện</span>
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(assessment.gapAreas || []).concat(assessment.criticalMissingSkills || []).length > 0 ? (
                    (assessment.gapAreas || []).concat(assessment.criticalMissingSkills || []).map((skill, index) => (
                      <span key={index} className={`${styles.skillBadge} ${styles.skillMissing}`}>
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: '#64748b', fontSize: '0.85rem', fontStyle: 'italic' }}>Không phát hiện thiếu hụt kỹ năng lớn.</span>
                  )}
                </div>
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
              <ul className={styles.suggestionsList} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '0.75rem', paddingLeft: 0, listStyle: 'none' }}>
                {(assessment.actionableImprovementSuggestions || []).length > 0 ? (
                  (assessment.actionableImprovementSuggestions || []).map((suggestion, index) => (
                    <li key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', margin: 0 }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold', fontSize: '1.1rem', lineHeight: '1' }}>✓</span>
                      <span style={{ fontSize: '0.88rem', color: '#475569', lineHeight: '1.4' }}>{suggestion}</span>
                    </li>
                  ))
                ) : (
                  <p style={{ fontSize: '0.85rem', color: '#64748b', fontStyle: 'italic' }}>Không có đề xuất thêm.</p>
                )}
              </ul>
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
      </main>

      <footer className={styles.footer}>
        <img src="/footer.png" alt="Smile Interview Footer" className={styles.footerImg} />
      </footer>
    </div>
  );
}
