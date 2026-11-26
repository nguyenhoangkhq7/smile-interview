'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import { LoaderCircle } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { loginPath } from '@/lib/authSession';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

// Zustand restores localStorage synchronously in the browser. The server
// snapshot is only needed for the initial HTML and its hydration.
const subscribe = () => () => undefined;
const browserSnapshot = () => true;
const serverSnapshot = () => false;

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const role = useAuthStore((state) => state.user?.role);
  const isBrowser = useSyncExternalStore(subscribe, browserSnapshot, serverSnapshot);

  useEffect(() => {
    if (isBrowser && !isAuthenticated) {
      router.replace(loginPath());
    }
  }, [isBrowser, isAuthenticated, router]);

  if (!isBrowser) {
    return (
      <div role="status" data-auth-pending className="flex min-h-48 items-center justify-center gap-2 px-4 text-sm text-muted-foreground">
        <LoaderCircle size={18} className="motion-safe:animate-spin" aria-hidden="true" />
        Đang xác thực…
      </div>
    );
  }

  if (!isAuthenticated) return null;
  if (requiredRole && role !== requiredRole) {
    return (
      <p role="alert" className="mx-auto max-w-7xl px-4 py-10 text-sm text-muted-foreground">
        Bạn không có quyền truy cập trang quản trị.
      </p>
    );
  }

  return children;
}
