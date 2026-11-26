'use client';

import { toast } from 'sonner';
import type { PasswordSetupLink } from './types';

export default function PasswordSetupLinkDialog({ link, onClose }: { link: PasswordSetupLink; onClose: () => void }) {
  const url = new URL('/setup-password', window.location.origin);
  url.hash = new URLSearchParams({ token: link.token }).toString();

  async function copy() {
    try {
      await navigator.clipboard.writeText(url.href);
      toast.success('Đã sao chép liên kết.');
    } catch {
      toast.error('Hãy chọn và sao chép liên kết trong ô bên dưới.');
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="password-link-title"
      className="fixed inset-0 z-[70] grid place-items-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-card p-6 shadow-lg">
        <h3 id="password-link-title" className="text-lg font-semibold">Liên kết đặt mật khẩu</h3>
        <p className="mt-2 text-sm">Chia sẻ riêng cho người nhận. Liên kết dùng một lần và hết hạn lúc {' '}
          {new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(link.expiresAt))}.
        </p>
        <input aria-label="Liên kết đặt mật khẩu" className="mt-4 w-full rounded-lg bg-[#f1f3ff] dark:bg-muted p-2 text-sm"
          readOnly value={url.href} onFocus={event => event.currentTarget.select()} />
        <div className="mt-4 flex justify-end gap-3 text-sm">
          <button type="button" onClick={onClose}>Đóng</button>
          <button type="button" onClick={() => void copy()} className="rounded-lg bg-[#ad2c00] px-4 py-2 text-white">
            Sao chép liên kết
          </button>
        </div>
      </div>
    </div>
  );
}
