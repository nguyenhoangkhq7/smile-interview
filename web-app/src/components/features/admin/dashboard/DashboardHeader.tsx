'use client';

import React from 'react';
import { TIME_RANGE_OPTIONS } from '../data/dashboardOptions';
import { TimeRangeKey } from '../types';

interface DashboardHeaderProps {
  selectedRange: TimeRangeKey;
  onSelectRange: (range: TimeRangeKey) => void;
}

export default function DashboardHeader({
  selectedRange,
  onSelectRange,
}: DashboardHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
          Tổng quan hệ thống
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
          Theo dõi hoạt động, chất lượng AI và tình trạng vận hành Smile Interview.
        </p>
      </div>

      {/* Time Filter Pills */}
      <div
        role="tablist"
        aria-label="Bộ lọc thời gian thống kê"
        className="flex items-center self-start rounded-xl bg-[#e9edff] dark:bg-secondary p-1 shadow-inner md:self-auto"
      >
        {TIME_RANGE_OPTIONS.map((option) => {
          const isActive = selectedRange === option.key;
          return (
            <button
              key={option.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelectRange(option.key)}
              className={`rounded-lg px-4 py-1.5 text-[13px] transition-all duration-200 cursor-pointer ${isActive
                  ? 'bg-white dark:bg-card font-semibold text-[#141b2c] dark:text-foreground shadow-xs'
                  : 'font-medium text-[#5c4039] dark:text-muted-foreground hover:text-[#141b2c] dark:hover:text-foreground'
                }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
