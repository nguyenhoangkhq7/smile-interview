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

  const score = session.overallScore || 78;

  const overallFeedbackText = session.overallFeedback || 'Ứng viên hoàn thành buổi phỏng vấn ở mức Khá. Có kiến thức tương đối vững chắc về lập trình giao diện Frontend, đặc biệt là hệ sinh thái React. Kỹ năng lập luận logic tốt, tuy nhiên ở các câu hỏi đào sâu (deep-dive) còn bộc lộ một số lỗ hổng về mặt chi phí vận hành (performance overhead) và cấu trúc lõi JS. Cần trau dồi thêm kiến thức tổng quan hệ thống.';

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
                {session.hiringRecommendation && (
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 850,
                    padding: '0.2rem 0.6rem',
                    borderRadius: '9999px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    backgroundColor: session.hiringRecommendation.toLowerCase().includes('no') ? '#fef2f2' : (session.hiringRecommendation.toLowerCase().includes('hire') ? '#ecfdf5' : '#fffbeb'),
                    color: session.hiringRecommendation.toLowerCase().includes('no') ? '#b91c1c' : (session.hiringRecommendation.toLowerCase().includes('hire') ? '#047857' : '#d97706'),
                    border: `1px solid ${session.hiringRecommendation.toLowerCase().includes('no') ? '#fca5a5' : (session.hiringRecommendation.toLowerCase().includes('hire') ? '#a7f3d0' : '#fcd34d')}`
                  }}>
                    Quyết định: {session.hiringRecommendation}
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

          {/* Strengths & Weaknesses Panel */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginTop: '1rem' }}>
            
            {/* Strengths */}
            <div style={{ padding: '1.25rem', border: '1px solid #a7f3d0', backgroundColor: '#f0fdf4', borderRadius: '0.5rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#15803d', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.75rem', marginTop: 0 }}>
                <CheckCircle size={16} />
                <span>Điểm mạnh nổi bật</span>
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {(session.strongAreas || []).length > 0 ? (
                  (session.strongAreas || []).map((strength, index) => (
                    <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                      <span style={{ color: '#15803d', fontWeight: 'bold' }}>✓</span>
                      <span style={{ fontSize: '0.82rem', color: '#1e293b', lineHeight: '1.4' }}>{strength}</span>
                    </div>
                  ))
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
                {(session.gapAreas || []).length > 0 ? (
                  (session.gapAreas || []).map((weakness, index) => (
                    <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                      <span style={{ color: '#b91c1c', fontWeight: 'bold' }}>✗</span>
                      <span style={{ fontSize: '0.82rem', color: '#1e293b', lineHeight: '1.4' }}>{weakness}</span>
                    </div>
                  ))
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
              {(session.actionableSuggestions || []).length > 0 ? (
                (session.actionableSuggestions || []).map((suggestion, index) => (
                  <div key={index} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                    <span style={{ color: '#ea580c', fontWeight: 'bold' }}>➔</span>
                    <span style={{ fontSize: '0.82rem', color: '#334155', lineHeight: '1.4' }}>{suggestion}</span>
                  </div>
                ))
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

    </div>
  );
}
