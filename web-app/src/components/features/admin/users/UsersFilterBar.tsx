'use client';

import React from 'react';
import { ChevronDown, FilterX, Search } from 'lucide-react';
import { AdminUserRole, AdminUserStatus } from './types';

interface UsersFilterBarProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  roleFilter: '' | AdminUserRole;
  onRoleFilterChange: (value: '' | AdminUserRole) => void;
  statusFilter: '' | AdminUserStatus;
  onStatusFilterChange: (value: '' | AdminUserStatus) => void;
  onResetFilters: () => void;
}

export default function UsersFilterBar({
  searchTerm,
  onSearchChange,
  roleFilter,
  onRoleFilterChange,
  statusFilter,
  onStatusFilterChange,
  onResetFilters,
}: UsersFilterBarProps) {
  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white p-4 shadow-xs lg:flex-row lg:items-center">
      {/* Search Bar */}
      <div className="relative min-w-[260px] flex-1">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-[#5c4039]" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Tìm theo tên, email hoặc số điện thoại..."
          className="w-full rounded-lg bg-[#f1f3ff] py-2 pl-10 pr-4 text-xs text-[#141b2c] placeholder:text-[#5c4039] outline-none transition-all focus:bg-[#e9edff]"
        />
      </div>

      {/* Filters Group */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[140px]">
          <select
            value={roleFilter}
            onChange={(e) => onRoleFilterChange(e.target.value as '' | AdminUserRole)}
            aria-label="Lọc theo vai trò"
            className="w-full cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] outline-none transition-colors hover:bg-[#e9edff]"
          >
            <option value="">Tất cả vai trò</option>
            <option value="USER">USER (Ứng viên)</option>
            <option value="ADMIN">ADMIN (Quản trị)</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039]" />
        </div>

        <div className="relative min-w-[150px]">
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value as '' | AdminUserStatus)}
            aria-label="Lọc theo trạng thái"
            className="w-full cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] outline-none transition-colors hover:bg-[#e9edff]"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="ACTIVE">ACTIVE (Hoạt động)</option>
            <option value="LOCKED">LOCKED (Bị khóa)</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039]" />
        </div>

        <button
          type="button"
          onClick={onResetFilters}
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium text-[#186392] transition-colors hover:bg-[#e9edff] cursor-pointer"
        >
          <FilterX className="size-3.5" />
          <span>Xóa bộ lọc</span>
        </button>
      </div>
    </div>
  );
}
