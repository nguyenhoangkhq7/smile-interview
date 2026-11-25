'use client';

import React, { useState } from 'react';
import {
  Bot,
  Clock,
  FileCheck2,
  MessagesSquare,
} from 'lucide-react';
import { SessionTurnDetail } from './types';

interface TranscriptInspectorColumnProps {
  turns: SessionTurnDetail[];
  selectedTurnId: string;
  onSelectTurn: (turnId: string) => void;
}

const RUBRIC_LABELS: Record<
  SessionTurnDetail['rubricLevel'],
  { label: string; className: string }
> = {
  DEMONSTRATED_ABOVE_TARGET: {
    label: 'Vượt kỳ vọng',
    className: 'bg-[#1f8642] text-white',
  },
  DEMONSTRATED_AT_TARGET: {
    label: 'Đạt chuẩn',
    className: 'bg-[#006b2f] text-white',
  },
  DEMONSTRATED_BELOW_TARGET: {
    label: 'Dưới chuẩn',
    className: 'bg-[#ba1a1a] text-white',
  },
};

export default function TranscriptInspectorColumn({
  turns,
  selectedTurnId,
  onSelectTurn,
}: TranscriptInspectorColumnProps) {
  const [viewAllTurns, setViewAllTurns] = useState(false);
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);

  const activeTurn = turns.find((t) => t.id === selectedTurnId) ?? turns[2];
  const displayedTurns = viewAllTurns ? turns : [activeTurn];

  return (
    <div className="space-y-4 lg:col-span-8">
      {/* Unified Header & Turn Switcher Card */}
      <div className="space-y-3 rounded-xl bg-white p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <MessagesSquare className="size-4.5 text-[#ad2c00]" />
            <h2 className="text-base font-semibold text-[#141b2c]">
              Nội dung hỏi đáp & Bằng chứng
            </h2>
          </div>

          <div className="flex items-center rounded-lg bg-[#f1f3ff] p-1">
            <button
              type="button"
              onClick={() => setViewAllTurns(false)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
                !viewAllTurns
                  ? 'bg-white text-[#141b2c] shadow-2xs'
                  : 'text-[#5c4039] hover:text-[#141b2c]'
              }`}
            >
              Theo lượt
            </button>
            <button
              type="button"
              onClick={() => setViewAllTurns(true)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
                viewAllTurns
                  ? 'bg-white text-[#141b2c] shadow-2xs'
                  : 'text-[#5c4039] hover:text-[#141b2c]'
              }`}
            >
              Tất cả ({turns.length})
            </button>
          </div>
        </div>

        {/* Compact Turn Selector Pills */}
        {!viewAllTurns && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-nowrap">
            {turns.map((turn) => {
              const isSelected = turn.id === activeTurn.id;
              return (
                <button
                  key={turn.id}
                  type="button"
                  onClick={() => onSelectTurn(turn.id)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#186392] font-semibold text-white shadow-2xs'
                      : 'bg-[#f1f3ff] text-[#5c4039] hover:bg-[#e9edff] hover:text-[#141b2c]'
                  }`}
                >
                  {turn.pillLabel}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Turn Dialogue Cards */}
      <div className="space-y-4">
        {displayedTurns.map((turn) => {
          const isEvidenceSelected = highlightedEvidenceId === turn.evidenceCode;
          const rubricInfo = RUBRIC_LABELS[turn.rubricLevel];

          return (
            <div
              key={turn.id}
              className="animate-fade-up overflow-hidden rounded-xl bg-white shadow-xs"
            >
              {/* Compact Turn Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-[#f1f3ff] px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-[#ad2c00] px-2 py-0.5 font-mono text-[11px] font-bold text-white">
                    {turn.turnBadge}
                  </span>
                  <span className="text-sm font-semibold text-[#141b2c]">{turn.topicTitle}</span>
                </div>

                <span className="flex items-center gap-1 font-mono text-xs text-[#5c4039]">
                  <Clock className="size-3.5 text-[#186392]" />
                  {turn.timeRange}
                </span>
              </div>

              <div className="space-y-4 p-5">
                {/* 1. AI Question */}
                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#8ccafe] text-[#005581]">
                    <Bot className="size-4.5" />
                  </div>
                  <div className="min-w-0 flex-1 space-y-1">
                    <span className="text-xs font-semibold text-[#5c4039]">AI Interviewer</span>
                    <div className="rounded-xl rounded-tl-none bg-[#f1f3ff] p-3.5 text-sm leading-relaxed text-[#141b2c]">
                      {turn.aiPromptText}
                    </div>
                  </div>
                </div>

                {/* 2. Candidate Answer + Highlighted Evidence */}
                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#ad2c00] text-xs font-semibold text-white">
                    {turn.candidateInitials}
                  </div>

                  <div className="min-w-0 flex-1 space-y-2.5">
                    <span className="text-xs font-semibold text-[#5c4039]">
                      {turn.candidateName}
                    </span>

                    <div className="space-y-2.5 rounded-xl rounded-tl-none border border-[#e9edff] bg-white p-3.5 text-sm leading-relaxed text-[#141b2c]">
                      <p>
                        {turn.transcriptBeforeMark}
                        <mark
                          onClick={() =>
                            setHighlightedEvidenceId(
                              isEvidenceSelected ? null : turn.evidenceCode
                            )
                          }
                          className={`cursor-pointer rounded px-1.5 py-0.5 font-medium transition-all duration-300 ${
                            isEvidenceSelected
                              ? 'bg-[#ffdbd1] text-[#872100] ring-2 ring-[#ad2c00]/50'
                              : 'bg-[#ffdbd1]/50 text-[#872100] hover:bg-[#ffdbd1]'
                          }`}
                        >
                          {turn.transcriptHighlightedMark}
                        </mark>
                        {turn.transcriptAfterMark}
                      </p>
                    </div>

                    {/* 3. Compact 1-Row Evidence Summary Strip */}
                    <div
                      onClick={() =>
                        setHighlightedEvidenceId(
                          isEvidenceSelected ? null : turn.evidenceCode
                        )
                      }
                      className={`flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-2.5 text-xs transition-all cursor-pointer ${
                        isEvidenceSelected
                          ? 'bg-[#e0e8ff] ring-1 ring-[#ad2c00]/40'
                          : 'bg-[#f1f3ff] hover:bg-[#e9edff]'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileCheck2 className="size-4 text-[#ad2c00]" />
                        <span className="text-[#5c4039]">Kỹ năng đánh giá:</span>
                        <strong className="font-semibold text-[#141b2c]">
                          {turn.linkedSkill}
                        </strong>
                      </div>

                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${rubricInfo.className}`}
                      >
                        {rubricInfo.label}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
