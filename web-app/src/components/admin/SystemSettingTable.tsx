'use client';

import { useState } from 'react';
import { adminService, SystemSettingDto } from '@/services/adminService';
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
  WEAK_COEFF_INTERN_FRESHER: {
    label: 'Hệ số Weak (Intern/Fresher)',
    description: 'Hệ số điểm cộng cho tiêu chí ở trạng thái Weak đối với ứng viên Intern hoặc Fresher (chấp nhận lý thuyết).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  WEAK_COEFF_SENIOR_LEAD: {
    label: 'Hệ số Weak (Senior/Lead)',
    description: 'Hệ số điểm cộng cho tiêu chí ở trạng thái Weak đối với ứng viên Senior hoặc Lead (đòi hỏi thực chiến khắt khe).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  MUST_HAVE_WEIGHT_RATIO: {
    label: 'Tỷ trọng tiêu chí Bắt buộc (Must-Have)',
    description: 'Tỷ lệ trọng số đóng góp của bộ tiêu chí chuẩn bắt buộc vào tổng điểm đánh giá cuối cùng.',
    unit: 'tỷ lệ (0.0 - 1.0)',
  },
  PREFER_TO_HAVE_WEIGHT_RATIO: {
    label: 'Tỷ trọng tiêu chí Ưu tiên (Prefer-to-Have)',
    description: 'Tỷ lệ trọng số đóng góp của các tiêu chí bổ sung (ad-hoc) vào tổng điểm đánh giá cuối cùng.',
    unit: 'tỷ lệ (0.0 - 1.0)',
  },
  DIFF_INTERN_FRESHER_MISSING: {
    label: 'Độ khó câu hỏi Intern/Fresher - Missing',
    description: 'Độ khó câu hỏi khi ứng viên Intern/Fresher bị thiếu (missing) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_INTERN_FRESHER_WEAK: {
    label: 'Độ khó câu hỏi Intern/Fresher - Weak',
    description: 'Độ khó câu hỏi khi ứng viên Intern/Fresher ở mức yếu (weak) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_INTERN_FRESHER_MATCHED: {
    label: 'Độ khó câu hỏi Intern/Fresher - Matched',
    description: 'Độ khó câu hỏi khi ứng viên Intern/Fresher ở mức tốt (matched) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_JUNIOR_MISSING: {
    label: 'Độ khó câu hỏi Junior - Missing',
    description: 'Độ khó câu hỏi khi ứng viên Junior bị thiếu (missing) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_JUNIOR_WEAK: {
    label: 'Độ khó câu hỏi Junior - Weak',
    description: 'Độ khó câu hỏi khi ứng viên Junior ở mức yếu (weak) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_JUNIOR_MATCHED: {
    label: 'Độ khó câu hỏi Junior - Matched',
    description: 'Độ khó câu hỏi khi ứng viên Junior ở mức tốt (matched) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_MID_MISSING: {
    label: 'Độ khó câu hỏi Mid - Missing',
    description: 'Độ khó câu hỏi khi ứng viên Mid bị thiếu (missing) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_MID_WEAK: {
    label: 'Độ khó câu hỏi Mid - Weak',
    description: 'Độ khó câu hỏi khi ứng viên Mid ở mức yếu (weak) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_MID_MATCHED: {
    label: 'Độ khó câu hỏi Mid - Matched',
    description: 'Độ khó câu hỏi khi ứng viên Mid ở mức tốt (matched) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_SENIOR_LEAD_MISSING: {
    label: 'Độ khó câu hỏi Senior/Lead - Missing',
    description: 'Độ khó câu hỏi khi ứng viên Senior/Lead bị thiếu (missing) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_SENIOR_LEAD_WEAK: {
    label: 'Độ khó câu hỏi Senior/Lead - Weak',
    description: 'Độ khó câu hỏi khi ứng viên Senior/Lead ở mức yếu (weak) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
  },
  DIFF_SENIOR_LEAD_MATCHED: {
    label: 'Độ khó câu hỏi Senior/Lead - Matched',
    description: 'Độ khó câu hỏi khi ứng viên Senior/Lead ở mức tốt (matched) tiêu chí kỹ năng.',
    unit: 'easy | medium | hard',
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

  const weakSetting = settings.find((s) => s.setting_key === 'STATUS_WEAK_COEFF');
  const isEditingWeak = editing?.key === 'STATUS_WEAK_COEFF';
  const currentWeakVal = isEditingWeak ? parseFloat(editing!.value) : (weakSetting ? parseFloat(weakSetting.setting_value) : 0.3);
  const activeWeakCoeff = isNaN(currentWeakVal) ? 0.3 : currentWeakVal;

  return (
    <RuleDashboardSection
      title="Hệ số hệ thống"
      count={settings.length}
      countLabel="tham số"
      description="Các cài đặt này có hiệu lực ngay lập tức cho lần xử lý tiếp theo."
    >
      {settings.length === 0 && (
        <div className="px-6 py-10 text-center text-slate-400">Chưa có cài đặt nào. Hãy chạy DatabaseSeeder.</div>
      )}
      <div className="border-t border-white/6 bg-slate-950/35 p-5 sm:p-6 lg:p-7">
        <div className="w-full space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {settings.map((s) => {
              const meta = SETTING_META[s.setting_key];
              const isEditing = editing?.key === s.setting_key;

              return (
                <div
                  key={s.setting_key}
                  className={`rounded-2xl border px-5 py-5 flex flex-col justify-between transition-all ${isEditing ? 'border-amber-400/40 bg-amber-400/8' : 'border-slate-700/70 bg-white/[0.025] hover:bg-white/[0.04]'}`}
                >
                  <div className="min-w-0 flex-1 flex flex-col justify-between h-full">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-white">{meta?.label ?? s.setting_key}</span>
                        <code className="rounded-md border border-orange-400/15 bg-orange-400/10 px-2 py-0.5 text-xs font-mono font-semibold text-orange-200">{s.setting_key}</code>
                      </div>
                      {meta?.unit && (
                        <span className="inline-block mb-2 rounded-full border border-slate-700/80 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">{meta.unit}</span>
                      )}
                      {meta && <p className="text-xs leading-relaxed text-slate-400 mb-4">{meta.description}</p>}
                    </div>

                    <div className="flex items-center justify-between border-t border-slate-800/80 pt-3">
                      {isEditing ? (
                        <div className="flex items-center gap-2 w-full justify-between">
                          <input
                            type="text"
                            className="w-20 rounded-lg border border-amber-400/35 bg-slate-900 px-2 py-1 text-xs font-mono tabular-nums text-white focus:border-amber-300 focus:outline-none"
                            value={editing.value}
                            onChange={(e) => setEditing({ key: s.setting_key, value: e.target.value })}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(null); }}
                            autoFocus
                          />
                          <div className="flex gap-1 shrink-0">
                            <button onClick={() => setEditing(null)} className="rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-[10px] font-semibold text-slate-400 transition-colors hover:border-slate-500 hover:bg-white/[0.05] hover:text-white">Hủy</button>
                            <button onClick={handleSave} disabled={saving} className="rounded-md border border-amber-400/25 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold text-amber-200 transition-colors hover:border-amber-400/50 hover:bg-amber-400/15 hover:text-white disabled:opacity-50">
                              {saving ? '...' : 'Lưu'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <span className="text-lg font-semibold tabular-nums font-mono text-white">{s.setting_value}</span>
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

          <ScoringSimulator weakCoeff={activeWeakCoeff} />
        </div>
      </div>
    </RuleDashboardSection>
  );
}

function ScoringSimulator({ weakCoeff }: { weakCoeff: number }) {
  const [statuses, setStatuses] = useState<Record<string, string>>({
    crit1: 'matched',
    crit2: 'weak',
    crit3: 'missing',
  });

  const mockCriteria = [
    { id: 'crit1', name: 'Frontend Skills (React, Next.js)', weight: 45 },
    { id: 'crit2', name: 'Backend Architecture (Spring Boot)', weight: 35 },
    { id: 'crit3', name: 'Cloud & DevOps Deployment', weight: 20 },
  ];

  const getPoints = (status: string) => {
    switch (status) {
      case 'matched': return 1.0;
      case 'weak': return weakCoeff;
      case 'missing': return 0.0;
      default: return 0.0;
    }
  };

  let totalWeightUsed = 0;
  let weightedPointsSum = 0;

  mockCriteria.forEach((c) => {
    const status = statuses[c.id];
    if (status !== 'not_applicable') {
      totalWeightUsed += c.weight;
      weightedPointsSum += c.weight * getPoints(status);
    }
  });

  const score = totalWeightUsed > 0 
    ? Math.max(0, Math.min(100, Math.round((weightedPointsSum / totalWeightUsed) * 100))) 
    : 0;

  return (
    <div className="mt-8 rounded-3xl border border-slate-800 bg-slate-950/60 p-6 shadow-[0_12px_40px_rgba(2,6,23,0.3)]">
      <h3 className="text-base font-bold text-white flex items-center gap-2 mb-2">
        <svg className="text-teal-400" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 17v-5M12 17V9M15 17v-3" />
        </svg>
        Trình mô phỏng chấm điểm (Scoring Simulator)
      </h3>
      <p className="text-xs text-slate-400 mb-6 leading-relaxed">
        Thử thay đổi trạng thái đánh giá bên dưới để xem cách hệ thống tự động tính toán <strong>Overall Match Score</strong> theo công thức backend với hệ số Weak hiện tại (<span className="text-amber-400 font-bold font-mono">{weakCoeff}</span>).
      </p>

      <div className="space-y-4">
        {mockCriteria.map((c) => {
          const currentStatus = statuses[c.id];
          const points = getPoints(currentStatus);
          return (
            <div key={c.id} className="flex flex-col gap-3 rounded-2xl border border-slate-800/80 bg-slate-900/30 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 className="text-sm font-semibold text-slate-200">{c.name}</h4>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                  <span>Trọng số: <strong className="text-slate-300 font-mono">{c.weight}%</strong></span>
                  <span>•</span>
                  <span>Hệ số điểm: <strong className="text-slate-300 font-mono">{currentStatus === 'not_applicable' ? 'N/A' : points}</strong></span>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { value: 'matched', label: 'Matched (1.0)', activeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' },
                  { value: 'weak', label: `Weak (${weakCoeff})`, activeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
                  { value: 'missing', label: 'Missing (0.0)', activeClass: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
                  { value: 'not_applicable', label: 'N/A (Bỏ qua)', activeClass: 'bg-slate-700/30 text-slate-400 border-slate-600' },
                ].map((opt) => {
                  const isSelected = currentStatus === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setStatuses({ ...statuses, [c.id]: opt.value })}
                      className={`rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all ${
                        isSelected
                          ? opt.activeClass
                          : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex flex-col items-center justify-between gap-4 rounded-2xl border border-teal-500/15 bg-teal-500/[0.03] p-5 sm:flex-row">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1">Công thức tính toán</div>
          <div className="text-xs text-slate-400 font-mono break-all max-w-xl">
            Score = Math.round((
            {mockCriteria.map((c, idx) => {
              const status = statuses[c.id];
              if (status === 'not_applicable') return null;
              const points = getPoints(status);
              return `${c.weight}% * ${points}${idx < mockCriteria.length - 1 ? ' + ' : ''}`;
            }).filter(Boolean)}
            ) / {totalWeightUsed}% * 100)
          </div>
        </div>
        <div className="text-center sm:text-right shrink-0">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1">Overall Match Score</div>
          <div className="text-3xl font-extrabold text-teal-400 font-mono tracking-tight">{score} <span className="text-lg font-bold text-slate-500">/ 100</span></div>
        </div>
      </div>
    </div>
  );
}
