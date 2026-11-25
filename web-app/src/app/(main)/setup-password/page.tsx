'use client';

import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { useState, type FormEvent } from 'react';

export default function SetupPasswordPage() {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token');
    if (!token) return setError('Liên kết đặt mật khẩu không hợp lệ.');
    if (password !== confirmation) return setError('Hai mật khẩu chưa trùng khớp.');
    if (new TextEncoder().encode(password).length > 72) return setError('Mật khẩu vượt quá 72 byte.');

    setPending(true);
    setError('');
    try {
      const response = await fetch('/api/auth/password-setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      if (!response.ok) {
        setError(response.status === 400 ? 'Liên kết không hợp lệ, đã hết hạn hoặc đã được sử dụng.' : 'Không đặt được mật khẩu. Vui lòng thử lại.');
        return;
      }
      window.history.replaceState(null, '', window.location.pathname);
      useAuthStore.getState().logout();
      setPassword('');
      setConfirmation('');
      setDone(true);
    } catch {
      setError('Không kết nối được với máy chủ. Vui lòng thử lại.');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto my-12 w-full max-w-md rounded-2xl bg-white dark:bg-card p-6 shadow-sm">
      <h1 className="text-xl font-semibold">Đặt mật khẩu</h1>
      {done ? (
        <p role="status" className="mt-4 text-sm">Đã cập nhật mật khẩu. <Link href="/login" className="underline">Đăng nhập</Link></p>
      ) : (
        <form className="mt-4 space-y-4" onSubmit={submit}>
          <label className="block text-sm">Mật khẩu mới
            <input type="password" autoComplete="new-password" required minLength={8} maxLength={72}
              className="mt-1 w-full rounded-lg border p-2" value={password} onChange={event => setPassword(event.target.value)} />
          </label>
          <label className="block text-sm">Nhập lại mật khẩu
            <input type="password" autoComplete="new-password" required minLength={8} maxLength={72}
              className="mt-1 w-full rounded-lg border p-2" value={confirmation} onChange={event => setConfirmation(event.target.value)} />
          </label>
          {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p>}
          <button type="submit" disabled={pending} className="rounded-lg bg-[#ad2c00] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            Lưu mật khẩu
          </button>
        </form>
      )}
    </div>
  );
}
