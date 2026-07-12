'use client';

import { useState } from 'react';
import { adminService, SystemSettingDto, UpdateSystemSettingPayload } from '@/services/adminService';
import { toast } from './Toast';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

interface Props {
  settings: SystemSettingDto[];
  onRefresh: () => void;
}

const SETTING_META: Record<string, { label: string; description: string; unit?: string }> = {
  MATCH_SCORE_PIVOT: {
    label: 'Điểm Pivot Matching',
    description: 'Điểm tham chiếu để tính hệ số điều chỉnh f trong DifficultyDistributor. Score > Pivot → tăng câu hỏi khó.',
    unit: 'điểm (0-100)',
  },
  STATUS_WEAK_COEFF: {
    label: 'Hệ số "Weak"',
    description: 'Điểm được cộng khi tiêu chí có trạng thái "weak" trong ScoringService. "matched" = 1.0, "missing" = 0.0.',
    unit: 'hệ số (0.0 - 1.0)',
  },
};

interface EditState {
  key: string;
  value: string;
}

export default function SystemSettingTable({ settings, onRefresh }: Props) {
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await adminService.updateSystemSetting(editing.key, { setting_value: editing.value });
      toast.success(`Đã cập nhật ${editing.key}!`);
      setEditing(null);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <RuleDashboardSection
      title="Hệ số hệ thống"
      count={settings.length}
      countLabel="tham số"
      description="Các cài đặt này có hiệu lực ngay lập tức cho lần xử lý tiếp theo."
    >
      {settings.length === 0 && (
        <div className="px-6 py-10 text-center text-slate-500">Chưa có cài đặt nào. Hãy chạy DatabaseSeeder.</div>
      )}
      <div className="space-y-5 border-t border-white/6 bg-slate-950/35 px-0 py-0">
        {settings.map((s) => {
          const meta = SETTING_META[s.setting_key];
          const isEditing = editing?.key === s.setting_key;

          return (
            <div
              key={s.setting_key}
              className={`rounded-2xl border px-6 py-6 transition-all ${isEditing ? 'border-amber-400/40 bg-amber-400/8' : 'border-slate-700/70 bg-white/[0.025] hover:bg-white/[0.04]'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-white">{meta?.label ?? s.setting_key}</span>
                    <code className="rounded-md border border-orange-400/15 bg-orange-400/10 px-2 py-0.5 text-xs font-mono font-semibold text-orange-200">{s.setting_key}</code>
                    {meta?.unit && (
                      <span className="rounded-full border border-slate-700/80 bg-white/[0.04] px-2 py-0.5 text-xs text-slate-400">{meta.unit}</span>
                    )}
                  </div>
                  {meta && <p className="text-xs leading-relaxed text-slate-400">{meta.description}</p>}
                </div>

                <div className="flex shrink-0 items-center gap-3">
                  {isEditing ? (
                    <>
                      <input
                        type="text"
                        className="w-28 rounded-lg border border-amber-400/35 bg-slate-900 px-3 py-2 text-sm font-mono tabular-nums text-white focus:border-amber-300 focus:outline-none"
                        value={editing.value}
                        onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(null); }}
                        autoFocus
                      />
                      <button onClick={() => setEditing(null)} className="rounded-lg border border-slate-700/80 bg-white/[0.02] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white">Hủy</button>
                      <button onClick={handleSave} disabled={saving} className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-1.5 text-xs font-medium text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-400/15 hover:text-white disabled:opacity-50">
                        {saving ? '...' : 'Lưu'}
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="text-xl font-semibold tabular-nums font-mono text-white">{s.setting_value}</span>
                      <ActionIconButton
                        label="Chỉnh sửa cài đặt"
                        onClick={() => setEditing({ key: s.setting_key, value: s.setting_value })}
                        icon={(
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                        )}
                      />
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}

      </div>
      <div className="mt-5 rounded-2xl border border-slate-700/70 bg-white/[0.025] p-4">
        <div className="flex items-start gap-3">
          <svg className="text-blue-400 flex-shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
          </svg>
          <p className="text-xs leading-relaxed text-slate-400">
            Thay đổi hệ số có hiệu lực ngay lập tức với phiên đánh giá tiếp theo. Không cần khởi động lại service.
          </p>
        </div>
      </div>
    </RuleDashboardSection>
  );
}
