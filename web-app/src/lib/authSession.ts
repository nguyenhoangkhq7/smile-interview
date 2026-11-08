import { useAuthStore } from '../store/authStore';

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

export function expireSession(token: string): void {
  // Ignore failures/timers belonging to a previous login.
  if (useAuthStore.getState().token !== token) return;
  useAuthStore.getState().logout();
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.replace('/login');
  }
}
