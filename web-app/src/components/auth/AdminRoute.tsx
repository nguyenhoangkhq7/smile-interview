'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';

import axiosClient from '@/lib/axiosClient';

interface AdminRouteProps {
  children: React.ReactNode;
}

/**
 * Role-based access guard for Admin-only pages.
 *
 * Hydration strategy (mirrors {@link ProtectedRoute}):
 * - Phase 1 — Hydrating: Zustand persist has not yet read from localStorage.
 *   Shows a loading spinner to prevent flash of unauthorized content.
 * - Phase 2 — Verifying: Fetches the latest profile from the backend to ensure
 *   the role is synced (prevents stale localStorage role from causing a false 403).
 * - Phase 3 — Not authenticated: Redirect to /login.
 * - Phase 4 — Authenticated but not ADMIN: Redirect to / (403-equivalent).
 * - Phase 5 — Authenticated + ADMIN: Render children.
 */
export default function AdminRoute({ children }: AdminRouteProps) {
  const router = useRouter();
  const { user, isAuthenticated, updateUser } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);
  const [verifying, setVerifying] = useState(true);

  // Wait for Zustand persist to rehydrate from localStorage
  useEffect(() => {
    setHydrated(true);
  }, []);

  // Sync user profile from backend on mount to refresh the role
  useEffect(() => {
    if (!hydrated) return;

    if (!isAuthenticated) {
      setVerifying(false);
      return;
    }

    let isMounted = true;
    axiosClient.get('/api/auth/me')
      .then(({ data }) => {
        if (isMounted) {
          updateUser({
            username: data.username,
            email: data.email,
            role: data.role,
            phoneNumber: data.phoneNumber ?? null,
            avatarUrl: data.avatarUrl ?? null,
            defaultResumeId: data.defaultResumeId ?? null,
          });
          setVerifying(false);
        }
      })
      .catch((err) => {
        console.error('[AdminRoute] Failed to sync user profile:', err);
        if (isMounted) {
          setVerifying(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [hydrated, isAuthenticated, updateUser]);

  // After hydration & verification: enforce auth + role
  useEffect(() => {
    if (!hydrated || verifying) return;

    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }

    if (user?.role !== 'ADMIN') {
      router.replace('/');
    }
  }, [hydrated, verifying, isAuthenticated, user, router]);

  // Phase 1: hydrating or verifying
  if (!hydrated || verifying) {
    return <AdminLoadingSpinner />;
  }

  // Phase 2: not authenticated — render nothing while redirect fires
  if (!isAuthenticated) {
    return null;
  }

  // Phase 3: not admin — render nothing while redirect fires
  if (user?.role !== 'ADMIN') {
    return <AdminForbidden />;
  }

  // Phase 4: all clear
  return <>{children}</>;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function AdminLoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 gap-4">
      <svg
        className="animate-spin text-brand-orange"
        width="40" height="40" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      <p className="text-slate-400 text-sm">Đang xác thực quyền truy cập...</p>
    </div>
  );
}

function AdminForbidden() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 gap-4">
      <div className="text-6xl">🔒</div>
      <h1 className="text-2xl font-bold text-white">Không có quyền truy cập</h1>
      <p className="text-slate-400 text-sm">Trang này chỉ dành cho Quản trị viên.</p>
    </div>
  );
}
