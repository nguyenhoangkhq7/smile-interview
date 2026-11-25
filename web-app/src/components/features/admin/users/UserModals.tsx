'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  LockOpen,
  UserPlus,
  X,
} from 'lucide-react';
import { AdminUserRecord } from './types';

interface LockAccountModalProps {
  targetUser: AdminUserRecord | null;
  onClose: () => void;
  onConfirm: (user: AdminUserRecord) => void;
}

export function LockAccountModal({
  targetUser,
  onClose,
  onConfirm,
}: LockAccountModalProps) {
  if (!targetUser) return null;

  const isLocked = targetUser.status === 'LOCKED';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#293041]/40 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-md animate-in fade-in zoom-in-95 duration-200 rounded-2xl bg-white p-6 shadow-2xl">
        <div
          className={`mb-4 flex size-12 items-center justify-center rounded-full ${
            isLocked ? 'bg-[#95f8a7] text-[#00210a]' : 'bg-[#ffdad6] text-[#93000a]'
          }`}
        >
          {isLocked ? <LockOpen className="size-6" /> : <AlertTriangle className="size-6" />}
        </div>

        <h3 className="text-xl font-bold text-[#141b2c]">
          {isLocked ? 'Xác nhận mở khóa tài khoản' : 'Xác nhận khóa tài khoản'}
        </h3>

        <p className="mt-2 text-sm text-[#5c4039]">
          {isLocked ? (
            <>
              Bạn có chắc muốn khôi phục quyền truy cập và đăng nhập cho tài khoản{' '}
              <strong className="font-semibold text-[#141b2c]">{targetUser.fullName}</strong>?
            </>
          ) : (
            <>
              Bạn có chắc muốn vô hiệu hóa phiên và khóa quyền đăng nhập của người dùng{' '}
              <strong className="font-semibold text-[#141b2c]">{targetUser.fullName}</strong>?
            </>
          )}
        </p>

        <div className="mt-4 rounded-lg bg-[#f1f3ff] p-3 text-xs text-[#5c4039]">
          {isLocked
            ? 'Ghi chú: Người dùng sẽ có thể đăng nhập lại và tiếp tục các phiên luyện tập phỏng vấn.'
            : 'Lý do khóa: Phát hiện hành vi nghi vấn spam session hoặc yêu cầu từ bộ phận An ninh & Bảo mật dữ liệu.'}
        </div>

        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-[#e0e8ff] px-4 py-2 text-[13px] font-medium text-[#141b2c] transition-colors hover:bg-[#e9edff] cursor-pointer"
          >
            Hủy bỏ
          </button>

          <button
            type="button"
            onClick={() => onConfirm(targetUser)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-colors cursor-pointer ${
              isLocked ? 'bg-[#006b2f] hover:bg-[#1f8642]' : 'bg-[#ba1a1a] hover:bg-[#ba1a1a]/90'
            }`}
          >
            {isLocked ? <LockOpen className="size-4" /> : <Lock className="size-4" />}
            <span>{isLocked ? 'Mở khóa ngay' : 'Khóa ngay'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

interface AddAdminModalProps {
  open: boolean;
  onClose: () => void;
  onAddAdmin: (payload: { fullName: string; email: string; level: string }) => void;
}

export function AddAdminModal({ open, onClose, onAddAdmin }: AddAdminModalProps) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [level, setLevel] = useState('ADMIN (Điều phối viên hệ thống)');

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAddAdmin({
      fullName: fullName.trim() || 'Trần Quốc Toản',
      email: email.trim() || 'toan.tran@smile.ai',
      level,
    });
    setFullName('');
    setEmail('');
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#293041]/40 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
    >
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-lg animate-in fade-in zoom-in-95 duration-200 rounded-2xl bg-white p-6 shadow-2xl"
      >
        <div className="mb-4 flex items-center justify-between border-b border-[#e9edff] pb-3">
          <div className="flex items-center gap-2">
            <UserPlus className="size-5.5 text-[#ad2c00]" />
            <h3 className="text-xl font-bold text-[#141b2c]">Thêm Quản trị viên mới</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="rounded p-1 text-[#5c4039] transition-colors hover:text-[#141b2c] cursor-pointer"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="space-y-4 text-sm">
          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#141b2c]">Họ và tên</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ví dụ: Trần Quốc Toản"
              className="w-full rounded-lg bg-[#f1f3ff] px-3 py-2 text-sm text-[#141b2c] outline-none transition-colors focus:bg-[#e9edff]"
            />
          </div>

          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#141b2c]">
              Email tổ chức (@smile.ai)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="toan.tran@smile.ai"
              className="w-full rounded-lg bg-[#f1f3ff] px-3 py-2 text-sm text-[#141b2c] outline-none transition-colors focus:bg-[#e9edff]"
            />
          </div>

          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#141b2c]">
              Cấp độ phân quyền
            </label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="w-full rounded-lg bg-[#f1f3ff] px-3 py-2 text-sm text-[#141b2c] outline-none transition-colors focus:bg-[#e9edff]"
            >
              <option>ADMIN (Điều phối viên hệ thống)</option>
              <option>MODERATOR (Giám sát phỏng vấn)</option>
              <option>SECURITY_AUDITOR (Kiểm toán bảo mật)</option>
            </select>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-[#e0e8ff] px-4 py-2 text-[13px] font-medium text-[#141b2c] transition-colors hover:bg-[#e9edff] cursor-pointer"
          >
            Đóng
          </button>
          <button
            type="submit"
            className="rounded-lg bg-[#ad2c00] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#d83900] cursor-pointer"
          >
            Cấp quyền ngay
          </button>
        </div>
      </form>
    </div>
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
