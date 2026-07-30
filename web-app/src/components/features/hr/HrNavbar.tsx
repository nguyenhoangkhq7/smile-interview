'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Building2,
  FileCheck,
  LogOut,
  User,
  ChevronDown,
  Shield,
  Home,
} from 'lucide-react';

export const HrNavbar: React.FC = () => {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const handleLogout = () => {
    logout();
    setDropdownOpen(false);
    router.push('/login');
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-700/60 bg-slate-900 text-white shadow-md">
      <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        {/* Brand Logo & Tag */}
        <div className="flex items-center space-x-3">
          <Link href="/hr-dashboard" className="flex items-center space-x-2.5 transition-opacity hover:opacity-90">
            <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 font-bold text-white shadow-sm ring-1 ring-blue-400/30">
              <Building2 className="size-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-1">
                Smile Interview
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-400">
                HR Workspace
              </span>
            </div>
          </Link>

          <Badge variant="outline" className="hidden sm:inline-flex border-blue-500/30 bg-blue-500/10 text-blue-300 text-xs px-2.5 py-0.5 font-medium">
            <Shield className="mr-1 size-3 text-blue-400" /> Professional HR Portal
          </Badge>
        </div>

        {/* Center Nav Links */}
        <nav className="flex items-center space-x-1">
          <Link
            href="/hr-dashboard"
            className="flex items-center space-x-1.5 rounded-lg bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-white border border-slate-700/80 shadow-inner"
          >
            <FileCheck className="size-4 text-blue-400" />
            <span>Danh Sách Đánh Giá AI</span>
          </Link>
        </nav>

        {/* Right User & Actions */}
        <div className="flex items-center space-x-3">
          {/* User Profile Dropdown */}
          {user ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                onBlur={() => setTimeout(() => setDropdownOpen(false), 200)}
                className="flex items-center space-x-2 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-slate-800 hover:text-white"
              >
                <div className="flex size-6 items-center justify-center rounded-full bg-blue-600/30 text-blue-400">
                  <User className="size-3.5" />
                </div>
                <span className="max-w-[120px] truncate font-semibold">{user.username}</span>
                <ChevronDown className="size-3.5 text-slate-400" />
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-700 bg-slate-900 p-2 shadow-xl z-50 text-xs space-y-1">
                  <div className="border-b border-slate-800 p-2.5">
                    <p className="font-bold text-white truncate">{user.username}</p>
                    <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
                    <Badge variant="outline" className="mt-1.5 bg-blue-500/10 text-blue-400 border-blue-500/30 text-[10px]">
                      Vai trò: {user.role}
                    </Badge>
                  </div>

                  <Link
                    href="/"
                    className="flex w-full items-center space-x-2 rounded-lg px-2.5 py-2 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                  >
                    <Home className="size-3.5 text-slate-400" />
                    <span>Quay lại trang chủ ứng viên</span>
                  </Link>

                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center space-x-2 rounded-lg px-2.5 py-2 text-rose-400 hover:bg-rose-950/40 hover:text-rose-300 transition-colors font-medium"
                  >
                    <LogOut className="size-3.5" />
                    <span>Đăng xuất HR Account</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Button size="xs" variant="outline" onClick={() => router.push('/login')}>
              Đăng nhập HR
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};
