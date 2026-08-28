'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { FolderOpen, Lightbulb, AlertTriangle, CheckCircle, AlertCircle, MessageSquare, BarChart3, CheckCircle2, XCircle, Download, CornerDownRight } from 'lucide-react';
import { historyService, SessionHistoryItem, QuestionFeedback } from '@/services/historyService';
import { exportQuestionBankToCSV } from '@/lib/exportUtils';
import { useAuthStore } from '@/store/authStore';
import styles from './result.module.css';

interface StrengthObject {
  area?: string;
  name?: string;
}

interface WeaknessObject {
  area?: string;
  name?: string;
}

interface RecommendationObject {
  question?: string;
  suggestion?: string;
}

interface QuestionObject {
  topic?: string;
  question?: string;
}

export default function InterviewResultPage() {
  const params = useParams();
  const id = (params?.id as string) || '';

  const [session, setSession] = useState<SessionHistoryItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedIndexes, setExpandedIndexes] = useState<number[]>([0]); // Open first item by default

  useEffect(() => {
    let active = true;
    let pollCount = 0;
    const maxPolls = 40; // ~120 seconds max (3s interval)
    let timerId: NodeJS.Timeout;
    let evalTriggered = false;

    // Returns true if evaluation was actually triggered (i.e. data was incomplete)
    async function triggerEvaluationIfNeeded(sessionData: SessionHistoryItem): Promise<boolean> {
      if (evalTriggered) return false;
      const hasFeedback = !!(sessionData.overallFeedback && sessionData.overallFeedback.trim() !== '');
      const hasScore = sessionData.overallScore !== undefined && sessionData.overallScore !== null && sessionData.overallScore > 0;
      const answeredQs = (sessionData.questions || []).filter(q => q.answer && q.answer.trim().length > 0);
      const hasTurnEvaluation = answeredQs.length === 0 ||
        answeredQs.some(q => q.score > 0 && q.strengths && q.strengths.trim().length > 0);
      if (!hasFeedback || !hasScore || !hasTurnEvaluation) {
        evalTriggered = true;
        try {
          const token = useAuthStore.getState().token;
          const headers: Record<string, string> = { 'Content-Type': 'application/json' };
          if (token) headers['Authorization'] = `Bearer ${token}`;
          console.log(`[ResultPage] Triggering evaluation for session ${id}...`);
          // Await the full LLM evaluation before continuing
          await fetch(`/api/sessions/${id}/evaluate`, { method: 'POST', headers });
        } catch (e) {
          console.error('[ResultPage] Error triggering evaluate:', e);
        }
        return true; // evaluation was triggered — caller should reload immediately
      }
      return false;
    }

    async function loadSession() {
      if (!id || !active) return;
      try {
        const data = await historyService.getSessionById(id);
        if (!active) return;

        if (data) {
          const hasFeedback = data.overallFeedback !== undefined && data.overallFeedback !== null && data.overallFeedback.trim() !== '';
          const hasScore = data.overallScore !== undefined && data.overallScore !== null && data.overallScore > 0;

          // Check if turn-level evaluation is also done:
          // At least one answered question must have a score > 0 AND strengths text
          const answeredQuestions = (data.questions || []).filter(q => q.answer && q.answer.trim().length > 0);
          const hasTurnEvaluation = answeredQuestions.length === 0 ||
            answeredQuestions.some(q => q.score > 0 && q.strengths && q.strengths.trim().length > 0);

          const isEvaluated = hasFeedback && hasScore && hasTurnEvaluation;

          if (isEvaluated || pollCount >= maxPolls) {
            // Evaluation complete (or timeout) — render the page
            setSession(data);
            setLoading(false);
          } else if (!evalTriggered) {
            // Evaluation not yet done and not yet triggered — trigger it now
            // and immediately reload once it finishes (no need to wait for polling)
            setLoading(true);
            const didTrigger = await triggerEvaluationIfNeeded(data);
            if (didTrigger && active) {
              // Evaluation just finished — fetch updated data immediately
              loadSession();
            } else if (active) {
              // evalTriggered was already true by another path — fall back to polling
              pollCount++;
              timerId = setTimeout(loadSession, 3000);
            }
          } else {
            // Evaluation already triggered and running — keep polling every 3s
            pollCount++;
            setLoading(true);
            timerId = setTimeout(loadSession, 3000);
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
    strengths?: string[];
    weaknesses?: string[];
    recommendations?: string[];
    overall_score?: number;
    overall_summary?: string;
    hiring_recommendation?: string;
    strongAreas?: string[];
    gapAreas?: string[];
    actionableSuggestions?: string[];
    overallScore?: number;
    overallFeedback?: string;
    hiringRecommendation?: string;
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

  const isPostInterviewEvaluated = (session.status === 'Completed' && report !== null) ||
    (session.status === 'Completed' && (session.overallScore !== undefined && session.overallScore !== null && session.overallScore > 0));

  if (isPostInterviewEvaluated) {
    // 1. Post-interview report loaded
    score = session.overallScore ?? 0;
    overallFeedbackText = session.overallFeedback || '';
    hiringRecommendation = session.hiringRecommendation || '';

    if (report) {
      strengths = report.strongAreas || report.strengths || (Array.isArray(session.strongAreas) ? session.strongAreas : []);
      weaknesses = report.gapAreas || report.weaknesses || (Array.isArray(session.gapAreas) ? session.gapAreas : []);
      recommendations = report.actionableSuggestions || report.recommendations || (Array.isArray(session.actionableSuggestions) ? session.actionableSuggestions : []);

      const rawScore = report.overallScore !== undefined ? report.overallScore : report.overall_score;
      if (rawScore !== undefined && rawScore !== null) {
        score = rawScore <= 10 ? Math.round(rawScore * 10) : rawScore;
      }

      overallFeedbackText = report.overallFeedback || report.overall_summary || (typeof session.overallFeedback === 'string' && !session.overallFeedback.startsWith('{') ? session.overallFeedback : '');
      hiringRecommendation = report.hiringRecommendation || report.hiring_recommendation || session.hiringRecommendation || '';
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
  } else if (session.status === 'Completed') {
    // Status is Completed but evaluate API hasn't finished yet — show pending state
    score = 0;
    overallFeedbackText = 'Đang chờ AI phân tích kết quả phỏng vấn... Vui lòng đợi trong giây lát.';
    hiringRecommendation = '';
  } else {
    // 2. CV Evaluation report loaded
    score = session.competencyFitScore || 0;

    // Construct a beautiful CV match overall feedback summary
    overallFeedbackText = 'Báo cáo đánh giá mức độ tương thích của hồ sơ ứng viên (CV) đối với mô tả công việc (JD).\n' +
      '• Mức độ phù hợp năng lực: ' + (session.matchLevel || 'N/A') + '\n' +
      '• Cấp độ ứng viên phù hợp: ' + (session.candidateLevel || 'N/A') + '\n' +
      '• Ước tính số năm kinh nghiệm: ' + (session.yearsOfExperienceEstimate || 'N/A');

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
                  (strengths as (string | StrengthObject)[] || []).map((strength, index) => {
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
                  (weaknesses as (string | WeaknessObject)[] || []).map((weakness, index) => {
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
                (recommendations as (string | RecommendationObject)[] || []).map((suggestion, index) => {
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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 className={styles.sectionTitle} style={{ margin: 0 }}>Chi tiết câu hỏi &amp; Trả lời</h2>
            {session.questions && session.questions.length > 0 && (
              <button
                onClick={() => exportQuestionBankToCSV(session.questions, session.id)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors shadow-sm cursor-pointer"
              >
                <Download size={16} />
                <span>Xuất chi tiết câu hỏi &amp; trả lời (CSV)</span>
              </button>
            )}
          </div>

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
          ) : (() => {
            // ── 1. Separate warmup introduction turns from technical questions ──
            const isWarmup = (q: QuestionFeedback) => {
              const rawQ = typeof q.question === 'object' && q.question !== null
                ? (q.question as unknown as QuestionObject).question
                : (q.question as string);
              const text = (rawQ || '').toLowerCase();
              return (
                q.topicTag === 'Warmup' ||
                q.topicTag === 'Khởi động' ||
                text.includes('giới thiệu đôi nét về bản thân') ||
                text.includes('giới thiệu về bản thân') ||
                text.includes('khởi động')
              );
            };

            const questionsList = session.questions || [];
            const warmupTurns = questionsList.filter(isWarmup);

            // ── 2. Build question groups: base question + its follow-ups ──────────
            type QGroup = {
              base: QuestionFeedback;
              baseGlobalIdx: number;      // index in session.questions[]
              baseNum: number;            // base question display number (1, 2, 3…)
              followUps: { q: QuestionFeedback; globalIdx: number }[];
            };

            const groups: QGroup[] = [];
            let baseNum = 0;
            for (let i = 0; i < questionsList.length; i++) {
              const q = questionsList[i];
              if (isWarmup(q)) continue;

              if (!q.isDeepDive) {
                baseNum++;
                groups.push({ base: q, baseGlobalIdx: i, baseNum, followUps: [] });
              } else if (groups.length > 0) {
                groups[groups.length - 1].followUps.push({ q, globalIdx: i });
              } else {
                baseNum++;
                groups.push({ base: q, baseGlobalIdx: i, baseNum, followUps: [] });
              }
            }

            // Calculate combined average score for a group
            const getGroupScore = (group: QGroup) => {
              if (!group.base.answer || group.base.answer.trim().length === 0) {
                return 0;
              }
              const answeredInGroup = [group.base, ...group.followUps.map(f => f.q)].filter(
                t => t.answer && t.answer.trim().length > 0
              );
              if (answeredInGroup.length === 0) return 0;
              const sum = answeredInGroup.reduce((acc, t) => acc + (t.score || 0), 0);
              return Math.round(sum / answeredInGroup.length);
            };

            // ── Helper: render an accordion item ─
            const renderAccordionItem = (
              q: QuestionFeedback,
              globalIdx: number,
              label: string,
              isFollowUp: boolean,
              displayScore?: number,
              hasFollowUps?: boolean
            ) => {
              const isExpanded = expandedIndexes.includes(globalIdx);
              const qText = typeof q.question === 'object' && q.question !== null
                ? (q.question as unknown as QuestionObject).question
                : q.question;
              const topicText = q.topicTag || (
                typeof q.question === 'object' && q.question !== null
                  ? (q.question as unknown as QuestionObject).topic
                  : ''
              );
              const finalScore = displayScore !== undefined ? displayScore : (q.score || 0);

              return (
                <div
                  key={globalIdx}
                  className={styles.accordionItem}
                  style={isFollowUp ? {
                    marginLeft: '1.5rem',
                    borderLeft: '3px solid #a5b4fc',
                    borderRadius: '0 0.75rem 0.75rem 0',
                  } : undefined}
                >
                  {/* Header */}
                  <button className={styles.accordionHeader} onClick={() => toggleAccordion(globalIdx)}>
                    <div className={styles.headerMain}>
                      <div className={styles.headerMeta}>
                        {isFollowUp ? (
                          <span
                            className={styles.qNum}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#6366f1', backgroundColor: '#eef2ff', borderColor: '#c7d2fe' }}
                          >
                            <CornerDownRight size={11} />
                            {label}
                          </span>
                        ) : (
                          <span className={styles.qNum}>{label}</span>
                        )}
                        {topicText && <span className={styles.topicBadge}>{topicText}</span>}
                        {isFollowUp && (
                          <span className={styles.deepDiveBadge}>Hỏi sâu</span>
                        )}
                        {hasFollowUps && !isFollowUp && (
                          <span style={{ fontSize: '0.7rem', color: '#6366f1', backgroundColor: '#eef2ff', border: '1px solid #c7d2fe', padding: '0.15rem 0.5rem', borderRadius: '9999px', fontWeight: 600 }}>
                            Điểm TB gồm câu hỏi sâu
                          </span>
                        )}
                      </div>
                      <div className={styles.qText}>{qText}</div>
                    </div>

                    <div className={styles.headerRight}>
                      <div className={styles.qScore}>
                        <span className={styles.qScoreNum}>{finalScore}</span>
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
                        <p className={styles.userAnswerText} style={!q.answer ? { fontStyle: 'italic', color: '#94a3b8' } : undefined}>
                          {q.answer || 'Ứng viên chưa trả lời câu hỏi này trong phiên phỏng vấn.'}
                        </p>
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
                            <div>{q.strengths || (q.answer ? 'Câu trả lời đã được ghi nhận.' : 'Chưa có phân tích do câu hỏi chưa được trả lời.')}</div>
                          </div>
                          <div className={`${styles.feedbackBox} ${styles.feedbackImprovement}`}>
                            <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.25rem' }}>
                              <XCircle size={14} style={{ color: '#f59e0b' }} />
                              <span>Cần cải thiện:</span>
                            </strong>
                            <div>{q.improvements || (q.answer ? 'Tiếp tục phát huy và bổ sung ví dụ thực tế.' : 'Cần chuẩn bị và luyện tập trả lời câu hỏi này.')}</div>
                          </div>
                        </div>
                      </div>

                      {/* Suggested Answer */}
                      <div className={styles.sectionBlock}>
                        <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Lightbulb size={16} style={{ color: '#4f46e5' }} />
                          <span>Gợi ý câu trả lời tốt hơn từ AI</span>
                        </h4>
                        <div className={styles.suggestedAnswerBox} style={!q.suggestedAnswer ? { fontStyle: 'italic', color: '#94a3b8' } : undefined}>
                          {q.suggestedAnswer || 'Nên chuẩn bị câu trả lời theo mô hình STAR (Tình huống - Nhiệm vụ - Hành động - Kết quả), nêu rõ các giải pháp công nghệ và số liệu minh họa thực tế.'}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            };

            return (
              <div className={styles.accordionList}>
                {/* ── Warmup Introduction Section (if present) ── */}
                {warmupTurns.map((wt, wIdx) => {
                  const qText = typeof wt.question === 'object' && wt.question !== null
                    ? (wt.question as unknown as QuestionObject).question
                    : wt.question;
                  return (
                    <div
                      key={`warmup-${wIdx}`}
                      style={{
                        backgroundColor: '#ffffff',
                        border: '1px solid #e0e7ff',
                        borderRadius: '0.75rem',
                        padding: '1.25rem',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        marginBottom: '0.5rem'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#4338ca', backgroundColor: '#e0e7ff', padding: '0.2rem 0.6rem', borderRadius: '9999px' }}>
                            Khởi động / Giới thiệu
                          </span>
                          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                            (Không tính điểm vào kết quả chuyên môn)
                          </span>
                        </div>
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#1e293b', marginBottom: '0.5rem' }}>
                        {qText}
                      </div>
                      {wt.answer ? (
                        <div style={{ backgroundColor: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '0.5rem', border: '1px solid #e2e8f0', fontSize: '0.85rem', color: '#334155' }}>
                          <strong>Câu trả lời của bạn: </strong>{wt.answer}
                        </div>
                      ) : (
                        <div style={{ fontStyle: 'italic', fontSize: '0.85rem', color: '#94a3b8' }}>
                          Ứng viên chưa trả lời phần giới thiệu này.
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* ── Technical Questions ── */}
                {groups.map((group) => {
                  const groupScore = getGroupScore(group);
                  const hasFollowUps = group.followUps.length > 0;
                  return (
                    <div key={group.baseGlobalIdx} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {/* Base question (displays group average score if follow-ups exist) */}
                      {renderAccordionItem(
                        group.base,
                        group.baseGlobalIdx,
                        `CÂU HỎI ${group.baseNum}`,
                        false,
                        hasFollowUps ? groupScore : group.base.score,
                        hasFollowUps
                      )}

                      {/* Follow-up questions indented below */}
                      {group.followUps.map(({ q, globalIdx }, fuIdx) =>
                        renderAccordionItem(q, globalIdx, `Hỏi sâu ${fuIdx + 1}`, true, q.score, false)
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })()}
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
