'use client';

import { useEffect } from 'react';
import { expireSession, getTokenExpiresAt } from '@/lib/authSession';
import { useAuthStore } from '@/store/authStore';

export default function AuthSessionMonitor() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const checkExpiry = () => {
      clearTimeout(timer);
      const token = useAuthStore.getState().token;
      if (!token) return;

      const expiresAt = getTokenExpiresAt(token);
      const remaining = expiresAt === null ? 0 : expiresAt - Date.now();
      if (remaining <= 0) {
        expireSession(token);
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

  return null;
}
