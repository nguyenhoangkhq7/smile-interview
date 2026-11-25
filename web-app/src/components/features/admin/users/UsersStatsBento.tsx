'use client';

import React from 'react';
import {
  Ban,
  CheckCircle2,
  ShieldCheck,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useCountUp } from '../hooks/useCountUp';
import { UsersOverviewStats } from './types';

interface UsersStatsBentoProps {
  stats: UsersOverviewStats;
}

export default function UsersStatsBento({ stats }: UsersStatsBentoProps) {
  const totalUsersStr = useCountUp(stats.totalUsers);
  const activeUsersStr = useCountUp(stats.activeUsers);
  const lockedUsersStr = useCountUp(stats.lockedUsers);
  const adminUsersStr = useCountUp(stats.adminUsers);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Card 1: Total Users */}
      <div
        style={{ animationDelay: '0ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-8 items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#5c4039]">
            Tổng người dùng
          </span>
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#186392]">
            <Users className="size-4" />
          </span>
        </div>

        <div className="mt-2 flex h-9 items-baseline gap-2">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {totalUsersStr}
          </span>
          <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-[#006b2f]">
            <TrendingUp className="size-3.5" />
            {stats.totalGrowth}
          </span>
        </div>
      </div>

      {/* Card 2: Active Users */}
      <div
        style={{ animationDelay: '70ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-8 items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#5c4039]">
            Đang hoạt động
          </span>
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#006b2f]">
            <CheckCircle2 className="size-4" />
          </span>
        </div>

        <div className="mt-2 flex h-9 items-baseline gap-2">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {activeUsersStr}
          </span>
          <span className="rounded-full bg-[#e9edff] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#006b2f]">
            {stats.activeRatePct}
          </span>
        </div>
      </div>

      {/* Card 3: Locked Users */}
      <div
        style={{ animationDelay: '140ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-8 items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#5c4039]">
            Đang bị khóa
          </span>
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#ba1a1a]">
            <Ban className="size-4" />
          </span>
        </div>

        <div className="mt-2 flex h-9 items-baseline gap-2">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#ba1a1a] tabular-nums">
            {lockedUsersStr}
          </span>
        </div>
      </div>

      {/* Card 4: Admins */}
      <div
        style={{ animationDelay: '210ms', animationFillMode: 'both' }}
        className="animate-fade-up flex flex-col justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
      >
        <div className="flex h-8 items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#5c4039]">
            Quản trị viên
          </span>
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#f1f3ff] text-[#186392]">
            <ShieldCheck className="size-4" />
          </span>
        </div>

        <div className="mt-2 flex h-9 items-baseline gap-2">
          <span className="text-2xl font-bold leading-none tracking-tight text-[#141b2c] tabular-nums">
            {adminUsersStr}
          </span>
        </div>
      </div>
    </div>
  );
}
