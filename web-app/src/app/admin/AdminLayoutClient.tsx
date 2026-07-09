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
      <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
        {/* Sidebar */}
        <AdminSidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((prev) => !prev)}
        />

        {/* Main content area */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          {/* Top header bar */}
          <header className="flex items-center justify-between px-6 py-4 bg-slate-900/60 border-b border-slate-800 backdrop-blur-sm sticky top-0 z-10">
            <div className="flex items-center gap-3">
              <h1 className="text-base font-semibold text-white">Admin Control Center</h1>
              <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded-full border border-emerald-900/50">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live
              </span>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </div>
    </AdminRoute>
  );
}
