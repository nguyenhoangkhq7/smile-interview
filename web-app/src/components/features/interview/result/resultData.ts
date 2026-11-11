import type { Assessment, EvidenceSession, ObjectiveReport, Observation } from '@/services/evidenceInterview';

export const assessmentLabels: Record<Assessment, string> = {
  NOT_ASSESSED: 'Chưa được kiểm tra',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng',
  NOT_DEMONSTRATED: 'Chưa thể hiện được',
  DEMONSTRATED_BELOW_TARGET: 'Đã thể hiện ở mức dưới yêu cầu',
  DEMONSTRATED_AT_TARGET: 'Đáp ứng yêu cầu đã kiểm tra',
  DEMONSTRATED_ABOVE_TARGET: 'Vượt yêu cầu đã kiểm tra',
};

export const resultReasons: Record<string, string> = {
  TIME_BUDGET: 'Hết thời gian',
  QUESTION_BUDGET: 'Đã hết số câu hỏi của phiên',
  USER_STOP: 'Bạn đã kết thúc phiên sớm',
  PLAN_COMPLETE: 'Đã xử lý các mục tiêu trong kế hoạch',
  MODE_FILTER: 'Ngoài dạng phỏng vấn đã chọn',
  PLAN_BUDGET: 'Ngoài ngân sách phiên',
  LOCAL_BUDGET: 'Hết lượt cho mục tiêu này',
  SUFFICIENT_EVIDENCE: 'Đã đủ bằng chứng',
  CRITERION_BUDGET: 'Đã hết lượt kiểm chứng tiêu chí',
  NO_PROGRESS: 'Dừng hỏi tiếp vì chưa thu được thêm bằng chứng',
  NO_INDEPENDENT_CRITERIA_IN_MODE: 'Không còn tiêu chí có thể kiểm chứng độc lập trong dạng phỏng vấn này',
};

export const skillStatuses = {
  strong: { label: 'Đạt yêu cầu', tone: 'bg-emerald-50 text-emerald-800', bar: 'bg-emerald-600' },
  weak: { label: 'Cần cải thiện', tone: 'bg-orange-50 text-orange-900', bar: 'bg-orange-600' },
  partial: { label: 'Chưa đủ bằng chứng', tone: 'bg-amber-50 text-amber-900', bar: 'bg-amber-500' },
  unchecked: { label: 'Chưa kiểm tra', tone: 'bg-slate-100 text-slate-700', bar: 'bg-slate-400' },
} as const;

export function assessmentStatus(value: Assessment): keyof typeof skillStatuses {
  switch (value) {
    case 'DEMONSTRATED_AT_TARGET':
    case 'DEMONSTRATED_ABOVE_TARGET': return 'strong';
    case 'DEMONSTRATED_BELOW_TARGET':
    case 'NOT_DEMONSTRATED': return 'weak';
    case 'INSUFFICIENT_EVIDENCE': return 'partial';
    default: return 'unchecked';
  }
}

export function percent(value: number | null) {
  return value == null || !Number.isFinite(value) ? null : Math.round(Math.min(1, Math.max(0, value)) * 100);
}

export function uniqueFindings(items: readonly string[]) {
  return [...new Set(items.map(item => item.trim()).filter(Boolean))];
}

export function buildResult({ report, turns }: EvidenceSession) {
  const bySkill = new Map<string, ObjectiveReport[]>();
  const byTurn = new Map<string, Observation[]>();
  for (const objective of report.objectives) {
    const objectives = bySkill.get(objective.skill_id) ?? [];
    objectives.push(objective);
    bySkill.set(objective.skill_id, objectives);
    for (const item of objective.evidence) {
      const evidence = byTurn.get(item.turn_id) ?? [];
      evidence.push(item);
      byTurn.set(item.turn_id, evidence);
    }
  }

  const skills = Array.from(bySkill, ([id, objectives]) => {
    const statuses = objectives.map(objective => assessmentStatus(objective.assessment));
    const status = statuses.includes('weak') ? 'weak' : statuses.every(value => value === 'strong') ? 'strong'
      : statuses.every(value => value === 'unchecked') ? 'unchecked' : 'partial';
    const checked = statuses.filter(value => value !== 'unchecked').length;
    return { id, objectives, status, checked } as const;
  });

  const questions = turns.map((turn, index) => {
    const evidence = byTurn.get(turn.turn_id) ?? [];
    const status = evidence.some(item => item.performance === 'BELOW') ? 'weak'
      : evidence.some(item => item.performance === 'AT_TARGET' || item.performance === 'ABOVE') ? 'strong' : 'partial';
    return { turn, index, evidence, status } as const;
  });

  return {
    skills,
    questions,
    strengths: uniqueFindings(report.objectives.flatMap(objective => objective.strengths)),
    weaknesses: uniqueFindings(report.objectives.flatMap(objective => objective.weaknesses)),
    recommendations: uniqueFindings([...(report.study_recommendations ?? []),
      ...report.objectives.flatMap(objective => objective.study_recommendations ?? [])]),
  };
}

export type ResultData = ReturnType<typeof buildResult>;
