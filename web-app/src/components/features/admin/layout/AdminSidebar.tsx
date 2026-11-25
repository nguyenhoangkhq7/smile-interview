'use client';

import React from 'react';
import {
  BrainCircuit,
  Layers,
  LayoutDashboard,
  ScrollText,
  Users,
  Video,
  X,
} from 'lucide-react';
import { ADMIN_NAV_ITEMS } from '../data/dashboardOptions';
import { AdminSectionKey } from '../types';

interface AdminSidebarProps {
  activeSection: AdminSectionKey;
  onSelectSection: (section: AdminSectionKey) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const SECTION_ICONS: Record<AdminSectionKey, React.ReactNode> = {
  'tong-quan': <LayoutDashboard className="size-5 shrink-0" />,
  'nguoi-dung': <Users className="size-5 shrink-0" />,
  'phien-phong-van': <Video className="size-5 shrink-0" />,
  'hang-doi-va-luu-tru': <Layers className="size-5 shrink-0" />,
  'ai-va-chinh-sach': <BrainCircuit className="size-5 shrink-0" />,
  'nhat-ky-quan-tri': <ScrollText className="size-5 shrink-0" />,
};

export default function AdminSidebar({
  activeSection,
  onSelectSection,
  mobileOpen,
  onCloseMobile,
}: AdminSidebarProps) {
  const sidebarContent = (
    <div className="flex h-full w-64 flex-col bg-white dark:bg-card border-r border-[#e5beb4]/35 dark:border-border/35 shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Section Group Title */}
        <div className="flex items-center justify-between px-4 pt-4 pb-2.5">
          <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-[#5c4039] dark:text-muted-foreground">
            Hệ thống điều hành
          </div>
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label="Đóng thanh điều hướng"
            className="rounded-lg p-1.5 text-[#5c4039] dark:text-muted-foreground hover:bg-[#e0e8ff] dark:hover:bg-secondary hover:text-[#141b2c] dark:hover:text-foreground lg:hidden"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-4 pb-6" aria-label="Điều hướng quản trị">
          {ADMIN_NAV_ITEMS.map((item) => {
            const isActive = activeSection === item.key;
            return (
              <button
                key={item.key}
                type="button"
                aria-current={isActive ? 'page' : undefined}
                onClick={() => {
                  onSelectSection(item.key);
                  onCloseMobile();
                }}
                className={`flex w-full items-center gap-2.5 rounded-lg px-4 py-2.5 text-left transition-all duration-200 cursor-pointer ${isActive
                    ? 'bg-[#d83900] text-[#fffbff] text-[15px] font-semibold shadow-[0_1px_3px_rgba(0,0,0,0.08)]'
                    : 'text-[#5c4039] dark:text-muted-foreground text-[13px] font-medium hover:bg-[#e0e8ff] dark:hover:bg-secondary hover:text-[#141b2c] dark:hover:text-foreground'
                  }`}
              >
                {SECTION_ICONS[item.key]}
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sticky Sidebar under the System Navbar */}
      <aside className="hidden lg:block lg:w-64 lg:shrink-0">
        <div className="sticky top-[4.25rem] h-[calc(100vh-4.25rem)]">{sidebarContent}</div>
      </aside>

      {/* Mobile Slide-Over Sidebar Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden" role="dialog" aria-modal="true">
          <div
            className="fixed inset-0 bg-[#141b2c]/40 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="relative z-10 flex h-full w-64 flex-col animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
