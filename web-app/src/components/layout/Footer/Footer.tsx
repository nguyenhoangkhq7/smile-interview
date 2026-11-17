import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight, Mail, MapPin, Phone } from 'lucide-react';
import styles from './footer.module.css';

const footerGroups = [
  {
    title: 'Khám phá',
    links: [
      { href: '/#quy-trinh', label: 'Quy trình luyện tập' },
      { href: '/#tinh-nang', label: 'Tính năng' },
      { href: '/interview/new', label: 'Bắt đầu phỏng vấn' },
    ],
  },
  {
    title: 'Luyện tập',
    links: [
      { href: '/interview/new', label: 'Phỏng vấn thử' },
      { href: '/practice', label: 'Kế hoạch ôn tập' },
      { href: '/history', label: 'Lịch sử buổi luyện' },
    ],
  },
  {
    title: 'Hồ sơ',
    links: [
      { href: '/applications', label: 'Hồ sơ ứng tuyển' },
      { href: '/profile', label: 'Thông tin cá nhân' },
      { href: '/login', label: 'Đăng nhập' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.brandColumn}>
          <Link href="/" className={styles.brand}>
            <Image src="/logo.png" alt="" width={64} height={64} className={styles.logo} unoptimized />
            <span className={styles.brandCopy}>
              <span className={styles.brandName}>Smile Interview</span>
              <span className={styles.tagline}>Career Mentorship</span>
            </span>
          </Link>
          <p className={styles.description}>
            Luyện phỏng vấn cùng AI, xem lại phản hồi và xây dựng lộ trình ôn tập phù hợp với mục tiêu nghề nghiệp của bạn.
          </p>
        </div>

        {footerGroups.map((group) => (
          <div className={styles.linkColumn} key={group.title}>
            <h2 className={styles.columnTitle}>{group.title}</h2>
            <ul className={styles.linkList}>
              {group.links.map((link) => (
                <li key={link.href + link.label}>
                  <Link href={link.href} className={styles.link}>{link.label}<ArrowUpRight size={12} aria-hidden="true" /></Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div className={styles.contactColumn}>
          <h2 className={styles.columnTitle}>Liên hệ & hỗ trợ</h2>
          <p className={styles.contactIntro}>Cần hỗ trợ khi sử dụng nền tảng? Liên hệ với chúng tôi.</p>
          <a className={styles.contactLink} href="tel:+84363636366"><Phone size={14} />036 3636 366</a>
          <a className={styles.contactLink} href="mailto:mkt@digisource.vn"><Mail size={14} />mkt@digisource.vn</a>
          <p className={styles.contactLink}><MapPin size={14} />59 Hồ Tùng Mậu, P. Phú Thuận, Quận 1, TP. Hồ Chí Minh</p>
        </div>
      </div>

      <div className={styles.bottom}>
        <p>© 2025 Smile Interview. Giữ toàn bộ bản quyền.</p>
        <Link href="/" className={styles.backToTop}>Smile Interview <span aria-hidden="true">↑</span></Link>
      </div>
    </footer>
  );
}
