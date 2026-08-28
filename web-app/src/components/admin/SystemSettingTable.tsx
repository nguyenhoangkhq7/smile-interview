'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { adminService, SystemSettingDto } from '@/services/adminService';
import { toast } from './Toast';
import RuleDashboardSection from './rule-dashboard/RuleDashboardSection';
import ActionIconButton from './rule-dashboard/ActionIconButton';

interface Props {
  settings: SystemSettingDto[];
  onRefresh: () => void;
}

interface SettingMeta {
  label: string;
  description: string;
  unit?: string;
}

const SETTING_META: Record<string, SettingMeta> = {
  // Group 1: Status Coefficients
  STATUS_MATCHED_COEFF: {
    label: 'Hệ số "Matched"',
    description: 'Hệ số điểm khi tiêu chí khớp hoàn toàn (có bằng chứng dự án/thực chiến rõ ràng).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  STATUS_PARTIAL_COEFF: {
    label: 'Hệ số "Partial"',
    description: 'Hệ số điểm khi tiêu chí khớp một phần (đã làm qua nhưng thiếu chiều sâu hoặc thiếu một số yêu cầu phụ).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  STATUS_WEAK_COEFF: {
    label: 'Hệ số "Weak"',
    description: 'Điểm được cộng khi tiêu chí ở mức cơ bản / chỉ liệt kê từ khóa mà chưa có dự án chứng minh.',
    unit: 'hệ số (0.0 - 1.0)',
  },
  STATUS_MISSING_COEFF: {
    label: 'Hệ số "Missing"',
    description: 'Hệ số điểm khi tiêu chí hoàn toàn không xuất hiện trong CV.',
    unit: 'hệ số (0.0 - 1.0)',
  },

  // Group 2: Level Adjustments
  PARTIAL_COEFF_INTERN_FRESHER: {
    label: 'Hệ số Partial (Intern/Fresher)',
    description: 'Hệ số điểm cho trạng thái Partial đối với ứng viên Intern/Fresher (linh hoạt hơn).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  WEAK_COEFF_INTERN_FRESHER: {
    label: 'Hệ số Weak (Intern/Fresher)',
    description: 'Hệ số điểm cộng cho tiêu chí ở trạng thái Weak đối với ứng viên Intern hoặc Fresher (chấp nhận lý thuyết).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  PARTIAL_COEFF_SENIOR_LEAD: {
    label: 'Hệ số Partial (Senior/Lead)',
    description: 'Hệ số điểm cho trạng thái Partial đối với ứng viên Senior/Lead (chấm điểm chặt chẽ hơn).',
    unit: 'hệ số (0.0 - 1.0)',
  },
  WEAK_COEFF_SENIOR_LEAD: {
    label: 'Hệ số Weak (Senior/Lead)',
    description: 'Hệ số điểm cộng cho tiêu chí ở trạng thái Weak đối với ứng viên Senior hoặc Lead (đòi hỏi thực chiến khắt khe).',
    unit: 'hệ số (0.0 - 1.0)',
  },

  // Group 3: Component Weights
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
  MATCHED_QUESTIONS_RATIO: {
    label: 'Tỷ lệ câu hỏi Matched',
    description: 'Tỷ lệ câu hỏi (0.0 - 1.0) tập trung vào các kỹ năng thế mạnh (Matched) của ứng viên. Phần còn lại dành cho Missing/Weak.',
    unit: 'tỷ lệ (0.0 - 1.0)',
  },

  // Group 4: AI & System Engine
  EVIDENCE_GROUNDING_THRESHOLD: {
    label: 'Ngưỡng kiểm chứng bằng chứng (Grounding Threshold)',
    description: 'Độ tương đồng chuỗi tối thiểu (0.0 - 1.0) để xác thực đoạn trích dẫn của LLM có thực sự tồn tại trong CV markdown.',
    unit: 'ngưỡng (0.0 - 1.0)',
  },
  CRITERIA_BATCH_SIZE: {
    label: 'Kích thước Batch tiêu chí (Batch Size)',
    description: 'Số lượng tiêu chí gửi trong một request LLM khi đối soát bằng chứng CV để tối ưu tốc độ.',
    unit: 'tiêu chí / batch',
  },
  MAX_CONCURRENT_LLM_CALLS: {
    label: 'Giới hạn gọi LLM đồng thời',
    description: 'Số lượng cuộc gọi API LLM đồng thời tối đa (Semaphore) để kiểm soát tài nguyên và rate limit.',
    unit: 'cuộc gọi đồng thời',
  },
  SELF_CONSISTENCY_RUNS: {
    label: 'Số lần chạy Self-Consistency',
    description: 'Số lượt chạy song song lấy majority voting để tăng độ tin cậy và chính xác của kết quả.',
    unit: 'lần chạy',
  },

  // Group 5: Prompt Strategies
  PROMPT_TECH_MATCHED: {
    label: 'Prompt Strategy (Technical - Matched)',
    description: 'Chiến lược đặt câu hỏi Technical khi ứng viên có thế mạnh (Matched).',
    unit: 'văn bản',
  },
  PROMPT_TECH_MISSING: {
    label: 'Prompt Strategy (Technical - Missing)',
    description: 'Chiến lược đặt câu hỏi Technical khi ứng viên bị thiếu kỹ năng (Missing/Weak).',
    unit: 'văn bản',
  },
  PROMPT_CODE_MATCHED: {
    label: 'Prompt Strategy (Coding - Matched)',
    description: 'Chiến lược đặt bài tập Coding khi ứng viên có thế mạnh (Matched).',
    unit: 'văn bản',
  },
  PROMPT_CODE_MISSING: {
    label: 'Prompt Strategy (Coding - Missing)',
    description: 'Chiến lược đặt bài tập Coding khi ứng viên bị thiếu kỹ năng (Missing/Weak).',
    unit: 'văn bản',
  },
  PROMPT_SYS_MATCHED: {
    label: 'Prompt Strategy (System Design - Matched)',
    description: 'Chiến lược đặt câu hỏi System Design khi ứng viên có thế mạnh (Matched).',
    unit: 'văn bản',
  },
  PROMPT_SYS_MISSING: {
    label: 'Prompt Strategy (System Design - Missing)',
    description: 'Chiến lược đặt câu hỏi System Design khi ứng viên bị thiếu kỹ năng (Missing/Weak).',
    unit: 'văn bản',
  },
  PROMPT_BEHAV_MATCHED: {
    label: 'Prompt Strategy (Behavioral - Matched)',
    description: 'Chiến lược đặt câu hỏi Hành vi (Behavioral) khi ứng viên có thế mạnh.',
    unit: 'văn bản',
  },
  PROMPT_BEHAV_MISSING: {
    label: 'Prompt Strategy (Behavioral - Missing)',
    description: 'Chiến lược đặt câu hỏi Hành vi (Behavioral) khi ứng viên bị thiếu kỹ năng (Missing/Weak).',
    unit: 'văn bản',
  },

  // Other configurations if present
  MATCH_SCORE_PIVOT: {
    label: 'Điểm Pivot Matching',
    description: 'Điểm tham chiếu để tính hệ số điều chỉnh f trong DifficultyDistributor. Score > Pivot → tăng câu hỏi khó.',
    unit: 'điểm (0-100)',
  },
  INCLUDE_NOT_APPLICABLE_CRITERIA: {
    label: 'Bao gồm tiêu chí N/A',
    description: 'Bật/tắt đưa các tiêu chí Không Áp Dụng vào kết quả đánh giá (true = 360 audit, false = strict JD matching).',
    unit: 'true | false',
  },
};

