'use client';

import React from 'react';
import {
  Briefcase,
  CheckCircle2,
  FileDown,
  Mic,
  Star,
  Timer,
} from 'lucide-react';
import { InspectedSessionData } from './types';

interface FocusedSessionBannerProps {
  session: InspectedSessionData;
  onExportPdf: () => void;
}

export default function FocusedSessionBanner({
  session,
  onExportPdf,
}: FocusedSessionBannerProps) {
  return (
    <div className="flex flex-col justify-between gap-4 rounded-xl bg-white p-5 shadow-xs sm:flex-row sm:items-center">
      {/* Candidate & Session Meta */}
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-[#e9edff] text-base font-bold text-[#186392]">
          HN
        </div>

        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-lg font-semibold text-[#141b2c]">
              {session.candidateName}
            </span>
            <span className="rounded bg-[#e0e8ff] px-2 py-0.5 font-mono text-xs font-medium text-[#5c4039]">
              {session.sessionId}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#95f8a7]/40 px-2.5 py-0.5 text-[11px] font-semibold text-[#006b2f]">
              <CheckCircle2 className="size-3" />
              Hoàn thành
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#5c4039]">
            <span className="flex items-center gap-1 font-medium text-[#141b2c]">
              <Briefcase className="size-3.5 text-[#186392]" />
              {session.roleTitle}
            </span>
            <span className="flex items-center gap-1">
              <Timer className="size-3.5" />
              {session.durationLabel}
            </span>
            <span className="flex items-center gap-1">
              <Mic className="size-3.5 text-[#ad2c00]" />
              Voice
            </span>
            <span className="flex items-center gap-1 font-semibold text-[#141b2c]">
              <Star className="size-3.5 fill-amber-500 text-amber-500" />
              5/5
            </span>
          </div>
        </div>
      </div>

      {/* Single Primary Action Button */}
      <button
        type="button"
        onClick={onExportPdf}
        className="flex shrink-0 items-center gap-1.5 self-start rounded-lg bg-[#186392] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-[#186392]/90 sm:self-center cursor-pointer"
      >
        <FileDown className="size-4" />
        <span>Xuất báo cáo PDF</span>
      </button>
    </div>
  );
}
