'use client';

import React from 'react';
import { ChevronDown, RotateCcw, Search } from 'lucide-react';
import { QueueJobStatus } from './types';

interface QueueFilterActionBarProps {
  jobSearch: string;
  onJobSearchChange: (value: string) => void;
  statusFilter: '' | QueueJobStatus;
  onStatusFilterChange: (value: '' | QueueJobStatus) => void;
  failedJobsCount: number;
  onRetryAllFailed: () => void;
  isBulkRetrying: boolean;
}

export default function QueueFilterActionBar({
  jobSearch,
  onJobSearchChange,
  statusFilter,
  onStatusFilterChange,
  failedJobsCount,
  onRetryAllFailed,
  isBulkRetrying,
}: QueueFilterActionBarProps) {
  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white p-4 shadow-xs sm:flex-row sm:items-center">
      {/* Left Filters */}
      <div className="flex flex-1 flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] max-w-sm flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#5c4039]" />
          <input
            type="text"
            value={jobSearch}
            onChange={(e) => onJobSearchChange(e.target.value)}
            placeholder="Tìm mã Job, ứng viên..."
            className="w-full rounded-lg bg-[#f1f3ff] py-2 pl-9 pr-4 text-xs text-[#141b2c] placeholder:text-[#5c4039] outline-none transition-all focus:bg-white focus:ring-2 focus:ring-[#ad2c00]/20"
          />
        </div>

        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value as '' | QueueJobStatus)}
            aria-label="Lọc theo trạng thái job"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] outline-none transition-colors hover:bg-[#e0e8ff]"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="RUNNING">Đang chạy (Running)</option>
            <option value="FAILED">Thất bại (Failed)</option>
            <option value="PENDING">Đang chờ (Pending)</option>
            <option value="SUCCEEDED">Thành công (Succeeded)</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039]" />
        </div>
      </div>

      {/* Bulk Retry Button */}
      <button
        type="button"
        onClick={onRetryAllFailed}
        disabled={isBulkRetrying || failedJobsCount === 0}
        className="flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-[#ad2c00] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-[#d83900] disabled:opacity-50 cursor-pointer"
      >
        <RotateCcw className={`size-3.5 ${isBulkRetrying ? 'animate-spin' : ''}`} />
        <span>Thử lại job lỗi ({failedJobsCount})</span>
      </button>
    </div>
  );
}
