'use client';

import React, { useEffect, useState, useRef, DragEvent, ChangeEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cvJdMatchingService, AssessmentResponse } from '@/services/cvJdMatching';
import { historyService } from '@/services/historyService';
import { FolderOpen, FileText, Briefcase, CheckCircle, XCircle, Brain, Lightbulb, X, AlertTriangle } from 'lucide-react';
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

  // Files
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState('');
  const [jdInputType, setJdInputType] = useState<'file' | 'text'>('file');

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

    loadActiveSessions();

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
    if (!cvFile || (jdInputType === 'file' && !jdFile) || (jdInputType === 'text' && !jdText.trim())) {
      return;
    }

    setUploading(true);
    setApiError(null);

    // Simulate upload progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += 15;
      if (progress >= 100) {
        clearInterval(interval);
        setUploadProgress(100);

        // Start API pipeline
        setTimeout(async () => {
          setUploading(false);
          setAnalyzing(true);
          const newSessionId = `session-${Date.now()}`;
          try {
            await historyService.createSession(
              newSessionId,
              roleTitle,
              cvFile.name,
              jdInputType === 'file' && jdFile ? jdFile.name : 'JD_Pasted_Text.txt',
              'In progress'
            );

            // Step 1: Ingestion
            await cvJdMatchingService.ingestCvJd(
              newSessionId,
              cvFile,
              jdInputType === 'file' ? jdFile : null,
              jdInputType === 'text' ? jdText : null
            );
            
            setSessionId(newSessionId);
            setIngested(true);
          } catch (err: any) {
            console.error('Ingestion error:', err);
            setApiError('Đã xảy ra lỗi khi tải lên tài liệu. Vui lòng thử lại sau.');
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
      // Persist the assessment result to the existing session draft
      await historyService.createSession(
        assessment.sessionId,
        roleTitle,
        cvFile ? cvFile.name : 'CV_Upload.pdf',
        jdInputType === 'file' && jdFile ? jdFile.name : 'JD_Pasted_Text.txt',
        'In progress'
      );

      // Store full assessment evaluation context into history (so Result page can view it later)
      const currentSession = await historyService.getSessionById(assessment.sessionId);
      if (currentSession) {
        currentSession.competencyFitScore = assessment.competencyFitScore;
        currentSession.technicalDepthScore = assessment.technicalDepthScore;
        currentSession.matchLevel = assessment.matchLevel;
        currentSession.candidateLevel = assessment.candidateLevel;
        currentSession.roleTypeDetected = assessment.roleTypeDetected;
        currentSession.yearsOfExperienceEstimate = assessment.yearsOfExperienceEstimate;
        currentSession.strongAreas = assessment.strongAreas;
        currentSession.gapAreas = assessment.gapAreas;
        currentSession.criticalMissingSkills = assessment.criticalMissingSkills;
        currentSession.sectionWiseFeedback = assessment.sectionWiseFeedback;
        currentSession.actionableSuggestions = assessment.actionableImprovementSuggestions;
        await historyService.saveSession(currentSession);
      }

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
                {!cvFile ? (
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
                      className={`${styles.tabButton} ${jdInputType === 'file' ? styles.tabButtonActive : ''}`}
                      onClick={() => setJdInputType('file')}
                    >
                      Tải tệp JD
                    </button>
                    <button
                      className={`${styles.tabButton} ${jdInputType === 'text' ? styles.tabButtonActive : ''}`}
                      onClick={() => setJdInputType('text')}
                    >
                      Dán văn bản
                    </button>
                  </div>

                  {jdInputType === 'file' ? (
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
                  ) : (
                    <textarea
                      className={styles.textAreaJd}
                      value={jdText}
                      onChange={(e) => setJdText(e.target.value)}
                      placeholder="Dán toàn bộ nội dung bản mô tả công việc (JD) vào đây..."
                    />
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
                  !cvFile ||
                  (jdInputType === 'file' && !jdFile) ||
                  (jdInputType === 'text' && !jdText.trim())
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
            <div className={styles.resultHeader}>
              <div className={styles.scoreRing}>
                <svg width="120" height="120" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r={radius} fill="transparent" stroke="#f1f5f9" strokeWidth="10" />
                  <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    fill="transparent"
                    stroke="#4f46e5"
                    strokeWidth="10"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    transform="rotate(-90 60 60)"
                  />
                </svg>
                <span className={styles.scoreVal}>{assessment.competencyFitScore}%</span>
              </div>
              <div className={styles.scoreText}>
                <h2>Kết quả phân tích độ tương thích</h2>
                <p>
                  CV của bạn có độ khớp đạt <strong>{assessment.competencyFitScore}%</strong> đối với vị trí{' '}
                  <strong>{roleTitle}</strong>. Bạn đã sẵn sàng để phỏng vấn.
                </p>
              </div>
            </div>

            <div className={styles.skillsSection}>
              {/* Matched Skills */}
              <div className={styles.skillsCol}>
                <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  <CheckCircle size={18} style={{ color: '#10b981' }} />
                  <span>Kỹ năng phù hợp</span>
                </h3>
                <div className={styles.skillsList}>
                  {assessment.strongAreas && assessment.strongAreas.length > 0 ? (
                    assessment.strongAreas.map((skill, index) => (
                      <span key={index} className={`${styles.skillBadge} ${styles.skillMatched}`}>
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: '#64748b', fontSize: '0.9rem' }}>Không phát hiện kỹ năng phù hợp nổi bật.</span>
                  )}
                </div>
              </div>

              {/* Missing Skills */}
              <div className={styles.skillsCol}>
                <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  <XCircle size={18} style={{ color: '#f59e0b' }} />
                  <span>Kỹ năng còn thiếu (Cần cải thiện)</span>
                </h3>
                <div className={styles.skillsList}>
                  {assessment.criticalMissingSkills && assessment.criticalMissingSkills.map((skill, index) => (
                    <span key={index} className={`${styles.skillBadge} ${styles.skillMissing}`}>
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* In-depth Evaluation */}
            <div className={styles.evaluationBox}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Brain size={18} style={{ color: '#4f46e5' }} />
                <span>Nhận xét chi tiết từ AI</span>
              </h3>
              {assessment.sectionWiseFeedback && Object.entries(assessment.sectionWiseFeedback).map(([section, feedback], idx) => (
                <div key={idx} style={{ marginBottom: '1rem' }}>
                  <h4 style={{ fontSize: '1rem', color: '#1e293b', marginBottom: '0.25rem' }}>{section}</h4>
                  <p>{feedback}</p>
                </div>
              ))}
            </div>

            {/* Suggestions for interview */}
            <div className={styles.evaluationBox} style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0' }}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Lightbulb size={18} style={{ color: '#eab308' }} />
                <span>Lời khuyên chuẩn bị phỏng vấn</span>
              </h3>
              <ul className={styles.suggestionsList}>
                {assessment.actionableImprovementSuggestions && assessment.actionableImprovementSuggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>

            <div className={styles.formActions}>
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
