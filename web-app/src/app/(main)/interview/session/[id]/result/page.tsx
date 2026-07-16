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
          const isEvaluated = data.status !== 'Completed' || (data.overallFeedback !== undefined && data.overallFeedback !== null && data.overallFeedback.trim() !== '');

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

  interface FinalReport {
    strengths: string[];
    weaknesses: string[];
    recommendations: string[];
    overall_score: number;
    overall_summary: string;
    hiring_recommendation: string;
  }

  let report: FinalReport | null = null;
  if (session.overallFeedback) {
    try {
      report = typeof session.overallFeedback === 'object'
        ? session.overallFeedback
        : JSON.parse(session.overallFeedback);
    } catch {
      report = null;
    }
  }

  let strengths = session.strongAreas || [];
  let weaknesses = session.gapAreas || [];
  let recommendations = session.actionableSuggestions || [];
  let score = 0;
  let overallFeedbackText = '';
  let hiringRecommendation = '';

  const isPostInterviewEvaluated = session.status === 'Completed' || report !== null;

  if (isPostInterviewEvaluated) {
    // 1. Post-interview report loaded
    score = session.overallScore || 0;
    overallFeedbackText = session.overallFeedback || '';
    hiringRecommendation = session.hiringRecommendation || '';

    if (report) {
      strengths = report.strengths || (report as any).strongAreas || strengths;
      weaknesses = report.weaknesses || (report as any).gapAreas || weaknesses;
      recommendations = report.recommendations || (report as any).actionableSuggestions || recommendations;
      
      const rawScore = report.overall_score !== undefined ? report.overall_score : (report as any).overallScore;
      if (rawScore !== undefined) {
        score = rawScore <= 10 ? rawScore * 10 : rawScore;
      }
      
      overallFeedbackText = report.overall_summary || (report as any).overallFeedback || overallFeedbackText;
      hiringRecommendation = report.hiring_recommendation || (report as any).hiringRecommendation || hiringRecommendation;
    }

    // Auto-calculate hiringRecommendation if it's 'N/A' or empty
    if (!hiringRecommendation || hiringRecommendation === 'N/A') {
      const numericScore = typeof score === 'number' ? score : parseInt(score) || 0;
      if (numericScore >= 90) {
        hiringRecommendation = 'Strong Hire';
      } else if (numericScore >= 70) {
        hiringRecommendation = 'Hire';
      } else if (numericScore >= 40) {
        hiringRecommendation = 'No Hire';
      } else {
        hiringRecommendation = 'Strong No Hire';
      }
    }
  } else {
    // 2. CV Evaluation report loaded
    score = session.competencyFitScore || 0;
    
    // Construct a beautiful CV match overall feedback summary
    overallFeedbackText = `Báo cáo đánh giá mức độ tương thích của hồ sơ ứng viên (CV) đối với mô tả công việc (JD).\n` +
      `• Mức độ phù hợp năng lực: ${session.matchLevel || 'N/A'}\n` +
      `• Cấp độ ứng viên phù hợp: ${session.candidateLevel || 'N/A'}\n` +
      `• Ước tính số năm kinh nghiệm: ${session.yearsOfExperienceEstimate || 'N/A'}`;
      
    hiringRecommendation = 'Đánh giá CV';
  }

  return (
    <div className={styles.container}>

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
              <span className={styles.scoreNum}>{score <= 10 ? `${score}/10` : score}</span>
              <span className={styles.scoreLabel}>ĐIỂM SỐ</span>
            </div>

            <div className={styles.scoreText}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                <h2 style={{ margin: 0 }}>Đánh giá chung</h2>
                {hiringRecommendation && (
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 850,
                    padding: '0.2rem 0.6rem',
                    borderRadius: '9999px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    backgroundColor: hiringRecommendation.toLowerCase().includes('no') ? '#fef2f2' : (hiringRecommendation.toLowerCase().includes('hire') ? '#ecfdf5' : '#fffbeb'),
                    color: hiringRecommendation.toLowerCase().includes('no') ? '#b91c1c' : (hiringRecommendation.toLowerCase().includes('hire') ? '#047857' : '#d97706'),
                    border: `1px solid ${hiringRecommendation.toLowerCase().includes('no') ? '#fca5a5' : (hiringRecommendation.toLowerCase().includes('hire') ? '#a7f3d0' : '#fcd34d')}`
                  }}>
                    Quyết định: {hiringRecommendation}
                  </span>
                )}
              </div>
              <p>{overallFeedbackText}</p>
              <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#64748b' }}>
                <span>Buổi phỏng vấn kết thúc ngày: </span>
                <strong>{formatDate(session.date)}</strong>
              </div>
            </div>
          </div>

          {/* Eligibility Card */}
          {session.eligibility && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              padding: '1.25rem',
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '0.5rem',
              marginTop: '1.5rem',
              marginBottom: '0.5rem'
            }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.1rem' }}>Kết quả sàng lọc hồ sơ</span>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', marginBottom: '0.1rem' }}>
                <span style={{ fontSize: '0.82rem', color: '#64748b' }}>Trạng thái:</span>
                <span style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  padding: '0.2rem 0.5rem',
                  borderRadius: '0.25rem',
                  backgroundColor: session.eligibility.status === 'ELIGIBLE' ? '#ecfdf5' : '#fef2f2',
                  color: session.eligibility.status === 'ELIGIBLE' ? '#047857' : '#b91c1c',
                  border: '1px solid currentColor'
                }}>
                  {session.eligibility.status === 'ELIGIBLE' ? 'ĐỦ ĐIỀU KIỆN (ELIGIBLE)' : 'CHƯA ĐỦ ĐIỀU KIỆN'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                {(session.eligibility.gate_checks || []).map((check: any, idx: number) => {
                  const isMet = check.status === 'met' || check.status === 'MET';
                  return (
                    <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', padding: '0.4rem 0.65rem', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '0.35rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ fontSize: '0.78rem', color: '#0f172a' }}>{check.criteria_name}</strong>
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: isMet ? '#047857' : '#b91c1c', display: 'flex', alignItems: 'center', gap: '0.15rem' }}>
                          {isMet ? '✓ Đạt' : '✗ Chưa đạt'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                        Yêu cầu: <span style={{ color: '#475569', fontWeight: 500 }}>{check.required_value}</span>
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                        Thực tế: <span style={{ color: isMet ? '#047857' : '#b91c1c', fontWeight: 600 }}>{check.actual_value}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Strengths & Weaknesses Panel */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginTop: '1.5rem' }}>
            
            {/* Strengths */}
            <div style={{ padding: '1.25rem', border: '1px solid #a7f3d0', backgroundColor: '#f0fdf4', borderRadius: '0.5rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#15803d', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.75rem', marginTop: 0 }}>
                <CheckCircle size={16} />
                <span>Điểm mạnh nổi bật</span>
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {(strengths || []).length > 0 ? (
                  (strengths || []).map((strength: any, index: number) => {
                    const text = typeof strength === 'object' && strength !== null ? (strength.area || strength.name || JSON.stringify(strength)) : strength;
                    return (
                      <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                        <span style={{ color: '#15803d', fontWeight: 'bold' }}>✓</span>
                        <span style={{ fontSize: '0.82rem', color: '#1e293b', lineHeight: '1.4' }}>{text}</span>
                      </div>
                    );
                  })
                ) : (
                  <span style={{ color: '#64748b', fontSize: '0.85rem', fontStyle: 'italic' }}>Không ghi nhận điểm mạnh.</span>
                )}
              </div>
            </div>

            {/* Weaknesses */}
            <div style={{ padding: '1.25rem', border: '1px solid #fca5a5', backgroundColor: '#fef2f2', borderRadius: '0.5rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#b91c1c', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.75rem', marginTop: 0 }}>
                <AlertCircle size={16} style={{ color: '#b91c1c' }} />
                <span>Điểm cần cải thiện</span>
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {(weaknesses || []).length > 0 ? (
                  (weaknesses || []).map((weakness: any, index: number) => {
                    const text = typeof weakness === 'object' && weakness !== null ? (weakness.area || weakness.name || JSON.stringify(weakness)) : weakness;
                    return (
                      <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                        <span style={{ color: '#b91c1c', fontWeight: 'bold' }}>✗</span>
                        <span style={{ fontSize: '0.82rem', color: '#1e293b', lineHeight: '1.4' }}>{text}</span>
                      </div>
                    );
                  })
                ) : (
                  <span style={{ color: '#64748b', fontSize: '0.85rem', fontStyle: 'italic' }}>Không ghi nhận điểm yếu.</span>
                )}
              </div>
            </div>

          </div>

          {/* Recommendations */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '0.5rem', padding: '1.25rem', marginTop: '1.5rem' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem', margin: '0 0 0.75rem 0' }}>
              <Lightbulb size={18} style={{ color: '#eab308' }} />
              <span>Khuyến nghị từ AI</span>
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {(recommendations || []).length > 0 ? (
                (recommendations || []).map((suggestion: any, index: number) => {
                  const text = typeof suggestion === 'object' && suggestion !== null ? (suggestion.question || suggestion.suggestion || JSON.stringify(suggestion)) : suggestion;
                  return (
                    <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                      <span style={{ color: '#ea580c', fontWeight: 'bold' }}>➔</span>
                      <span style={{ fontSize: '0.82rem', color: '#334155', lineHeight: '1.4' }}>{text}</span>
                    </div>
                  );
                })
              ) : (
                <p style={{ fontSize: '0.82rem', color: '#64748b', fontStyle: 'italic', margin: 0 }}>Không có đề xuất thêm.</p>
              )}
            </div>
          </div>
        </section>







        {/* ── Accordion QA Section ── */}
        <section className={styles.questionsSection}>
          <h2 className={styles.sectionTitle}>Chi tiết câu hỏi &amp; Trả lời</h2>

          {session.questions.length === 0 ? (
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '0.75rem', padding: '3rem', textAlign: 'center', color: '#94a3b8', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <AlertTriangle size={32} style={{ color: '#eab308' }} />
              <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#64748b' }}>
                {isPostInterviewEvaluated 
                  ? 'Không có câu hỏi nào được trả lời trong phiên phỏng vấn này.'
                  : 'Buổi phỏng vấn chưa được thực hiện.'}
              </p>
              {!isPostInterviewEvaluated && (
                <Link href={`/interview/session/${session.id}`} className={styles.primaryButton} style={{ marginTop: '1rem', textDecoration: 'none' }}>
                  Bắt đầu phỏng vấn ngay
                </Link>
              )}
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
                          <span className={styles.topicBadge}>
                            {q.topicTag || (typeof q.question === 'object' && q.question !== null ? (q.question as any).topic : '')}
                          </span>
                          {q.isDeepDive && (
                            <span className={styles.deepDiveBadge}>Hỏi sâu (Deep dive)</span>
                          )}
                        </div>
                        <div className={styles.qText}>
                          {typeof q.question === 'object' && q.question !== null ? (q.question as any).question : q.question}
                        </div>
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
          {isPostInterviewEvaluated ? (
            <Link href="/interview/new" className={styles.primaryButton}>
              Luyện tập lại
            </Link>
          ) : (
            <Link href={`/interview/session/${session.id}`} className={styles.primaryButton}>
              Bắt đầu phỏng vấn
            </Link>
          )}
        </div>
      </main>

    </div>
  );
}
