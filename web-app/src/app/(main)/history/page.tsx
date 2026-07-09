'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import styles from './history.module.css';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { historyService, SessionHistoryItem } from '@/services/historyService';

// ── Empty State ──────────────────────────────────────────────────────────────

function EmptyHistory() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4rem 2rem',
        gap: '1rem',
        color: '#94a3b8',
        textAlign: 'center',
      }}
    >
      <svg
        width="52"
        height="52"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.4 }}
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      <p style={{ margin: 0, fontSize: '0.95rem' }}>Bạn chưa có lịch sử phân tích nào.</p>
      <p style={{ margin: 0, fontSize: '0.82rem', opacity: 0.7 }}>
        Hãy tạo một phiên phỏng vấn mới để bắt đầu!
      </p>
    </div>
  );
}

// ── History Item Card ────────────────────────────────────────────────────────

interface HistoryItemCardProps {
  item: SessionHistoryItem;
}

function HistoryItemCard({ item }: HistoryItemCardProps) {
  const isCompleted = item.status === 'Completed';
  
  // Format score based on status
  let displayScore = 'N/A';
  if (isCompleted && item.overallScore !== undefined && item.overallScore !== null) {
    displayScore = item.overallScore <= 10 ? `${item.overallScore}/10` : `${item.overallScore}`;
  } else if (item.competencyFitScore !== undefined && item.competencyFitScore !== null) {
    displayScore = `${item.competencyFitScore}% (CV Match)`;
  }

  // Format badge
  const badgeText = isCompleted ? 'Đã hoàn thành' : 'Đang phỏng vấn';
  const badgeClass = isCompleted ? styles.badgeGreen : styles.badgeAmber;

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const actionLink = isCompleted 
    ? `/interview/session/${item.id}/result` 
    : `/interview/session/${item.id}`;

  return (
    <div className={styles.itemCard}>
      {/* Content Details */}
      <div className={styles.itemMain}>
        <div className={styles.itemTitleRow}>
          <span className={styles.itemTitle}>{item.roleTitle || item.cvFilename || 'Không rõ vị trí'}</span>
          <span className={`${styles.itemBadge} ${badgeClass}`}>
            {badgeText}
          </span>
        </div>

        {/* Meta items */}
        <div className={styles.itemMeta}>
          <div>
            <span className={styles.metaLabel}>Điểm số:</span>
            <span className={styles.metaScore}>{displayScore}</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Cấp độ:</span>
            <span className={styles.metaVal}>&quot;{item.candidateLevel || 'N/A'}&quot;</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Ngành nghề:</span>
            <span className={styles.metaVal}>&quot;{item.roleTypeDetected || 'N/A'}&quot;</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Ngày tạo:</span>
            <span className={styles.metaVal}>{formatDate(item.date)}</span>
          </div>
        </div>
      </div>

      {/* Action button */}
      <div>
        <Link href={actionLink}>
          <button className={styles.btnMatching}>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 8 12 12 16 14" />
            </svg>
            <span>{isCompleted ? 'Xem báo cáo' : 'Tiếp tục'}</span>
          </button>
        </Link>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [timeFilter, setTimeFilter] = useState('all');
  const [scoreFilter, setScoreFilter] = useState('all');
  const [historyData, setHistoryData] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHistory() {
      try {
        const data = await historyService.getHistory();
        setHistoryData(data);
      } catch (err) {
        console.error('Error fetching history:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchHistory();
  }, []);

  const filtered = historyData.filter((item) => {
    // 1. Search filter
    const title = item.roleTitle || item.cvFilename || '';
    const matchSearch =
      !searchTerm ||
      title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.candidateLevel || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.roleTypeDetected || '').toLowerCase().includes(searchTerm.toLowerCase());
    
    if (!matchSearch) return false;

    // 2. Time filter
    if (timeFilter !== 'all') {
      const createdDate = new Date(item.date);
      const now = new Date();
      const diffTime = Math.abs(now.getTime() - createdDate.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      
      if (timeFilter === 'week' && diffDays > 7) return false;
      if (timeFilter === 'month' && diffDays > 30) return false;
    }

    // 3. Score filter
    if (scoreFilter !== 'all') {
      // Prioritize overallScore, fallback to competencyFitScore
      const score = item.overallScore !== undefined && item.overallScore !== null
        ? (item.overallScore <= 10 ? item.overallScore * 10 : item.overallScore)
        : (item.competencyFitScore || 0);

      if (scoreFilter === 'high' && score < 80) return false;
      if (scoreFilter === 'medium' && (score < 60 || score > 80)) return false;
      if (scoreFilter === 'low' && score >= 60) return false;
    }

    return true;
  });

  return (
    <ProtectedRoute>
      <div className={styles.page}>
        <div className={styles.inner}>

          {/* Header Icon + Title */}
          <div className={styles.header}>
            <div className={styles.headerIcon}>
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h1 className={styles.title}>Lịch sử phân tích</h1>
            <p className={styles.subtitle}>Xem lại tất cả CV đã phân tích và kết quả đánh giá</p>
          </div>

          {/* Filters Card */}
          <div className={styles.filterCard}>
            {/* Search Box */}
            <div className={styles.searchWrap}>
              <span className={styles.searchIcon}>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </span>
              <input
                type="text"
                placeholder="Tìm kiếm theo tên file, level, category..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={styles.searchInput}
              />
            </div>

            {/* Filter Selectors */}
            <div className={styles.filterActions}>
              <div className={styles.selectWrap}>
                <select
                  value={timeFilter}
                  onChange={(e) => setTimeFilter(e.target.value)}
                  className={styles.select}
                >
                  <option value="all">Tất cả thời gian</option>
                  <option value="month">Tháng này</option>
                  <option value="week">Tuần này</option>
                </select>
                <div className={styles.selectIcon}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>

              <div className={styles.selectWrap}>
                <select
                  value={scoreFilter}
                  onChange={(e) => setScoreFilter(e.target.value)}
                  className={styles.select}
                >
                  <option value="all">Tất cả điểm số</option>
                  <option value="high">Trên 80</option>
                  <option value="medium">60 - 80</option>
                  <option value="low">Dưới 60</option>
                </select>
                <div className={styles.selectIcon}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* List Card Container */}
          <div className={styles.listCard}>
            <div className={styles.listHead}>
              <h2 className={styles.listTitle}>Lịch sử phân tích CV</h2>
              <span className={styles.listCount}>Tổng cộng: {filtered.length}</span>
            </div>

            <div className={styles.listItems}>
              {loading ? (
                <div style={{ display: 'flex', padding: '3rem', justifyContent: 'center' }}>
                  <div style={{ width: '30px', height: '30px', border: '3px solid #f1f5f9', borderTop: '3px solid #166534', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  <style jsx>{`
                    @keyframes spin {
                      0% { transform: rotate(0deg); }
                      100% { transform: rotate(360deg); }
                    }
                  `}</style>
                </div>
              ) : filtered.length === 0 ? (
                <EmptyHistory />
              ) : (
                filtered.map((item) => (
                  <HistoryItemCard key={item.id} item={item} />
                ))
              )}
            </div>
          </div>

        </div>
      </div>
    </ProtectedRoute>
  );
}
