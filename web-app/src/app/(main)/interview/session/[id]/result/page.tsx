'use client';
import { MarkdownContent } from '@/components/common/MarkdownContent';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { FolderOpen, AlertTriangle, MessageSquare, BarChart3, CheckCircle2, Download, CornerDownRight, ShieldCheck, BrainCircuit } from 'lucide-react';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { cvJdMatchingService, HITLReportResponse } from '@/services/cvJdMatching';
import { exportQuestionBankToCSV } from '@/lib/exportUtils';
import styles from './result.module.css';
import { useEvidenceInterview } from '@/hooks/useEvidenceInterview';
import { InterviewOutcome } from '@/components/features/interview/InterviewOutcome';

function LegacyInterviewResultPage() {
  const params = useParams();
  const id = (params?.id as string) || '';

  const [session, setSession] = useState<SessionHistoryItem | null>(null);
  const [report, setReport] = useState<HITLReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number[]>([0]);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!id) return;
      try {
        const data = await historyService.getSessionById(id);
        if (!active) return;
        setSession(data);
        if (data?.interviewReport) {
          setReport(data.interviewReport);
        } else if (data?.aiInterviewSessionId) {
          try {
            const live = await cvJdMatchingService.getInterviewReport(id);
            if (active) setReport(live);
          } catch (e) {
            console.warn('[ResultPage] HITL report not available yet', e);
          }
        }
      } catch (err) {
        console.error('Lỗi khi tải kết quả phỏng vấn:', err);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [id]);

  const toggle = (i: number) =>
    setExpanded((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));

  const formatDate = (d?: string) => {
    if (!d) return 'N/A';
    try {
      return new Date(d).toLocaleString('vi-VN');
    } catch {
      return d;
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <p style={{ padding: '4rem', textAlign: 'center', color: '#64748b' }}>Đang tải báo cáo phỏng vấn...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className={styles.container}>
        <div style={{ display: 'flex', minHeight: '80vh', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
          <FolderOpen size={48} style={{ color: '#94a3b8' }} />
          <h2 style={{ fontSize: '1.25rem', marginTop: '1rem', fontWeight: 700 }}>Không tìm thấy kết quả phỏng vấn</h2>
          <Link href="/history" className={styles.primaryButton} style={{ marginTop: '1rem' }}>
            Quay lại Lịch sử
          </Link>
        </div>
      </div>
    );
  }

  const completionPct = report ? Math.round(report.completion_rate * 100) : session.overallScore ?? 0;
  const summary = report?.markdown_summary || session.overallFeedback || 'Chưa có báo cáo tổng kết cho phiên này.';
  const questions = session.questions ?? [];

  return (
    <div className={styles.container}>
      <main className={styles.content}>
        <div className={styles.titleSection}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BrainCircuit size={28} style={{ color: '#4f46e5' }} />
            <h1 style={{ margin: 0 }}>Báo cáo phỏng vấn thích ứng</h1>
          </div>
          <p className={styles.subtitle}>Kết quả kiểm chứng năng lực theo từng kỹ năng trong JD</p>
        </div>

        <section className={styles.summaryCard}>
          <div className={styles.scoreRow}>
            <div className={styles.scoreCircle}>
              <span className={styles.scoreNum}>{completionPct}%</span>
              <span className={styles.scoreLabel}>HOÀN THÀNH</span>
            </div>
            <div className={styles.scoreText}>
              <h2 style={{ margin: 0 }}>Tổng kết</h2>
              <MarkdownContent content={summary} />
              <div style={{ fontSize: '0.8rem', color: '#64748b', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                <span>Vị trí: <strong>{session.roleTitle || 'N/A'}</strong></span>
                <span>Ngày: <strong>{formatDate(session.date)}</strong></span>
                {report && <span>Số lượt: <strong>{report.total_turns}</strong></span>}
                {report && (
                  <span>
                    Kỹ năng xác thực: <strong>{report.verified_primary_skills}/{report.total_initial_primary_skills}</strong>
                  </span>
                )}
              </div>
            </div>
          </div>

          {report && report.evaluated_skills.length > 0 && (
            <div style={{ marginTop: '1.5rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.95rem', fontWeight: 700 }}>
                <ShieldCheck size={18} style={{ color: '#4f46e5' }} /> Kiểm chứng theo kỹ năng
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', color: '#475569' }}>
                      <th style={{ padding: '0.5rem' }}>Kỹ năng</th>
                      <th style={{ padding: '0.5rem' }}>CV ban đầu</th>
                      <th style={{ padding: '0.5rem' }}>Đã kiểm chứng</th>
                      <th style={{ padding: '0.5rem' }}>Yêu cầu JD</th>
                      <th style={{ padding: '0.5rem' }}>Gap</th>
                      <th style={{ padding: '0.5rem' }}>Mức</th>
                      <th style={{ padding: '0.5rem' }}>Lượt</th>
                      <th style={{ padding: '0.5rem' }}>Nhận định</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.evaluated_skills.map((s) => (
                      <tr key={s.jd_skill_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{s.jd_skill_id}</td>
                        <td style={{ padding: '0.5rem' }}>{s.initial_cv_proficiency.toFixed(2)}</td>
                        <td style={{ padding: '0.5rem', fontWeight: 700, color: s.is_verified ? '#15803d' : '#b45309' }}>
                          {s.verified_proficiency.toFixed(2)}
                        </td>
                        <td style={{ padding: '0.5rem' }}>{s.required_jd_proficiency.toFixed(2)}</td>
                        <td style={{ padding: '0.5rem' }}>{s.verified_skill_gap.toFixed(2)}</td>
                        <td style={{ padding: '0.5rem' }}>{s.map_rubric_level}</td>
                        <td style={{ padding: '0.5rem' }}>{s.local_turns_spent}</td>
                        <td style={{ padding: '0.5rem', maxWidth: 280 }}>{s.consolidated_finding || s.verification_reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        <section className={styles.questionsSection}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 className={styles.sectionTitle} style={{ margin: 0 }}>Nhật ký hỏi – đáp</h2>
            {questions.length > 0 && (
              <button
                onClick={() => exportQuestionBankToCSV(questions, session.id)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer"
              >
                <Download size={16} /> Xuất CSV
              </button>
            )}
          </div>

          {questions.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
              <AlertTriangle size={32} style={{ color: '#eab308' }} />
              <p>Chưa có lượt hỏi đáp nào trong phiên này.</p>
              <Link href={`/interview/session/${session.id}`} className={styles.primaryButton}>
                Bắt đầu phỏng vấn
              </Link>
            </div>
          ) : (
            <div className={styles.accordionList}>
              {questions.map((q, idx) => {
                const open = expanded.includes(idx);
                return (
                  <div
                    key={q.id ?? idx}
                    className={styles.accordionItem}
                    style={q.isDeepDive ? { marginLeft: '1.5rem', borderLeft: '3px solid #a5b4fc' } : undefined}
                  >
                    <button className={styles.accordionHeader} onClick={() => toggle(idx)}>
                      <div className={styles.headerMain}>
                        <div className={styles.headerMeta}>
                          <span className={styles.qNum}>
                            {q.isDeepDive ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                <CornerDownRight size={11} /> HỎI SÂU
                              </span>
                            ) : (
                              `LƯỢT ${idx + 1}`
                            )}
                          </span>
                          {q.topicTag && <span className={styles.topicBadge}>{q.topicTag}</span>}
                        </div>
                        <div className={styles.qText}>{q.question}</div>
                      </div>
                      <div className={styles.headerRight}>
                        <div className={styles.qScore}>
                          <span className={styles.qScoreNum}>{q.score || 0}</span>
                          <span className={styles.qScoreLabel}>Điểm</span>
                        </div>
                        <span className={`${styles.arrowIcon} ${open ? styles.arrowExpanded : ''}`}>▼</span>
                      </div>
                    </button>

                    {open && (
                      <div className={styles.accordionBody}>
                        <div className={styles.sectionBlock}>
                          <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <MessageSquare size={16} style={{ color: '#4f46e5' }} /> Câu trả lời
                          </h4>
                          <p className={styles.userAnswerText} style={!q.answer ? { fontStyle: 'italic', color: '#94a3b8' } : undefined}>
                            {q.answer || 'Chưa trả lời.'}
                          </p>
                        </div>
                        <div className={styles.sectionBlock}>
                          <h4 style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <BarChart3 size={16} style={{ color: '#4f46e5' }} /> Đánh giá của Judge
                          </h4>
                          <div className={styles.aiFeedbackGrid}>
                            <div className={`${styles.feedbackBox} ${styles.feedbackStrength}`}>
                              <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                <CheckCircle2 size={14} style={{ color: '#10b981' }} /> Nhận xét
                              </strong>
                              <div>{q.strengths || '—'}</div>
                            </div>
                          </div>
                        </div>
                        {q.suggestedAnswer && (
                          <div className={styles.sectionBlock}>
                            <h4>Suy luận khởi tạo (Abductive)</h4>
                            <div className={styles.suggestedAnswerBox}>{q.suggestedAnswer}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <div className={styles.actions}>
          <Link href="/history" className={styles.secondaryButton}>Quay lại Lịch sử</Link>
          <Link href="/interview/new" className={styles.primaryButton}>Phỏng vấn mới</Link>
        </div>
      </main>
    </div>
  );
}

export default function InterviewResultPage() {
  const { id } = useParams<{ id: string }>();
  const result = useEvidenceInterview(id, true);
  if (result.loading) return <p className="p-8">Đang tải kết quả…</p>;
  if (result.error) return <div role="alert" className="p-8">{result.error}<button onClick={() => void result.reload()}>Thử lại</button></div>;
  if (!result.session) return <LegacyInterviewResultPage />;
  return <main className="mx-auto max-w-4xl space-y-5 p-6">{result.metadata?.applicationProfileTitle && <h2 className="text-xl font-semibold">{result.metadata.applicationProfileTitle} · Lượt {result.metadata.attemptNumber}</h2>}<InterviewOutcome session={result.session} metadata={result.metadata} /></main>;
}
