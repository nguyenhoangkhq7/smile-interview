'use client';

import React from 'react';
import { Copy, Eye } from 'lucide-react';
import type { AuditBadgeVariant, AuditRow } from './types';
import { displayAuditRow } from './auditDisplay';

interface AuditLogsTableProps {
  logs: AuditRow[];
  totalCount: number;
  page: number;
  size: number;
  onPage: (page: number) => void;
  selectedLogId: string | null;
  onSelectLog: (id: string) => void;
  onCopyCode: (code: string) => void;
}

const ACTION_BADGE_STYLES: Record<
  AuditBadgeVariant,
  { wrapper: string; dot: string }
> = {
  primary: {
    wrapper: 'bg-[#e0e8ff] dark:bg-secondary text-[#ad2c00] dark:text-orange-300',
    dot: 'bg-[#ad2c00]',
  },
  error: {
    wrapper: 'bg-[#ffdad6] dark:bg-red-950 text-[#ba1a1a] dark:text-red-300',
    dot: 'bg-[#ba1a1a]',
  },
  secondary: {
    wrapper: 'bg-[#cce5ff] dark:bg-sky-950 text-[#005581] dark:text-sky-300',
    dot: 'bg-[#186392]',
  },
  neutral: {
    wrapper: 'bg-[#e9edff] dark:bg-secondary text-[#141b2c] dark:text-foreground',
    dot: 'bg-[#5c4039]',
  },
};

export default function AuditLogsTable({
  logs,
  totalCount,
  page,
  size,
  onPage,
  selectedLogId,
  onSelectLog,
  onCopyCode,
}: AuditLogsTableProps) {
  const last = Math.max(1, Math.ceil(totalCount / size));
  const firstRow = logs.length ? (page - 1) * size + 1 : 0;
  const lastRow = logs.length ? firstRow + logs.length - 1 : 0;
  const pages = [...new Set([1, page - 1, page, page + 1, last])]
    .filter((value) => value >= 1 && value <= last)
    .sort((a, b) => a - b);
  return (
    <div className="overflow-hidden rounded-xl bg-white dark:bg-card shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-[#f1f3ff] dark:bg-muted text-[11px] font-semibold uppercase tracking-wider text-[#5c4039] dark:text-muted-foreground">
              <th className="px-4 py-3">Thời gian</th>
              <th className="px-4 py-3">Quản trị viên</th>
              <th className="px-4 py-3">Hành động</th>
              <th className="px-4 py-3">Đối tượng</th>
              <th className="px-4 py-3">Tóm tắt</th>
              <th className="px-4 py-3 text-right">Chi tiết</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-[#e9edff] text-xs text-[#141b2c] dark:text-foreground">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-xs text-[#5c4039] dark:text-muted-foreground">
                  Không tìm thấy bản ghi nhật ký khớp với bộ lọc hiện tại.
                </td>
              </tr>
            ) : (
              logs.map((log) => {
                const isSelected = selectedLogId === log.id;
                const display = displayAuditRow(log);
                const badgeStyle = ACTION_BADGE_STYLES[display.badge];

                return (
                  <tr
                    key={log.id}
                    onClick={() => onSelectLog(log.id)}
                    className={`cursor-pointer transition-colors duration-150 ${
                      isSelected
                        ? 'bg-[#cce5ff]/30 dark:bg-sky-950/30 hover:bg-[#cce5ff]/40 dark:hover:bg-sky-950/40'
                        : 'hover:bg-[#f1f3ff]/70 dark:hover:bg-muted/70'
                    }`}
                  >
                    {/* Time */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <div className="font-mono text-xs font-semibold text-[#141b2c] dark:text-foreground">
                        {display.time}
                      </div>
                      <div className="text-[11px] text-[#5c4039] dark:text-muted-foreground">{display.date}</div>
                    </td>

                    {/* Admin */}
                    <td className="whitespace-nowrap px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white ${display.avatar}`}
                        >
                          {display.initials}
                        </div>
                        <span className="text-xs font-semibold text-[#141b2c] dark:text-foreground">
                          {log.actorName}
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
                          className="inline-flex items-center gap-1 rounded bg-[#cce5ff]/35 dark:bg-sky-950/35 px-2 py-0.5 font-mono text-xs text-[#186392] dark:text-sky-300 transition-colors hover:text-[#ad2c00] dark:hover:text-orange-300 cursor-pointer"
                        >
                          <span className="max-w-28 truncate" title={log.targetCode}>{log.targetCode}</span>
                          <Copy className="size-3" />
                        </button>
                        <span className="text-[11px] text-[#5c4039] dark:text-muted-foreground">{display.target}</span>
                      </div>
                    </td>

                    {/* Summary */}
                    <td className="max-w-md px-4 py-3.5">
                      <div className="truncate text-xs text-[#141b2c] dark:text-foreground" title={log.summary}>
                        {log.summary}
                      </div>
                    </td>

                    {/* View Action */}
                    <td className="whitespace-nowrap px-4 py-3.5 text-right">
                      <button
                        type="button"
                        aria-label="Xem chi tiết nhật ký"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectLog(log.id);
                        }}
                        className="rounded-lg p-1.5 text-[#5c4039] dark:text-muted-foreground transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary hover:text-[#ad2c00] dark:hover:text-orange-300 cursor-pointer"
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

      <div className="flex flex-col items-center justify-between gap-2 bg-[#f1f3ff] dark:bg-muted px-6 py-3.5 text-xs text-[#5c4039] dark:text-muted-foreground sm:flex-row">
        <p>
          Hiển thị <strong>{firstRow}–{lastRow}</strong> / <strong>{totalCount.toLocaleString('vi-VN')}</strong> bản ghi
        </p>
        {last > 1 && <nav aria-label="Phân trang nhật ký" className="flex items-center gap-1">
          <button type="button" disabled={page === 1} onClick={() => onPage(page - 1)}
            className="rounded bg-[#e9edff] dark:bg-secondary px-2.5 py-1 disabled:opacity-50">Trước</button>
          {pages.map((value, index) => (
            <React.Fragment key={value}>
              {index > 0 && value - pages[index - 1] > 1 && <span aria-hidden="true" className="px-1">…</span>}
              <button type="button" aria-current={value === page ? 'page' : undefined}
                aria-label={'Trang ' + value} onClick={() => onPage(value)}
                className={value === page ? 'rounded bg-[#ad2c00] px-2.5 py-1 text-white' : 'rounded bg-[#e9edff] dark:bg-secondary px-2.5 py-1'}>
                {value}
              </button>
            </React.Fragment>
          ))}
          <button type="button" disabled={page === last} onClick={() => onPage(page + 1)}
            className="rounded bg-[#e9edff] dark:bg-secondary px-2.5 py-1 disabled:opacity-50">Sau</button>
        </nav>}
      </div>
    </div>
  );
}
