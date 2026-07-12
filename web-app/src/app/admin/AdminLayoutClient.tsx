'use client';

import { useState } from 'react';
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

  return (
    <AdminRoute>
      <div className="relative flex min-h-screen overflow-hidden bg-slate-950 text-slate-100">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.16),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.12),_transparent_24%),linear-gradient(180deg,_rgba(15,23,42,0.96),_rgba(2,6,23,1))]" />
          <div className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.5)_1px,transparent_1px)] [background-size:32px_32px]" />
        </div>

        <div className="relative z-10 flex w-full gap-4 p-4 lg:p-5">
          <AdminSidebar
            collapsed={collapsed}
            onToggle={() => setCollapsed((prev) => !prev)}
          />

          <div className="flex min-w-0 flex-1">
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[28px] border border-white/5 bg-slate-950/80 shadow-[0_24px_90px_rgba(2,6,23,0.55)] backdrop-blur-sm">

              <main className="flex-1 overflow-auto px-5 py-5 lg:px-7 lg:py-7">
                {children}
              </main>
            </div>
          </div>
        </div>
      </div>
    </AdminRoute>
  );
}
