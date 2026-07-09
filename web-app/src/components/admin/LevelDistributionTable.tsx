'use client';

import { useState } from 'react';
import { adminService, LevelDistributionRuleDto, UpdateLevelRulePayload } from '@/services/adminService';
import { toast } from './Toast';

interface Props {
  rules: LevelDistributionRuleDto[];
  onRefresh: () => void;
}

const LEVEL_LABELS: Record<string, string> = {
  INTERN: 'Thực tập sinh',
  FRESHER: 'Mới ra trường',
  JUNIOR: 'Junior (1-2 năm)',
  MID: 'Mid-level (2-5 năm)',
  SENIOR: 'Senior (5+ năm)',
  LEAD: 'Tech Lead',
};

interface EditState {
  level: string;
  form: UpdateLevelRulePayload;
}

export default function LevelDistributionTable({ rules, onRefresh }: Props) {
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

  const startEdit = (rule: LevelDistributionRuleDto) => {
    setEditing({
      level: rule.level,
      form: {
        behavioral_pct: rule.behavioral_pct,
        technical_pct: rule.technical_pct,
        coding_pct: rule.coding_pct,
        system_design_pct: rule.system_design_pct,
      },
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await adminService.updateLevelDistributionRule(editing.level, editing.form);
      toast.success(`Đã cập nhật phân phối cho ${editing.level}!`);
      setEditing(null);
      onRefresh();
    } catch {
      toast.error('Có lỗi xảy ra. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  };

  const PctBar = ({ value, color }: { value: number; color: string }) => (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-400 w-8 text-right">{value}%</span>
    </div>
  );

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Phân phối câu hỏi theo cấp bậc</h3>
      {rules.length === 0 && (
        <div className="rounded-xl border border-slate-800 px-6 py-8 text-center text-slate-500">Chưa có dữ liệu. Hãy chạy DatabaseSeeder.</div>
      )}
      {rules.map((rule) => {
        const isEditing = editing?.level === rule.level;
        const f = isEditing ? editing!.form : null;

        return (
          <div
            key={rule.level}
            className={`rounded-xl border p-5 transition-all ${isEditing ? 'border-orange-600/50 bg-orange-950/10' : 'border-slate-800 bg-slate-800/20 hover:bg-slate-800/40'}`}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h4 className="text-sm font-bold text-white">{rule.level}</h4>
                <p className="text-xs text-slate-500 mt-0.5">{LEVEL_LABELS[rule.level] ?? rule.level}</p>
              </div>
              {!isEditing ? (
                <button
                  onClick={() => startEdit(rule)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 rounded-lg transition-colors"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                  Chỉnh sửa
                </button>
              ) : (
                <div className="flex gap-2">
                  <button onClick={() => setEditing(null)} className="px-3 py-1.5 text-xs text-slate-400 border border-slate-700 rounded-lg hover:border-slate-500 transition-colors">Hủy</button>
                  <button onClick={handleSave} disabled={saving} className="px-3 py-1.5 text-xs font-medium bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white rounded-lg transition-colors">
                    {saving ? 'Lưu...' : 'Lưu'}
                  </button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { key: 'behavioral_pct' as const, label: 'Behavioral', color: 'bg-purple-500' },
                { key: 'technical_pct' as const, label: 'Technical', color: 'bg-blue-500' },
                { key: 'coding_pct' as const, label: 'Coding', color: 'bg-emerald-500' },
                { key: 'system_design_pct' as const, label: 'System Design', color: 'bg-orange-500' },
              ].map(({ key, label, color }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-slate-400">{label}</span>
                    {isEditing && (
                      <input
                        type="number" min={0} max={100} step={1}
                        className="w-16 px-2 py-0.5 bg-slate-800 border border-slate-600 rounded text-white text-xs tabular-nums text-right focus:outline-none focus:border-orange-500"
                        value={f![key]}
                        onChange={(e) => setEditing({ ...editing!, form: { ...f!, [key]: Number(e.target.value) } })}
                      />
                    )}
                  </div>
                  <PctBar value={isEditing ? f![key] : rule[key]} color={color} />
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