interface SettingGroup {
  id: string;
  name: string;
  badge: string;
  description: string;
  icon: ReactNode;
  keys: string[];
}

const SETTING_GROUPS: SettingGroup[] = [
  {
    id: 'status',
    name: 'Hệ số trạng thái',
    badge: 'Status Coefficients',
    description: 'Quy định mức điểm tương ứng cho các mức độ đáp ứng tiêu chí trong CV (Matched, Partial, Weak, Missing).',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
    keys: [
      'STATUS_MATCHED_COEFF',
      'STATUS_PARTIAL_COEFF',
      'STATUS_WEAK_COEFF',
      'STATUS_MISSING_COEFF',
    ],
  },
  {
    id: 'level',
    name: 'Hệ số theo cấp bậc',
    badge: 'Level Adjustments',
    description: 'Điều chỉnh độ khắt khe của hệ số Partial và Weak theo từng cấp bậc kinh nghiệm (Intern/Fresher vs. Senior/Lead).',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
    keys: [
      'PARTIAL_COEFF_INTERN_FRESHER',
      'WEAK_COEFF_INTERN_FRESHER',
      'PARTIAL_COEFF_SENIOR_LEAD',
      'WEAK_COEFF_SENIOR_LEAD',
    ],
  },
  {
    id: 'weights',
    name: 'Tỷ trọng & Phân bổ',
    badge: 'Component Weights',
    description: 'Tỷ trọng đóng góp của tiêu chí Must-Have, Prefer-to-Have và phân bổ câu hỏi phỏng vấn theo thế mạnh.',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
        <path d="M22 12A10 10 0 0 0 12 2v10z" />
      </svg>
    ),
    keys: [
      'MUST_HAVE_WEIGHT_RATIO',
      'PREFER_TO_HAVE_WEIGHT_RATIO',
      'MATCHED_QUESTIONS_RATIO',
    ],
  },
  {
    id: 'ai_engine',
    name: 'Cấu hình AI & Engine',
    badge: 'AI & System Engine',
    description: 'Tham số kiểm chứng bằng chứng (Grounding), batch size và giới hạn concurrency khi tương tác với LLM.',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
    keys: [
      'EVIDENCE_GROUNDING_THRESHOLD',
      'CRITERIA_BATCH_SIZE',
      'MAX_CONCURRENT_LLM_CALLS',
      'SELF_CONSISTENCY_RUNS',
    ],
  },
  {
    id: 'prompts',
    name: 'Chiến lược Prompt',
    badge: 'Prompt Strategies',
    description: 'Định hướng nội dung sinh câu hỏi phỏng vấn cho từng loại câu hỏi theo trạng thái kỹ năng ứng viên.',
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    keys: [
      'PROMPT_TECH_MATCHED',
      'PROMPT_TECH_MISSING',
      'PROMPT_CODE_MATCHED',
      'PROMPT_CODE_MISSING',
      'PROMPT_SYS_MATCHED',
      'PROMPT_SYS_MISSING',
      'PROMPT_BEHAV_MATCHED',
      'PROMPT_BEHAV_MISSING',
    ],
  },
];

