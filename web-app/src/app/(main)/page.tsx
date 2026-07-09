import Link from 'next/link';
import styles from './page.module.css';

/* ── Icon helpers (inline SVGs to avoid Tailwind class dependency) ── */
function IconUpload() {
  return (
    <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </svg>
  );
}
function IconBriefcase() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    </svg>
  );
}
function IconMic() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
function IconBar() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}
function IconCheck({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function IconArrow({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
    </svg>
  );
}
function IconFile() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
    </svg>
  );
}
function IconUsers() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}
function IconTrend() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" />
    </svg>
  );
}
function IconStar() {
  return (
    <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

const steps = [
  { step: '01', icon: <IconUpload />, title: 'Tải CV lên', desc: 'Upload CV PDF — AI phân tích kỹ năng và kinh nghiệm ngay lập tức.', orange: true },
  { step: '02', icon: <IconBriefcase />, title: 'Chọn Job Description', desc: 'Tải JD hoặc dán trực tiếp. AI đối chiếu CV với yêu cầu vị trí.', orange: false },
  { step: '03', icon: <IconMic />, title: 'Phỏng vấn giọng nói', desc: 'Trả lời bằng giọng nói với avatar AI 3D. Trải nghiệm như phỏng vấn thật.', orange: true },
  { step: '04', icon: <IconBar />, title: 'Nhận kết quả chi tiết', desc: 'Điểm số, phân tích điểm mạnh/yếu và gợi ý cải thiện cá nhân hóa.', orange: false },
];

const stats = [
  { icon: <IconFile />, value: '10,000+', label: 'CV đã phân tích', orange: true },
  { icon: <IconUsers />, value: '2,500+', label: 'Người dùng tin tưởng', orange: false },
  { icon: <IconTrend />, value: '87%', label: 'Cải thiện sau 3 buổi', orange: true },
  { icon: <IconStar />, value: '4.9 ★', label: 'Đánh giá trung bình', orange: false },
];

const features = [
  'Phân tích CV & JD tức thì bằng AI',
  'Avatar 3D với giọng nói tự nhiên',
  'Câu hỏi được cá nhân hóa theo vị trí',
  'Phản hồi chi tiết sau mỗi buổi',
  'Lưu lịch sử & theo dõi tiến trình',
  'Hỗ trợ tiếng Việt & tiếng Anh',
];

export default function HomePage() {
  return (
    <div className={styles.page}>

      {/* ── Hero ── */}
      <section className={styles.heroSection}>
        <div className={styles.heroBg}>
          <div className={styles.heroBgOrange} />
          <div className={styles.heroBgGreen} />
        </div>
        <div className={styles.heroInner}>
          <div className={styles.heroBadge}>
            <span className={styles.badgeDot} />
            Được hỗ trợ bởi AI tiên tiến nhất
          </div>
          <h1 className={styles.heroTitle}>
            Phỏng vấn giả lập bằng AI.{' '}
            <span className={styles.heroGradient}>Chuẩn xác, Tự nhiên,</span>{' '}
            Chuyên nghiệp.
          </h1>
          <p className={styles.heroSubtitle}>
            Upload CV và Job Description — AI phân tích mức độ phù hợp, đặt câu hỏi thực tế
            bằng giọng nói 3D và cho bạn phản hồi chuyên sâu sau mỗi buổi luyện tập.
          </p>
          <div className={styles.heroActions}>
            <Link href="/interview/new" className={styles.ctaPrimary}>
              <IconUpload />
              Tải CV &amp; Bắt đầu ngay
              <IconArrow size={18} />
            </Link>
            <Link href="/history" className={styles.ctaSecondary}>
              Xem lịch sử
            </Link>
          </div>
          <div className={styles.heroTrust}>
            {['Miễn phí bắt đầu', 'Không cần thẻ tín dụng', 'Phân tích trong 30 giây'].map((t) => (
              <span key={t} className={styles.trustItem}>
                <span className={styles.trustCheck}><IconCheck size={14} /></span>
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className={styles.statsSection}>
        <div className={styles.statsInner}>
          {stats.map(({ icon, value, label, orange }) => (
            <div key={label} className={styles.statItem}>
              <span className={orange ? styles.statOrange : styles.statGreen}>{icon}</span>
              <span className={`${styles.statValue} ${orange ? styles.statOrange : styles.statGreen}`}>{value}</span>
              <span className={styles.statLabel}>{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Steps ── */}
      <section className={styles.stepsSection}>
        <div className={styles.stepsInner}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>
              4 bước để luyện tập{' '}
              <span className={styles.sectionOrange}>hiệu quả</span>
            </h2>
            <p className={styles.sectionSub}>Từ CV đến phản hồi chi tiết — chỉ trong vài phút.</p>
          </div>
          <div className={styles.stepsGrid}>
            {steps.map(({ step, icon, title, desc, orange }, idx) => (
              <div key={step} className={`${styles.stepCard} ${orange ? styles.stepCardOrange : styles.stepCardGreen}`}>
                {idx < steps.length - 1 && (
                  <span className={styles.stepArrow}><IconArrow size={20} /></span>
                )}
                <div className={`${styles.stepIconWrap} ${orange ? styles.stepIconOrange : styles.stepIconGreen}`}>
                  {icon}
                </div>
                <div>
                  <span className={styles.stepNum}>BƯỚC {step}</span>
                  <p className={styles.stepTitle}>{title}</p>
                  <p className={styles.stepDesc}>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className={styles.featuresSection}>
        <div className={styles.featuresInner}>
          <div className={styles.featuresLeft}>
            <h2>
              Tất cả những gì bạn cần để{' '}
              <span className={styles.featuresOrange}>tự tin phỏng vấn</span>
            </h2>
            <p className={styles.featuresDesc}>
              Smile Interview không chỉ hỏi câu hỏi — nền tảng hiểu CV của bạn, hiểu JD của nhà tuyển dụng
              và cho bạn trải nghiệm phỏng vấn thực tế nhất.
            </p>
            <Link href="/interview/new" className={styles.featuresCtaBtn}>
              Bắt đầu miễn phí <IconArrow size={16} />
            </Link>
          </div>
          <div className={styles.featuresGrid}>
            {features.map((feat) => (
              <div key={feat} className={styles.featureItem}>
                <span className={styles.featureCheck}><IconCheck size={16} /></span>
                <span className={styles.featureText}>{feat}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className={styles.ctaSection}>
        <div className={styles.ctaBanner}>
          <h2>Sẵn sàng chinh phục buổi phỏng vấn tiếp theo?</h2>
          <p>
            Hàng nghìn ứng viên đã cải thiện kỹ năng và tự tin hơn sau khi luyện tập với Smile Interview.
          </p>
          <Link href="/interview/new" className={styles.ctaBannerBtn}>
            <IconUpload />
            Thử ngay — Miễn phí
          </Link>
        </div>
      </section>

    </div>
  );
}
