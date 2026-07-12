'use client';

import { useState, useEffect } from 'react';
import AdminRoute from '@/components/auth/AdminRoute';
import AdminSidebar from '@/components/admin/AdminSidebar';

/**
 * Client-side Admin layout wrapper. Provides:
 * - AdminRoute guard (auth + role check)
 * - Collapsible sidebar navigation
 * - Dark theme consistent with brand design system
 */
export default function AdminLayoutClient({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  const toggleSidebar = () => {
    const nextCollapsed = !collapsed;
    setCollapsed(nextCollapsed);
    window.dispatchEvent(new CustomEvent('admin-sidebar-collapsed', { detail: nextCollapsed }));
  };

  useEffect(() => {
    const handleToggle = () => {
      toggleSidebar();
    };
    window.addEventListener('toggle-admin-sidebar', handleToggle);
    return () => window.removeEventListener('toggle-admin-sidebar', handleToggle);
  }, [collapsed]);

  return (
    <AdminRoute>
      <div className="relative flex h-screen w-full overflow-hidden bg-slate-950 text-slate-200">
        {/* Premium background gradient effect */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-0"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.16),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.12),_transparent_24%),linear-gradient(180deg,_rgba(15,23,42,0.96),_rgba(2,6,23,1))]" />
          <div className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.5)_1px,transparent_1px)] [background-size:32px_32px]" />
        </div>

        <div className="relative z-10 flex h-full w-full overflow-hidden">
          <AdminSidebar
            collapsed={collapsed}
            onToggle={toggleSidebar}
          />

          <main className="flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </div>
    </AdminRoute>
  );
}
