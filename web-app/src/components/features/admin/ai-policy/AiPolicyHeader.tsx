'use client';

import React from 'react';
import { RefreshCw } from 'lucide-react';

interface AiPolicyHeaderProps {
  isCheckingHealth: boolean;
  onTriggerHealthCheck: () => void;
}

export default function AiPolicyHeader({
  isCheckingHealth,
  onTriggerHealthCheck,
}: AiPolicyHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold leading-8 tracking-tight text-[#141b2c]">
          AI & Chính sách hệ thống
        </h1>
        <p className="max-w-2xl text-sm leading-5 text-[#5c4039]">
          Giám sát trạng thái các dịch vụ AI và cấu hình tham số phỏng vấn thích ứng.
        </p>
      </div>

      <button
        type="button"
        onClick={onTriggerHealthCheck}
        className="inline-flex items-center gap-2 self-start rounded-lg bg-white px-3.5 py-2 text-xs font-semibold text-[#141b2c] shadow-xs transition-all hover:bg-[#f1f3ff] sm:self-auto cursor-pointer"
      >
        <RefreshCw
          className={`size-3.5 text-[#006b2f] ${isCheckingHealth ? 'animate-spin' : ''}`}
        />
        <span>{isCheckingHealth ? 'Đang kiểm tra...' : 'Kiểm tra dịch vụ'}</span>
      </button>
    </div>
  );
}
