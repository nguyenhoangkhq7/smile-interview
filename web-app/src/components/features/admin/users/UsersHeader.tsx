'use client';

import React from 'react';
import { Download, UserPlus } from 'lucide-react';

interface UsersHeaderProps {
  onExportCsv: () => void;
  onOpenAddAdmin: () => void;
}

export default function UsersHeader({
  onExportCsv,
  onOpenAddAdmin,
}: UsersHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
          Quản lý người dùng
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
          Quản lý tài khoản, quyền truy cập và hoạt động phỏng vấn trực tiếp của ứng viên trên nền
          tảng Smile AI.
        </p>
      </div>

      {/* Quick Action / Primary Buttons */}
      <div className="flex shrink-0 items-center gap-2.5">
        <button
          type="button"
          onClick={onExportCsv}
          className="inline-flex items-center gap-2 rounded-lg bg-white dark:bg-card px-4 py-2.5 text-[13px] font-medium text-[#141b2c] dark:text-foreground shadow-xs transition-all hover:bg-[#f1f3ff] dark:hover:bg-muted hover:shadow-sm cursor-pointer"
        >
          <Download className="size-4 text-[#5c4039] dark:text-muted-foreground" />
          <span>Xuất dữ liệu CSV</span>
        </button>

        <button
          type="button"
          onClick={onOpenAddAdmin}
          className="inline-flex items-center gap-2 rounded-lg bg-[#d83900] px-5 py-2.5 text-sm font-semibold text-[#fffbff] shadow-sm transition-all hover:bg-[#ad2c00] hover:shadow-md cursor-pointer"
        >
          <UserPlus className="size-4.5" />
          <span>+ Thêm quản trị viên</span>
        </button>
      </div>
    </div>
  );
}
