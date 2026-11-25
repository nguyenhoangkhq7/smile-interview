'use client';

import React from 'react';
import { Download } from 'lucide-react';

interface AuditLogsHeaderProps {
  totalLogsCount: number;
  todayActionsCount: number;
  activeAdminsCount: number;
  onExportCsv: () => void;
}

export default function AuditLogsHeader({
  totalLogsCount,
  todayActionsCount,
  activeAdminsCount,
  onExportCsv,
}: AuditLogsHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c]">
          Nhật ký quản trị
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039]">
          Theo dõi và tra cứu lịch sử thao tác cấu hình, điều phối hàng đợi và quản lý tài khoản
          của quản trị viên.
        </p>
      </div>

      {/* Right Summary Pills & CSV Action */}
      <div className="flex flex-wrap items-center gap-2.5 self-start md:self-auto">
        <div className="flex items-center gap-3 rounded-xl bg-white px-3.5 py-2 text-xs shadow-xs">
          <span className="text-[#5c4039]">
            Tổng ghi: <strong className="font-semibold text-[#141b2c]">{totalLogsCount.toLocaleString('en-US')}</strong>
          </span>
          <span className="size-1 rounded-full bg-[#e5beb4]" />
          <span className="text-[#5c4039]">
            Hôm nay: <strong className="font-semibold text-[#ad2c00]">{todayActionsCount}</strong>
          </span>
          <span className="size-1 rounded-full bg-[#e5beb4]" />
          <span className="text-[#5c4039]">
            Admin: <strong className="font-semibold text-[#186392]">{activeAdminsCount}</strong>
          </span>
        </div>

        <button
          type="button"
          onClick={onExportCsv}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#ad2c00] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-[#d83900] cursor-pointer"
        >
          <Download className="size-4" />
          <span>Xuất CSV</span>
        </button>
      </div>
    </div>
  );
}
