'use client';

import type { LucideIcon } from 'lucide-react';
import {
  BarChart3, CalendarDays, Coins, Eye, FileJson2, LockKeyhole,
  MapPin, PencilLine, Sparkles, Star, Upload, UserRound,
  BriefcaseBusiness, ChevronDown, CheckCircle, AlertCircle, X,
} from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import styles from './profile.module.css';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { useAuthStore } from '@/store/authStore';
import axiosClient from '@/lib/axiosClient';

// ── Types ─────────────────────────────────────────────────────────────────────

type StatItem = {
  label: string;
  value: number;
  icon: LucideIcon;
  iconClass: string;
};

type ResumeOption = {
  id: number;
  name: string;
};

// ── Toast helper (lightweight, no external dep) ───────────────────────────────

type ToastState = { type: 'success' | 'error'; message: string } | null;

function Toast({ toast }: { toast: ToastState }) {
  if (!toast) return null;
  const isSuccess = toast.type === 'success';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.75rem 1rem',
        borderRadius: '0.5rem',
        marginBottom: '1rem',
        fontSize: '0.875rem',
        background: isSuccess ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
        border: `1px solid ${isSuccess ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'}`,
        color: isSuccess ? '#4ade80' : '#f87171',
      }}
    >
      {isSuccess
        ? <CheckCircle size={15} />
        : <AlertCircle size={15} />}
      {toast.message}
    </div>
  );
}

// ── Admin-only Stats block ────────────────────────────────────────────────────

