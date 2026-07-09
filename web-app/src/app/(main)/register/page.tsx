'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './register.module.css';
import axiosClient from '@/lib/axiosClient';

export default function RegisterPage() {
  const router = useRouter();

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ fullName: '', email: '', password: '', confirmPassword: '' });
  const [passwordError, setPasswordError] = useState('');
  const [apiError, setApiError] = useState('');
  const [success, setSuccess] = useState(false);

  const strength = (() => {
    const p = form.password;
    if (!p) return null;
    if (p.length < 6) return { label: 'Yếu', cls: styles.strengthWeak, w: '33%' };
    if (p.length < 10) return { label: 'Trung bình', cls: styles.strengthMedium, w: '66%' };
    return { label: 'Mạnh', cls: styles.strengthStrong, w: '100%' };
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (form.password !== form.confirmPassword) {
      setPasswordError('Mật khẩu xác nhận không khớp.');
      return;
    }
    setPasswordError('');
    setApiError('');
    setLoading(true);

    try {
      await axiosClient.post('/api/auth/register', {
        username: form.fullName,
        email: form.email,
        password: form.password,
      });

      setSuccess(true);
      // Brief success flash, then redirect to login
      setTimeout(() => router.push('/login'), 1500);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Đăng ký thất bại. Vui lòng thử lại.';
      setApiError(msg);
    } finally {
      setLoading(false);
    }
  };

  const EyeOpen = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
  const EyeOff = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );

  return (
    <div className={styles.page}>
      <div className={styles.bgBlob1} />
      <div className={styles.bgBlob2} />

      <div className={styles.wrap}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <div className={styles.cardIcon}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h1 className={styles.cardTitle}>Tạo tài khoản</h1>
            <p className={styles.cardSub}>Miễn phí — bắt đầu ngay hôm nay</p>
          </div>

          {/* Success banner */}
          {success && (
            <div style={{
              background: 'rgba(34,197,94,0.12)',
              border: '1px solid rgba(34,197,94,0.4)',
              borderRadius: '10px',
              padding: '10px 14px',
              marginBottom: '16px',
              color: '#4ade80',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Đăng ký thành công! Đang chuyển hướng đến trang đăng nhập...
            </div>
          )}

          {/* API error banner */}
          {apiError && (
            <div style={{
              background: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: '10px',
              padding: '10px 14px',
              marginBottom: '16px',
              color: '#f87171',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {apiError}
            </div>
          )}

          <form onSubmit={handleSubmit} className={styles.form}>
            {/* Full Name */}
            <div className={styles.field}>
              <label htmlFor="fullName" className={styles.label}>Họ và tên</label>
              <div className={styles.inputWrap}>
                <span className={styles.inputIcon}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                  </svg>
                </span>
                <input id="fullName" type="text" placeholder="Nguyễn Văn An" required value={form.fullName}
                  onChange={(e) => setForm({ ...form, fullName: e.target.value })} className={styles.input}
                  autoComplete="name" />
              </div>
            </div>

            {/* Email */}
            <div className={styles.field}>
              <label htmlFor="reg-email" className={styles.label}>Email</label>
              <div className={styles.inputWrap}>
                <span className={styles.inputIcon}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" />
                  </svg>
                </span>
                <input id="reg-email" type="email" placeholder="you@example.com" required value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} className={styles.input}
                  autoComplete="email" />
              </div>
            </div>

            {/* Password */}
            <div className={styles.field}>
              <label htmlFor="reg-password" className={styles.label}>Mật khẩu</label>
              <div className={styles.inputWrap}>
                <span className={styles.inputIcon}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </span>
                <input id="reg-password" type={showPassword ? 'text' : 'password'} placeholder="Ít nhất 6 ký tự"
                  required minLength={6} value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className={`${styles.input} ${styles.inputWithEye}`}
                  autoComplete="new-password" />
                <button type="button" className={styles.eyeBtn} onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? <EyeOff /> : <EyeOpen />}
                </button>
              </div>
              {strength && (
                <div className={styles.strengthRow}>
                  <div className={styles.strengthBar}>
                    <div className={`${styles.strengthFill} ${strength.cls}`} style={{ width: strength.w }} />
                  </div>
                  <span className={styles.strengthLabel}>{strength.label}</span>
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div className={styles.field}>
              <label htmlFor="confirm-password" className={styles.label}>Xác nhận mật khẩu</label>
              <div className={styles.inputWrap}>
                <span className={styles.inputIcon}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </span>
                <input id="confirm-password" type={showConfirm ? 'text' : 'password'} placeholder="Nhập lại mật khẩu"
                  required value={form.confirmPassword}
                  onChange={(e) => { setForm({ ...form, confirmPassword: e.target.value }); setPasswordError(''); }}
                  className={`${styles.input} ${styles.inputWithEye} ${passwordError ? styles.inputError : ''}`}
                  autoComplete="new-password" />
                <button type="button" className={styles.eyeBtn} onClick={() => setShowConfirm(!showConfirm)}>
                  {showConfirm ? <EyeOff /> : <EyeOpen />}
                </button>
              </div>
              {passwordError && <p className={styles.errorText}>{passwordError}</p>}
            </div>

            {/* Terms */}
            <p className={styles.termsText}>
              Bằng cách đăng ký, bạn đồng ý với{' '}
              <Link href="#" className={styles.termsLink}>Điều khoản sử dụng</Link>{' '}và{' '}
              <Link href="#" className={styles.termsLink}>Chính sách bảo mật</Link>.
            </p>

            {/* Submit */}
            <button type="submit" disabled={loading || success} className={styles.submitBtn}>
              {loading ? (
                <svg width="16" height="16" className={styles.spinner} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                </svg>
              )}
              {loading ? 'Đang tạo tài khoản...' : 'Tạo tài khoản'}
            </button>
          </form>

          <p className={styles.footerText}>
            Đã có tài khoản?{' '}
            <Link href="/login" className={styles.footerLink}>Đăng nhập</Link>
          </p>
        </div>

        <Link href="/" className={styles.backLink}>← Quay lại trang chủ</Link>
      </div>
    </div>
  );
}
