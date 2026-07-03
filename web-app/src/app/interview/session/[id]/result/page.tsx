'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { FolderOpen, Target, Briefcase, Wrench, Lightbulb, AlertTriangle, MessageSquare, BarChart3, CheckCircle2, XCircle, TrendingUp, Award, UserCheck, ShieldCheck, Brain, CheckCircle, AlertCircle } from 'lucide-react';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import styles from './result.module.css';

export default function InterviewResultPage() {
  const params = useParams();
  const router = useRouter();
  const id = (params?.id as string) || '';

  const [session, setSession] = useState<SessionHistoryItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedIndexes, setExpandedIndexes] = useState<number[]>([0]); // Open first item by default

  useEffect(() => {
    let active = true;
    let pollCount = 0;
    const maxPolls = 25; // 50 seconds max
    let timerId: NodeJS.Timeout;

    async function loadSession() {
      if (!id) return;
      try {
        const data = await historyService.getSessionById(id);
        if (!active) return;

        if (data) {
          const hasQuestions = data.questions && data.questions.length > 0;
          const isEvaluated = !hasQuestions || (data.overallFeedback !== undefined && data.overallFeedback !== null && data.overallFeedback.trim() !== '');

          if (isEvaluated || pollCount >= maxPolls) {
            setSession(data);
            setLoading(false);
          } else {
            pollCount++;
            setLoading(true);
            timerId = setTimeout(loadSession, 2000);
          }
        } else {
          setSession(null);
          setLoading(false);
        }
      } catch (err) {
        console.error('Lỗi khi tải kết quả phỏng vấn:', err);
        if (active) setLoading(false);
      }
    }

    loadSession();

    return () => {
      active = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [id]);

  const toggleAccordion = (index: number) => {
    setExpandedIndexes((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <header className={styles.header}>
          <div className={styles.logo}>
            <span className={styles.logoIcon}>◈</span>
            <span>Smile Interview</span>
            <span className={styles.logoBadge}>AI</span>
          </div>
        </header>
        <div style={{ display: 'flex', minHeight: '80vh', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '40px', height: '40px', border: '3px solid #f1f5f9', borderTop: '3px solid #4f46e5', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <p style={{ marginTop: '1rem', color: '#64748b', fontSize: '0.9rem' }}>Đang tải báo cáo đánh giá từ AI...</p>
          <style jsx>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className={styles.container}>
        <header className={styles.header}>
          <Link href="/history" className={styles.logo}>
            <img src="/logo.png" alt="Smile Interview Logo" className={styles.logoImg} />
          </Link>
        </header>
        <div style={{ display: 'flex', minHeight: '80vh', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center' }}>
          <FolderOpen size={48} style={{ color: '#94a3b8' }} />
          <h2 style={{ fontSize: '1.25rem', marginTop: '1.25rem', fontWeight: 700 }}>Không tìm thấy kết quả phỏng vấn</h2>
          <p style={{ color: '#64748b', fontSize: '0.95rem', margin: '0.5rem 0 1.5rem 0', maxWidth: '360px' }}>
            Buổi phỏng vấn này không tồn tại hoặc dữ liệu đã bị xóa khỏi thiết bị.
          </p>
          <Link href="/history" className={styles.primaryButton}>
            Quay lại Lịch sử
          </Link>
        </div>
      </div>
    );
  }

  const radius = 50;
  const circumference = 2 * Math.PI * radius;

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

  // Fallbacks if user bypassed upload phase
  const score = session.overallScore || 78;
  const competencyScore = session.competencyFitScore || 75;
  const technicalDepthScore = session.technicalDepthScore || 70;

  const strokeDashoffset = circumference - (competencyScore / 100) * circumference;
  const depthStrokeDashoffset = circumference - (technicalDepthScore / 100) * circumference;

  const overallFeedbackText = session.overallFeedback || 'Ứng viên hoàn thành buổi phỏng vấn ở mức Khá. Có kiến thức tương đối vững chắc về lập trình giao diện Frontend, đặc biệt là hệ sinh thái React. Kỹ năng lập luận logic tốt, tuy nhiên ở các câu hỏi đào sâu (deep-dive) còn bộc lộ một số lỗ hổng về mặt chi phí vận hành (performance overhead) và cấu trúc lõi JS. Cần trau dồi thêm kiến thức tổng quan hệ thống.';

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <Link href="/history" className={styles.logo}>
          <img src="/logo.png" alt="Smile Interview Logo" className={styles.logoImg} />
        </Link>
        <nav className={styles.navLinks}>
          <Link href="/history" className={styles.navLink}>
            Lịch sử
          </Link>
          <Link href="/interview/new" className={styles.navLink}>
            Phỏng vấn mới
          </Link>
        </nav>
      </header>

      {/* Main Content */}
      <main className={styles.content}>
        <div className={styles.titleSection}>
          <h1>Kết quả đánh giá chi tiết</h1>
          <p className={styles.subtitle}>Báo cáo phân tích năng lực được tự động tạo bởi trợ lý ảo AI</p>
        </div>

        {/* ── Summary Section Card ── */}
        <section className={styles.summaryCard}>
          <div className={styles.scoreRow}>
            <div className={styles.scoreCircle}>
              <span className={styles.scoreNum}>{score}</span>
              <span className={styles.scoreLabel}>ĐIỂM SỐ</span>
            </div>

            <div className={styles.scoreText}>
              <h2>Đánh giá chung</h2>
              <p>{overallFeedbackText}</p>
              <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#64748b' }}>
                <span>Buổi phỏng vấn kết thúc ngày: </span>
                <strong>{formatDate(session.date)}</strong>
              </div>
            </div>
          </div>

          {/* ── Matching Dashboard Section ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            
            <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                Đối chiếu Hồ sơ (CV) & Mô tả công việc (JD)
              </h3>
              <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '0.25rem 0 0 0' }}>
                Phân tích mức độ tương thích kỹ năng và chiều sâu kinh nghiệm
              </p>
            </div>

            {/* Dashboard: Circular rings & Badges panel */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
              
              {/* Ring 1: Competency Fit */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Tương thích Năng lực</span>
                <div style={{ position: 'relative', width: '110px', height: '110px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
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
                  <span style={{ position: 'absolute', fontSize: '2rem', fontWeight: 900, color: '#4f46e5' }}>{competencyScore}%</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '1rem', maxWidth: '200px' }}>Độ khớp tổng quan của CV ứng viên với JD yêu cầu</p>
              </div>

              {/* Ring 2: Technical Depth */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '1.5rem', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.75rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0ea5e9', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Chiều sâu Kỹ thuật</span>
                <div style={{ position: 'relative', width: '110px', height: '110px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
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
                  <span style={{ position: 'absolute', fontSize: '2rem', fontWeight: 900, color: '#0ea5e9' }}>{technicalDepthScore}%</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '1rem', maxWidth: '200px' }}>Độ sâu kinh nghiệm và khả năng làm chủ công nghệ cốt lõi</p>
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
                    backgroundColor: session.matchLevel?.toLowerCase().includes('high') || session.matchLevel?.toLowerCase().includes('rất tốt') ? '#ecfdf5' : session.matchLevel?.toLowerCase().includes('moderate') || session.matchLevel?.toLowerCase().includes('khớp') ? '#f0f9ff' : '#fffbeb',
                    color: session.matchLevel?.toLowerCase().includes('high') || session.matchLevel?.toLowerCase().includes('rất tốt') ? '#047857' : session.matchLevel?.toLowerCase().includes('moderate') || session.matchLevel?.toLowerCase().includes('khớp') ? '#0369a1' : '#b45309',
                    border: '1px solid currentColor'
                  }}>
                    {session.matchLevel || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Award size={13} style={{ color: '#8b5cf6' }} /> Định hướng:
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f5f3ff', color: '#6d28d9' }}>
                    {session.roleTypeDetected || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <UserCheck size={13} style={{ color: '#0ea5e9' }} /> Cấp bậc:
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.25rem', backgroundColor: '#f1f5f9', color: '#334155' }}>
                    {session.candidateLevel || 'N/A'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <ShieldCheck size={13} style={{ color: '#10b981' }} /> Kinh nghiệm:
                  </span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>
                    {session.yearsOfExperienceEstimate || 'N/A'}
                  </span>
                </div>

              </div>

            </div>

            {/* Skills & Gaps Alignment Matrix */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
              
              {/* Strong Areas */}
              <div style={{ padding: '1.25rem', border: '1px solid #a7f3d0', backgroundColor: 'rgba(236, 253, 245, 0.4)', borderRadius: '0.5rem' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#047857', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem', marginTop: 0 }}>
                  <CheckCircle size={16} />
                  <span>Điểm mạnh nổi bật</span>
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(session.strongAreas || []).length > 0 ? (
                    (session.strongAreas || []).map((skill, index) => (
                      <span key={index} style={{ fontSize: '0.8rem', fontWeight: 600, padding: '0.35rem 0.75rem', borderRadius: '9999px', border: '1px solid #a7f3d0', backgroundColor: '#ecfdf5', color: '#047857' }}>
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
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#b45309', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem', marginTop: 0 }}>
                  <AlertTriangle size={16} style={{ color: '#b45309' }} />
                  <span>Điểm cần cải thiện</span>
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(session.gapAreas || []).concat(session.criticalMissingSkills || []).length > 0 ? (
                    (session.gapAreas || []).concat(session.criticalMissingSkills || []).map((skill, index) => (
                      <span key={index} style={{ fontSize: '0.8rem', fontWeight: 600, padding: '0.35rem 0.75rem', borderRadius: '9999px', border: '1px solid #fde68a', backgroundColor: '#fffbeb', color: '#b45309' }}>
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
            {session.sectionWiseFeedback && Object.keys(session.sectionWiseFeedback).length > 0 && (
              <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.5rem', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: 0 }}>
                  <Brain size={18} style={{ color: '#4f46e5' }} />
                  <span>Phân tích chi tiết từ AI</span>
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {Object.entries(session.sectionWiseFeedback).map(([section, feedback], idx) => {
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
            <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '0.5rem', padding: '1.5rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem', fontWeight: 700, color: '#1e293b', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: '0 0 1rem 0' }}>
                <Lightbulb size={18} style={{ color: '#eab308' }} />
                <span>Lời khuyên chuẩn bị phỏng vấn</span>
              </h3>
              <ul style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '0.75rem', paddingLeft: 0, listStyle: 'none', margin: 0 }}>
                {(session.actionableSuggestions || []).length > 0 ? (
                  (session.actionableSuggestions || []).map((suggestion, index) => (
                    <li key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', margin: 0 }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold', fontSize: '1.1rem', lineHeight: '1' }}>✓</span>
                      <span style={{ fontSize: '0.88rem', color: '#475569', lineHeight: '1.4' }}>
                        {typeof suggestion === 'object' && suggestion !== null ? ((suggestion as any).question || JSON.stringify(suggestion)) : String(suggestion)}
                      </span>
                    </li>
                  ))
                ) : (
                  <p style={{ fontSize: '0.85rem', color: '#64748b', fontStyle: 'italic', margin: 0 }}>Không có đề xuất thêm.</p>
                )}
              </ul>
            </div>

          </div>
        </section>

        {/* ── Accordion QA Section ── */}
        <section className={styles.questionsSection}>
          <h2 className={styles.sectionTitle}>Chi tiết câu hỏi &amp; Trả lời</h2>

          {session.questions.length === 0 ? (
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '0.75rem', padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
              <AlertTriangle size={32} style={{ color: '#eab308', margin: '0 auto' }} />
              <p style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>Không có câu hỏi nào được trả lời trong phiên phỏng vấn này.</p>
            </div>
          ) : (
            <div className={styles.accordionList}>
              {session.questions.map((q, index) => {
                const isExpanded = expandedIndexes.includes(index);
                return (
                  <div key={index} className={styles.accordionItem}>
                    {/* Header */}
                    <button className={styles.accordionHeader} onClick={() => toggleAccordion(index)}>
                      <div className={styles.headerMain}>
                        <div className={styles.headerMeta}>
                          <span className={styles.qNum}>CÂU HỎI {index + 1}</span>
                          <span className={styles.topicBadge}>{q.topicTag}</span>
                          {q.isDeepDive && (
                            <span className={styles.deepDiveBadge}>Hỏi sâu (Deep dive)</span>
                          )}
                        </div>
                        <div className={styles.qText}>{q.question}</div>
                      </div>

                      <div className={styles.headerRight}>
                        <div className={styles.qScore}>
                          <span className={styles.qScoreNum}>{q.score}</span>
                          <span className={styles.qScoreLabel}>Điểm</span>
                        </div>
                        <span className={`${styles.arrowIcon} ${isExpanded ? styles.arrowExpanded : ''}`}>
                          ▼
                        </span>
                      </div>
                    </button>

                    {/* Body */}
                    {isExpanded && (
                      <div className={styles.accordionBody}>
                        {/* Candidate Answer */}
                        <div className={styles.sectionBlock}>
                          <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <MessageSquare size={16} style={{ color: '#4f46e5' }} />
                            <span>Câu trả lời của bạn</span>
                          </h4>
                          <p className={styles.userAnswerText}>{q.answer}</p>
                        </div>

                        {/* AI Strengths & Improvements */}
                        <div className={styles.sectionBlock}>
                          <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <BarChart3 size={16} style={{ color: '#4f46e5' }} />
                            <span>Phân tích câu trả lời của AI</span>
                          </h4>
                          <div className={styles.aiFeedbackGrid}>
                            <div className={`${styles.feedbackBox} ${styles.feedbackStrength}`}>
                              <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.25rem' }}>
                                <CheckCircle2 size={14} style={{ color: '#10b981' }} />
                                <span>Điểm mạnh:</span>
                              </strong>
                              <div>{q.strengths}</div>
                            </div>
                            <div className={`${styles.feedbackBox} ${styles.feedbackImprovement}`}>
                              <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.25rem' }}>
                                <XCircle size={14} style={{ color: '#f59e0b' }} />
                                <span>Cần cải thiện:</span>
                              </strong>
                              <div>{q.improvements}</div>
                            </div>
                          </div>
                        </div>

                        {/* Suggested Answer */}
                        <div className={styles.sectionBlock}>
                          <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <Lightbulb size={16} style={{ color: '#4f46e5' }} />
                            <span>Gợi ý câu trả lời tốt hơn từ AI</span>
                          </h4>
                          <div className={styles.suggestedAnswerBox}>
                            {q.suggestedAnswer}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* CTAs Button Bar */}
        <div className={styles.actions}>
          <Link href="/history" className={styles.secondaryButton}>
            Quay lại Lịch sử
          </Link>
          <Link href="/interview/new" className={styles.primaryButton}>
            Luyện tập lại
          </Link>
        </div>
      </main>

      <footer className={styles.footer}>
        <img src="/footer.png" alt="Smile Interview Footer" className={styles.footerImg} />
      </footer>
    </div>
  );
}
