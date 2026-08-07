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

const LEVEL_ORDER: Record<string, number> = {
  INTERN: 1,
  FRESHER: 2,
  JUNIOR: 3,
  MID: 4,
  SENIOR: 5,
  LEAD: 6,
};

type SortOption = 'level_asc' | 'level_desc' | 'questions_asc' | 'questions_desc';

interface EditState {
  level: string;
  form: UpdateLevelRulePayload;
}

export default function LevelDistributionTable({ rules, onRefresh }: Props) {
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>('level_asc');

  const sortedRules = [...rules].sort((a, b) => {
    const levelOrderA = LEVEL_ORDER[a.level.toUpperCase()] || 99;
    const levelOrderB = LEVEL_ORDER[b.level.toUpperCase()] || 99;
    const qA = a.total_questions || 5;
    const qB = b.total_questions || 5;

    if (sortBy === 'level_asc') {
      return levelOrderA - levelOrderB;
    } else if (sortBy === 'level_desc') {
      return levelOrderB - levelOrderA;
    } else if (sortBy === 'questions_asc') {
      if (qA !== qB) return qA - qB;
      return levelOrderA - levelOrderB;
    } else if (sortBy === 'questions_desc') {
      if (qA !== qB) return qB - qA;
      return levelOrderA - levelOrderB;
    }
    return 0;
  });

  const startEdit = (rule: LevelDistributionRuleDto) => {
    setEditing({
      level: rule.level,
      form: {
        behavioral_pct: rule.behavioral_pct,
        technical_pct: rule.technical_pct,
        coding_pct: rule.coding_pct,
        system_design_pct: rule.system_design_pct,
        total_questions: rule.total_questions || 5,
      },
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    const total = (editing.form.behavioral_pct ?? 0) + (editing.form.technical_pct ?? 0) + (editing.form.coding_pct ?? 0) + (editing.form.system_design_pct ?? 0);
    if (total !== 100) {
      toast.error('Tổng tỷ lệ phân phối các loại câu hỏi phải bằng 100%!');
      return;
    }
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

  const WeightBar = ({ value, colorClass }: { value: number; colorClass: string }) => (
    <div className="flex items-center gap-4 w-full">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.08]">
        <div className={`h-full rounded-full transition-all duration-500 ${colorClass}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="w-14 shrink-0 text-right text-sm font-semibold tabular-nums text-slate-300">{value}%</span>
    </div>
  );

  return (
    <RuleDashboardSection
      title="Phân phối câu hỏi theo cấp bậc"
      count={rules.length}
      countLabel="mức"
      description="Điều chỉnh tỷ lệ behavioral, technical, coding, system design và tổng số câu hỏi cho từng seniority."
      action={(
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-400 hidden sm:inline">Sắp xếp:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-1.5 text-xs font-semibold text-slate-200 transition-colors focus:border-amber-400/50 focus:outline-none cursor-pointer"
          >
            <option value="level_asc">Trình độ: Thấp đến Cao (Mặc định)</option>
            <option value="level_desc">Trình độ: Cao đến Thấp</option>
            <option value="questions_asc">Số câu hỏi: Ít đến Nhiều</option>
            <option value="questions_desc">Số câu hỏi: Nhiều đến Ít</option>
          </select>
        </div>
      )}
    >
      {rules.length === 0 && (
        <div className="px-6 py-10 text-center text-slate-400">Chưa có dữ liệu. Hãy chạy DatabaseSeeder.</div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 border-t border-white/6 bg-slate-950/35 p-6 sm:p-8 lg:p-10">
        {sortedRules.map((rule) => {
        const isEditing = editing?.level === rule.level;
        const f = isEditing ? editing!.form : null;
        const total = isEditing
          ? (f!.behavioral_pct ?? 0) + (f!.technical_pct ?? 0) + (f!.coding_pct ?? 0) + (f!.system_design_pct ?? 0)
          : rule.behavioral_pct + rule.technical_pct + rule.coding_pct + rule.system_design_pct;
        const currentTotalQuestions = isEditing ? (f!.total_questions ?? 5) : (rule.total_questions ?? 5);

        return (
          <div
            key={rule.level}
            className={`flex flex-col justify-between rounded-2xl border p-6 transition-all ${isEditing ? 'border-amber-400/40 bg-amber-400/8' : 'border-slate-700/70 bg-white/[0.025] hover:bg-white/[0.04]'}`}
          >
            <div>
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <h4 className="text-base font-bold tracking-wide text-white">{rule.level}</h4>
                  <p className="mt-1.5 text-xs text-slate-400">{LEVEL_LABELS[rule.level] ?? rule.level}</p>
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
                    <button onClick={() => setEditing(null)} className="rounded-lg border border-slate-700 bg-slate-900/60 px-2.5 py-1 text-xs font-semibold text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white min-h-[28px]">Hủy</button>
                    <button onClick={handleSave} disabled={saving} className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-2.5 py-1 text-xs font-semibold text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-400/15 hover:text-white disabled:opacity-50 min-h-[28px]">
                      {saving ? '...' : 'Lưu'}
                    </button>
                  </div>
                )}
              </div>

              {/* Total Questions Setting Field */}
              <div className="mb-5 flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/50 px-3.5 py-2.5">
                <span className="text-xs font-medium text-slate-300 flex items-center gap-2">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber-400"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  Số câu hỏi quy định:
                </span>
                {isEditing ? (
                  <input
                    type="number" min={1} max={30} step={1}
                    className="w-14 rounded border border-amber-400/50 bg-slate-900 px-2 py-1 text-center text-xs font-bold font-mono text-amber-300 focus:outline-none"
                    value={f!.total_questions ?? 5}
                    onChange={(e) => setEditing({ ...editing!, form: { ...f!, total_questions: Math.max(1, Number(e.target.value)) } })}
                  />
                ) : (
                  <span className="rounded-md bg-amber-400/10 px-2.5 py-0.5 text-xs font-bold text-amber-300 border border-amber-400/20">
                    {currentTotalQuestions} câu
                  </span>
                )}
              </div>

              <div className="space-y-5">
                {[
                  { key: 'behavioral_pct' as const, label: 'Behavioral', color: 'bg-purple-500' },
                  { key: 'technical_pct' as const, label: 'Technical', color: 'bg-blue-500' },
                  { key: 'coding_pct' as const, label: 'Coding', color: 'bg-emerald-500' },
                  { key: 'system_design_pct' as const, label: 'System Design', color: 'bg-orange-500' },
                ].map(({ key, label, color }) => (
                  <div key={key}>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-300">{label}</span>
                      {isEditing && (
                        <input
                          type="number" min={0} max={100} step={1}
                          className="w-12 rounded border border-slate-600 bg-slate-900 px-1 py-0.5 text-center text-xs font-mono tabular-nums text-white focus:border-amber-400/50 focus:outline-none"
                          value={f![key]}
                          onChange={(e) => setEditing({ ...editing!, form: { ...f!, [key]: Number(e.target.value) } })}
                        />
                      )}
                    </div>
                    <WeightBar value={isEditing ? f![key] : rule[key]} colorClass={color} />
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between border-t border-white/5 pt-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-slate-400">Tổng phân phối:</span>
                <span className={`text-sm font-bold ${total === 100 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {total}%
                </span>
                {total !== 100 && (
                  <span className="text-[10px] text-amber-400 flex items-center gap-1 animate-pulse">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    (phải = 100%)
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
      </div>
    </RuleDashboardSection>
  );
}
