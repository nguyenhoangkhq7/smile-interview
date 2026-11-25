'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight, Home, Menu } from 'lucide-react';
import { AdminSectionKey } from '../types';

interface AdminBreadcrumbBarProps {
  activeSection: AdminSectionKey;
  onOpenMobileSidebar: () => void;
}

const SECTION_BREADCRUMB_TITLES: Record<AdminSectionKey, string> = {
  'tong-quan': 'Tổng quan hệ thống',
  'nguoi-dung': 'Quản lý người dùng',
  'phien-phong-van': 'Giám sát phiên phỏng vấn',
  'hang-doi-va-luu-tru': 'Hàng đợi & Lưu trữ',
  'ai-va-chinh-sach': 'AI & Chính sách',
  'nhat-ky-quan-tri': 'Nhật ký quản trị',
};

export default function AdminBreadcrumbBar({
  activeSection,
  onOpenMobileSidebar,
}: AdminBreadcrumbBarProps) {
  const currentBreadcrumbTitle =
    SECTION_BREADCRUMB_TITLES[activeSection] || 'Tổng quan hệ thống';

  return (
    <div className="border-b border-[#e0e8ff] bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-8">
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          aria-label="Mở menu quản trị"
          className="inline-flex items-center justify-center rounded-lg border border-[#e0e8ff] bg-[#f1f3ff] p-2 text-[#141b2c] transition-colors hover:bg-[#e0e8ff] lg:hidden"
        >
          <Menu className="size-4" />
        </button>

        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-1.5 text-[13px] font-medium text-[#5c4039]"
        >
          <Link
            href="/"
            className="inline-flex items-center gap-1 transition-colors hover:text-[#141b2c]"
          >
            <Home className="size-3.5" />
            <span>Trang chủ</span>
          </Link>
          <ChevronRight className="size-3.5 text-[#907067]" />
          <span>Admin</span>
          <ChevronRight className="size-3.5 text-[#907067]" />
          <span className="font-semibold text-[#141b2c]">{currentBreadcrumbTitle}</span>
        </nav>
      </div>
    </div>
  );
}
