'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { useState } from 'react';

interface AdminSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  {
    href: '/admin/rules',
    label: 'Rule Engine',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z" />
        <path d="M7 7h.01" />
      </svg>
    ),
  },
];

function AdminSidebar({ collapsed, onToggle }: AdminSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <aside
      className={`sticky top-0 flex h-screen flex-col overflow-y-auto border-r border-slate-800 bg-slate-950/90 transition-all duration-300 ${collapsed ? 'w-[76px]' : 'w-[256px]'} flex-shrink-0 backdrop-blur-md`}
      style={{ position: 'sticky', top: 0 }}
    >
      {/* Logo */}
      <div className="flex min-h-[72px] items-center justify-between border-b border-slate-800 px-4 py-4">
        {!collapsed ? (
          <div className="flex items-center gap-2.5">
            <span className="text-xl font-semibold bg-gradient-to-r from-amber-300 to-orange-500 bg-clip-text text-transparent">
              Smile
            </span>
            <span className="rounded-full border border-slate-800 bg-white/[0.04] px-2 py-0.5 text-[10px] font-semibold tracking-[0.16em] text-slate-400">
              ADMIN
            </span>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 text-sm font-bold text-white shadow-[0_10px_24px_rgba(20,184,166,0.22)]">
              A
            </div>
          </div>
        )}
      </div>

      {/* Nav Links */}
      <nav className="flex-1 space-y-1.5 overflow-y-auto px-4 py-4">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all duration-150 ${
                isActive
                  ? 'bg-teal-500/10 text-teal-300 border border-teal-500/20 shadow-[0_4px_12px_rgba(20,184,166,0.06)]'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-white border border-transparent'
              } ${collapsed ? 'justify-center' : ''}`}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* User + Logout Footer */}
      <div className="space-y-3 border-t border-slate-800 px-4 pb-4 pt-4">
        {!collapsed && user && (
          <div className="flex items-center gap-2.5 rounded-xl border border-slate-800 bg-white/[0.03] px-3 py-3">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 text-xs font-bold text-white">
              {user.username?.charAt(0).toUpperCase() ?? 'A'}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{user.username}</p>
              <p className="truncate text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
        )}
        <Link
          href="/"
          title={collapsed ? 'Về trang chủ' : undefined}
          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white ${collapsed ? 'justify-center' : ''}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          {!collapsed && <span>Trang chủ</span>}
        </Link>
        <button
          onClick={handleLogout}
          title={collapsed ? 'Đăng xuất' : undefined}
          className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-rose-300 transition-colors hover:bg-rose-500/10 hover:text-rose-200 ${collapsed ? 'justify-center' : ''}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          {!collapsed && <span>Đăng xuất</span>}
        </button>
      </div>
    </aside>
  );
}

export default AdminSidebar;
