'use client';

import React from 'react';
import { Calendar, ChevronDown, FilterX, Search } from 'lucide-react';
import { getTodayAuditDate } from '@/services/adminAudit';
import {
  auditActions,
  type AuditActionType,
  type AuditActor,
  type AuditDatePreset,
  type AuditFilter,
} from './types';

interface AuditLogsFilterBarProps {
  filter: AuditFilter;
  actors: AuditActor[];
  onChange: (filter: AuditFilter) => void;
  onResetFilters: () => void;
}

const DATE_PRESET_OPTIONS: { value: AuditDatePreset; label: string }[] = [
  { value: 'all', label: 'Tất cả thời gian' },
  { value: 'today', label: 'Hôm nay' },
  { value: '7d', label: '7 ngày qua' },
  { value: '1m', label: '1 tháng qua' },
  { value: '2m', label: '2 tháng qua' },
  { value: 'day', label: 'Một ngày cụ thể' },
  { value: 'range', label: 'Khoảng ngày tùy chọn' },
];

export default function AuditLogsFilterBar({
  filter,
  actors,
  onChange,
  onResetFilters,
}: AuditLogsFilterBarProps) {
  const today = getTodayAuditDate();
  const hasActiveFilter = Boolean(
    filter.search ||
      filter.actorId ||
      filter.action ||
      filter.datePreset !== 'all' ||
      filter.date ||
      filter.fromDate ||
      filter.toDate
  );

  const handlePresetChange = (nextPreset: AuditDatePreset) => {
    if (nextPreset === 'day') {
      onChange({
        ...filter,
        datePreset: nextPreset,
        date: filter.date || today,
        fromDate: '',
        toDate: '',
      });
    } else if (nextPreset === 'range') {
      onChange({
        ...filter,
        datePreset: nextPreset,
        date: '',
        fromDate: filter.fromDate || today,
        toDate: filter.toDate || today,
      });
    } else {
      onChange({
        ...filter,
        datePreset: nextPreset,
        date: '',
        fromDate: '',
        toDate: '',
      });
    }
  };

  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white dark:bg-card p-4 shadow-xs lg:flex-row lg:items-center">
      {/* Search Input */}
      <div className="relative min-w-[240px] flex-1">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        <input
          type="text"
          value={filter.search}
          onChange={(e) => onChange({ ...filter, search: e.target.value })}
          maxLength={200}
          aria-label="Tìm nhật ký"
          placeholder="Tìm theo mã đối tượng hoặc nội dung…"
          className="w-full rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-10 pr-4 text-xs text-[#141b2c] dark:text-foreground placeholder:text-[#5c4039] dark:placeholder:text-muted-foreground outline-none transition-all focus:bg-[#e9edff] dark:focus:bg-secondary"
        />
      </div>

      {/* Single-Row Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Time / Date Filter */}
        <div className="relative">
          <Calendar className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
          <select
            value={filter.datePreset}
            onChange={(e) => handlePresetChange(e.target.value as AuditDatePreset)}
            aria-label="Lọc theo thời gian"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-8 pr-8 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
          >
            {DATE_PRESET_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        </div>

        {/* Specific Day Picker */}
        {filter.datePreset === 'day' && (
          <input
            type="date"
            aria-label="Chọn ngày cụ thể"
            value={filter.date}
            max={today}
            onChange={(e) => onChange({ ...filter, date: e.target.value })}
            className="rounded-lg bg-[#f1f3ff] dark:bg-muted px-2.5 py-1.5 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
          />
        )}

        {/* Custom Date Range Pickers */}
        {filter.datePreset === 'range' && (
          <div className="flex flex-wrap items-center gap-1.5">
            <input
              type="date"
              aria-label="Từ ngày"
              value={filter.fromDate}
              max={filter.toDate || today}
              onChange={(e) => onChange({ ...filter, fromDate: e.target.value })}
              className="rounded-lg bg-[#f1f3ff] dark:bg-muted px-2.5 py-1.5 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
            />
            <span className="text-xs text-[#5c4039] dark:text-muted-foreground">–</span>
            <input
              type="date"
              aria-label="Đến ngày"
              value={filter.toDate}
              min={filter.fromDate || undefined}
              max={today}
              onChange={(e) => onChange({ ...filter, toDate: e.target.value })}
              className="rounded-lg bg-[#f1f3ff] dark:bg-muted px-2.5 py-1.5 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
            />
          </div>
        )}

        {/* Admin Actor Filter */}
        <div className="relative">
          <select
            value={filter.actorId}
            onChange={(e) => onChange({ ...filter, actorId: e.target.value })}
            aria-label="Lọc theo Quản trị viên"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
          >
            <option value="">Tất cả Admin</option>
            {actors.map((actor) => (
              <option key={actor.id} value={actor.id}>
                {actor.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        </div>

        {/* Action Filter */}
        <div className="relative">
          <select
            value={filter.action}
            onChange={(e) => onChange({ ...filter, action: e.target.value as '' | AuditActionType })}
            aria-label="Lọc theo hành động"
            className="cursor-pointer appearance-none rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-3 pr-8 text-xs font-medium text-[#141b2c] dark:text-foreground outline-none transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary"
          >
            <option value="">Tất cả hành động</option>
            {auditActions.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        </div>

        {hasActiveFilter && (
          <button
            type="button"
            onClick={onResetFilters}
            className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium text-[#186392] dark:text-sky-300 transition-colors hover:bg-[#e9edff] dark:hover:bg-secondary cursor-pointer"
          >
            <FilterX className="size-3.5" />
            <span>Xóa lọc</span>
          </button>
        )}
      </div>
    </div>
  );
}
