'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
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

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>◈</span>
          <span>Smile Interview</span>
          <span className={styles.logoBadge}>AI</span>
        </div>
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
          <Link href="/interview/new" className={styles.primaryButton}>
            <span>+</span> Bắt đầu phỏng vấn mới
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
            <div className={styles.emptyIcon}>📂</div>
            <h2>Chưa có lịch sử phỏng vấn</h2>
            <p>
              Hãy tải lên CV và Mô tả công việc (JD) của bạn để AI phân tích mức độ phù hợp và bắt đầu buổi phỏng vấn đầu tiên.
            </p>
            <Link href="/interview/new" className={styles.primaryButton}>
              Bắt đầu luyện tập ngay
            </Link>
          </div>
        ) : (
          /* History List */
          <div className={styles.historyList}>
            {sessions.map((item) => (
              <div key={item.id} className={styles.card}>
                <div className={styles.cardMain}>
                  <div className={styles.cardHeader}>
                    <span className={styles.roleTitle}>{item.roleTitle}</span>
                    <span className={styles.typeBadge}>Kỹ thuật (Technical)</span>
                  </div>
                  <div className={styles.cardMeta}>
                    <div className={styles.metaItem}>
                      <span>📅</span>
                      <span>{formatDate(item.date)}</span>
                    </div>
                    {item.cvFilename && (
                      <div className={styles.metaItem}>
                        <span>📄 CV:</span>
                        <span>{item.cvFilename}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className={styles.cardAction}>
                  {item.status === 'Completed' && item.overallScore !== undefined && (
                    <div className={styles.scoreWrapper}>
                      <span className={styles.scoreNum}>{item.overallScore}</span>
                      <span className={styles.scoreLabel}>ĐIỂM SỐ</span>
                    </div>
                  )}
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-end' }}>
                    {getStatusBadge(item.status)}
                    {item.status === 'Completed' ? (
                      <Link href={`/interview/session/${item.id}/result`} className={styles.secondaryButton}>
                        Xem kết quả ➔
                      </Link>
                    ) : (
                      <Link href={`/interview/session/${item.id}`} className={styles.primaryButton} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
                        Tiếp tục ➔
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
