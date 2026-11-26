import { useAuthStore } from '../store/authStore';

const SESSION_EXPIRED_NOTICE_KEY = 'smile_session_expired_notice';

export function consumeSessionExpiredNotice(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const message = window.sessionStorage.getItem(SESSION_EXPIRED_NOTICE_KEY);
    if (message) window.sessionStorage.removeItem(SESSION_EXPIRED_NOTICE_KEY);
    return message;
  } catch {
    return null;
  }
}

// This only reads expiry for client UX; the backend verifies the JWT signature.
export function getTokenExpiresAt(token: string): number | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const { exp } = JSON.parse(atob(payload)) as { exp?: unknown };
    if (typeof exp !== 'number' || !Number.isFinite(exp)) return null;
    const expiresAt = exp * 1000;
    return Number.isFinite(expiresAt) ? expiresAt : null;
  } catch {
    return null;
  }
}

export function analysisResultSearch(): string {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('sessionId');
  const jobId = params.get('jobId');
  return sessionId && jobId ? '?' + new URLSearchParams({ sessionId, jobId }) : '';
}

export function loginPath(): string {
  return '/login' + (window.location.pathname === '/interview/new' ? analysisResultSearch() : '');
}

export function expireSession(token: string, reason?: string): void {
  // Ignore failures/timers belonging to a previous login.
  if (useAuthStore.getState().token !== token) return;
  useAuthStore.getState().logout();
  if (typeof window !== 'undefined') {
    if (reason) {
      try {
        window.sessionStorage.setItem(SESSION_EXPIRED_NOTICE_KEY, reason);
      } catch {
        // Ignore storage errors
      }
    }
    if (window.location.pathname !== '/login' && window.location.pathname !== '/setup-password') {
      window.location.replace(loginPath());
    }
  }
}
