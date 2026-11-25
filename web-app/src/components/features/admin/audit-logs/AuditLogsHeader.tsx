'use client';

import React from 'react';
import { Download } from 'lucide-react';
import type { AuditStats } from './types';

interface AuditLogsHeaderProps {
  stats?: AuditStats;
  exporting: boolean;
  canExport: boolean;
  onExportCsv: () => void;
}

export default function AuditLogsHeader({
  stats,
  exporting,
  canExport,
  onExportCsv,
}: AuditLogsHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
          Nhật ký quản trị
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
          Theo dõi và tra cứu lịch sử thao tác cấu hình, điều phối hàng đợi và quản lý tài khoản
          của quản trị viên.
        </p>
      </div>

      {/* Right Summary Pills & CSV Action */}
      <div className="flex flex-wrap items-center gap-2.5 self-start md:self-auto">
        <div className="flex items-center gap-3 rounded-xl bg-white dark:bg-card px-3.5 py-2 text-xs shadow-xs">
          <span className="text-[#5c4039] dark:text-muted-foreground">
            Tổng ghi: <strong className="font-semibold text-[#141b2c] dark:text-foreground">{stats?.total.toLocaleString('vi-VN') ?? '—'}</strong>
          </span>
          <span className="size-1 rounded-full bg-[#e5beb4] dark:bg-border" />
          <span className="text-[#5c4039] dark:text-muted-foreground">
            Hôm nay: <strong className="font-semibold text-[#ad2c00] dark:text-orange-300">{stats?.today.toLocaleString('vi-VN') ?? '—'}</strong>
          </span>
          <span className="size-1 rounded-full bg-[#e5beb4] dark:bg-border" />
          <span className="text-[#5c4039] dark:text-muted-foreground">
            Admin đã thao tác: <strong className="font-semibold text-[#186392] dark:text-sky-300">{stats?.admins.toLocaleString('vi-VN') ?? '—'}</strong>
          </span>
        </div>

        <button
          type="button"
          onClick={onExportCsv}
          disabled={!canExport || exporting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#ad2c00] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-[#d83900] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download className="size-4" />
          <span>{exporting ? 'Đang xuất…' : 'Xuất CSV'}</span>
        </button>
      </div>
    </div>
  );
}
