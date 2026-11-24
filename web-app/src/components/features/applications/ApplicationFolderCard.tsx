'use client';

import Link from 'next/link';
import type { CSSProperties } from 'react';
import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  FileText,
} from 'lucide-react';
import type { ApplicationProfile, InterviewAttempt } from '@/services/applicationProfiles';
import { activeAttempt, finishedAttempt, formatProfileDate } from './applicationUi';
import styles from './application-folder-card.module.css';

function ProfileStatus({ profile, active }: { profile: ApplicationProfile; active: InterviewAttempt | undefined }) {
  const completed = profile.attempts.some((attempt) => finishedAttempt(attempt) && attempt.answeredCount > 0);

  if (active?.status === 'In progress') {
    return <span className={`${styles.status} ${styles.inProgress}`}><span className={styles.statusDot} />Đang phỏng vấn</span>;
  }

  if (completed) {
    return <span className={`${styles.status} ${styles.completed}`}><span className={styles.statusDot} />Đã có kết quả</span>;
  }

  return <span className={`${styles.status} ${styles.notStarted}`}><span className={styles.statusDot} />Chưa bắt đầu</span>;
}

export function ApplicationFolderCard({ profile, index }: { profile: ApplicationProfile; index: number }) {
  const active = activeAttempt(profile.attempts);

  return (
    <article
      className={styles.folder}
      style={{ '--folder-index': index } as CSSProperties & { '--folder-index': number }}
    >
      <span className={styles.folderTab} aria-hidden="true"><BriefcaseBusiness size={14} />Hồ sơ ứng tuyển</span>
      <span className={styles.folderBody}>
        <span className={styles.topRow}>
          <span className={styles.titleGroup}>
            <span className={styles.icon}><BriefcaseBusiness size={21} aria-hidden="true" /></span>
            <span className={styles.titleDetails}>
              <Link className={styles.title} href={`/applications/${profile.id}`} title={profile.title}>{profile.title}</Link>
              <span className={styles.company}>
                <Building2 size={14} aria-hidden="true" />{profile.company || 'Chưa thêm công ty'}
              </span>
            </span>
          </span>
          <ProfileStatus profile={profile} active={active} />
        </span>

        <span className={styles.metadata}>
          <span className={styles.fileChip}><FileText size={15} aria-hidden="true" /><span title={profile.cvFilename}>{profile.cvFilename}</span></span>
        </span>

        <span className={styles.date}><CalendarDays size={14} aria-hidden="true" />Tạo {formatProfileDate(profile.createdAt)}</span>

        <span className={styles.footer}>
          <Link className={styles.openAction} href={`/applications/${profile.id}/documents`}>Xem CV &amp; JD<ArrowRight size={16} aria-hidden="true" /></Link>
        </span>
      </span>
    </article>
  );
}
