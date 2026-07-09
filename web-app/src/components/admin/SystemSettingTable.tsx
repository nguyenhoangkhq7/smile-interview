'use client';

import { useState } from 'react';
import { adminService, SystemSettingDto, UpdateSystemSettingPayload } from '@/services/adminService';
import { toast } from './Toast';

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
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Hệ số hệ thống</h3>
      {settings.length === 0 && (
        <div className="rounded-xl border border-slate-800 px-6 py-8 text-center text-slate-500">Chưa có cài đặt nào. Hãy chạy DatabaseSeeder.</div>
      )}
      {settings.map((s) => {
        const meta = SETTING_META[s.setting_key];
        const isEditing = editing?.key === s.setting_key;

        return (
          <div
            key={s.setting_key}
            className={`rounded-xl border p-5 transition-all ${isEditing ? 'border-orange-600/50 bg-orange-950/10' : 'border-slate-800 bg-slate-800/20'}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-sm font-mono font-bold text-orange-400">{s.setting_key}</code>
                  {meta?.unit && (
                    <span className="text-xs text-slate-600 bg-slate-800 px-2 py-0.5 rounded-full">{meta.unit}</span>
                  )}
                </div>
                {meta && <p className="text-xs text-slate-500 leading-relaxed">{meta.description}</p>}
              </div>

              <div className="flex items-center gap-3 flex-shrink-0">
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      className="w-28 px-3 py-1.5 bg-slate-800 border border-orange-600/50 rounded-lg text-white text-sm tabular-nums font-mono focus:outline-none focus:border-orange-500"
                      value={editing.value}
                      onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(null); }}
                      autoFocus
                    />
                    <button onClick={() => setEditing(null)} className="px-3 py-1.5 text-xs text-slate-400 border border-slate-700 rounded-lg hover:border-slate-500 transition-colors">Hủy</button>
                    <button onClick={handleSave} disabled={saving} className="px-3 py-1.5 text-xs font-medium bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg transition-colors">
                      {saving ? '...' : 'Lưu'}
                    </button>
                  </>
                ) : (
                  <>
                    <span className="text-xl font-bold tabular-nums font-mono text-white">{s.setting_value}</span>
                    <button
                      onClick={() => setEditing({ key: s.setting_key, value: s.setting_value })}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                      title="Chỉnh sửa"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <div className="mt-4 p-4 rounded-xl bg-slate-800/30 border border-slate-800">
        <div className="flex items-start gap-3">
          <svg className="text-blue-400 flex-shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
          </svg>
          <p className="text-xs text-slate-500 leading-relaxed">
            Thay đổi hệ số có hiệu lực ngay lập tức với phiên đánh giá tiếp theo. Không cần khởi động lại service.
          </p>
        </div>
      </div>
    </div>
  );
}
