'use client';

import React, { useEffect, useState } from 'react';
import { FolderX, HardDrive, Sparkles } from 'lucide-react';
import { StorageOverviewData } from './types';

interface StorageAllocationSectionProps {
  storage: StorageOverviewData;
  isCleaningOrphans: boolean;
  onCleanOrphans: () => void;
}

export default function StorageAllocationSection({
  storage,
  isCleaningOrphans,
  onCleanOrphans,
}: StorageAllocationSectionProps) {
  const [barAnimated, setBarAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setBarAnimated(true), 150);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="space-y-4 rounded-xl bg-white p-5 shadow-xs">
      {/* Header */}
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-[#e0e8ff] text-[#186392]">
          <HardDrive className="size-4.5" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-[#141b2c]">Tổng quan lưu trữ</h3>
          <p className="text-xs text-[#5c4039]">Dung lượng phân bổ theo từng nhóm tài nguyên</p>
        </div>
      </div>

      {/* Storage Usage Bar */}
      <div className="space-y-2.5 rounded-xl bg-[#f1f3ff] p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-[#5c4039]">Đã dùng:</span>
            <span className="text-xl font-bold text-[#141b2c] tabular-nums">
              {storage.totalUsedGb.toFixed(1)} GB
            </span>
            <span className="text-xs text-[#5c4039]">/ {storage.totalCapacityGb} GB</span>
          </div>
          <div className="text-xs font-semibold text-[#186392] tabular-nums">
            {storage.usedPercentage.toFixed(1)}%
          </div>
        </div>

        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[#e0e8ff]">
          {storage.segments.map((seg) => (
            <div
              key={seg.id}
              className={`h-full transition-all duration-700 ease-out ${seg.colorClass}`}
              style={{ width: barAnimated ? `${seg.widthPct}%` : '0%' }}
              title={`${seg.label}: ${seg.sizeGb} GB`}
            />
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 pt-1.5 md:grid-cols-4">
          {storage.segments.map((seg) => (
            <div key={seg.id} className="flex items-center gap-2">
              <span className={`size-2.5 shrink-0 rounded-xs ${seg.colorClass}`} />
              <div className="truncate">
                <div className="truncate text-[11px] font-medium text-[#5c4039]">{seg.label}</div>
                <div className="text-xs font-semibold text-[#141b2c] tabular-nums">
                  {seg.sizeGb.toFixed(1)} GB
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Orphan Files Action Banner */}
      <div
        className={`flex flex-col items-start justify-between gap-3 rounded-xl p-4 transition-colors duration-300 sm:flex-row sm:items-center ${storage.orphanedFilesCount > 0 ? 'bg-[#ffdad6]/35' : 'bg-[#95f8a7]/25'
          }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${storage.orphanedFilesCount > 0
                ? 'bg-[#ffdad6] text-[#93000a]'
                : 'bg-[#95f8a7] text-[#00210a]'
              }`}
          >
            <FolderX className="size-4.5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-[#141b2c]">
              {storage.orphanedFilesCount > 0
                ? `Phát hiện ${storage.orphanedFilesCount} tệp CV mồ côi (${storage.orphanedFilesSizeMb} MB)`
                : 'Không có tệp CV mồ côi tồn đọng (0 MB)'}
            </div>
            <p className="text-xs text-[#5c4039]">
              {storage.orphanedFilesCount > 0
                ? 'Các tệp không còn liên kết với hồ sơ ứng viên hợp lệ.'
                : 'Tài nguyên lưu trữ đã được đồng bộ sạch sẽ.'}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onCleanOrphans}
          disabled={isCleaningOrphans || storage.orphanedFilesCount === 0}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[#ba1a1a] px-3.5 py-2 text-xs font-semibold text-white shadow-2xs transition-all hover:bg-[#ba1a1a]/90 disabled:opacity-50 cursor-pointer"
        >
          <Sparkles className={`size-3.5 ${isCleaningOrphans ? 'animate-spin' : ''}`} />
          <span>
            {isCleaningOrphans
              ? 'Đang dọn dẹp...'
              : storage.orphanedFilesCount > 0
                ? 'Dọn dẹp tệp mồ côi'
                : 'Đã dọn sạch'}
          </span>
        </button>
      </div>
    </div>
  );
}
