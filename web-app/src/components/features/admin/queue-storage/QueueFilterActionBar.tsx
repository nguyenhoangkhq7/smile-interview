'use client';

import { ChevronDown, Search } from 'lucide-react';
import { QueueJobStatus } from './types';

interface QueueFilterActionBarProps {
  jobSearch: string;
  onJobSearchChange: (value: string) => void;
  statusFilter: '' | QueueJobStatus;
  onStatusFilterChange: (value: '' | QueueJobStatus) => void;
}

export default function QueueFilterActionBar({
  jobSearch,
  onJobSearchChange,
  statusFilter,
  onStatusFilterChange,
}: QueueFilterActionBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-white dark:bg-card p-4 shadow-xs">
      <div className="relative min-w-48 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        <input
          type="text" maxLength={200}
          value={jobSearch}
          onChange={(e) => onJobSearchChange(e.target.value)}
          placeholder="Tìm mã Job, ứng viên..."
          className="w-full rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-9 pr-4 text-xs text-[#141b2c] dark:text-foreground placeholder:text-[#5c4039] dark:placeholder:text-muted-foreground outline-none transition-all focus:bg-white dark:focus:bg-card focus:ring-2 focus:ring-[#ad2c00]/20"
        />
      </div>

      <div className="relative">
        <select
          value={statusFilter}
          onChange={(e) => onStatusFilterChange(e.target.value as '' | QueueJobStatus)}
          aria-label="Lọc theo trạng thái job"
          className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e0e8ff] dark:hover:bg-secondary"
        >
          <option value="">Tất cả trạng thái</option>
          <option value="RUNNING">Đang chạy (Running)</option>
          <option value="FAILED">Thất bại (Failed)</option>
          <option value="PENDING">Đang chờ (Pending)</option>
          <option value="SUCCEEDED">Thành công (Succeeded)</option>
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
      </div>
    </div>
  );
}