interface EditState {
  key: string;
  value: string;
}

export default function SystemSettingTable({ settings, onRefresh }: Props) {
  const [activeTab, setActiveTab] = useState<string>('status');
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

  // Map settings by setting_key for O(1) lookups
  const settingsMap = useMemo(() => {
    const map = new Map<string, SystemSettingDto>();
    settings.forEach((s) => map.set(s.setting_key, s));
    return map;
  }, [settings]);

  // Identify any leftover settings that do not belong to the 5 predefined groups
  const knownKeys = useMemo(() => {
    const set = new Set<string>();
    SETTING_GROUPS.forEach((g) => g.keys.forEach((k) => set.add(k)));
    return set;
  }, []);

  const otherSettings = useMemo(() => {
    return settings.filter((s) => !knownKeys.has(s.setting_key));
  }, [settings, knownKeys]);

  const allGroups = useMemo(() => {
    if (otherSettings.length === 0) return SETTING_GROUPS;
    return [
      ...SETTING_GROUPS,
      {
        id: 'other',
        name: 'Cấu hình khác',
        badge: 'Other Settings',
        description: 'Các tham số hệ thống bổ sung khác đang được lưu trữ trong cơ sở dữ liệu.',
        icon: (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="1" />
            <circle cx="19" cy="12" r="1" />
            <circle cx="5" cy="12" r="1" />
          </svg>
        ),
        keys: otherSettings.map((s) => s.setting_key),
      },
    ];
  }, [otherSettings]);

  const currentGroup = useMemo(() => {
    return allGroups.find((g) => g.id === activeTab) ?? allGroups[0];
  }, [allGroups, activeTab]);

  const currentGroupSettings = useMemo(() => {
    if (!currentGroup) return [];
    return currentGroup.keys
      .map((k) => settingsMap.get(k))
      .filter((s): s is SystemSettingDto => Boolean(s));
  }, [currentGroup, settingsMap]);

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
      {settings.length === 0 ? (
        <div className="px-6 py-12 text-center text-slate-400">
          Chưa có cài đặt nào. Hãy chạy DatabaseSeeder hoặc tải lại trang.
        </div>
      ) : (
        <div className="border-t border-white/6 bg-slate-950/35 p-5 sm:p-6 lg:p-7 space-y-7">
          {/* Category Tabs Navigation */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-slate-800">
              {allGroups.map((group) => {
                const count = group.keys.filter((k) => settingsMap.has(k)).length;
                const isActive = activeTab === group.id;

                return (
                  <button
                    key={group.id}
                    type="button"
                    onClick={() => setActiveTab(group.id)}
                    className={`group flex items-center gap-2.5 whitespace-nowrap rounded-xl px-4 py-2.5 text-xs font-semibold transition-all ${
                      isActive
                        ? 'border border-amber-400/40 bg-amber-400/10 text-amber-300 shadow-[0_0_20px_rgba(251,191,36,0.15)]'
                        : 'border border-slate-800 bg-slate-900/50 text-slate-400 hover:border-slate-700 hover:bg-slate-900 hover:text-slate-200'
                    }`}
                  >
                    <span className={isActive ? 'text-amber-400' : 'text-slate-500 group-hover:text-slate-400'}>
                      {group.icon}
                    </span>
                    <span>{group.name}</span>
                    <span
                      className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-mono font-bold transition-colors ${
                        isActive
                          ? 'bg-amber-400/20 text-amber-200 border border-amber-400/30'
                          : 'bg-white/[0.04] text-slate-500 border border-slate-800'
                      }`}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Active Tab Info Banner */}
            {currentGroup && (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-xl border border-slate-800/80 bg-slate-900/30 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400/80 text-xs font-mono font-semibold uppercase tracking-wider">
                    {currentGroup.badge}
                  </span>
                  <span className="hidden sm:inline text-slate-600">•</span>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {currentGroup.description}
                  </p>
                </div>
                <span className="text-[11px] text-slate-500 shrink-0 font-medium">
                  {currentGroupSettings.length} tham số trong nhóm
                </span>
              </div>
            )}
          </div>

          {/* Setting Cards Responsive Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {currentGroupSettings.map((setting) => (
              <SystemSettingCard
                key={setting.setting_key}
                setting={setting}
                meta={SETTING_META[setting.setting_key]}
                isEditing={editing?.key === setting.setting_key}
                editValue={editing?.key === setting.setting_key ? editing.value : setting.setting_value}
                saving={saving}
                onStartEdit={() => setEditing({ key: setting.setting_key, value: setting.setting_value })}
                onCancelEdit={() => setEditing(null)}
                onValueChange={(val) => setEditing({ key: setting.setting_key, value: val })}
                onSave={handleSave}
              />
            ))}
          </div>

          {/* Info Banner */}
          <div className="rounded-2xl border border-slate-800/90 bg-slate-900/40 p-4">
            <div className="flex items-start gap-3">
              <svg className="text-amber-400/90 flex-shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              <p className="text-xs leading-relaxed text-slate-400">
                Các thay đổi hệ số và chiến lược prompt có hiệu lực <strong>ngay lập tức</strong> cho phiên phân tích CV và sinh câu hỏi tiếp theo mà không cần khởi động lại dịch vụ backend.
              </p>
            </div>
          </div>

          {/* Scoring Simulator Section */}
          <ScoringSimulator weakCoeff={activeWeakCoeff} />
        </div>
      )}
    </RuleDashboardSection>
  );
}

/**
 * Reusable Card Component for a Single System Setting
 */
interface SystemSettingCardProps {
  setting: SystemSettingDto;
  meta?: SettingMeta;
  isEditing: boolean;
  editValue: string;
  saving: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onValueChange: (val: string) => void;
  onSave: () => void;
}

function SystemSettingCard({
  setting,
  meta,
  isEditing,
  editValue,
  saving,
  onStartEdit,
  onCancelEdit,
  onValueChange,
  onSave,
}: SystemSettingCardProps) {
  const isPrompt = setting.setting_key.startsWith('PROMPT_') || setting.setting_value.length > 50;

  return (
    <div
      className={`rounded-2xl border p-4 sm:p-5 flex flex-col justify-between transition-all duration-200 ${
        isEditing
          ? 'border-amber-400/50 bg-amber-400/[0.07] shadow-[0_0_24px_rgba(251,191,36,0.1)]'
          : 'border-slate-800/80 bg-white/[0.02] hover:border-slate-700/80 hover:bg-white/[0.035]'
      }`}
    >
      <div className="min-w-0 flex-1 flex flex-col justify-between h-full">
        {/* Header: Label, Key & Unit */}
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-slate-100 leading-snug">
              {meta?.label ?? setting.setting_key}
            </span>
            <code className="rounded-md border border-orange-400/20 bg-orange-400/10 px-2 py-0.5 text-[11px] font-mono font-semibold text-orange-300">
              {setting.setting_key}
            </code>
          </div>

          {meta?.unit && (
            <div className="mb-2">
              <span className="inline-block rounded-full border border-slate-700/70 bg-white/[0.04] px-2.5 py-0.5 text-[10px] font-medium text-slate-400">
                {meta.unit}
              </span>
            </div>
          )}

          <p className="text-xs leading-relaxed text-slate-400 mb-4 line-clamp-3">
            {meta?.description || setting.description || 'Không có mô tả chi tiết.'}
          </p>
        </div>

        {/* Value and Edit Controls */}
        <div className="border-t border-slate-800/80 pt-3 mt-auto">
          {isEditing ? (
            <div className="space-y-2.5">
              {isPrompt ? (
                <textarea
                  rows={3}
                  className="w-full rounded-xl border border-amber-400/40 bg-slate-900 p-2.5 text-xs text-slate-100 focus:border-amber-300 focus:outline-none focus:ring-1 focus:ring-amber-300"
                  value={editValue}
                  onChange={(e) => onValueChange(e.target.value)}
                  placeholder="Nhập nội dung chiến lược prompt..."
                  autoFocus
                />
              ) : (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    className="w-full rounded-xl border border-amber-400/40 bg-slate-900 px-3 py-1.5 text-xs font-mono tabular-nums text-white focus:border-amber-300 focus:outline-none focus:ring-1 focus:ring-amber-300"
                    value={editValue}
                    onChange={(e) => onValueChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') onSave();
                      if (e.key === 'Escape') onCancelEdit();
                    }}
                    autoFocus
                  />
                </div>
              )}

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={onCancelEdit}
                  disabled={saving}
                  className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-200"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={onSave}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400/40 bg-amber-400/15 px-3.5 py-1.5 text-xs font-semibold text-amber-200 transition-colors hover:bg-amber-400/25 hover:text-white disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <svg className="animate-spin h-3.5 w-3.5 text-amber-300" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      <span>Đang lưu...</span>
                    </>
                  ) : (
                    'Lưu thay đổi'
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                {isPrompt ? (
                  <p className="text-xs font-medium italic text-slate-300 bg-slate-900/40 border border-slate-800/60 rounded-lg p-2 leading-relaxed line-clamp-2">
                    &ldquo;{setting.setting_value}&rdquo;
                  </p>
                ) : (
                  <span className="text-base font-bold tabular-nums font-mono text-white tracking-tight">
                    {setting.setting_value}
                  </span>
                )}
              </div>
              <ActionIconButton
                label={`Chỉnh sửa ${meta?.label ?? setting.setting_key}`}
                onClick={onStartEdit}
                variant="accent"
                className="shrink-0"
                icon={(
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                )}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Interactive Scoring Simulator
 */
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
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 17v-5M12 17V9M15 17v-3" />
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

