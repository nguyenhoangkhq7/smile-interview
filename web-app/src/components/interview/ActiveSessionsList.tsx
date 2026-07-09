import { useState } from 'react';
import Link from 'next/link';
import { RefreshCw, ChevronDown, ChevronUp, FileText, X } from 'lucide-react';
import styles from '@/app/(main)/interview/new/new.module.css';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ActiveSession {
  sessionId: string;
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  status: string;
  date: string;
  hasAssessment?: boolean;
}

interface ActiveSessionsListProps {
  sessions: ActiveSession[];
  cloningId: string | null;
  onResume: (sessionId: string) => void;
  onRestart: (sessionId: string) => void;
  onViewAssessment: (sessionId: string) => void;
}

// ── Empty State ──────────────────────────────────────────────────────────────

export function EmptySessionsState() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 2rem',
        gap: '0.75rem',
        borderRadius: '0.75rem',
        border: '1.5px dashed rgba(99,102,241,0.25)',
        background: 'rgba(99,102,241,0.04)',
        textAlign: 'center',
      }}
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#6366f1"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.5 }}
      >
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
      <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.9rem', fontWeight: 500 }}>
        Bạn chưa có phiên phỏng vấn nào đang thực hiện.
      </p>
      <p style={{ margin: 0, color: '#64748b', fontSize: '0.8rem' }}>
        Tải lên CV &amp; JD bên dưới để bắt đầu phiên mới.
      </p>
    </div>
  );
}

// ── Session Card ─────────────────────────────────────────────────────────────

interface SessionCardProps {
  session: ActiveSession;
  isCloning: boolean;
  onResume: (id: string) => void;
  onRestart: (id: string) => void;
  onViewAssessment: (id: string) => void;
}

function SessionCard({ session, isCloning, onResume, onRestart, onViewAssessment }: SessionCardProps) {
  return (
    <div className={styles.sessionCard}>
      <div className={styles.sessionMain}>
        <div className={styles.sessionTitleRow}>
          <strong className={styles.sessionTitle}>{session.roleTitle}</strong>
          <span className={styles.statusPill}>{session.status}</span>
        </div>
        <p className={styles.sessionMeta}>
          {session.cvFilename} • {session.jdFilename}
        </p>
        <p className={styles.sessionDate}>
          Cập nhật: {new Date(session.date).toLocaleString('vi-VN')}
        </p>
      </div>

      <div className={styles.sessionActions}>
        {session.hasAssessment && (
          <button
            onClick={() => onViewAssessment(session.sessionId)}
            className={styles.secondaryButton}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              backgroundColor: '#eff6ff',
              color: '#1d4ed8',
              border: '1px solid #bfdbfe',
              padding: '0.5rem 0.8rem',
              borderRadius: '0.50rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <FileText size={14} />
            Đánh giá CV
          </button>
        )}
        <button
          onClick={() => onRestart(session.sessionId)}
          disabled={isCloning}
          className={styles.secondaryButton}
        >
          <RefreshCw size={14} className={isCloning ? 'animate-spin' : undefined} />
          Thực hiện lại
        </button>
        <button
          className={styles.primaryButton}
          onClick={() => onResume(session.sessionId)}
        >
          Tiếp tục phiên này
        </button>
      </div>
    </div>
  );
}

// ── Active Sessions List ─────────────────────────────────────────────────────

