'use client';

import React from 'react';
import { BellRing, Database, GitFork, Trash2 } from 'lucide-react';
import { QUEUE_PRIMARY_TABS } from './mockQueueStorageData';
import { QueuePrimaryTabKey } from './types';

interface QueuePrimaryTabsProps {
  activeTab: QueuePrimaryTabKey;
  onSelectTab: (tab: QueuePrimaryTabKey) => void;
}

const TAB_ICONS: Record<QueuePrimaryTabKey, React.ReactNode> = {
  'skill-gap-jobs': <GitFork className="size-4" />,
  'web-push': <BellRing className="size-4" />,
  'trash-profiles': <Trash2 className="size-4" />,
  storage: <Database className="size-4" />,
};

export default function QueuePrimaryTabs({
  activeTab,
  onSelectTab,
}: QueuePrimaryTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Phân mục Hàng đợi & Lưu trữ"
      className="flex flex-wrap items-center gap-1 rounded-xl bg-white p-1.5 shadow-xs"
    >
      {QUEUE_PRIMARY_TABS.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onSelectTab(tab.key)}
            className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] transition-all cursor-pointer ${
              isActive
                ? 'bg-[#ad2c00] font-semibold text-white shadow-xs'
                : 'font-medium text-[#5c4039] hover:bg-[#e0e8ff] hover:text-[#141b2c]'
            }`}
          >
            {TAB_ICONS[tab.key]}
            <span>{tab.label}</span>
            {typeof tab.badgeCount === 'number' && (
              <span
                className={`ml-1 rounded-full px-2 py-0.5 font-mono text-xs ${
                  isActive
                    ? 'bg-[#d83900] text-[#fffbff]'
                    : 'bg-[#e0e8ff] text-[#141b2c]'
                }`}
              >
                {tab.badgeCount.toLocaleString('en-US')}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
