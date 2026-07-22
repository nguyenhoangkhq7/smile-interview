import Link from 'next/link';
import Image from 'next/image';
import styles from './footer.module.css';

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        {/* Left Column */}
        <div className={styles.columnLeft}>
          <Link href="/" className={styles.brand}>
            <Image src="/logo.png" alt="Smile Interview Logo" width={150} height={36} className={styles.footerLogo} unoptimized />
          </Link>
          <p className={styles.description}>
            Chấm điểm CV theo chuẩn ATS chỉ trong 30s, nhận ngay báo cáo đánh giá và gợi ý cải thiện CV để tăng cơ hội gọi phỏng vấn
          </p>
        </div>

        {/* Middle Column: Khám phá */}
        <div className={styles.columnMiddle}>
          <h4 className={styles.columnTitle}>Khám phá</h4>
          <ul className={styles.linkList}>
            <li>
              <a href="#" className={styles.linkItem}>
                <span className={styles.iconWrap}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></svg>
                </span>
                Matching JD
              </a>
            </li>
            <li>
              <a href="#" className={styles.linkItem}>
                <span className={styles.iconWrap}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                </span>
                Resume Studio
                <span className={styles.badge}>
                  <span className={styles.badgeOrange}>AI</span>
                  <span className={styles.badgeTeal}>NEW</span>
                </span>
              </a>
            </li>
            <li>
              <a href="#" className={styles.linkItem}>
                <span className={styles.iconWrap}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
                </span>
                Chấm năng lượng nghề
              </a>
            </li>
            <li>
              <a href="#" className={styles.linkItem}>
                <span className={styles.iconWrap}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></svg>
                </span>
                Tìm việc
              </a>
            </li>
            <li>
              <a href="#" className={styles.linkItem}>
                <span className={styles.iconWrap}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                </span>
                Liên hệ
              </a>
            </li>
          </ul>
        </div>

        {/* Right Column: Liên hệ với chúng tôi */}
        <div className={styles.columnRight}>
          <h4 className={styles.columnTitle}>Liên hệ với chúng tôi</h4>
          <p className={styles.rightSub}>
            Hãy để lại thông tin, chúng tôi sẽ liên hệ với bạn trong thời gian sớm nhất.
          </p>
          <ul className={styles.contactList}>
            <li>
              <span className={styles.contactIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" /></svg>
              </span>
              <span className={styles.contactText}>
                036 3636 366 <span className={styles.note}>(Zalo/Call)</span>
              </span>
            </li>
            <li>
              <span className={styles.contactIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
              </span>
              <span className={styles.contactText}>mkt@digisource.vn</span>
            </li>
            <li>
              <span className={styles.contactIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></svg>
              </span>
              <span className={styles.contactText}>
                59 Hồ Tùng Mậu, P. Phú Thuận, Quận 1, Thành phố Hồ Chí Minh, Vietnam
              </span>
            </li>
          </ul>
        </div>
      </div>

      {/* Bottom Strip */}
      <div className={styles.bottom}>
        <span className={styles.poweredBy}>Powered by</span>
        <Image src="/logo.png" alt="Powered By Logo" width={80} height={20} className={styles.poweredLogo} unoptimized />
      </div>
    </footer>
  );
}