function AdminStatsBlock({ stats }: { stats: StatItem[] }) {
  return (
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
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const { user, updateUser } = useAuthStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Personal info state ──────────────────────────────────────────
  const [fullName, setFullName] = useState(user?.username ?? '');
  const [phone, setPhone] = useState(user?.phoneNumber ?? '');
  const [isEditing, setIsEditing] = useState(false);
  const [infoLoading, setInfoLoading] = useState(false);
  const [infoToast, setInfoToast] = useState<ToastState>(null);

  // Sync inputs with authStore when user loads or updates
  useEffect(() => {
    if (user) {
      setFullName(user.username);
      setPhone(user.phoneNumber ?? '');
    }
  }, [user]);

  const handleSaveProfile = async () => {
    if (!fullName.trim()) {
      setInfoToast({ type: 'error', message: 'Họ và tên không được để trống.' });
      return;
    }

    setInfoLoading(true);
    setInfoToast(null);

    try {
      const { data } = await axiosClient.put('/api/auth/profile', {
        username: fullName,
        phoneNumber: phone,
        avatarUrl: user?.avatarUrl,
      });

      updateUser({
        username: data.username,
        phoneNumber: data.phoneNumber,
        avatarUrl: data.avatarUrl,
      });

      setInfoToast({ type: 'success', message: 'Cập nhật thông tin cá nhân thành công!' });
      setIsEditing(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Cập nhật thất bại. Vui lòng thử lại sau.';
      setInfoToast({ type: 'error', message: msg });
    } finally {
      setInfoLoading(false);
      setTimeout(() => setInfoToast(null), 5000);
    }
  };

  const handleCancelEdit = () => {
    setFullName(user?.username ?? '');
    setPhone(user?.phoneNumber ?? '');
    setIsEditing(false);
    setInfoToast(null);
  };

  // ── Avatar Upload State ──────────────────────────────────────────
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [avatarToast, setAvatarToast] = useState<ToastState>(null);

  const triggerAvatarUpload = () => {
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const maxSize = 2 * 1024 * 1024; // 2MB

    if (file.size > maxSize) {
      setAvatarToast({ type: 'error', message: 'Kích thước ảnh đại diện không được vượt quá 2MB.' });
      return;
    }

    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
      setAvatarToast({ type: 'error', message: 'Chỉ chấp nhận các định dạng ảnh: JPG, PNG, WebP hoặc GIF.' });
      return;
    }

    setAvatarLoading(true);
    setAvatarToast(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const { data } = await axiosClient.post('/api/auth/avatar', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      updateUser({
        avatarUrl: data.avatarUrl,
      });

      setAvatarToast({ type: 'success', message: 'Cập nhật ảnh đại diện thành công!' });
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Tải ảnh lên thất bại. Vui lòng thử lại sau.';
      setAvatarToast({ type: 'error', message: msg });
    } finally {
      setAvatarLoading(false);
      // Reset input value to allow uploading same file again
      if (fileInputRef.current) fileInputRef.current.value = '';
      setTimeout(() => setAvatarToast(null), 5000);
    }
  };

  // Helper to construct fully qualified image URL if it's stored locally
  const getAvatarUrl = (url: string | null | undefined) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8081';
    return `${baseUrl.replace(/\/$/, '')}/${url.replace(/^\//, '')}`;
  };

  // ── Default CV state ─────────────────────────────────────────────
  // Mock list — will be replaced with a real API call when the resume API is ready
  const resumes: ResumeOption[] = [
    { id: 1, name: 'CV của tôi' },
  ];
  const [selectedResumeId, setSelectedResumeId] = useState<number>(
    user?.defaultResumeId ? Number(user.defaultResumeId) : (resumes[0]?.id ?? 0)
  );

  const handleSaveDefaultResume = () => {
    console.log('[Profile] Save default resume:', selectedResumeId);
    setCvToast({ type: 'success', message: `Đã lưu CV mặc định (id=${selectedResumeId}).` });
    setTimeout(() => setCvToast(null), 3000);
  };

  const [cvToast, setCvToast] = useState<ToastState>(null);

  // ── Change password state ────────────────────────────────────────
  const [currentPass, setCurrentPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [pwToast, setPwToast] = useState<ToastState>(null);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwToast(null);

    if (newPass !== confirmPass) {
      setPwToast({ type: 'error', message: 'Mật khẩu mới và xác nhận không khớp.' });
      return;
    }

    setPwLoading(true);
    try {
      await axiosClient.post('/api/auth/change-password', {
        currentPassword: currentPass,
        newPassword: newPass,
        confirmPassword: confirmPass,
      });

      // Clear form on success
      setCurrentPass('');
      setNewPass('');
      setConfirmPass('');
      setPwToast({ type: 'success', message: 'Đổi mật khẩu thành công!' });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; message?: string } } };
      const msg =
        axiosErr?.response?.data?.detail ||
        axiosErr?.response?.data?.message ||
        'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại mật khẩu hiện tại.';
      setPwToast({ type: 'error', message: msg });
    } finally {
      setPwLoading(false);
      setTimeout(() => setPwToast(null), 5000);
    }
  };

  // ── Admin stats (only rendered for ADMIN role) ───────────────────
  const stats: StatItem[] = [
    { label: 'LƯỢT PHÂN TÍCH CV', value: 0, icon: BarChart3, iconClass: styles.statIconBlue },
    { label: 'PHÂN TÍCH HÔM NAY', value: 0, icon: CalendarDays, iconClass: styles.statIconOrange },
    { label: 'ĐIỂM TRUNG BÌNH', value: 0, icon: Star, iconClass: styles.statIconGreen },
    { label: 'COINS', value: 0, icon: Coins, iconClass: styles.statIconAmber },
  ];

  return (
    <ProtectedRoute>
      <div className={styles.page}>
        <div className={styles.inner}>

          {/* ── Top Banner ────────────────────────────────────────── */}
          <div className={styles.banner}>
            <div className={styles.bannerBgCircle}>
              <svg width="240" height="240" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
              </svg>
            </div>

            {/* Avatar: show image if avatarUrl exists, else placeholder icon */}
            <div className={styles.avatarBig}>
              {user?.avatarUrl ? (
                <img
                  src={getAvatarUrl(user.avatarUrl)}
                  alt="Avatar"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
                />
              ) : (
                <UserRound size={30} strokeWidth={2.4} />
              )}
            </div>

            <div className={styles.bannerInfo}>
              <span className={styles.bannerSub}>HỒ SƠ ỨNG VIÊN</span>
              <h1 className={styles.bannerName}>{user?.username ?? '...'}</h1>
              <p className={styles.bannerEmail}>{user?.email ?? ''}</p>
            </div>
          </div>

          {/* ── Card 1: Thông tin cá nhân ─────────────────────────── */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <div>
                <h2 className={styles.cardTitle}>Thông tin cá nhân</h2>
                <p className={styles.cardSubText}>Quản lý thông tin tài khoản và cài đặt cá nhân</p>
              </div>
              {!isEditing ? (
                <button className={styles.btnEdit} onClick={() => setIsEditing(true)}>
                  <PencilLine size={12} strokeWidth={2.5} />
                  Sửa
                </button>
              ) : (
                <button className={styles.btnEdit} onClick={handleCancelEdit} style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.2)' }}>
                  <X size={12} strokeWidth={2.5} />
                  Hủy
                </button>
              )}
            </div>

            <div className={styles.grid}>
              <div className={styles.field}>
                <label className={styles.label}>Họ và tên</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className={`${styles.input} ${!isEditing ? styles.inputDisabled : ''}`}
                  disabled={!isEditing}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Email</label>
                <input
                  type="email"
                  value={user?.email ?? ''}
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
                  className={`${styles.input} ${!isEditing ? styles.inputDisabled : ''}`}
                  disabled={!isEditing}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Vai trò</label>
                <input
                  type="text"
                  value={user?.role ?? ''}
                  disabled
                  className={`${styles.input} ${styles.inputDisabled}`}
                />
              </div>
            </div>

            <Toast toast={infoToast} />

            {isEditing && (
              <button
                onClick={handleSaveProfile}
                disabled={infoLoading}
                className={styles.btnPrimary}
                style={{ marginTop: '1.25rem', width: 'fit-content' }}
              >
                {infoLoading ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 0.9s linear infinite' }}>
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                ) : (
                  <CheckCircle size={14} strokeWidth={2.5} />
                )}
                {infoLoading ? 'Đang lưu...' : 'Lưu thay đổi'}
              </button>
            )}
          </div>

          {/* ── Card 2: Ảnh đại diện & CV mặc định ───────────────── */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <div>
                <span className={styles.badgeOrangeText}>Ứng viên</span>
                <h2 className={styles.cardTitle} style={{ marginTop: '0.375rem' }}>
                  Ảnh đại diện &amp; CV mặc định
                </h2>
                <p className={styles.cardSubText}>
                  Avatar lưu trên hệ thống lưu trữ. CV mặc định tự động điền bảng candidates
                  và dữ liệu JSON Resume trong hệ thống.
                </p>
              </div>
            </div>

            <div className={styles.grid}>
              {/* Left: Avatar upload */}
              <div className={styles.field} style={{ gap: '0.75rem' }}>
                <h3 className={styles.label} style={{ color: '#475569' }}>Ảnh đại diện</h3>
                <p className={styles.cardSubText} style={{ margin: 0 }}>JPG, PNG, WebP hoặc GIF — Tối đa 2MB.</p>
                
                <Toast toast={avatarToast} />
                
                <button
                  className={styles.btnPrimary}
                  style={{ width: 'fit-content' }}
                  onClick={triggerAvatarUpload}
                  disabled={avatarLoading}
                >
                  {avatarLoading ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 0.9s linear infinite' }}>
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                  ) : (
                    <Upload size={14} strokeWidth={2.5} />
                  )}
                  {avatarLoading ? 'Đang tải lên...' : 'Tải ảnh lên'}
                </button>
                
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleAvatarChange}
                  style={{ display: 'none' }}
                  accept="image/jpeg, image/jpg, image/png, image/webp, image/gif"
                />
              </div>

              {/* Right: Default CV */}
              <div className={styles.field} style={{ gap: '0.75rem' }}>
                <h3 className={styles.label} style={{ color: '#475569' }}>CV mặc định (JSON Resume)</h3>
                <p className={styles.cardSubText} style={{ margin: 0 }}>
                  Chọn file CV bạn đã upload. Dùng cho tính năng tạo CV và hồ sơ ứng viên.
                </p>

                <div className={styles.field} style={{ gap: '0.875rem' }}>
                  <Toast toast={cvToast} />

                  <div className={styles.selectWrap}>
                    <select
                      value={selectedResumeId}
                      onChange={(e) => setSelectedResumeId(Number(e.target.value))}
                      className={styles.select}
                    >
                      {resumes.map((r) => (
                        <option key={r.id} value={r.id}>{r.name}</option>
                      ))}
                    </select>
                    <div className={styles.selectIcon}>
                      <ChevronDown size={12} strokeWidth={2.5} />
                    </div>
                  </div>

                  <div className={styles.chips} style={{ gap: '0.625rem' }}>
                    <button className={styles.btnPrimary} onClick={handleSaveDefaultResume}>
                      <FileJson2 size={12} strokeWidth={2.5} />
                      Lưu làm mặc định
                    </button>
                    <button className={styles.btnSecondary}>
                      <Eye size={12} strokeWidth={2.5} />
                      Xem JSON Resume
                    </button>
                  </div>

                  <a
                    href="https://jsonresume.org/schema"
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.linkExternal}
                  >
                    jsonresume.org/schema
                    <Sparkles size={10} strokeWidth={2.5} />
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* ── Card 3: Sở thích công việc ────────────────────────── */}
          <div className={`${styles.card} ${styles.cardOrangeSide}`}>
            <div className={styles.cardHead}>
              <div>
                <span className={styles.badgeOrangeText} style={{ backgroundColor: '#fff7ed', color: '#ea580c' }}>
                  Gợi ý việc làm
                </span>
                <h2 className={styles.cardTitle} style={{ marginTop: '0.375rem' }}>Sở thích công việc</h2>
                <p className={styles.cardSubText}>
                  Cập nhật địa điểm và lĩnh vực mong muốn để nhận gợi ý việc làm phù hợp.
                </p>
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
                    <BriefcaseBusiness size={12} strokeWidth={2.5} /> BA - IT
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Card 4: Thống kê tài khoản (Admin only) ───────────── */}
          {user?.role === 'ADMIN' && <AdminStatsBlock stats={stats} />}

          {/* ── Coach Banner ───────────────────────────────────────── */}
          <div className={styles.coachingBanner}>
            <div className={styles.coachingLeft}>
              <div className={styles.coachingIcon}>
                <Sparkles size={16} strokeWidth={2.5} />
              </div>
              <div>
                <h4 className={styles.coachingTitle}>Coach 1-1 (45-60 phút)</h4>
                <p className={styles.coachingText}>
                  Đặt lịch buổi tư vấn 1-1 với chuyên gia sự nghiệp. Voucher đi kèm gói Career Transition, hiệu lực 90 ngày.
                </p>
              </div>
            </div>
            <button className={styles.coachingButton}>
              <CalendarDays size={12} strokeWidth={2.5} /> Xem &amp; đặt lịch coaching
            </button>
          </div>

          {/* ── Card 5: Đổi mật khẩu ──────────────────────────────── */}
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <div>
                <h2 className={styles.cardTitle}>Đổi mật khẩu</h2>
                <p className={styles.cardSubText}>Bảo vệ tài khoản bằng mật khẩu mạnh.</p>
              </div>
            </div>

            <form onSubmit={handleChangePassword} className={styles.formSmall}>
              <Toast toast={pwToast} />

              <div className={styles.field}>
                <label className={styles.label} style={{ color: '#475569' }}>Mật khẩu hiện tại</label>
                <input
                  type="password"
                  value={currentPass}
                  onChange={(e) => setCurrentPass(e.target.value)}
                  placeholder="Nhập mật khẩu hiện tại"
                  required
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
                  placeholder="Nhập mật khẩu mới (tối thiểu 6 ký tự)"
                  required
                  minLength={6}
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
                  required
                  className={styles.input}
                  style={{ backgroundColor: '#ffffff' }}
                />
              </div>

              <button
                type="submit"
                disabled={pwLoading}
                className={styles.btnPrimary}
                style={{ padding: '0.75rem 1.5rem', width: 'fit-content', marginTop: '0.5rem' }}
              >
                {pwLoading ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 0.9s linear infinite' }}>
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                ) : (
                  <LockKeyhole size={14} strokeWidth={2.5} />
                )}
                {pwLoading ? 'Đang đổi mật khẩu...' : 'Đổi mật khẩu'}
              </button>
            </form>
          </div>

        </div>
      </div>
    </ProtectedRoute>
  );
}
