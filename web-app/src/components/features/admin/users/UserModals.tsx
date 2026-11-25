'use client';

import { useState, type FormEvent, type ReactNode } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { AdminUserRecord } from './types';

const input = 'mt-1 w-full rounded-lg bg-[#f1f3ff] dark:bg-muted p-2 text-sm';
const button = 'rounded-lg bg-[#ad2c00] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60';

function Dialog({ title, busy, onClose, children }: {
  title: string; busy: boolean; onClose: () => void; children: ReactNode;
}) {
  return (
    <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-[70] grid place-items-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button type="button" onClick={onClose} disabled={busy} className="text-sm disabled:opacity-50">Đóng</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function LockAccountModal({ targetUser, busy, onClose, onConfirm }: {
  targetUser: AdminUserRecord; busy: boolean; onClose: () => void;
  onConfirm: (user: AdminUserRecord, reason?: string) => void;
}) {
  const [reason, setReason] = useState('');
  const locked = targetUser.status === 'LOCKED';

  return (
    <Dialog title={locked ? 'Mở khóa tài khoản' : 'Khóa tài khoản'} busy={busy} onClose={onClose}>
      <p className="mb-4 text-sm">
        {locked ? 'Khôi phục quyền đăng nhập cho ' : 'Vô hiệu hóa quyền đăng nhập và các phiên đang dùng của '}
        <strong>{targetUser.fullName}</strong>.
      </p>
      {!locked && (
        <label className="block text-sm">Lý do khóa (không bắt buộc)
          <textarea className={input} maxLength={500} rows={3} value={reason} onChange={event => setReason(event.target.value)} />
        </label>
      )}
      <div className="mt-4 flex justify-end">
        <button type="button" className={button} disabled={busy} onClick={() => onConfirm(targetUser, reason.trim() || undefined)}>
          {locked ? 'Mở khóa' : 'Khóa tài khoản'}
        </button>
      </div>
    </Dialog>
  );
}

export function AddAdminModal({ busy, onClose, onAddAdmin }: {
  busy: boolean; onClose: () => void;
  onAddAdmin: (payload: { fullName: string; email: string }) => void;
}) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (fullName.trim() && email.trim()) onAddAdmin({ fullName: fullName.trim(), email: email.trim() });
  }

  return (
    <Dialog title="Thêm quản trị viên mới" busy={busy} onClose={onClose}>
      <form className="space-y-4" onSubmit={submit}>
        <label className="block text-sm">Họ và tên
          <input type="text" autoComplete="name" required maxLength={255} className={input}
            value={fullName} onChange={event => setFullName(event.target.value)} />
        </label>
        <label className="block text-sm">Email
          <input type="email" autoComplete="email" required maxLength={255} className={input}
            value={email} onChange={event => setEmail(event.target.value)} />
        </label>
        <p className="text-xs text-[#5c4039] dark:text-muted-foreground">Hệ thống tạo liên kết dùng một lần để quản trị viên mới đặt mật khẩu.</p>
        <div className="flex justify-end"><button type="submit" className={button} disabled={busy}>Tạo quản trị viên</button></div>
      </form>
    </Dialog>
  );
}

interface ActionToastProps {
  message: string | null;
}

export function ActionToast({ message }: ActionToastProps) {
  return (
    <div
      aria-live="polite"
      className={`pointer-events-none fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl bg-[#293041] px-4 py-3 text-[13px] font-medium text-[#edf0ff] shadow-xl transition-all duration-300 ${
        message ? 'translate-y-0 opacity-100' : 'translate-y-24 opacity-0'
      }`}
    >
      <CheckCircle2 className="size-5 text-[#95f8a7]" />
      <span>{message || 'Thao tác thành công'}</span>
    </div>
  );
}
