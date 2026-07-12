'use client';

import type { ReactNode } from 'react';

interface RuleDashboardSectionProps {
  title: string;
  description?: string;
  count?: number | string;
  countLabel?: string;
  action?: ReactNode;
  children: ReactNode;
}

export default function RuleDashboardSection({
  title,
  description,
  count,
  countLabel,
  action,
  children,
}: RuleDashboardSectionProps) {
  return (
    <section className="overflow-hidden rounded-[28px] border border-white/6 bg-slate-950/55 shadow-[0_18px_70px_rgba(2,6,23,0.22)] backdrop-blur-sm">
      <div className="flex flex-col gap-4 border-b border-white/6 px-5 py-5 sm:flex-row sm:items-start sm:justify-between sm:px-6 lg:px-7 lg:py-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-base font-semibold tracking-wide text-white sm:text-[17px]">{title}</h3>
            {typeof count !== 'undefined' && (
              <span className="inline-flex items-center rounded-full border border-slate-700/80 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-slate-300">
                {count}
                {countLabel ? <span className="ml-1 text-slate-500">{countLabel}</span> : null}
              </span>
            )}
          </div>
          {description && <p className="mt-1.5 max-w-4xl text-sm leading-6 text-slate-400">{description}</p>}
        </div>
        {action ? <div className="flex-shrink-0">{action}</div> : null}
      </div>
      <div className="px-0 py-0 sm:px-0">{children}</div>
    </section>
  );
}
