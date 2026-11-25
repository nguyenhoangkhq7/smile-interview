'use client';

import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { InspectionPipelineStage } from './types';

interface InspectionPipelineStepperProps {
  stages: InspectionPipelineStage[];
  activeStageId: number;
  onSelectStage: (stageId: number) => void;
}

export default function InspectionPipelineStepper({
  stages,
  activeStageId,
  onSelectStage,
}: InspectionPipelineStepperProps) {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-5">
      {stages.map((stage, index) => {
        const isActive = activeStageId === stage.id;

        return (
          <button
            key={stage.id}
            type="button"
            onClick={() => onSelectStage(stage.id)}
            style={{ animationDelay: `${index * 60}ms`, animationFillMode: 'both' }}
            className={`animate-fade-up flex flex-col justify-between rounded-xl p-3 text-left transition-all cursor-pointer ${
              isActive
                ? 'bg-[#d83900] text-white shadow-sm'
                : 'bg-white text-[#141b2c] shadow-xs hover:bg-[#f1f3ff]'
            }`}
          >
            <div className="flex w-full items-center justify-between gap-1">
              <span
                className={`font-mono text-xs font-semibold ${
                  isActive ? 'text-white' : 'text-[#186392]'
                }`}
              >
                {stage.stepCode}
              </span>
              <CheckCircle2
                className={`size-4 shrink-0 ${isActive ? 'text-white' : 'text-[#006b2f]'}`}
              />
            </div>

            <p
              className={`mt-1 line-clamp-1 text-xs ${
                isActive ? 'text-white/90' : 'text-[#5c4039]'
              }`}
            >
              {stage.description}
            </p>
          </button>
        );
      })}
    </div>
  );
}
