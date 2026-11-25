'use client';

import React from 'react';
import { CheckCircle2, Search, X } from 'lucide-react';
import { SESSION_FILTER_TABS } from './mockSessionsData';
import { SessionFilterTabKey } from './types';

interface SessionsFilterBarProps {
  activeFilterTab: SessionFilterTabKey;
  onSelectFilterTab: (tab: SessionFilterTabKey) => void;
  sessionSearch: string;
  onSessionSearchChange: (value: string) => void;
}

export default function SessionsFilterBar({
  activeFilterTab,
  onSelectFilterTab,
  sessionSearch,
  onSessionSearchChange,
}: SessionsFilterBarProps) {
  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white p-2.5 shadow-xs sm:flex-row sm:items-center">
      {/* Filter Tabs */}
      <div
        role="tablist"
        aria-label="Lọc trạng thái phiên phỏng vấn"
        className="flex items-center gap-1 overflow-x-auto text-nowrap"
      >
        {SESSION_FILTER_TABS.map((tab) => {
          const isActive = activeFilterTab === tab.key;

          if (tab.isAnomaly) {
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onSelectFilterTab(tab.key)}
                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-[#ba1a1a] text-white shadow-xs'
                    : 'bg-[#ffdad6]/40 text-[#ba1a1a] hover:bg-[#ffdad6] hover:text-[#93000a]'
                }`}
              >
                <span className="size-2 rounded-full bg-current" />
                <span>Phiên bất thường</span>
                <span
                  className={`rounded-full px-1.5 py-0.5 font-mono text-[11px] font-semibold ${
                    isActive ? 'bg-white/20 text-white' : 'bg-[#ba1a1a] text-white'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          }

          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelectFilterTab(tab.key)}
              className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#d83900] font-semibold text-[#fffbff] shadow-xs'
                  : 'font-medium text-[#5c4039] hover:bg-[#f1f3ff] hover:text-[#141b2c]'
              }`}
            >
              {isActive && <CheckCircle2 className="size-3.5" />}
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-1.5 py-0.5 font-mono text-[11px] ${
                  isActive ? 'bg-white/20 text-[#fffbff]' : 'bg-[#e0e8ff] text-[#5c4039]'
                }`}
              >
                {tab.count.toLocaleString('en-US')}
              </span>
            </button>
          );
        })}
      </div>

      {/* Clean Search Input */}
      <div className="relative w-full sm:w-64">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#5c4039]" />
        <input
          type="text"
          value={sessionSearch}
          onChange={(e) => onSessionSearchChange(e.target.value)}
          placeholder="Tìm mã phiên, ứng viên..."
          className="w-full rounded-lg bg-[#f1f3ff] py-2 pl-9 pr-8 text-xs text-[#141b2c] outline-none transition-all focus:bg-white focus:ring-2 focus:ring-[#ad2c00]/20"
        />
        {sessionSearch && (
          <button
            type="button"
            onClick={() => onSessionSearchChange('')}
            aria-label="Xóa tìm kiếm"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#5c4039] hover:text-[#141b2c] cursor-pointer"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
