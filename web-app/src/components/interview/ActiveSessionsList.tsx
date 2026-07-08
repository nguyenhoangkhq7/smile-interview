'use client';

import Link from 'next/link';
import { RefreshCw } from 'lucide-react';
import styles from '@/app/interview/new/new.module.css';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ActiveSession {
  sessionId: string;
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  status: string;
  date: string;
}

interface ActiveSessionsListProps {
  sessions: ActiveSession[];
  cloningId: string | null;
  onResume: (sessionId: string) => void;
  onRestart: (sessionId: string) => void;
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
}

function SessionCard({ session, isCloning, onResume, onRestart }: SessionCardProps) {
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
}: ActiveSessionsListProps) {
  return (
    <section className={styles.formSection} style={{ marginBottom: '1.5rem' }}>
      <div className={styles.sectionHeader} style={{ marginBottom: '1rem' }}>
        <div className={styles.sectionHeaderContent}>
          <span className={styles.sectionEyebrow}>Phiên đang hoạt động</span>
          <h2 className={styles.sectionTitle}>Phiên đang thực hiện</h2>
          <p className={styles.subtitle} style={{ marginTop: '0.35rem' }}>
            Các phiên này đang được quản lý trong PostgreSQL, bạn có thể tiếp tục ngay từ đây.
          </p>
        </div>
        <Link href="/history" className={styles.secondaryButton}>
          Mở toàn bộ lịch sử
        </Link>
      </div>

      {sessions.length === 0 ? (
        <EmptySessionsState />
      ) : (
        <div className={styles.sessionList}>
          {sessions.slice(0, 3).map((session) => (
            <SessionCard
              key={session.sessionId}
              session={session}
              isCloning={cloningId === session.sessionId}
              onResume={onResume}
              onRestart={onRestart}
            />
          ))}
        </div>
      )}
    </section>
  );
}
