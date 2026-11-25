'use client';

import React from 'react';
import {
  Bot,
  Lock,
  MicVocal,
  RefreshCw,
  RotateCcw,
  Save,
  SlidersHorizontal,
  Timer,
  ToggleRight,
  Zap,
} from 'lucide-react';
import { ACADEMIC_FROZEN_PARAMETERS } from './mockAiPolicyData';
import { AdaptivePolicyConfig } from './types';

interface AdaptivePolicyFormProps {
  config: AdaptivePolicyConfig;
  isSaving: boolean;
  onUpdateField: <K extends keyof AdaptivePolicyConfig>(
    key: K,
    value: AdaptivePolicyConfig[K]
  ) => void;
  onResetDefault: () => void;
  onCancelChanges: () => void;
  onSavePolicy: () => void;
}

export default function AdaptivePolicyForm({
  config,
  isSaving,
  onUpdateField,
  onResetDefault,
  onCancelChanges,
  onSavePolicy,
}: AdaptivePolicyFormProps) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSavePolicy();
      }}
      className="flex flex-col gap-5"
    >
      <div>
        <h2 className="text-lg font-semibold text-[#141b2c]">
          Cấu hình chính sách phỏng vấn thích ứng
        </h2>
        <p className="text-xs text-[#5c4039]">
          Áp dụng cho các phiên phỏng vấn mới được khởi tạo sau khi lưu.
        </p>
      </div>

      {/* Main 12-Col Form Grid */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* LEFT COLUMN (Span 7) */}
        <div className="flex flex-col gap-5 lg:col-span-7">
          {/* GROUP 1: Interview Policy */}
          <div className="flex flex-col gap-3.5 rounded-xl bg-white p-5 shadow-xs">
            <div className="flex items-center gap-2 border-b border-[#e0e8ff] pb-2.5">
              <SlidersHorizontal className="size-4.5 text-[#ad2c00]" />
              <h3 className="text-sm font-semibold text-[#141b2c]">
                Thuật toán khảo sát & Thích ứng
              </h3>
            </div>

            {/* Item 1.1: core_importance */}
            <div className="flex flex-col gap-1.5 rounded-lg bg-[#f1f3ff]/55 p-3">
              <div className="flex items-center justify-between gap-2">
                <label
                  htmlFor="core_importance"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Trọng số ưu tiên kỹ năng cốt lõi
                </label>
                <span className="rounded bg-white px-2 py-0.5 font-mono text-xs font-bold text-[#ad2c00] shadow-2xs">
                  {config.coreImportance.toFixed(2)} / 1.0
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3">
                <span className="font-mono text-[11px] text-[#5c4039]">0.1</span>
                <input
                  id="core_importance"
                  type="range"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={config.coreImportance}
                  onChange={(e) => onUpdateField('coreImportance', parseFloat(e.target.value))}
                  className="h-1.5 w-full cursor-pointer rounded-lg bg-[#e0e8ff] accent-[#ad2c00]"
                />
                <span className="font-mono text-[11px] text-[#5c4039]">1.0</span>
              </div>
            </div>

            {/* Item 1.2: reserve_followup_fraction */}
            <div className="flex flex-col gap-1.5 rounded-lg bg-[#f1f3ff]/55 p-3">
              <div className="flex items-center justify-between gap-2">
                <label
                  htmlFor="reserve_followup"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Tỷ lệ câu hỏi đào sâu dự phòng
                </label>
                <span className="rounded bg-white px-2 py-0.5 font-mono text-xs font-bold text-[#186392] shadow-2xs">
                  {config.reserveFollowupFraction.toFixed(2)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3">
                <span className="font-mono text-[11px] text-[#5c4039]">0.05</span>
                <input
                  id="reserve_followup"
                  type="range"
                  min={0.05}
                  max={0.6}
                  step={0.05}
                  value={config.reserveFollowupFraction}
                  onChange={(e) =>
                    onUpdateField('reserveFollowupFraction', parseFloat(e.target.value))
                  }
                  className="h-1.5 w-full cursor-pointer rounded-lg bg-[#e0e8ff] accent-[#186392]"
                />
                <span className="font-mono text-[11px] text-[#5c4039]">0.60</span>
              </div>
            </div>

            {/* Item 1.3 & 1.4 side by side */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
                <label
                  htmlFor="fallback_depth"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Số lần hạ độ sâu câu hỏi
                </label>
                <div className="flex shrink-0 items-center rounded-lg bg-white px-2 py-1 shadow-2xs">
                  <input
                    id="fallback_depth"
                    type="number"
                    min={1}
                    max={4}
                    value={config.fallbackDepth}
                    onChange={(e) =>
                      onUpdateField(
                        'fallbackDepth',
                        Math.min(4, Math.max(1, Number(e.target.value)))
                      )
                    }
                    className="w-10 bg-transparent text-center font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                  />
                  <span className="text-[11px] text-[#5c4039]">lần</span>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
                <label
                  htmlFor="min_failure_contexts"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Số lần sai chuyển chủ đề
                </label>
                <div className="flex shrink-0 items-center rounded-lg bg-white px-2 py-1 shadow-2xs">
                  <input
                    id="min_failure_contexts"
                    type="number"
                    min={1}
                    max={5}
                    value={config.minFailureContexts}
                    onChange={(e) =>
                      onUpdateField(
                        'minFailureContexts',
                        Math.min(5, Math.max(1, Number(e.target.value)))
                      )
                    }
                    className="w-10 bg-transparent text-center font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                  />
                  <span className="text-[11px] text-[#5c4039]">lần</span>
                </div>
              </div>
            </div>

            {/* Item 1.5: allow_extension_probes */}
            <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
              <span className="text-xs font-medium text-[#141b2c]">
                Cho phép mở rộng câu hỏi tình huống thực tế (Case Study)
              </span>

              <button
                type="button"
                role="switch"
                aria-checked={config.allowExtensionProbes}
                onClick={() =>
                  onUpdateField('allowExtensionProbes', !config.allowExtensionProbes)
                }
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 ${
                  config.allowExtensionProbes ? 'bg-[#006b2f]' : 'bg-[#dbe2f9]'
                }`}
              >
                <span
                  className={`inline-block size-5 transform rounded-full bg-white shadow-2xs transition-transform duration-300 ${
                    config.allowExtensionProbes ? 'translate-x-5.5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* GROUP 2: Session Limits */}
          <div className="flex flex-col gap-3.5 rounded-xl bg-white p-5 shadow-xs">
            <div className="flex items-center gap-2 border-b border-[#e0e8ff] pb-2.5">
              <Timer className="size-4.5 text-[#186392]" />
              <h3 className="text-sm font-semibold text-[#141b2c]">
                Giới hạn phiên phỏng vấn
              </h3>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="flex flex-col justify-between gap-2 rounded-lg bg-[#f1f3ff]/55 p-3">
                <label
                  htmlFor="max_questions"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Tổng câu hỏi tối đa
                </label>
                <div className="flex items-center rounded-lg bg-white px-2.5 py-1.5 shadow-2xs">
                  <input
                    id="max_questions"
                    type="number"
                    min={3}
                    max={25}
                    value={config.maxQuestions}
                    onChange={(e) => onUpdateField('maxQuestions', Number(e.target.value))}
                    className="w-full bg-transparent font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                  />
                  <span className="shrink-0 text-[11px] text-[#5c4039]">câu</span>
                </div>
              </div>

              <div className="flex flex-col justify-between gap-2 rounded-lg bg-[#f1f3ff]/55 p-3">
                <label
                  htmlFor="duration_seconds"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Thời lượng tối đa
                </label>
                <div className="flex items-center rounded-lg bg-white px-2.5 py-1.5 shadow-2xs">
                  <input
                    id="duration_seconds"
                    type="number"
                    min={600}
                    max={7200}
                    step={60}
                    value={config.durationSeconds}
                    onChange={(e) => onUpdateField('durationSeconds', Number(e.target.value))}
                    className="w-full bg-transparent font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                  />
                  <span className="shrink-0 text-[11px] text-[#5c4039]">
                    {Math.round(config.durationSeconds / 60)}p
                  </span>
                </div>
              </div>

              <div className="flex flex-col justify-between gap-2 rounded-lg bg-[#f1f3ff]/55 p-3">
                <label
                  htmlFor="max_obj_questions"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Tối đa mỗi kỹ năng
                </label>
                <div className="flex items-center rounded-lg bg-white px-2.5 py-1.5 shadow-2xs">
                  <input
                    id="max_obj_questions"
                    type="number"
                    min={1}
                    max={5}
                    value={config.maxQuestionsPerObjective}
                    onChange={(e) =>
                      onUpdateField('maxQuestionsPerObjective', Number(e.target.value))
                    }
                    className="w-full bg-transparent font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                  />
                  <span className="shrink-0 text-[11px] text-[#5c4039]">câu</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN (Span 5) */}
        <div className="flex flex-col gap-5 lg:col-span-5">
          {/* GROUP 3: Feature Flags */}
          <div className="flex flex-col gap-3 rounded-xl bg-white p-5 shadow-xs">
            <div className="flex items-center gap-2 border-b border-[#e0e8ff] pb-2.5">
              <ToggleRight className="size-4.5 text-[#ad2c00]" />
              <h3 className="text-sm font-semibold text-[#141b2c]">Tính năng hệ thống</h3>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
              <div className="flex items-center gap-2.5 pr-2">
                <MicVocal className="size-4 shrink-0 text-[#006b2f]" />
                <span className="text-xs font-medium text-[#141b2c]">
                  Phỏng vấn giọng nói (Voice STT/TTS)
                </span>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={config.voiceEnabled}
                onClick={() => onUpdateField('voiceEnabled', !config.voiceEnabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 ${
                  config.voiceEnabled ? 'bg-[#006b2f]' : 'bg-[#dbe2f9]'
                }`}
              >
                <span
                  className={`inline-block size-5 transform rounded-full bg-white shadow-2xs transition-transform duration-300 ${
                    config.voiceEnabled ? 'translate-x-5.5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
              <div className="flex items-center gap-2.5 pr-2">
                <Bot className="size-4 shrink-0 text-[#186392]" />
                <span className="text-xs font-medium text-[#141b2c]">
                  Avatar 3D Simli (WebRTC)
                </span>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={config.simliAvatarEnabled}
                onClick={() => onUpdateField('simliAvatarEnabled', !config.simliAvatarEnabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 ${
                  config.simliAvatarEnabled ? 'bg-[#006b2f]' : 'bg-[#dbe2f9]'
                }`}
              >
                <span
                  className={`inline-block size-5 transform rounded-full bg-white shadow-2xs transition-transform duration-300 ${
                    config.simliAvatarEnabled ? 'translate-x-5.5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-[#f1f3ff]/55 p-3">
              <div className="flex items-center gap-2.5 pr-2">
                <Zap className="size-4 shrink-0 text-[#ad2c00]" />
                <label
                  htmlFor="daily_quota"
                  className="text-xs font-medium text-[#141b2c]"
                >
                  Hạn mức phỏng vấn mỗi ngày
                </label>
              </div>

              <div className="flex shrink-0 items-center rounded-lg bg-white px-2.5 py-1 shadow-2xs">
                <input
                  id="daily_quota"
                  type="number"
                  min={1}
                  max={20}
                  value={config.dailyQuota}
                  onChange={(e) => onUpdateField('dailyQuota', Number(e.target.value))}
                  className="w-10 bg-transparent text-center font-mono text-xs font-semibold text-[#141b2c] focus:outline-none"
                />
                <span className="text-[11px] text-[#5c4039]">phiên</span>
              </div>
            </div>
          </div>

          {/* GROUP 4: Read-only Academic Parameters */}
          <div className="flex flex-col gap-3 rounded-xl border border-[#e5beb4]/40 bg-[#f1f3ff] p-5 shadow-xs">
            <div className="flex items-center justify-between border-b border-[#e5beb4]/50 pb-2.5">
              <div className="flex items-center gap-2">
                <Lock className="size-4 text-[#907067]" />
                <h3 className="text-sm font-semibold text-[#141b2c]">
                  Tham số mô hình Skill Gap (Chỉ xem)
                </h3>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              {ACADEMIC_FROZEN_PARAMETERS.map((param) => (
                <div
                  key={param.key}
                  className="flex items-center justify-between rounded-lg bg-white px-3 py-2.5 shadow-2xs"
                >
                  <div className="pr-2">
                    <div className="font-mono text-xs font-semibold text-[#141b2c]">
                      {param.key}
                    </div>
                    <div className="text-[11px] text-[#5c4039]">{param.description}</div>
                  </div>
                  <span className="shrink-0 rounded bg-[#e0e8ff] px-2.5 py-1 font-mono text-xs font-bold text-[#141b2c]">
                    {param.valueLabel}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* FOOTER ACTION BAR */}
      <div className="sticky bottom-4 z-30 flex flex-col items-center justify-between gap-3 rounded-xl bg-white/95 p-3.5 shadow-lg backdrop-blur-md sm:flex-row">
        <button
          type="button"
          onClick={onResetDefault}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-[#f1f3ff] px-3.5 py-2 text-xs font-medium text-[#141b2c] transition-colors hover:bg-[#e0e8ff] sm:w-auto cursor-pointer"
        >
          <RotateCcw className="size-3.5" />
          <span>Khôi phục mặc định</span>
        </button>

        <div className="flex w-full items-center justify-end gap-2.5 sm:w-auto">
          <button
            type="button"
            onClick={onCancelChanges}
            className="rounded-lg px-3.5 py-2 text-xs font-medium text-[#5c4039] transition-colors hover:text-[#141b2c] cursor-pointer"
          >
            Hủy thay đổi
          </button>

          <button
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-1.5 rounded-lg bg-[#ad2c00] px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-[#d83900] disabled:opacity-60 cursor-pointer"
          >
            {isSaving ? (
              <>
                <RefreshCw className="size-3.5 animate-spin" />
                <span>Đang lưu...</span>
              </>
            ) : (
              <>
                <Save className="size-3.5" />
                <span>Lưu chính sách</span>
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
