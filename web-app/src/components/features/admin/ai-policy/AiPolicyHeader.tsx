'use client';

import React from 'react';
import { Gauge, RefreshCw } from 'lucide-react';

interface AiPolicyHeaderProps {
  isMeasuring: boolean;
  isRefreshing: boolean;
  disabled: boolean;
  onMeasure: () => void;
  onRefresh: () => void;
}

const buttonClass = 'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-60';

export default function AiPolicyHeader({
  isMeasuring,
  isRefreshing,
  disabled,
  onMeasure,
  onRefresh,
}: AiPolicyHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c] dark:text-foreground">
          AI & Chính sách hệ thống
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039] dark:text-muted-foreground">
          Giám sát trạng thái các dịch vụ AI và cấu hình tham số phỏng vấn thích ứng.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 sm:shrink-0">
        <button type="button" onClick={onRefresh} disabled={disabled}
          className={`${buttonClass} bg-white text-[#141b2c] hover:bg-[#f1f3ff] dark:bg-card dark:text-foreground dark:hover:bg-muted`}>
          <RefreshCw aria-hidden="true" className={`size-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Đang kiểm tra…' : 'Kiểm tra dịch vụ'}
        </button>
        <button type="button" onClick={onMeasure} disabled={disabled}
          className={`${buttonClass} bg-primary text-primary-foreground hover:bg-primary/90`}>
          <Gauge aria-hidden="true" className="size-3.5" />
          {isMeasuring ? 'Đang đo phản hồi…' : 'Đo phản hồi'}
        </button>
      </div>
    </div>
  );
}
