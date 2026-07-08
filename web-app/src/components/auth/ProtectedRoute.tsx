'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * Wraps any page that requires authentication.
 *
 * Hydration strategy:
 *  - On the first render the Zustand `persist` store has NOT yet rehydrated
 *    from localStorage (this happens client-side, after mount).
 *  - We track `hydrated` state and render a spinner until rehydration is done.
 *  - Once hydrated, if the user is NOT authenticated we redirect to /login.
 *  - No infinite redirect loop: the redirect only fires when isAuthenticated is
 *    definitively false (after hydration), not during the loading phase.
 */
export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [hydrated, setHydrated] = useState(false);

  // Wait for Zustand persist to rehydrate from localStorage
  useEffect(() => {
    setHydrated(true);
  }, []);

  // After hydration: redirect unauthenticated users
  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace('/login');
    }
  }, [hydrated, isAuthenticated, router]);

  // Phase 1: Still hydrating — show a centered spinner to avoid flash
  if (!hydrated) {
    return <HydrationSpinner />;
  }

  // Phase 2: Hydrated but not authenticated — render nothing while redirect fires
  if (!isAuthenticated) {
    return null;
  }

  // Phase 3: Authenticated — render the protected content
  return <>{children}</>;
}

// ── Internal sub-component ───────────────────────────────────────────────────

function HydrationSpinner() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: '1rem',
        background: 'var(--bg, #0f172a)',
      }}
      aria-label="Đang tải..."
      role="status"
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#6366f1"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ animation: 'spin 0.9s linear infinite' }}
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: 0 }}>Đang xác thực...</p>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
