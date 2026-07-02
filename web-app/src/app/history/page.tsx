'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Calendar, FileText, FolderOpen, Plus } from 'lucide-react';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import styles from './history.module.css';

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadHistory() {
      try {
        const data = await historyService.getHistory();
        setSessions(data);
      } catch (err) {
        console.error('Lỗi khi tải lịch sử luyện tập:', err);
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

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

  const getStatusBadge = (status: SessionHistoryItem['status']) => {
    switch (status) {
      case 'Completed':
        return <span className={`${styles.badge} ${styles.badgeSuccess}`}>Đã hoàn thành</span>;
      case 'In progress':
        return <span className={`${styles.badge} ${styles.badgeWarning}`}>Đang thực hiện</span>;
      case 'Not started':
        return <span className={`${styles.badge} ${styles.badgeDanger}`}>Chưa bắt đầu</span>;
      default:
        return null;
    }
  };

  const activeSessions = sessions.filter((item) => item.status !== 'Completed');
  const completedSessions = sessions.filter((item) => item.status === 'Completed');

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <Link href="/history" className={styles.logo}>
          <img src="/logo.png" alt="Smile Interview Logo" className={styles.logoImg} />
        </Link>
        <nav className={styles.navLinks}>
          <Link href="/history" className={`${styles.navLink} ${styles.navLinkActive}`}>
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
          <div>
            <h1>Lịch sử luyện tập</h1>
            <p className={styles.subtitle}>Danh sách các buổi phỏng vấn giả lập của bạn với trợ lý AI</p>
          </div>
          <Link href="/interview/new" className={styles.primaryButton} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <Plus size={16} /> Bắt đầu phỏng vấn mới
          </Link>
        </div>

        {loading ? (
          /* Loading Skeleton */
          <div className={styles.historyList}>
            {[1, 2].map((i) => (
              <div key={i} className={styles.card} style={{ opacity: 0.6, animation: 'pulse 1.5s infinite' }}>
                <div className={styles.cardMain}>
                  <div style={{ height: '20px', width: '250px', backgroundColor: '#e2e8f0', borderRadius: '4px', marginBottom: '8px' }} />
                  <div style={{ height: '14px', width: '180px', backgroundColor: '#f1f5f9', borderRadius: '4px' }} />
                </div>
                <div style={{ height: '38px', width: '120px', backgroundColor: '#e2e8f0', borderRadius: '6px' }} />
              </div>
            ))}
          </div>
        ) : sessions.length === 0 ? (
          /* Empty State */
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <FolderOpen size={48} style={{ color: '#94a3b8' }} />
            </div>
            <h2>Chưa có lịch sử phỏng vấn</h2>
            <p>
              Hãy tải lên CV và Mô tả công việc (JD) của bạn để AI phân tích mức độ phù hợp và bắt đầu buổi phỏng vấn đầu tiên.
            </p>
            <Link href="/interview/new" className={styles.primaryButton}>
              Bắt đầu luyện tập ngay
            </Link>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '2rem' }}>
            {activeSessions.length > 0 && (
              <section>
                <div style={{ marginBottom: '0.75rem' }}>
                  <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Phiên đang thực hiện</h2>
                  <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>
                    Những phiên này còn trạng thái mở trong cơ sở dữ liệu và có thể tiếp tục ngay.
                  </p>
                </div>
                <div className={styles.historyList}>
                  {activeSessions.map((item) => (
                    <div key={item.id} className={styles.card}>
                      <div className={styles.cardMain}>
                        <div className={styles.cardHeader}>
                          <span className={styles.roleTitle}>{item.roleTitle}</span>
                          <span className={styles.typeBadge}>Kỹ thuật (Technical)</span>
                        </div>
                        <div className={styles.cardMeta}>
                          <div className={styles.metaItem} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                            <Calendar size={14} style={{ color: '#64748b' }} />
                            <span>{formatDate(item.date)}</span>
                          </div>
                          {item.cvFilename && (
                            <div className={styles.metaItem} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                              <FileText size={14} style={{ color: '#64748b' }} />
                              <span>CV: {item.cvFilename}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className={styles.cardAction}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-end' }}>
                          {getStatusBadge(item.status)}
                          <Link href={`/interview/session/${item.id}`} className={styles.primaryButton} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
                            Tiếp tục ➔
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {completedSessions.length > 0 && (
              <section>
                <div style={{ marginBottom: '0.75rem' }}>
                  <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Phiên đã hoàn thành</h2>
                  <p className={styles.subtitle} style={{ marginTop: '0.25rem' }}>
                    Các session đã lưu đầy đủ kết quả đánh giá và câu hỏi trả lời.
                  </p>
                </div>
                <div className={styles.historyList}>
                  {completedSessions.map((item) => (
                    <div key={item.id} className={styles.card}>
                      <div className={styles.cardMain}>
                        <div className={styles.cardHeader}>
                          <span className={styles.roleTitle}>{item.roleTitle}</span>
                          <span className={styles.typeBadge}>Kỹ thuật (Technical)</span>
                        </div>
                        <div className={styles.cardMeta}>
                          <div className={styles.metaItem} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                            <Calendar size={14} style={{ color: '#64748b' }} />
                            <span>{formatDate(item.date)}</span>
                          </div>
                          {item.cvFilename && (
                            <div className={styles.metaItem} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                              <FileText size={14} style={{ color: '#64748b' }} />
                              <span>CV: {item.cvFilename}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className={styles.cardAction}>
                        {item.overallScore !== undefined && (
                          <div className={styles.scoreWrapper}>
                            <span className={styles.scoreNum}>{item.overallScore}</span>
                            <span className={styles.scoreLabel}>ĐIỂM SỐ</span>
                          </div>
                        )}

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-end' }}>
                          {getStatusBadge(item.status)}
                          <Link href={`/interview/session/${item.id}/result`} className={styles.secondaryButton}>
                            Xem kết quả ➔
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        <img src="/footer.png" alt="Smile Interview Footer" className={styles.footerImg} />
      </footer>
    </div>
  );
}
