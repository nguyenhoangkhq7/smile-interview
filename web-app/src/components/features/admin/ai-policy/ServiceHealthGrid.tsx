'use client';

import React, { useEffect, useState } from 'react';
import {
  BellRing,
  BrainCircuit,
  CloudSync,
  Database,
  GitFork,
  Mic,
  ShieldCheck,
  SmilePlus,
  Zap,
} from 'lucide-react';
import { ServiceHealthCardItem, ServiceIconKey } from './types';

interface ServiceHealthGridProps {
  services: ServiceHealthCardItem[];
  isCheckingHealth: boolean;
}

const SERVICE_ICONS: Record<ServiceIconKey, React.ReactNode> = {
  database: <Database className="size-4.5" />,
  bolt: <Zap className="size-4.5" />,
  cloud: <CloudSync className="size-4.5" />,
  bell: <BellRing className="size-4.5" />,
  brain: <BrainCircuit className="size-4.5" />,
  tree: <GitFork className="size-4.5" />,
  mic: <Mic className="size-4.5" />,
  avatar: <SmilePlus className="size-4.5" />,
};

export default function ServiceHealthGrid({
  services,
  isCheckingHealth,
}: ServiceHealthGridProps) {
  const [barsAnimated, setBarsAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setBarsAnimated(true), 120);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-5 text-[#ad2c00]" />
          <h2 className="text-lg font-semibold text-[#141b2c]">Trạng thái dịch vụ hạ tầng</h2>
        </div>

        <span className="flex items-center gap-1.5 rounded-full bg-[#006b2f]/10 px-2.5 py-1 font-mono text-xs font-semibold text-[#006b2f]">
          <span
            className={`size-2 rounded-full bg-[#006b2f] ${
              isCheckingHealth ? 'animate-ping' : ''
            }`}
          />
          8/8 Sẵn sàng
        </span>
      </div>

      {/* 8 Compact Service Cards */}
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {services.map((svc, idx) => (
          <div
            key={svc.id}
            style={{ animationDelay: `${idx * 40}ms`, animationFillMode: 'both' }}
            className="animate-fade-up flex flex-col justify-between rounded-xl bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
          >
            <div>
              <div className="mb-2.5 flex items-center justify-between">
                <div
                  className={`rounded-lg bg-[#f1f3ff] p-2 ${
                    svc.iconAccent === 'primary' ? 'text-[#ad2c00]' : 'text-[#186392]'
                  }`}
                >
                  {SERVICE_ICONS[svc.iconKey]}
                </div>

                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#006b2f]/10 px-2 py-0.5 text-[11px] font-semibold text-[#006b2f]">
                  <span className="relative flex size-1.5">
                    <span
                      className={`absolute inline-flex h-full w-full rounded-full bg-[#006b2f] opacity-75 ${
                        idx === 0 || isCheckingHealth ? 'animate-ping' : ''
                      }`}
                    />
                    <span className="relative inline-flex size-1.5 rounded-full bg-[#006b2f]" />
                  </span>
                  Healthy
                </span>
              </div>

              <h3 className="truncate text-sm font-semibold text-[#141b2c]">{svc.name}</h3>
            </div>

            <div className="mt-3 space-y-1.5 border-t border-[#f1f3ff] pt-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[11px] text-[#5c4039]">{svc.latencyLabel}</span>
                <span
                  className={`font-mono text-xs font-semibold tabular-nums ${
                    svc.latencyColor === 'tertiary' ? 'text-[#006b2f]' : 'text-[#186392]'
                  }`}
                >
                  {svc.latencyValue}
                </span>
              </div>

              <div className="h-1 w-full overflow-hidden rounded-full bg-[#e0e8ff]">
                <div
                  className={`h-full rounded-full transition-all duration-700 ease-out ${
                    svc.latencyColor === 'tertiary' ? 'bg-[#006b2f]' : 'bg-[#186392]'
                  }`}
                  style={{ width: barsAnimated ? `${svc.latencyBarPct}%` : '0%' }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
