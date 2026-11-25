'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import axiosClient from '@/lib/axiosClient';
import { expireSession, getTokenExpiresAt } from '@/lib/authSession';
import { useAuthStore } from '@/store/authStore';

const SESSION_HEARTBEAT_MS = 4000;

export default function AuthSessionMonitor() {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    if (isAuthenticated && user?.role === 'ADMIN' && pathname && pathname !== '/setup-password' && !pathname.startsWith('/admin')) {
      router.replace('/admin');
    }
  }, [isAuthenticated, user, pathname, router]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const checkExpiry = () => {
      clearTimeout(timer);
      const currentToken = useAuthStore.getState().token;
      if (!currentToken) return;

      const expiresAt = getTokenExpiresAt(currentToken);
      const remaining = expiresAt === null ? 0 : expiresAt - Date.now();
      if (remaining <= 0) {
        expireSession(currentToken, 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
        return;
      }
      // Browsers cap timeout delays at a signed 32-bit integer.
      timer = setTimeout(checkExpiry, Math.min(remaining, 2_147_483_647));
    };

    const unsubscribe = useAuthStore.subscribe(checkExpiry);
    const unsubscribeHydration = useAuthStore.persist.onFinishHydration(checkExpiry);
    window.addEventListener('focus', checkExpiry);
    document.addEventListener('visibilitychange', checkExpiry);
    checkExpiry();

    return () => {
      clearTimeout(timer);
      unsubscribe();
      unsubscribeHydration();
      window.removeEventListener('focus', checkExpiry);
      document.removeEventListener('visibilitychange', checkExpiry);
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    let inFlight = false;

    const verifySession = () => {
      if (inFlight || document.visibilityState === 'hidden') return;
      const currentToken = useAuthStore.getState().token;
      if (!currentToken) return;
      inFlight = true;
      void axiosClient
        .get('/api/auth/me')
        .catch(() => {
          // 401 is handled by axiosClient interceptor which calls expireSession(...)
        })
        .finally(() => {
          inFlight = false;
        });
    };

    const interval = setInterval(verifySession, SESSION_HEARTBEAT_MS);
    window.addEventListener('focus', verifySession);
    document.addEventListener('visibilitychange', verifySession);

    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', verifySession);
      document.removeEventListener('visibilitychange', verifySession);
    };
  }, [isAuthenticated, token]);

  return null;
}
