'use client';

import React from 'react';
import {
  ArrowRight,
  Copy,
  FileCode2,
  GitCompare,
  X,
} from 'lucide-react';
import { AuditLogRecord } from './types';

interface AuditLogDetailDrawerProps {
  record: AuditLogRecord | null;
  onClose: () => void;
  onCopyJson: (jsonText: string) => void;
}

export default function AuditLogDetailDrawer({
  record,
  onClose,
  onCopyJson,
}: AuditLogDetailDrawerProps) {
  const isOpen = record !== null;
  const formattedJson = record ? JSON.stringify(record.jsonPayload, null, 2) : '';

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#293041]/30 backdrop-blur-[1px] transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Slide-Over Detail Drawer */}
      <aside
        aria-label="Chi tiết bản ghi nhật ký"
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {record && (
          <>
            {/* Drawer Header */}
            <div className="flex items-start justify-between gap-4 bg-[#f1f3ff] p-6">
              <div className="min-w-0">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[#ad2c00]/10 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#ad2c00]">
                    {record.action}
                  </span>
                  <span className="rounded bg-white px-2 py-0.5 font-mono text-xs text-[#186392]">
                    {record.targetCode}
                  </span>
                </div>
                <h2 className="truncate text-lg font-semibold text-[#141b2c]">
                  Chi tiết nhật ký thao tác
                </h2>
                <span className="text-xs text-[#5c4039]">
                  Mã bản ghi:{' '}
                  <code className="font-mono text-[11px] font-medium text-[#141b2c]">
                    {record.recordCode}
                  </code>
                </span>
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Đóng"
                className="rounded-lg p-2 text-[#5c4039] transition-colors hover:bg-[#e9edff] hover:text-[#141b2c] cursor-pointer"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="flex-1 space-y-5 overflow-y-auto p-6">
              {/* Section 1: Metadata Grid */}
              <div className="space-y-3 rounded-xl bg-[#f1f3ff] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#5c4039]">
                  Thông tin thực thi
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="block text-[11px] text-[#5c4039]">Quản trị viên:</span>
                    <span className="font-semibold text-[#141b2c]">
                      {record.adminName} ({record.adminRole})
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[#5c4039]">Thời gian:</span>
                    <span className="font-mono text-[#141b2c]">
                      {record.time} • {record.date}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[#5c4039]">Địa chỉ IP:</span>
                    <span className="font-mono font-semibold text-[#186392]">
                      {record.adminIp}
                    </span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-[#5c4039]">Đối tượng:</span>
                    <span className="font-medium text-[#141b2c]">{record.targetType}</span>
                  </div>
                </div>
              </div>

              {/* Section 2: Diff Inspection */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[13px] font-semibold text-[#141b2c]">
                    <GitCompare className="size-4 text-[#ad2c00]" />
                    Giá trị thay đổi
                  </span>
                  <span className="rounded bg-[#006b2f]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
                    {record.diffs.length} trường
                  </span>
                </div>

                <div className="space-y-2.5 rounded-xl bg-[#f1f3ff] p-3.5">
                  {record.diffs.map((diff) => (
                    <div
                      key={diff.field}
                      className="flex flex-col gap-1.5 rounded-lg bg-white p-3"
                    >
                      <span className="font-mono text-xs font-semibold text-[#141b2c]">
                        {diff.field}
                      </span>
                      <div className="flex items-center gap-2.5 font-mono text-xs">
                        <span className="rounded bg-[#ffdad6] px-2.5 py-0.5 text-[#ba1a1a] line-through">
                          {diff.oldValue}
                        </span>
                        <ArrowRight className="size-3.5 text-[#5c4039]" />
                        <span className="rounded bg-[#1f8642]/15 px-2.5 py-0.5 font-bold text-[#006b2f]">
                          {diff.newValue}
                        </span>
                      </div>
                      {diff.description && (
                        <span className="text-[11px] text-[#5c4039]">{diff.description}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Section 3: Clean JSON Payload */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[13px] font-semibold text-[#141b2c]">
                    <FileCode2 className="size-4 text-[#186392]" />
                    JSON Payload
                  </span>
                  <button
                    type="button"
                    onClick={() => onCopyJson(formattedJson)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[#186392] transition-colors hover:text-[#ad2c00] cursor-pointer"
                  >
                    <Copy className="size-3.5" />
                    <span>Sao chép JSON</span>
                  </button>
                </div>

                <div className="overflow-x-auto rounded-xl bg-[#293041] p-4 font-mono text-xs leading-relaxed text-[#edf0ff] shadow-inner">
                  <pre>{formattedJson}</pre>
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="flex items-center justify-end border-t border-[#e9edff] bg-[#f1f3ff] p-4">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-[#293041] px-5 py-2 text-xs font-semibold text-[#edf0ff] transition-colors hover:bg-[#293041]/90 cursor-pointer"
              >
                Đóng
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
