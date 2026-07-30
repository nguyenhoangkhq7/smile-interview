'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import axiosClient from '@/lib/axiosClient';

interface HrRouteProps {
  children: React.ReactNode;
}

/**
 * Role-based access guard for HR Workspace pages (/hr-dashboard/**).
 * Ensures only authenticated users with 'HR' or 'ADMIN' role can access HR pages.
 */
export default function HrRoute({ children }: HrRouteProps) {
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
        console.error('[HrRoute] Failed to sync user profile:', err);
        if (isMounted) {
          setVerifying(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [hydrated, isAuthenticated, updateUser]);

  // After hydration & verification: enforce auth + HR/ADMIN role
  useEffect(() => {
    if (!hydrated || verifying) return;

    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }

    if (user?.role !== 'HR' && user?.role !== 'ADMIN') {
      router.replace('/');
    }
  }, [hydrated, verifying, isAuthenticated, user, router]);

  if (!hydrated || verifying) {
    return <HrLoadingSpinner />;
  }

  if (!isAuthenticated) {
    return null;
  }

  if (user?.role !== 'HR' && user?.role !== 'ADMIN') {
    return <HrForbidden />;
  }

  return <>{children}</>;
}

function HrLoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-900 gap-4">
      <div className="size-10 animate-spin rounded-full border-3 border-blue-500 border-t-transparent" />
      <p className="text-slate-400 text-sm font-medium">Đang xác thực quyền truy cập HR Workspace...</p>
    </div>
  );
}

function HrForbidden() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-900 gap-4">
      <div className="text-6xl">🔒</div>
      <h1 className="text-2xl font-bold text-white">Không Có Quyền Truy Cập</h1>
      <p className="text-slate-400 text-sm">Trang này dành riêng cho Chuyên viên HR và Quản trị viên.</p>
    </div>
  );
}
