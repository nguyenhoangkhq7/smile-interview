'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import { LoaderCircle } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

// Zustand restores localStorage synchronously in the browser. The server
// snapshot is only needed for the initial HTML and its hydration.
const subscribe = () => () => undefined;
const browserSnapshot = () => true;
const serverSnapshot = () => false;

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isBrowser = useSyncExternalStore(subscribe, browserSnapshot, serverSnapshot);

  useEffect(() => {
    if (isBrowser && !isAuthenticated) {
      router.replace('/login');
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

  return isAuthenticated ? children : null;
}