export function ActiveSessionsList({
  sessions,
  cloningId,
  onResume,
  onRestart,
  onViewAssessment,
}: ActiveSessionsListProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [showAllModal, setShowAllModal] = useState(false);
  const [modalTimeFilter, setModalTimeFilter] = useState('all');

  const displayedSessions = isCollapsed 
    ? sessions.slice(0, 1) 
    : sessions.slice(0, 5);

  const filteredModalSessions = sessions.filter((s) => {
    if (modalTimeFilter === 'all') return true;
    const now = new Date();
    const sDate = new Date(s.date);
    const diffTime = Math.abs(now.getTime() - sDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (modalTimeFilter === 'today') {
      return sDate.toDateString() === now.toDateString();
    } else if (modalTimeFilter === 'week') {
      return diffDays <= 7;
    } else if (modalTimeFilter === 'month') {
      return diffDays <= 30;
    }
    return true;
  });

  return (
    <section className={styles.formSection} style={{ marginBottom: '1.5rem' }}>
      <div className={styles.sectionHeader} style={{ marginBottom: '1rem', alignItems: 'center' }}>
        <div className={styles.sectionHeaderContent}>
          <span className={styles.sectionEyebrow}>Phiên đang hoạt động</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.25rem' }}>
            <h2 className={styles.sectionTitle} style={{ margin: 0 }}>
              Phiên đang thực hiện
            </h2>
            <span style={{
              backgroundColor: '#ffedd5',
              color: '#ea580c',
              padding: '0.2rem 0.65rem',
              borderRadius: '9999px',
              fontSize: '0.78rem',
              fontWeight: 700
            }}>
              {sessions.length} phiên
            </span>
          </div>
          <p className={styles.subtitle} style={{ marginTop: '0.35rem' }}>
            Các phiên này đang được quản lý trong PostgreSQL, bạn có thể tiếp tục ngay từ đây.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              backgroundColor: '#f1f5f9',
              border: '1px solid #cbd5e1',
              color: '#475569',
              padding: '0.5rem 0.8rem',
              borderRadius: '0.5rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            title={isCollapsed ? "Mở rộng danh sách" : "Thu gọn danh sách"}
          >
            {isCollapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
            {isCollapsed ? 'Mở rộng' : 'Thu gọn'}
          </button>
          <Link href="/history" className={styles.secondaryButton}>
            Mở toàn bộ lịch sử
          </Link>
        </div>
      </div>

      {sessions.length === 0 ? (
        <EmptySessionsState />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          <div className={styles.sessionList}>
            {displayedSessions.map((session) => (
              <SessionCard
                key={session.sessionId}
                session={session}
                isCloning={cloningId === session.sessionId}
                onResume={onResume}
                onRestart={onRestart}
                onViewAssessment={onViewAssessment}
              />
            ))}
          </div>

          {!isCollapsed && sessions.length > 5 && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.5rem' }}>
              <button
                onClick={() => setShowAllModal(true)}
                style={{
                  backgroundColor: '#ffffff',
                  border: '1px solid #ea580c',
                  color: '#ea580c',
                  padding: '0.5rem 1.2rem',
                  borderRadius: '0.50rem',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.backgroundColor = '#ea580c';
                  e.currentTarget.style.color = '#ffffff';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = '#ea580c';
                }}
              >
                Xem thêm các phiên khác
              </button>
            </div>
          )}
        </div>
      )}

      {/* Full Sessions Modal */}
      {showAllModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.4)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1.5rem',
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '1.25rem',
            width: '100%',
            maxWidth: '750px',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            border: '1px solid #e2e8f0',
            overflow: 'hidden',
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: '#0f172a' }}>
                  Danh sách tất cả phiên ({sessions.length})
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: '#64748b' }}>
                  Các phiên chưa hoàn thành được liệt kê chi tiết dưới đây
                </p>
              </div>
              
              {/* Time Filter & Close */}
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <select
                  value={modalTimeFilter}
                  onChange={(e) => setModalTimeFilter(e.target.value)}
                  style={{
                    padding: '0.45rem 0.75rem',
                    borderRadius: '0.5rem',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.85rem',
                    color: '#334155',
                    outline: 'none',
                    cursor: 'pointer',
                    backgroundColor: '#fff',
                  }}
                >
                  <option value="all">Tất cả thời gian</option>
                  <option value="today">Hôm nay</option>
                  <option value="week">7 ngày qua</option>
                  <option value="month">30 ngày qua</option>
                </select>
                
                <button
                  onClick={() => setShowAllModal(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#94a3b8',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '0.25rem',
                    borderRadius: '9999px',
                    transition: 'all 0.2s',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f1f5f9'}
                  onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <X size={20} />
                </button>
              </div>
            </div>
            
            {/* Modal Content - Scrollable List */}
            <div style={{
              padding: '1.5rem',
              overflowY: 'auto',
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.85rem',
            }}>
              {filteredModalSessions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b', fontSize: '0.9rem' }}>
                  Không tìm thấy phiên nào phù hợp với bộ lọc thời gian.
                </div>
              ) : (
                filteredModalSessions.map((session) => (
                  <SessionCard
                    key={session.sessionId}
                    session={session}
                    isCloning={cloningId === session.sessionId}
                    onResume={(id) => {
                      onResume(id);
                      setShowAllModal(false);
                    }}
                    onRestart={(id) => {
                      onRestart(id);
                      setShowAllModal(false);
                    }}
                    onViewAssessment={(id) => {
                      onViewAssessment(id);
                      setShowAllModal(false);
                    }}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
