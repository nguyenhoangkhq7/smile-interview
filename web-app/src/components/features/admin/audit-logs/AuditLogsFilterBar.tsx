'use client';

import React from 'react';
import { ChevronDown, FilterX, Search } from 'lucide-react';
import { AuditActionType } from './types';

interface AuditLogsFilterBarProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  adminFilter: string;
  onAdminFilterChange: (value: string) => void;
  actionFilter: 'ALL' | AuditActionType;
  onActionFilterChange: (value: 'ALL' | AuditActionType) => void;
  onResetFilters: () => void;
}

export default function AuditLogsFilterBar({
  searchTerm,
  onSearchChange,
  adminFilter,
  onAdminFilterChange,
  actionFilter,
  onActionFilterChange,
  onResetFilters,
}: AuditLogsFilterBarProps) {
  const hasActiveFilter =
    searchTerm.trim() !== '' || adminFilter !== 'ALL' || actionFilter !== 'ALL';

  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white p-4 shadow-xs lg:flex-row lg:items-center">
      {/* Search Input */}
      <div className="relative min-w-[260px] flex-1">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-[#5c4039]" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Tìm theo mã đối tượng (#USR-..., #SESS-..., #JOB-..., #POL-...) hoặc nội dung..."
          className="w-full rounded-lg bg-[#f1f3ff] py-2 pl-10 pr-4 text-xs text-[#141b2c] placeholder:text-[#5c4039] outline-none transition-all focus:bg-[#e9edff]"
        />
      </div>

      {/* Single-Row Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <select
            value={adminFilter}
            onChange={(e) => onAdminFilterChange(e.target.value)}
            aria-label="Lọc theo Quản trị viên"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] outline-none transition-colors hover:bg-[#e9edff]"
          >
            <option value="ALL">Tất cả Admin</option>
            <option value="Dong Cao">Dong Cao</option>
            <option value="Pham Minh Duc">Pham Minh Duc</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039]" />
        </div>

        <div className="relative">
          <select
            value={actionFilter}
            onChange={(e) =>
              onActionFilterChange(e.target.value as 'ALL' | AuditActionType)
            }
            aria-label="Lọc theo hành động"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] outline-none transition-colors hover:bg-[#e9edff]"
          >
            <option value="ALL">Tất cả hành động</option>
            <option value="UPDATE_POLICY">UPDATE_POLICY</option>
            <option value="FORCE_CLOSE_SESSION">FORCE_CLOSE_SESSION</option>
            <option value="RETRY_JOB">RETRY_JOB</option>
            <option value="LOCK_USER">LOCK_USER</option>
            <option value="RESET_PASSWORD">RESET_PASSWORD</option>
            <option value="RELEASE_JOB_LEASE">RELEASE_JOB_LEASE</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039]" />
        </div>

        {hasActiveFilter && (
          <button
            type="button"
            onClick={onResetFilters}
            className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium text-[#186392] transition-colors hover:bg-[#e9edff] cursor-pointer"
          >
            <FilterX className="size-3.5" />
            <span>Xóa lọc</span>
          </button>
        )}
      </div>
    </div>
  );
}
