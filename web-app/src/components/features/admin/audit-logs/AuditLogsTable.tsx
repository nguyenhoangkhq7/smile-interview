'use client';

import React from 'react';
import { Copy, Eye } from 'lucide-react';
import { AuditBadgeVariant, AuditLogRecord } from './types';

interface AuditLogsTableProps {
  logs: AuditLogRecord[];
  totalCount: number;
  selectedLogId: string | null;
  onSelectLog: (log: AuditLogRecord) => void;
  onCopyCode: (code: string) => void;
}

const ACTION_BADGE_STYLES: Record<
  AuditBadgeVariant,
  { wrapper: string; dot: string }
> = {
  primary: {
    wrapper: 'bg-[#e0e8ff] text-[#ad2c00]',
    dot: 'bg-[#ad2c00]',
  },
  error: {
    wrapper: 'bg-[#ffdad6] text-[#ba1a1a]',
    dot: 'bg-[#ba1a1a]',
  },
  secondary: {
    wrapper: 'bg-[#cce5ff] text-[#005581]',
    dot: 'bg-[#186392]',
  },
  neutral: {
    wrapper: 'bg-[#e9edff] text-[#141b2c]',
    dot: 'bg-[#5c4039]',
  },
};

export default function AuditLogsTable({
  logs,
  totalCount,
  selectedLogId,
  onSelectLog,
  onCopyCode,
}: AuditLogsTableProps) {
  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-[#f1f3ff] text-[11px] font-semibold uppercase tracking-wider text-[#5c4039]">
              <th className="px-4 py-3">Thời gian</th>
              <th className="px-4 py-3">Quản trị viên</th>
              <th className="px-4 py-3">Hành động</th>
              <th className="px-4 py-3">Đối tượng</th>
              <th className="px-4 py-3">Tóm tắt</th>
              <th className="px-4 py-3 text-right">Chi tiết</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[#e9edff] text-xs text-[#141b2c]">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-xs text-[#5c4039]">
                  Không tìm thấy bản ghi nhật ký khớp với bộ lọc hiện tại.
                </td>
              </tr>
            ) : (
              logs.map((log) => {
                const isSelected = selectedLogId === log.id;
                const badgeStyle = ACTION_BADGE_STYLES[log.badgeVariant];

                return (
                  <tr
                    key={log.id}
                    onClick={() => onSelectLog(log)}
                    className={`cursor-pointer transition-colors duration-150 ${
                      isSelected
                        ? 'bg-[#cce5ff]/30 hover:bg-[#cce5ff]/40'
                        : 'hover:bg-[#f1f3ff]/70'
                    }`}
                  >
                    {/* Time */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <div className="font-mono text-xs font-semibold text-[#141b2c]">
                        {log.time}
                      </div>
                      <div className="text-[11px] text-[#5c4039]">{log.date}</div>
                    </td>

                    {/* Admin */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white ${log.adminAvatarBgClass}`}
                        >
                          {log.adminInitials}
                        </div>
                        <span className="text-xs font-semibold text-[#141b2c]">
                          {log.adminName}
                        </span>
                      </div>
                    </td>

                    {/* Action Badge */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold ${badgeStyle.wrapper}`}
                      >
                        <span className={`size-1.5 rounded-full ${badgeStyle.dot}`} />
                        {log.action}
                      </span>
                    </td>

                    {/* Merged Target Code & Type */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onCopyCode(log.targetCode);
                          }}
                          className="inline-flex items-center gap-1 rounded bg-[#cce5ff]/35 px-2 py-0.5 font-mono text-xs text-[#186392] transition-colors hover:text-[#ad2c00] cursor-pointer"
                        >
                          <span>{log.targetCode}</span>
                          <Copy className="size-3" />
                        </button>
                        <span className="text-[11px] text-[#5c4039]">{log.targetType}</span>
                      </div>
                    </td>

                    {/* Summary */}
                    <td className="max-w-md px-4 py-3.5">
                      <div className="truncate text-xs text-[#141b2c]" title={log.summaryText}>
                        {log.summaryText}
                      </div>
                    </td>

                    {/* View Action */}
                    <td className="whitespace-nowrap px-4 py-3.5 text-right">
                      <button
                        type="button"
                        aria-label="Xem chi tiết nhật ký"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectLog(log);
                        }}
                        className="rounded-lg p-1.5 text-[#5c4039] transition-colors hover:bg-[#e9edff] hover:text-[#ad2c00] cursor-pointer"
                      >
                        <Eye className="size-4.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="flex flex-col items-center justify-between gap-2 bg-[#f1f3ff] px-6 py-3.5 text-xs text-[#5c4039] sm:flex-row">
        <div>
          Hiển thị <strong className="font-semibold text-[#141b2c]">1 - {logs.length}</strong> /{' '}
          <strong className="font-semibold text-[#141b2c]">
            {totalCount.toLocaleString('en-US')}
          </strong>{' '}
          bản ghi
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled
            className="rounded bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c] opacity-50"
          >
            Trước
          </button>
          <button
            type="button"
            className="rounded bg-[#ad2c00] px-2.5 py-1 text-xs font-semibold text-white"
          >
            1
          </button>
          <button
            type="button"
            className="rounded bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            2
          </button>
          <button
            type="button"
            className="rounded bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            3
          </button>
          <span className="px-1 text-[#5c4039]">...</span>
          <button
            type="button"
            className="rounded bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            238
          </button>
          <button
            type="button"
            className="rounded bg-[#e9edff] px-2.5 py-1 text-xs font-medium text-[#141b2c] hover:bg-[#e0e8ff] cursor-pointer"
          >
            Sau
          </button>
        </div>
      </div>
    </div>
  );
}
