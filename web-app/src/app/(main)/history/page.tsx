'use client';

import { useState } from 'react';
import styles from './history.module.css';
import ProtectedRoute from '@/components/auth/ProtectedRoute';

// ── Types ────────────────────────────────────────────────────────────────────

interface HistoryItem {
  id: string;
  filename: string;
  badge: string;
  badgeClass: string;
  score: string;
  level: string;
  category: string;
  date: string;
}

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
  item: HistoryItem;
}

function HistoryItemCard({ item }: HistoryItemCardProps) {
  return (
    <div className={styles.itemCard}>
      {/* Content Details */}
      <div className={styles.itemMain}>
        <div className={styles.itemTitleRow}>
          <span className={styles.itemTitle}>{item.filename}</span>
          <span className={`${styles.itemBadge} ${item.badgeClass}`}>
            {item.badge}
          </span>
        </div>

        {/* Meta items */}
        <div className={styles.itemMeta}>
          <div>
            <span className={styles.metaLabel}>Điểm số:</span>
            <span className={styles.metaScore}>{item.score}</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Cấp độ:</span>
            <span className={styles.metaVal}>&quot;{item.level}&quot;</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Ngành nghề:</span>
            <span className={styles.metaVal}>&quot;{item.category}&quot;</span>
          </div>
          <div>
            <span className={styles.metaLabel}>Ngày tạo:</span>
            <span className={styles.metaVal}>{item.date}</span>
          </div>
        </div>
      </div>

      {/* Action button */}
      <div>
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
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
          </svg>
          Matching JD
        </button>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [timeFilter, setTimeFilter] = useState('all');
  const [scoreFilter, setScoreFilter] = useState('all');

  // TODO: replace with real API call when backend is ready
  const historyData: HistoryItem[] = [];

  const filtered = historyData.filter((item) => {
    const matchSearch =
      !searchTerm ||
      item.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.level.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.category.toLowerCase().includes(searchTerm.toLowerCase());
    return matchSearch;
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
              {filtered.length === 0 ? (
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
