'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { LayoutDashboard, Home, LogOut, ChevronLeft, User } from 'lucide-react';

interface AdminSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  {
    href: '/admin/rules',
    label: 'Rule Engine',
    icon: <LayoutDashboard size={18} />,
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
      className={`sticky top-0 flex h-screen flex-col border-r border-white/5 bg-slate-950/85 backdrop-blur-xl transition-all duration-300 ${
        collapsed ? 'w-[76px]' : 'w-[260px]'
      } flex-shrink-0 z-20`}
    >
      {/* Brand Header */}
      <div className="flex min-h-[72px] items-center justify-between border-b border-white/5 px-4 py-4">
        {!collapsed ? (
          <div className="flex items-center gap-2">
            <span className="text-xl font-black bg-gradient-to-r from-amber-400 via-orange-500 to-red-500 bg-clip-text text-transparent tracking-tight">
              Smile
            </span>
            <span className="rounded-md border border-orange-500/30 bg-orange-500/10 px-2 py-0.5 text-[9px] font-bold tracking-[0.15em] text-orange-400 uppercase">
              Admin
            </span>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 text-sm font-bold text-white shadow-[0_4px_16px_rgba(249,115,22,0.3)]">
              S
            </div>
          </div>
        )}

        {/* Collapse button inside header */}
        {!collapsed && (
          <button
            onClick={onToggle}
            className="hidden md:flex h-6 w-6 items-center justify-center rounded-md border border-slate-700 bg-slate-900 text-slate-400 hover:text-white hover:border-slate-500 transition-all cursor-pointer"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft size={12} />
          </button>
        )}
      </div>

      {/* Navigation List */}
      <nav className="flex-1 space-y-2 px-3 py-6 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3.5 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 border ${
                isActive
                  ? 'bg-gradient-to-r from-orange-500/15 to-amber-500/5 text-orange-400 border-orange-500/30 shadow-[0_4px_20px_rgba(249,115,22,0.06)]'
                  : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200 border-transparent'
              } ${collapsed ? 'justify-center px-0' : ''}`}
            >
              <span className={`shrink-0 ${isActive ? 'text-orange-400' : 'text-slate-400'}`}>
                {item.icon}
              </span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer Profile & Logout */}
      <div className="border-t border-white/5 p-4 space-y-3 bg-slate-950/40">
        {!collapsed && user && (
          <div className="flex items-center gap-3 rounded-2xl border border-white/5 bg-white/[0.02] p-3 shadow-[inset_0_1px_1px_rgba(255,255,255,0.02)]">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/25 to-orange-600/20 text-orange-400 border border-orange-500/25">
              <User size={16} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{user.username}</p>
              <p className="truncate text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
        )}

        <div className="space-y-1">
          <Link
            href="/"
            title={collapsed ? 'Về trang chủ' : undefined}
            className={`flex items-center gap-3.5 rounded-xl px-4 py-2.5 text-sm font-medium text-slate-400 transition-all hover:bg-white/[0.03] hover:text-slate-200 ${
              collapsed ? 'justify-center' : ''
            }`}
          >
            <Home size={16} className="shrink-0" />
            {!collapsed && <span>Trang chủ</span>}
          </Link>

          <button
            onClick={handleLogout}
            title={collapsed ? 'Đăng xuất' : undefined}
            className={`flex w-full items-center gap-3.5 rounded-xl px-4 py-2.5 text-sm font-medium text-rose-400 transition-all hover:bg-rose-500/10 hover:text-rose-300 cursor-pointer ${
              collapsed ? 'justify-center' : ''
            }`}
          >
            <LogOut size={16} className="shrink-0" />
            {!collapsed && <span>Đăng xuất</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}

export default AdminSidebar;
