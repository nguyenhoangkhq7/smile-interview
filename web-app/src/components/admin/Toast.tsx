'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

export type ToastType = 'success' | 'error' | 'info';

interface ToastMessage {
  id: number;
  type: ToastType;
  message: string;
}

// ── Global toast store (simple singleton without Zustand) ─────────────────────
type Listener = (msg: ToastMessage) => void;
const listeners: Listener[] = [];
let nextId = 1;

function subscribe(fn: Listener) {
  listeners.push(fn);
  return () => {
    const idx = listeners.indexOf(fn);
    if (idx !== -1) listeners.splice(idx, 1);
  };
}

/**
 * Programmatic toast trigger — call from anywhere (no hooks required).
 * @example toast.success('Lưu thành công!');
 */
export const toast = {
  success: (message: string) => emit('success', message),
  error:   (message: string) => emit('error', message),
  info:    (message: string) => emit('info', message),
};

function emit(type: ToastType, message: string) {
  const msg: ToastMessage = { id: nextId++, type, message };
  listeners.forEach((fn) => fn(msg));
}

// ── Icons ─────────────────────────────────────────────────────────────────────
const icons: Record<ToastType, React.ReactNode> = {
  success: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="m9 11 3 3L22 4" />
    </svg>
  ),
  error: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" />
    </svg>
  ),
  info: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
    </svg>
  ),
};

const styles: Record<ToastType, string> = {
  success: 'border-emerald-700 bg-emerald-950/80 text-emerald-300',
  error:   'border-red-700 bg-red-950/80 text-red-300',
  info:    'border-blue-700 bg-blue-950/80 text-blue-300',
};

// ── ToastContainer — mount once in admin layout ───────────────────────────────
export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    const unsub = subscribe((msg) => {
      setToasts((prev) => [...prev, msg]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== msg.id));
      }, 3500);
    });
    return unsub;
  }, []);

  if (typeof window === 'undefined') return null;

  return createPortal(
    <div
      aria-live="polite"
      className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-sm text-sm font-medium shadow-xl pointer-events-auto animate-slide-in ${styles[t.type]}`}
          style={{ animation: 'slideInRight 0.3s ease' }}
        >
          <span className="flex-shrink-0">{icons[t.type]}</span>
          <span>{t.message}</span>
        </div>
      ))}
      <style>{`
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>,
    document.body
  );
}
