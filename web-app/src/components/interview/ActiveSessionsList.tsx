import { useState } from 'react';
import Link from 'next/link';
import { RefreshCw, ChevronDown, ChevronUp, FileText, X, MessageCircle, Briefcase, Play, Clock, Sparkles } from 'lucide-react';
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

// Helper: Status badge generator
const getStatusBadge = (status: string) => {
  let label = status;
  let bg = '#e0e7ff';
  let color = '#3730a3';
  let border = '1px solid #c7d2fe';

  if (status === 'In progress') {
    label = 'Đang phỏng vấn';
    bg = '#fff7ed';
    color = '#ea580c';
    border = '1px solid #ffedd5';
  } else if (status === 'Not started') {
    label = 'Chưa bắt đầu';
    bg = '#f1f5f9';
    color = '#475569';
    border = '1px solid #e2e8f0';
  }

  return (
    <span style={{
      fontSize: '0.72rem',
      padding: '0.18rem 0.5rem',
      borderRadius: '999px',
      backgroundColor: bg,
      color: color,
      border: border,
      fontWeight: 700,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.2rem'
    }}>
      <Clock size={10} />
      {label}
    </span>
  );
};

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
        border: '1.5px dashed rgba(234, 88, 12, 0.25)',
        background: 'rgba(234, 88, 12, 0.04)',
        textAlign: 'center',
      }}
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#ea580c"
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
          <strong className={styles.sessionTitle} style={{ 
            fontSize: '0.92rem', 
            fontWeight: 700, 
            color: '#0f172a',
            maxWidth: '180px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }} title={session.roleTitle}>
            {session.roleTitle}
          </strong>
          {getStatusBadge(session.status)}
        </div>
        
        {/* CV & JD Badges */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', margin: '0.5rem 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#475569', fontSize: '0.8rem' }}>
            <FileText size={13} style={{ flexShrink: 0, color: '#f97316' }} />
            <span style={{ 
              overflow: 'hidden', 
              textOverflow: 'ellipsis', 
              whiteSpace: 'nowrap',
              maxWidth: '280px' 
            }} title={session.cvFilename}>
              {session.cvFilename}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#475569', fontSize: '0.8rem' }}>
            <Briefcase size={13} style={{ flexShrink: 0, color: '#3b82f6' }} />
            <span style={{ 
              overflow: 'hidden', 
              textOverflow: 'ellipsis', 
              whiteSpace: 'nowrap',
              maxWidth: '280px' 
            }} title={session.jdFilename}>
              {session.jdFilename}
            </span>
          </div>
        </div>

        <p className={styles.sessionDate} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#94a3b8', margin: 0 }}>
          <Clock size={12} />
          Cập nhật: {new Date(session.date).toLocaleString('vi-VN')}
        </p>
      </div>

      {/* Action buttons wrapper */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: session.hasAssessment ? '1fr 1fr' : '1fr', 
        gap: '0.5rem',
        marginTop: '0.5rem' 
      }}>
        {session.hasAssessment && (
          <button
            onClick={() => onViewAssessment(session.sessionId)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.35rem',
              backgroundColor: '#eff6ff',
              color: '#2563eb',
              border: '1px solid #bfdbfe',
              padding: '0.5rem 0.5rem',
              borderRadius: '0.5rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#dbeafe'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#eff6ff'}
          >
            <Sparkles size={13} />
            Đánh giá CV
          </button>
        )}
        <button
          onClick={() => onRestart(session.sessionId)}
          disabled={isCloning}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.35rem',
            backgroundColor: '#ffffff',
            color: '#475569',
            border: '1px solid #cbd5e1',
            padding: '0.5rem 0.5rem',
            borderRadius: '0.5rem',
            fontSize: '0.78rem',
            fontWeight: 600,
            cursor: isCloning ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => !isCloning && (e.currentTarget.style.backgroundColor = '#f8fafc')}
          onMouseOut={(e) => !isCloning && (e.currentTarget.style.backgroundColor = '#ffffff')}
        >
          <RefreshCw size={13} className={isCloning ? 'animate-spin' : undefined} />
          Thực hiện lại
        </button>
        <button
          onClick={() => onResume(session.sessionId)}
          style={{
            gridColumn: session.hasAssessment ? 'span 2' : 'auto',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.35rem',
            backgroundColor: '#ea580c',
            color: '#ffffff',
            border: 'none',
            padding: '0.55rem 0.5rem',
            borderRadius: '0.5rem',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(234, 88, 12, 0.15)',
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#c2410c'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#ea580c'}
        >
          <Play size={13} fill="currentColor" />
          Tiếp tục phỏng vấn
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
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAllModal, setShowAllModal] = useState(false);
  const [modalTimeFilter, setModalTimeFilter] = useState('all');

  const displayedSessions = sessions.slice(0, 5);

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

  // Floating chat button - positioned at bottom right corner
  const ChatButton = () => (
    <button
      onClick={() => setIsExpanded(true)}
      style={{
        position: 'fixed',
        bottom: '25px',
        right: '25px',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        backgroundColor: '#ea580c',
        color: 'white',
        padding: '0.75rem 1.25rem',
        borderRadius: '9999px',
        fontSize: '0.9rem',
        fontWeight: 600,
        cursor: 'pointer',
        boxShadow: '0 4px 16px rgba(234, 88, 12, 0.35)',
        transition: 'all 0.3s ease',
        border: 'none',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 6px 20px rgba(234, 88, 12, 0.45)';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(234, 88, 12, 0.35)';
      }}
    >
      <MessageCircle size={20} />
      <span>Phiên đang thực hiện</span>
      {sessions.length > 0 && (
        <span style={{
          backgroundColor: 'white',
          color: '#ea580c',
          padding: '0.15rem 0.5rem',
          borderRadius: '9999px',
          fontSize: '0.75rem',
          fontWeight: 700,
          minWidth: '20px',
          textAlign: 'center',
        }}>
          {sessions.length}
        </span>
      )}
    </button>
  );

  // Expanded panel - displays above the floating button
  const ExpandedPanel = () => (
    <div style={{
      position: 'fixed',
      bottom: '90px',
      right: '25px',
      zIndex: 999,
      backgroundColor: 'white',
      borderRadius: '1rem',
      boxShadow: '0 10px 40px rgba(15, 23, 42, 0.15)',
      border: '1px solid #e2e8f0',
      width: '400px',
      maxHeight: '520px',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
    }}>
      {/* Header */}
      <div style={{
        padding: '1rem 1.25rem',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: '#f8fafc',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <MessageCircle size={18} color="#ea580c" />
          <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.95rem' }}>
            Phiên đang thực hiện
          </span>
          {sessions.length > 0 && (
            <span style={{
              backgroundColor: '#fff7ed',
              color: '#ea580c',
              padding: '0.15rem 0.5rem',
              borderRadius: '9999px',
              fontSize: '0.7rem',
              fontWeight: 700,
            }}>
              {sessions.length}
            </span>
          )}
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          style={{
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
            padding: '0.25rem',
            borderRadius: '9999px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f1f5f9'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div style={{
        padding: '1rem',
        overflowY: 'auto',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}>
        {sessions.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '2.5rem 1rem',
            color: '#64748b',
            fontSize: '0.85rem',
          }}>
            Không có phiên nào đang thực hiện
          </div>
        ) : (
          <>
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
            {sessions.length > 5 && (
              <button
                onClick={() => setShowAllModal(true)}
                style={{
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  color: '#64748b',
                  padding: '0.6rem 1rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  width: '100%',
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.backgroundColor = '#e2e8f0';
                  e.currentTarget.style.color = '#475569';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.backgroundColor = '#f8fafc';
                  e.currentTarget.style.color = '#64748b';
                }}
              >
                Xem thêm {sessions.length - 5} phiên khác
              </button>
            )}
            <Link
              href="/history"
              style={{
                display: 'block',
                textAlign: 'center',
                color: '#ea580c',
                fontSize: '0.85rem',
                fontWeight: 600,
                padding: '0.5rem',
                textDecoration: 'none',
              }}
            >
              Mở toàn bộ lịch sử →
            </Link>
          </>
        )}
      </div>
    </div>
  );

  return (
    <>
      {!isExpanded ? <ChatButton /> : <ExpandedPanel />}

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
                  Danh sách tất cả phiên đang thực hiện ({sessions.length})
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
    </>
  );
}
