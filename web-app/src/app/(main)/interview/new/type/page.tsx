'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { Terminal, UserCheck, Code2, Briefcase, Network } from 'lucide-react';
import styles from './type.module.css';

interface InterviewTypeCard {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  enabled: boolean;
}

const INTERVIEW_TYPES: InterviewTypeCard[] = [
  {
    id: 'technical',
    name: 'Phỏng vấn Kỹ thuật',
    description: 'Đánh giá kiến thức chuyên môn, tư duy thuật toán, và khả năng giải quyết các vấn đề kỹ thuật thực tế.',
    icon: Terminal,
    enabled: true,
  },
  {
    id: 'behavioural',
    name: 'Phỏng vấn Hành vi',
    description: 'Đánh giá các kỹ năng mềm, độ phù hợp văn hóa doanh nghiệp, cách giải quyết xung đột thông qua các tình huống thực tế.',
    icon: UserCheck,
    enabled: false,
  },
  {
    id: 'live-coding',
    name: 'Lập trình Trực tiếp',
    description: 'Kiểm tra kỹ năng lập trình trực tiếp, viết mã sạch, tối ưu thuật toán và cấu trúc dữ liệu dưới áp lực thời gian thực.',
    icon: Code2,
    enabled: false,
  },
  {
    id: 'case-study',
    name: 'Giải quyết Tình huống',
    description: 'Phân tích các tình huống thực tế (case study) về nghiệp vụ kinh doanh, đưa ra giải pháp toàn diện và tối ưu.',
    icon: Briefcase,
    enabled: false,
  },
  {
    id: 'system-design',
    name: 'Thiết kế Hệ thống',
    description: 'Đánh giá khả năng thiết kế kiến trúc phần mềm quy mô lớn, tính mở rộng (scalability) và khả năng chịu tải cao.',
    icon: Network,
    enabled: false,
  },
];

function TypeSelectionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('sessionId') || `session-${Date.now()}`;

  const handleCardClick = (type: InterviewTypeCard) => {
    if (!type.enabled) return;
    router.push(`/interview/session/${sessionId}`);
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <Link href="/history" className={styles.logo}>
          <Image src="/logo.png" alt="Smile Interview Logo" width={180} height={50} className={styles.logoImg} unoptimized />
        </Link>
        <nav className={styles.navLinks}>
          <Link href="/history" className={styles.navLink}>
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
          <h1>Lựa chọn loại hình phỏng vấn</h1>
          <p className={styles.subtitle}>Chọn hình thức phỏng vấn giả lập phù hợp với mục tiêu của bạn</p>
        </div>

        <div className={styles.grid}>
          {INTERVIEW_TYPES.map((type) => {
            const isEnabled = type.enabled;
            return (
              <div
                key={type.id}
                className={`${styles.card} ${isEnabled ? styles.cardEnabled : styles.cardDisabled}`}
                onClick={() => handleCardClick(type)}
              >
                <div className={styles.cardHeader}>
                  <div className={`${styles.iconWrapper} ${isEnabled ? styles.iconWrapperActive : styles.iconWrapperDisabled}`}>
                    <type.icon className={styles.iconElement} size={24} />
                  </div>
                  <span className={`${styles.badge} ${isEnabled ? styles.badgeActive : ''}`}>
                    {isEnabled ? 'Sẵn có' : 'Sắp ra mắt'}
                  </span>
                </div>
                
                <div className={styles.cardBody}>
                  <h3>{type.name}</h3>
                  <p>{type.description}</p>
                </div>

                <div className={styles.cardFooter}>
                  {isEnabled ? (
                    <span>Bắt đầu luyện tập ➔</span>
                  ) : (
                    <span>Tạm khóa</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.actions}>
          <Link href={`/interview/new?sessionId=${sessionId}`} className={styles.backButton}>
            ➔ Quay lại tải lên CV
          </Link>
        </div>
      </main>

      <footer className={styles.footer}>
        <Image src="/footer.png" alt="Smile Interview Footer" width={1200} height={200} className={styles.footerImg} unoptimized />
      </footer>
    </div>
  );
}

export default function InterviewTypePage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc' }}>
        <p style={{ fontFamily: 'Inter, sans-serif', color: '#64748b' }}>Đang tải cấu hình...</p>
      </div>
    }>
      <TypeSelectionContent />
    </Suspense>
  );
}
