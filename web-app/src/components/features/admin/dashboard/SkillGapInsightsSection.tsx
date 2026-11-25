'use client';

import React, { useEffect, useState } from 'react';
import { Brain, Briefcase } from 'lucide-react';
import { KnowledgeGapItem, PopularRoleItem } from '../types';

interface SkillGapInsightsSectionProps {
  knowledgeGaps: KnowledgeGapItem[];
  popularRoles: PopularRoleItem[];
}

export default function SkillGapInsightsSection({
  knowledgeGaps,
  popularRoles,
}: SkillGapInsightsSectionProps) {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 250);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      {/* Left: Top 5 Knowledge Gaps (7 Cols) */}
      <div className="flex flex-col justify-between rounded-xl bg-white p-6 shadow-xs lg:col-span-7">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-[#141b2c]">
              Top 5 Lỗ hổng kiến thức phổ biến
            </h2>
            <p className="text-xs text-[#5c4039]">
              Tổng hợp từ kết quả đối sánh CV–JD và phỏng vấn
            </p>
          </div>
          <span className="rounded-lg bg-[#f1f3ff] p-2 text-[#ad2c00]">
            <Brain className="size-4.5" />
          </span>
        </div>

        <div className="space-y-3.5">
          {knowledgeGaps.map((gap) => (
            <div key={gap.rank}>
              <div className="mb-1.5 flex items-center justify-between text-xs font-medium">
                <span className="flex items-center gap-2">
                  <span className={`font-mono font-bold ${gap.rankTextClass}`}>#{gap.rank}</span>
                  <span className="font-medium text-[#141b2c]">{gap.title}</span>
                </span>
                <span className="font-mono font-bold text-[#141b2c] tabular-nums">
                  {gap.percentage}%{' '}
                  <span className="font-normal text-[#5c4039]">
                    ({gap.candidatesCount.toLocaleString('en-US')})
                  </span>
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-[#e9edff]">
                <div
                  className={`${gap.barColorClass} h-full rounded-full transition-all duration-700 ease-out`}
                  style={{ width: animated ? `${gap.percentage}%` : '0%' }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Target Role Distribution (5 Cols) */}
      <div className="flex flex-col justify-between rounded-xl bg-white p-6 shadow-xs lg:col-span-5">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-[#141b2c]">
              Vị trí phỏng vấn phổ biến
            </h2>
            <p className="text-xs text-[#5c4039]">Phân bố theo nhóm ngành tuyển dụng</p>
          </div>
          <span className="rounded-lg bg-[#f1f3ff] p-2 text-[#186392]">
            <Briefcase className="size-4.5" />
          </span>
        </div>

        <div className="space-y-1.5">
          {popularRoles.map((role) => (
            <div
              key={role.code}
              className="flex items-center justify-between rounded-lg p-2 transition-colors hover:bg-[#f1f3ff]"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div
                  className={`flex size-8 shrink-0 items-center justify-center rounded-lg font-mono text-xs font-bold ${role.badgeBgClass} ${role.badgeTextClass}`}
                >
                  {role.code}
                </div>
                <div className="truncate">
                  <div className="truncate text-sm font-semibold text-[#141b2c]">
                    {role.title}
                  </div>
                  <div className="truncate text-xs text-[#5c4039]">{role.techStack}</div>
                </div>
              </div>

              <div className="pl-2 text-right">
                <div className="text-sm font-semibold text-[#141b2c] tabular-nums">
                  {role.count.toLocaleString('en-US')}
                </div>
                <div className={`text-[11px] font-semibold ${role.growthTextClass}`}>
                  {role.growth}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
