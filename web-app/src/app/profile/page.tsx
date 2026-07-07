'use client';

import type { LucideIcon } from 'lucide-react';
import { BarChart3, CalendarDays, Coins, Eye, FileJson2, LockKeyhole, MapPin, PencilLine, Sparkles, Star, Upload, UserRound, BriefcaseBusiness, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import styles from './profile.module.css';

type StatItem = {
  label: string;
  value: number;
  icon: LucideIcon;
  iconClass: string;
};

export default function ProfilePage() {
  const [fullName, setFullName] = useState('Đông Cao');
  const [phone, setPhone] = useState('');
  const [defaultCv, setDefaultCv] = useState('Cao Thanh Dong - CV.pdf');
  const [currentPass, setCurrentPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');

  const stats: StatItem[] = [
    { label: 'LƯỢT PHÂN TÍCH CV', value: 0, icon: BarChart3, iconClass: styles.statIconBlue },
    { label: 'PHÂN TÍCH HÔM NAY', value: 0, icon: CalendarDays, iconClass: styles.statIconOrange },
    { label: 'ĐIỂM TRUNG BÌNH', value: 0, icon: Star, iconClass: styles.statIconGreen },
    { label: 'COINS', value: 2, icon: Coins, iconClass: styles.statIconAmber },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.inner}>
        
        {/* Top Banner */}
        <div className={styles.banner}>
          <div className={styles.bannerBgCircle}>
            <svg width="240" height="240" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
            </svg>
          </div>

          {/* Avatar Placeholder */}
          <div className={styles.avatarBig}>
            <UserRound size={30} strokeWidth={2.4} />
          </div>
          <div className={styles.bannerInfo}>
            <span className={styles.bannerSub}>
              HỒ SƠ ỨNG VIÊN
            </span>
            <h1 className={styles.bannerName}>Đông Cao</h1>
            <p className={styles.bannerEmail}>caothanhdong.41118@gmail.com</p>
          </div>
        </div>

        {/* Card 1: Thông tin cá nhân */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h2 className={styles.cardTitle}>Thông tin cá nhân</h2>
              <p className={styles.cardSubText}>Quản lý thông tin tài khoản và cài đặt cá nhân</p>
            </div>
            <button className={styles.btnEdit}>
              <PencilLine size={12} strokeWidth={2.5} />
              Sửa
            </button>
          </div>

          <div className={styles.grid}>
            <div className={styles.field}>
              <label className={styles.label}>Họ và tên</label>
              <input 
                type="text" 
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className={styles.input}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Email</label>
              <input 
                type="email" 
                value="caothanhdong.41118@gmail.com" 
                disabled 
                className={`${styles.input} ${styles.inputDisabled}`}
              />
              <span className={styles.helpText}>Email không thể thay đổi</span>
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Số điện thoại</label>
              <input 
                type="tel" 
                value={phone} 
                placeholder="Chưa cập nhật"
                onChange={(e) => setPhone(e.target.value)}
                className={styles.input}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Ngày tham gia</label>
              <input 
                type="text" 
                value="24 thg 6, 2026" 
                disabled 
                className={`${styles.input} ${styles.inputDisabled}`}
              />
            </div>
          </div>
        </div>

        {/* Card 2: Ảnh đại diện & CV mặc định */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <span className={styles.badgeOrangeText}>Ứng viên</span>
              <h2 className={styles.cardTitle} style={{ marginTop: '0.375rem' }}>Ảnh đại diện &amp; CV mặc định</h2>
              <p className={styles.cardSubText}>Avatar lưu trên Cloudinary Storage. CV mặc định tự động điền bảng candidates và dữ liệu JSON Resume trong hệ thống.</p>
            </div>
          </div>

          <div className={styles.grid}>
            {/* Left Column: Avatar */}
            <div className={styles.field} style={{ gap: '0.75rem' }}>
              <h3 className={styles.label} style={{ color: '#475569' }}>Ảnh đại diện</h3>
              <p className={styles.cardSubText} style={{ margin: 0 }}>JPG, PNG, WebP hoặc GIF — Tối đa 2MB.</p>
              <button className={styles.btnPrimary} style={{ width: 'fit-content' }}>
                <Upload size={14} strokeWidth={2.5} />
                Tải ảnh lên
              </button>
            </div>

            {/* Right Column: CV Mặc định */}
            <div className={styles.field} style={{ gap: '0.75rem' }}>
              <h3 className={styles.label} style={{ color: '#475569' }}>CV mặc định (JSON Resume)</h3>
              <p className={styles.cardSubText} style={{ margin: 0 }}>Chọn file CV bạn đã upload. Dùng cho tính năng tạo CV và hồ sơ ứng viên.</p>
              
              <div className={styles.field} style={{ gap: '0.875rem' }}>
                <div className={styles.selectWrap}>
                  <select 
                    value={defaultCv}
                    onChange={(e) => setDefaultCv(e.target.value)}
                    className={styles.select}
                  >
                    <option value="Cao Thanh Dong - CV.pdf">Cao Thanh Dong - CV.pdf</option>
                    <option value="Cao Thanh Dong - CV (Original).pdf">Cao Thanh Dong - CV (Original).pdf</option>
                  </select>
                  <div className={styles.selectIcon}>
                    <ChevronDown size={12} strokeWidth={2.5} />
                  </div>
                </div>

                <div className={styles.chips} style={{ gap: '0.625rem' }}>
                  <button className={styles.btnPrimary}>
                    <FileJson2 size={12} strokeWidth={2.5} />
                    Lưu làm mặc định
                  </button>
                  <button className={styles.btnSecondary}>
                    <Eye size={12} strokeWidth={2.5} />
                    Xem JSON Resume
                  </button>
                </div>

                <a href="https://jsonresume.org/schema" target="_blank" rel="noopener noreferrer" className={styles.linkExternal}>
                  jsonresume.org/schema
                  <Sparkles size={10} strokeWidth={2.5} />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Sở thích công việc */}
        <div className={`${styles.card} ${styles.cardOrangeSide}`}>
          <div className={styles.cardHead}>
            <div>
              <span className={styles.badgeOrangeText} style={{ backgroundColor: '#fff7ed', color: '#ea580c' }}>Gợi ý việc làm</span>
              <h2 className={styles.cardTitle} style={{ marginTop: '0.375rem' }}>Sở thích công việc</h2>
              <p className={styles.cardSubText}>Cập nhật địa điểm và lĩnh vực mong muốn để nhận gợi ý việc làm phù hợp.</p>
            </div>
            <button className={styles.btnPrimaryOrange}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
              Chỉnh sửa gợi ý việc làm
            </button>
          </div>

          <div className={styles.chipContainer}>
            <div className={styles.chipGroup}>
              <h4 className={styles.chipGroupTitle}>Địa điểm ưu tiên</h4>
              <div className={styles.chips}>
                <span className={styles.chip}>
                  <MapPin size={12} strokeWidth={2.5} /> Hồ Chí Minh
                </span>
              </div>
            </div>
            <div className={styles.chipGroup}>
              <h4 className={styles.chipGroupTitle}>Nhóm ngành quan tâm</h4>
              <div className={styles.chips}>
                <span className={styles.chip}>
                  <BriefcaseBusiness size={12} strokeWidth={2.5} /> Architecture &amp; Engineering - Kiến trúc &amp; Kỹ thuật (Civil, Structural, MEP)
                </span>
                <span className={styles.chip}>
                  <BriefcaseBusiness size={12} strokeWidth={2.5} /> BA - IT
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Thống kê tài khoản */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h2 className={styles.cardTitle}>Thống kê tài khoản</h2>
              <p className={styles.cardSubText}>Hoạt động phân tích và điểm số trong hệ thống</p>
            </div>
            <span className={styles.statsBrandText}>ATS - CAREER</span>
          </div>

          <div className={styles.statsGrid}>
            {stats.map((stat, idx) => (
              <div key={idx} className={styles.statCard}>
                <div className={styles.statCardHeader}>
                  <span className={styles.statCardLabel}>{stat.label}</span>
                  <span className={`${styles.statCardIcon} ${stat.iconClass}`}>
                    <stat.icon size={14} strokeWidth={2.5} />
                  </span>
                </div>
                <span className={styles.statCardVal}>{stat.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Coach 1-1 Card Banner */}
        <div className={styles.coachingBanner}>
          <div className={styles.coachingLeft}>
            <div className={styles.coachingIcon}>
              <Sparkles size={16} strokeWidth={2.5} />
            </div>
            <div>
              <h4 className={styles.coachingTitle}>Coach 1-1 (45-60 phút)</h4>
              <p className={styles.coachingText}>Đặt lịch buổi tư vấn 1-1 với chuyên gia sự nghiệp. Voucher đi kèm gói Career Transition, hiệu lực 90 ngày.</p>
            </div>
          </div>
          <button className={styles.coachingButton}>
            <CalendarDays size={12} strokeWidth={2.5} /> Xem &amp; đặt lịch coaching
          </button>
        </div>

        {/* Card 5: Đổi mật khẩu */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div>
              <h2 className={styles.cardTitle}>Đổi mật khẩu</h2>
              <p className={styles.cardSubText}>Bảo vệ tài khoản bằng mật khẩu mạnh.</p>
            </div>
          </div>

          <form onSubmit={(e) => e.preventDefault()} className={styles.formSmall}>
            <div className={styles.field}>
              <label className={styles.label} style={{ color: '#475569' }}>Mật khẩu hiện tại</label>
              <input 
                type="password" 
                value={currentPass}
                onChange={(e) => setCurrentPass(e.target.value)}
                placeholder="Nhập mật khẩu hiện tại"
                className={styles.input}
                style={{ backgroundColor: '#ffffff' }}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} style={{ color: '#475569' }}>Mật khẩu mới</label>
              <input 
                type="password" 
                value={newPass}
                onChange={(e) => setNewPass(e.target.value)}
                placeholder="Nhập mật khẩu mới"
                className={styles.input}
                style={{ backgroundColor: '#ffffff' }}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} style={{ color: '#475569' }}>Xác nhận mật khẩu</label>
              <input 
                type="password" 
                value={confirmPass}
                onChange={(e) => setConfirmPass(e.target.value)}
                placeholder="Nhập lại mật khẩu mới"
                className={styles.input}
                style={{ backgroundColor: '#ffffff' }}
              />
            </div>
            <button 
              type="submit" 
              className={styles.btnPrimary}
              style={{ padding: '0.75rem 1.5rem', width: 'fit-content', marginTop: '0.5rem' }}
            >
              <LockKeyhole size={14} strokeWidth={2.5} /> Đổi mật khẩu
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
