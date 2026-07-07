'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './navbar.module.css';

const navLinks = [
  { 
    href: '/', 
    label: 'Trang chủ',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      </svg>
    )
  },
  { 
    href: '/interview/new', 
    label: 'Matching JD',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    )
  },
];

export default function Navbar() {
  const pathname = usePathname();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mockUser, setMockUser] = useState<any>({
    name: 'Đông Cao',
    email: 'caothanhdong.41118@gmail.com',
    avatar: '',
    coins: 2
  });

  return (
    <header className={styles.header}>
      <div className={styles.inner}>

        {/* Logo */}
        <Link href="/" className={styles.logo}>
          <img src="/logo.png" alt="Smile Interview Logo" className={styles.logoImg} />
        </Link>

        {/* Center Nav */}
        <nav className={styles.nav}>
          {navLinks.map((link) => {
            const isActive =
              pathname === link.href ||
              (link.href !== '/' && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
              >
                {link.icon}
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Auth / Profile section */}
        {mockUser ? (
          <div className={styles.profileSection}>
            {/* Dropdown Menu Wrapper */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                onBlur={() => setTimeout(() => setDropdownOpen(false), 200)}
                className={styles.dropdownTrigger}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={styles.dropdownIconUser}>
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <span>{mockUser.name}</span>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={styles.dropdownIconChevron}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {/* Dropdown Menu list */}
              {dropdownOpen && (
                <div className={styles.dropdownMenu}>
                  {/* User info details */}
                  <div className={styles.dropdownHeader}>
                    <p className={styles.dropdownName}>{mockUser.name}</p>
                    <p className={styles.dropdownEmail}>{mockUser.email}</p>
                  </div>

                  {/* Menu Options */}
                  <div>
                    <Link
                      href="/profile"
                      className={styles.dropdownItem}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={styles.dropdownItemBlue}>
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                      Hồ sơ cá nhân
                    </Link>

                    <Link
                      href="/history"
                      className={styles.dropdownItem}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={styles.dropdownItemGreen}>
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      Lịch sử phân tích
                    </Link>
                  </div>

                  {/* Log Out option */}
                  <div className={styles.dropdownDivider}></div>
                  <div>
                    <button
                      type="button"
                      onClick={() => setMockUser(null)}
                      className={styles.logoutButton}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <polyline points="16 17 21 12 16 7" />
                        <line x1="21" y1="12" x2="9" y2="12" />
                      </svg>
                      Đăng xuất
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className={styles.authButtons}>
            <Link href="/login" className={styles.btnLogin}>Đăng nhập</Link>
            <Link href="/register" className={styles.btnRegister}>Đăng ký</Link>
          </div>
        )}
      </div>
    </header>
  );
}
