'use client';

import React, { useRef, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import AdaptivePolicyForm from './AdaptivePolicyForm';
import AiPolicyHeader from './AiPolicyHeader';
import {
  DEFAULT_ADAPTIVE_POLICY_CONFIG,
  INITIAL_SERVICE_HEALTH_CARDS,
} from './mockAiPolicyData';
import ServiceHealthGrid from './ServiceHealthGrid';
import { AdaptivePolicyConfig, ServiceHealthCardItem } from './types';

export default function AiPolicyView() {
  const [services, setServices] = useState<ServiceHealthCardItem[]>(
    INITIAL_SERVICE_HEALTH_CARDS
  );
  const [config, setConfig] = useState<AdaptivePolicyConfig>(
    DEFAULT_ADAPTIVE_POLICY_CONFIG
  );
  const [savedConfig, setSavedConfig] = useState<AdaptivePolicyConfig>(
    DEFAULT_ADAPTIVE_POLICY_CONFIG
  );

  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<{ title: string; message: string } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (title: string, message: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ title, message });
    toastTimerRef.current = setTimeout(() => {
      setToast(null);
    }, 3200);
  };

  const handleTriggerHealthCheck = () => {
    setIsCheckingHealth(true);
    setTimeout(() => {
      setServices((prev) =>
        prev.map((svc) => {
          const jitter = Math.floor(Math.random() * 11) - 5;
          const nextPct = Math.min(92, Math.max(8, svc.latencyBarPct + jitter));
          return {
            ...svc,
            latencyBarPct: nextPct,
            lastCheckedText: 'Vừa xong',
          };
        })
      );
      setIsCheckingHealth(false);
      showToast(
        'Đã làm mới Telemetry!',
        'Toàn bộ 8/8 dịch vụ hạ tầng AI và lưu trữ đều hoạt động ổn định.'
      );
    }, 650);
  };

  const handleUpdateField = <K extends keyof AdaptivePolicyConfig>(
    key: K,
    value: AdaptivePolicyConfig[K]
  ) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSavePolicy = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      setSavedConfig(config);
      showToast(
        'Chính sách đã cập nhật!',
        'Đã tạo Snapshot phiên bản mới và phân phối tới các worker pods.'
      );
    }, 750);
  };

  const handleResetDefault = () => {
    setConfig(DEFAULT_ADAPTIVE_POLICY_CONFIG);
    setSavedConfig(DEFAULT_ADAPTIVE_POLICY_CONFIG);
    showToast(
      'Đã khôi phục mặc định',
      'Các tham số đã được hoàn về thiết lập gốc của hệ thống.'
    );
  };

  const handleCancelChanges = () => {
    setConfig(savedConfig);
    showToast('Đã hủy thay đổi', 'Các thay đổi chưa lưu trên biểu mẫu đã được hoàn tác.');
  };

  return (
    <div className="flex w-full flex-col gap-8 pb-8">
      {/* 1. Page Header & Policy Immutability Alert Banner */}
      <AiPolicyHeader
        isCheckingHealth={isCheckingHealth}
        onTriggerHealthCheck={handleTriggerHealthCheck}
      />

      {/* 2. Section A: Health Monitor Grid (8 Service Cards) */}
      <ServiceHealthGrid
        services={services}
        isCheckingHealth={isCheckingHealth}
      />

      {/* 3. Section B: Form Controls for Adaptive Policies */}
      <AdaptivePolicyForm
        config={config}
        isSaving={isSaving}
        onUpdateField={handleUpdateField}
        onResetDefault={handleResetDefault}
        onCancelChanges={handleCancelChanges}
        onSavePolicy={handleSavePolicy}
      />

      {/* Toast Notification */}
      <div
        aria-live="polite"
        className={`pointer-events-none fixed bottom-24 right-8 z-50 transition-all duration-300 ${
          toast ? 'translate-y-0 opacity-100' : 'translate-y-20 opacity-0'
        }`}
      >
        <div className="flex items-center gap-3 rounded-xl bg-[#293041] px-4 py-3 text-[#edf0ff] shadow-xl">
          <CheckCircle2 className="size-5 shrink-0 text-[#95f8a7]" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white">
              {toast?.title || 'Đã lưu thành công'}
            </span>
            <span className="text-xs text-[#edf0ff]/80">
              {toast?.message || 'Chính sách phỏng vấn mới đã được nạp vào Redis Cluster.'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
