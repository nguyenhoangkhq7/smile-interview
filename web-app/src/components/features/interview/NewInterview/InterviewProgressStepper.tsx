'use client';

import React from 'react';
import { UploadCloud, Sparkles, Mic, Check } from 'lucide-react';

export type InterviewFlowStep = 'upload' | 'assessment' | 'interview';

interface InterviewProgressStepperProps {
  currentStep: InterviewFlowStep;
  uploading?: boolean;
  analyzing?: boolean;
  generating?: boolean;
  hasAssessment?: boolean;
  onSelectStep?: (step: InterviewFlowStep) => void;
}

export function InterviewProgressStepper({
  currentStep,
  uploading = false,
  analyzing = false,
  generating = false,
  hasAssessment = false,
  onSelectStep,
}: InterviewProgressStepperProps) {
  const steps = [
    {
      id: 'upload' as InterviewFlowStep,
      number: 1,
      title: 'Tải lên CV & JD',
      subtitle: uploading ? 'Đang tải lên...' : 'Chọn hoặc upload tài liệu',
      icon: UploadCloud,
      isCompleted: currentStep !== 'upload' || hasAssessment,
      isCurrent: currentStep === 'upload',
    },
    {
      id: 'assessment' as InterviewFlowStep,
      number: 2,
      title: 'Đánh giá tương thích',
      subtitle: analyzing
        ? 'AI đang phân tích...'
        : hasAssessment
        ? 'Đã có kết quả'
        : 'Đối chiếu năng lực & kỹ năng',
      icon: Sparkles,
      isCompleted: currentStep === 'interview',
      isCurrent: currentStep === 'assessment',
    },
    {
      id: 'interview' as InterviewFlowStep,
      number: 3,
      title: 'Phòng phỏng vấn AI',
      subtitle: generating ? 'Đang tạo câu hỏi...' : 'Phỏng vấn 1-1 với AI',
      icon: Mic,
      isCompleted: false,
      isCurrent: currentStep === 'interview',
    },
  ];

  // Calculate progress percentage for connector bar
  const progressPercent =
    currentStep === 'upload' ? 0 : currentStep === 'assessment' ? 50 : 100;

  return (
    <div className="w-full mb-8">
      {/* Stepper Card Container */}
      <div className="bg-card/70 backdrop-blur-md border border-border/80 rounded-2xl p-4 sm:p-6 shadow-sm">
        <div className="relative">
          {/* Background track line */}
          <div className="absolute top-6 left-12 right-12 h-1 bg-muted/70 rounded-full z-0 hidden sm:block">
            {/* Animated active progress fill */}
            <div
              className="h-full bg-gradient-to-r from-brand-orange via-amber-500 to-emerald-500 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Step Nodes */}
          <div className="relative z-10 grid grid-cols-3 gap-2 sm:gap-6">
            {steps.map((step) => {
              const Icon = step.icon;
              const isClickable =
                onSelectStep &&
                ((step.id === 'upload' && currentStep === 'assessment') ||
                  (step.id === 'assessment' && hasAssessment && currentStep === 'interview'));

              return (
                <div
                  key={step.id}
                  onClick={() => {
                    if (isClickable) onSelectStep(step.id);
                  }}
                  className={`flex flex-col items-center text-center group transition-all duration-300 ${
                    isClickable ? 'cursor-pointer' : 'cursor-default'
                  }`}
                >
                  {/* Icon Circle */}
                  <div
                    className={`relative flex size-12 sm:size-13 items-center justify-center rounded-2xl border-2 transition-all duration-300 shadow-md ${
                      step.isCurrent
                        ? 'border-brand-orange bg-brand-orange text-white ring-4 ring-brand-orange/20 scale-105 shadow-brand-orange/25'
                        : step.isCompleted
                        ? 'border-emerald-500 bg-emerald-500 text-white shadow-emerald-500/20'
                        : 'border-border bg-background text-muted-foreground'
                    } ${isClickable ? 'group-hover:ring-2 group-hover:ring-brand-orange/30 group-hover:scale-105' : ''}`}
                  >
                    {step.isCompleted && !step.isCurrent ? (
                      <Check size={20} className="stroke-[2.5]" />
                    ) : (
                      <Icon
                        size={20}
                        className={`${step.isCurrent && (uploading || analyzing || generating) ? 'animate-pulse' : ''}`}
                      />
                    )}

                    {/* Step number badge */}
                    <span
                      className={`absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full text-[10px] font-bold border ${
                        step.isCurrent
                          ? 'bg-white text-brand-orange border-brand-orange shadow-sm'
                          : step.isCompleted
                          ? 'bg-white text-emerald-600 border-emerald-500'
                          : 'bg-muted text-muted-foreground border-border'
                      }`}
                    >
                      {step.number}
                    </span>
                  </div>

                  {/* Text Labels */}
                  <div className="mt-3 space-y-0.5">
                    <p
                      className={`text-xs sm:text-sm font-bold tracking-tight transition-colors ${
                        step.isCurrent
                          ? 'text-brand-orange'
                          : step.isCompleted
                          ? 'text-foreground'
                          : 'text-muted-foreground'
                      }`}
                    >
                      {step.title}
                    </p>
                    <p className="text-[11px] text-muted-foreground hidden sm:block max-w-[140px] truncate">
                      {step.subtitle}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
