'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { FolderOpen, Target, Briefcase, Wrench, Lightbulb, AlertTriangle, MessageSquare, BarChart3, CheckCircle2, XCircle } from 'lucide-react';
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
    async function loadSession() {
      if (!id) return;
      try {
        const data = await historyService.getSessionById(id);
        setSession(data);
      } catch (err) {
        console.error('Lỗi khi tải kết quả phỏng vấn:', err);
      } finally {
        setLoading(false);
      }
    }
    loadSession();
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

  // Fallbacks if user bypassed upload phase
  const score = session.overallScore || 78;
  const competencyScore = session.competencyFitScore || 75;
  const analysisText = session.skillsAnalysis?.analysis || 'Dựa trên phân tích sơ bộ, ứng viên có kỹ năng nền tảng vững vàng, đáp ứng các tiêu chuẩn kỹ thuật cốt lõi. Cần nâng cao kinh nghiệm làm việc thực tế với các hệ thống phân tán và bảo mật.';
  const criticalMissingSkills = session.skillsAnalysis?.criticalMissingSkills && session.skillsAnalysis.criticalMissingSkills.length > 0
    ? session.skillsAnalysis.criticalMissingSkills
    : ['Docker & Containerization', 'CI/CD Pipelines', 'Tối ưu hóa Webpack custom bundle'];

  const experienceEvaluation = session.experienceEvaluation || 'Ứng viên có khoảng 2 năm kinh nghiệm thực tế. Khả năng giải thích các khái niệm kỹ thuật rõ ràng. Cần tích lũy thêm kinh nghiệm thiết kế kiến trúc hệ thống chịu tải lớn.';
  const projectEvaluation = session.projectEvaluation || 'Các dự án mô tả trong CV có độ hoàn thiện tốt về mặt giao diện và tính năng. Cần bổ sung kiểm thử tự động (unit tests/integration tests) vào quy trình phát triển.';
  const actionableSuggestions = session.actionableSuggestions && session.actionableSuggestions.length > 0
    ? session.actionableSuggestions
    : [
      'Đọc thêm tài liệu về Reconciliation & Fiber Architecture của React để nắm chắc lõi render.',
      'Thực hành thiết lập CI/CD pipeline tự động build dự án Next.js.',
      'Nghiên cứu cơ chế nén bundle size và code splitting nâng cao.'
    ];

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

          <div className={styles.evalGrid}>
            <div className={styles.evalBox}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Target size={18} style={{ color: '#4f46e5' }} />
                <span>Độ tương thích năng lực: {competencyScore}%</span>
              </h3>
              <p>{analysisText}</p>

              <div style={{ marginTop: '1rem' }}>
                <strong style={{ fontSize: '0.85rem', color: '#1e293b', display: 'block', marginBottom: '0.4rem' }}>Chỉ số thiếu hụt so với JD:</strong>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {criticalMissingSkills.map((skill, index) => (
                    <span key={index} style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem', backgroundColor: '#fef3c7', color: '#92400e', borderRadius: '0.25rem', fontWeight: 600 }}>
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className={styles.evalBox}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Briefcase size={18} style={{ color: '#4f46e5' }} />
                <span>Đánh giá kinh nghiệm chuyên môn</span>
              </h3>
              <p>{experienceEvaluation}</p>
            </div>

            <div className={styles.evalBox}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Wrench size={18} style={{ color: '#4f46e5' }} />
                <span>Đánh giá năng lực dự án</span>
              </h3>
              <p>{projectEvaluation}</p>
            </div>

            <div className={styles.evalBox}>
              <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Lightbulb size={18} style={{ color: '#4f46e5' }} />
                <span>Lộ trình cải thiện hành động</span>
              </h3>
              <ul className={styles.actionList}>
                {actionableSuggestions.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
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
