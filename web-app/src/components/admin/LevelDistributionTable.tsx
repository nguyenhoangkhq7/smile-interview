'use client';

import { useState } from 'react';
import { adminService, LevelDistributionRuleDto, UpdateLevelRulePayload } from '@/services/adminService';
import { toast } from './Toast';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

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
    <div className="flex items-center gap-3">
      <div className="flex-1 overflow-hidden rounded-full bg-slate-700/90">
        <div className={`h-2.5 rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-12 text-right text-sm tabular-nums text-slate-300">{value}%</span>
    </div>
  );

  return (
    <RuleDashboardSection
      title="Phân phối câu hỏi theo cấp bậc"
      count={rules.length}
      countLabel="mức"
      description="Điều chỉnh tỷ lệ behavioral, technical, coding và system design cho từng seniority."
    >
      {rules.length === 0 && (
        <div className="px-6 py-10 text-center text-slate-500">Chưa có dữ liệu. Hãy chạy DatabaseSeeder.</div>
      )}
      <div className="space-y-5 border-t border-white/6 bg-slate-950/35 px-0 py-0">
        {rules.map((rule) => {
        const isEditing = editing?.level === rule.level;
        const f = isEditing ? editing!.form : null;

        return (
          <div
            key={rule.level}
            className={`rounded-2xl border px-6 py-6 transition-all ${isEditing ? 'border-amber-400/40 bg-amber-400/8' : 'border-slate-700/70 bg-white/[0.025] hover:bg-white/[0.04]'}`}
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h4 className="text-sm font-semibold tracking-wide text-white">{rule.level}</h4>
                <p className="mt-1 text-xs text-slate-400">{LEVEL_LABELS[rule.level] ?? rule.level}</p>
              </div>
              {!isEditing ? (
                <ActionIconButton
                  label="Chỉnh sửa phân phối"
                  variant="accent"
                  onClick={() => startEdit(rule)}
                  icon={(
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                  )}
                />
              ) : (
                <div className="flex gap-2">
                  <button onClick={() => setEditing(null)} className="rounded-lg border border-slate-700/80 bg-white/[0.02] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white">Hủy</button>
                  <button onClick={handleSave} disabled={saving} className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-1.5 text-xs font-medium text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-400/15 hover:text-white disabled:opacity-50">
                    {saving ? 'Lưu...' : 'Lưu'}
                  </button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              {[
                { key: 'behavioral_pct' as const, label: 'Behavioral', color: 'bg-purple-500' },
                { key: 'technical_pct' as const, label: 'Technical', color: 'bg-blue-500' },
                { key: 'coding_pct' as const, label: 'Coding', color: 'bg-emerald-500' },
                { key: 'system_design_pct' as const, label: 'System Design', color: 'bg-orange-500' },
              ].map(({ key, label, color }) => (
                <div key={key}>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-300">{label}</span>
                    {isEditing && (
                      <input
                        type="number" min={0} max={100} step={1}
                        className="w-16 rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-right text-xs tabular-nums text-white focus:border-amber-400/50 focus:outline-none"
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
    </RuleDashboardSection>
  );
}
