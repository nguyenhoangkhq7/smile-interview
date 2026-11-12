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
  PLAN_COMPLETE: 'Đã hoàn thành các nội dung phỏng vấn dự kiến',
  MODE_FILTER: 'Ngoài dạng phỏng vấn đã chọn',
  PLAN_BUDGET: 'Chưa được hỏi do giới hạn thời lượng hoặc số câu đã chọn',
  LOCAL_BUDGET: 'Đã hết số câu dành cho nội dung này',
  SUFFICIENT_EVIDENCE: 'Đã đủ bằng chứng',
  CRITERION_BUDGET: 'Đã hết số câu dành cho tiêu chí này',
  NO_PROGRESS: 'Chưa đủ thông tin mới để kết luận thêm',
  NO_INDEPENDENT_CRITERIA_IN_MODE: 'Cần dạng phỏng vấn khác để đánh giá thêm nội dung này',
};

export const skillStatuses = {
  strong: { label: 'Đạt yêu cầu', tone: 'bg-emerald-50 text-emerald-800', bar: 'bg-emerald-600' },
  weak: { label: 'Cần cải thiện', tone: 'bg-orange-50 text-orange-900', bar: 'bg-orange-600' },
  partial: { label: 'Chưa đủ cơ sở kết luận', tone: 'bg-amber-50 text-amber-900', bar: 'bg-amber-500' },
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
  // A session result describes completed questions, not the full interview plan.
  // Evidence can also link a question to an objective other than its primary one.
  const turnIds = new Set(turns.map(turn => turn.turn_id));
  const askedObjectiveIds = new Set(turns.map(turn => turn.objective_id));
  const interviewedObjectives = report.objectives.filter(objective =>
    askedObjectiveIds.has(objective.objective_id)
    || objective.evidence_turn_ids.some(id => turnIds.has(id))
    || objective.evidence.some(item => turnIds.has(item.turn_id)));
  const bySkill = new Map<string, ObjectiveReport[]>();
  const byTurn = new Map<string, Observation[]>();
  for (const turn of turns) {
    if (turn.skill_id) bySkill.set(turn.skill_id, []);
  }
  for (const objective of interviewedObjectives) {
    const objectives = bySkill.get(objective.skill_id) ?? [];
    objectives.push(objective);
    bySkill.set(objective.skill_id, objectives);
    for (const item of objective.evidence) {
      if (!turnIds.has(item.turn_id)) continue;
      const evidence = byTurn.get(item.turn_id) ?? [];
      evidence.push(item);
      byTurn.set(item.turn_id, evidence);
    }
  }

  const skills = Array.from(bySkill, ([id, objectives]) => {
    const statuses = objectives.map(objective => assessmentStatus(objective.assessment));
    const status = statuses.includes('weak') ? 'weak'
      : statuses.length > 0 && statuses.every(value => value === 'strong') ? 'strong' : 'partial';
    const evidenceIds = new Set(objectives.flatMap(objective => [
      ...objective.evidence_turn_ids, ...objective.evidence.map(item => item.turn_id),
    ]));
    const objectiveIds = new Set(objectives.map(objective => objective.objective_id));
    const questionCount = turns.filter(turn => turn.skill_id === id
      || objectiveIds.has(turn.objective_id) || evidenceIds.has(turn.turn_id)).length;
    return { id, objectives, status, questionCount } as const;
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
    assessedCount: interviewedObjectives.filter(objective => ['strong', 'weak'].includes(assessmentStatus(objective.assessment))).length,
    achievedCount: interviewedObjectives.filter(objective => assessmentStatus(objective.assessment) === 'strong').length,
    strengths: uniqueFindings(interviewedObjectives.flatMap(objective => objective.strengths)),
    weaknesses: uniqueFindings(interviewedObjectives.flatMap(objective => objective.weaknesses)),
    // Global recommendations also include untouched objectives in the plan.
    recommendations: uniqueFindings(interviewedObjectives.flatMap(objective => objective.study_recommendations ?? [])),
  };
}

export type ResultData = ReturnType<typeof buildResult>;
