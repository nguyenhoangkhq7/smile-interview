import type {
  Assessment, EvidenceDepthRole, EvidenceSession, ObjectiveReport, PublicEvidence, SessionCoaching,
} from '@/services/evidenceInterview';

export const assessmentLabels: Record<Assessment, string> = {
  NOT_ASSESSED: 'Chưa hỏi trong lượt này',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ cơ sở kết luận',
  NOT_DEMONSTRATED: 'Chưa đạt yêu cầu',
  DEMONSTRATED_BELOW_TARGET: 'Dưới yêu cầu',
  DEMONSTRATED_AT_TARGET: 'Đạt yêu cầu',
  DEMONSTRATED_ABOVE_TARGET: 'Vượt yêu cầu',
};

export const resultReasons: Record<string, string> = {
  TIME_BUDGET: 'Đã hết thời gian buổi phỏng vấn',
  QUESTION_BUDGET: 'Đã hoàn thành tối đa số câu hỏi đã chọn',
  USER_STOP: 'Bạn đã chủ động kết thúc sớm',
  PLAN_COMPLETE: 'Đã hoàn thành toàn bộ nội dung dự kiến',
  MODE_FILTER: 'Ngoài dạng phỏng vấn đã chọn',
  SKILL_FILTER: 'Ngoài nhóm kỹ năng bạn chọn tập trung',
  PLAN_BUDGET: 'Chưa kịp hỏi trong thời lượng / số câu đã chọn',
  LOCAL_BUDGET: 'Đã hết giới hạn câu cho nội dung này',
  SUFFICIENT_EVIDENCE: 'Đã đủ bằng chứng đánh giá',
  CRITERION_BUDGET: 'Đã hết số câu tối đa cho tiêu chí này',
  NO_PROGRESS: 'Chưa bổ sung được thông tin mới để kết luận thêm',
  NO_INDEPENDENT_CRITERIA_IN_MODE: 'Các tiêu chí còn lại nằm ở dạng câu hỏi khác',
};

export const skillStatuses = {
  strong: { label: 'Đạt yêu cầu', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200/70', bar: 'bg-emerald-600' },
  weak: { label: 'Cần cải thiện', tone: 'bg-orange-50 text-orange-900 border-orange-200/70', bar: 'bg-orange-600' },
  partial: { label: 'Chưa đủ cơ sở', tone: 'bg-amber-50 text-amber-900 border-amber-200/70', bar: 'bg-amber-500' },
  unchecked: { label: 'Chưa kiểm tra', tone: 'bg-slate-100 text-slate-700 border-slate-200/70', bar: 'bg-slate-400' },
} as const;

export function isBoilerplateClaim(claim: string, skillId: string) {
  const normalized = claim.trim().toLowerCase();
  if (!normalized || normalized === skillId.trim().toLowerCase()) return true;
  return normalized.startsWith('đánh giá kiến thức thực hành ');
}

export function cleanStudyRecommendation(text: string) {
  return text.replace(/^[a-z0-9_+#.-]+\s*\([^)]+\):\s*/i, '').trim();
}

export function looksLikeRawCode(text: string, mode?: string) {
  const trimmed = text.trim();
  if (!trimmed || trimmed.includes('```')) return false;
  if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && trimmed.includes('\n')) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch {
      // Fall through to general syntax checks for partial JSON snippets.
    }
  }
  const hasNewline = trimmed.includes('\n');
  const codeKeyword = /^\s*(?:const|let|var|function|async\s+function|def|func|class|interface|type|import|export|package|SELECT|CREATE|INSERT|UPDATE|DELETE|FROM|WHERE)\b/m;
  const codePunctuation = /[{};]\s*$|=>/m;
  if (hasNewline && (codeKeyword.test(trimmed) || codePunctuation.test(trimmed))) return true;
  if (mode === 'CODING' && !hasNewline && (codeKeyword.test(trimmed) || /;\s*$|=>|\)\s*\{/.test(trimmed))) return true;
  return false;
}

export function normalizeSameText(a: string, b: string) {
  return a.replace(/\s+/g, ' ').trim() === b.replace(/\s+/g, ' ').trim();
}

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

export const evidenceDepthLabels: Record<EvidenceDepthRole, string> = {
  TARGET: 'Độ sâu mục tiêu',
  DIAGNOSTIC: 'Câu hỏi chẩn đoán nền tảng',
  EXTENSION: 'Câu hỏi mở rộng nâng cao',
};

export const modeDisplayLabels: Record<string, string> = {
  CODING: 'Lập trình',
  DEBUGGING: 'Tìm & sửa lỗi',
  DESIGN: 'Thiết kế hệ thống',
  TECHNICAL_EXPLANATION: 'Giải thích kỹ thuật',
  BEHAVIORAL: 'Kinh nghiệm & ứng xử',
};

const MODE_DISPLAY_ORDER = ['CODING', 'DEBUGGING', 'DESIGN', 'TECHNICAL_EXPLANATION', 'BEHAVIORAL'] as const;

export interface ModeBreakdownItem {
  mode: string;
  label: string;
  total: number;
  strong: number;
  weak: number;
  partial: number;
  passRate: number | null;
}

export const depthLevelLabels: Record<number, string> = {
  1: 'L1 · Nền tảng',
  2: 'L2 · Ứng dụng',
  3: 'L3 · Phân tích',
  4: 'L4 · Thiết kế',
};

export type HiringSignalKey = 'STRONG_HIRE' | 'HIRE' | 'BORDERLINE' | 'NEEDS_PREP' | 'INCOMPLETE';

export interface HiringSignal {
  key: HiringSignalKey;
  label: string;
  description: string;
  tone: string;
}

export function objectiveHasObservedRisk(objective: ObjectiveReport): boolean {
  if ((objective.weaknesses?.length ?? 0) > 0) return true;
  return (objective.evidence ?? []).some(item =>
    item.performance === 'BELOW' || item.observation === 'CONTRADICTS',
  );
}

export function questionBadge(item: {
  status: 'strong' | 'weak' | 'partial';
  depthRole?: EvidenceDepthRole;
  evidence: readonly PublicEvidence[];
  clarifiedLater?: boolean;
  usedHint?: boolean;
}) {
  if (item.status === 'strong') {
    if (item.depthRole === 'DIAGNOSTIC') {
      return {
        key: 'diagnostic' as const,
        label: 'Đạt nền tảng (chẩn đoán)',
        tone: 'bg-teal-50 text-teal-800 border-teal-200/70',
      };
    }
    if (item.depthRole === 'EXTENSION' && item.evidence.some(ev => ev.performance === 'ABOVE')) {
      return {
        key: 'extension' as const,
        label: item.usedHint ? 'Vượt yêu cầu (có gợi ý)' : 'Vượt yêu cầu (mở rộng)',
        tone: 'bg-emerald-100/90 text-emerald-900 border-emerald-300/80',
      };
    }
    if (item.usedHint) {
      return {
        key: 'strong' as const,
        label: 'Đạt yêu cầu (có gợi ý)',
        tone: 'bg-teal-50 text-teal-800 border-teal-200/70',
      };
    }
    return { key: 'strong' as const, label: 'Đạt yêu cầu', tone: skillStatuses.strong.tone };
  }
  if (item.status === 'weak') {
    return { key: 'weak' as const, label: 'Cần cải thiện', tone: skillStatuses.weak.tone };
  }
  if (item.clarifiedLater) {
    return { key: 'clarified' as const, label: 'Hỏi làm rõ tiếp', tone: 'bg-sky-50 text-sky-800 border-sky-200/70' };
  }
  return { key: 'partial' as const, label: 'Chưa kết luận', tone: skillStatuses.partial.tone };
}

export function buildResult({ report, turns }: EvidenceSession) {
  // A session result describes completed questions, not the full interview plan.
  // Evidence can also link a question to an objective other than its primary one.
  const turnIds = new Set(turns.map(turn => turn.turn_id));
  const askedObjectiveIds = new Set(turns.map(turn => turn.objective_id));
  const skillByObjective = new Map(report.objectives.map(objective => [objective.objective_id, objective.skill_id]));
  const interviewedObjectives = report.objectives.filter(objective =>
    askedObjectiveIds.has(objective.objective_id)
    || objective.evidence.some(item => turnIds.has(item.turn_id)));
  const needsIndependentCheck = (objective: ObjectiveReport) => {
    const hintedCriteria = (objective.criteria ?? []).filter(c => c.hinted);
    if (hintedCriteria.length) return hintedCriteria.some(c => !c.transfer_verified);
    return Boolean(objective.hinted) || turns.some(t => t.objective_id === objective.objective_id
      && t.clarifications?.some(c => c.kind === 'HINT'));
  };
  const bySkill = new Map<string, ObjectiveReport[]>();
  const byTurn = new Map<string, PublicEvidence[]>();
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
    const evidenceIds = new Set(objectives.flatMap(objective =>
      objective.evidence.map(item => item.turn_id)));
    const objectiveIds = new Set(objectives.map(objective => objective.objective_id));
    const relatedTurns = turns.filter(turn => objectiveIds.has(turn.objective_id) || evidenceIds.has(turn.turn_id));
    const questionCount = relatedTurns.length;
    const hinted = objectives.some(needsIndependentCheck);
    return { id, objectives, status, questionCount, hinted } as const;
  });

  const questions = turns.map((turn, index) => {
    const evidence = byTurn.get(turn.turn_id) ?? [];
    const status = evidence.some(item =>
      item.performance === 'BELOW' || item.observation === 'CONTRADICTS',
    ) ? 'weak'
      : evidence.some(item => item.performance === 'AT_TARGET' || item.performance === 'ABOVE') ? 'strong' : 'partial';
    const depthRole: EvidenceDepthRole = evidence.some(item => item.depth_role === 'EXTENSION') ? 'EXTENSION'
      : evidence.length > 0 && evidence.every(item => item.depth_role === 'DIAGNOSTIC') ? 'DIAGNOSTIC'
      : 'TARGET';
    const clarifiedLater = status === 'partial' && turns.some((later, laterIndex) =>
      laterIndex > index
      && later.objective_id === turn.objective_id
      && (byTurn.get(later.turn_id)?.length ?? 0) > 0);
    const usedHint = Boolean(turn.clarifications?.some(item => item.kind === 'HINT'));
    const badge = turn.practice_step === 'RETRY'
      ? { key: 'retry' as const, label: 'Làm lại sau góp ý', tone: skillStatuses.partial.tone }
      : questionBadge({ status, depthRole, evidence, clarifiedLater, usedHint });
    return {
      turn,
      reviews: (report.turn_reviews ?? []).filter(review => review.turn_id === turn.turn_id),
      skillId: skillByObjective.get(turn.objective_id) ?? '',
      index,
      evidence,
      status,
      depthRole,
      clarifiedLater,
      usedHint,
      badge,
    } as const;
  });

  const coaching: SessionCoaching | null = report.coaching && report.coaching.overall_summary?.trim()
    ? {
        overall_summary: report.coaching.overall_summary.trim(),
        top_strengths: uniqueFindings(report.coaching.top_strengths ?? []),
        priority_gaps: uniqueFindings(report.coaching.priority_gaps ?? []),
        actionable_study_steps: uniqueFindings((report.coaching.actionable_study_steps ?? []).map(cleanStudyRecommendation)),
        introduction_feedback: report.coaching.introduction_feedback?.trim() || undefined,
      }
    : null;

  const criteria = interviewedObjectives.flatMap(objective => objective.criteria ?? []);
  const required = criteria.filter(c => c.essential);
  const checked = required.filter(c => c.assessment !== 'NOT_ASSESSED');
  const coverage = criteria.length && interviewedObjectives.every(o => o.criteria?.length)
    && criteria.every(c => typeof c.essential === 'boolean')
    ? { total: required.length, checked: checked.length, passed: checked.filter(c => assessmentStatus(c.assessment) === 'strong').length }
    : null;

  let weightedMet = 0, weightedTotal = 0, provisionalTotal = 0;
  let coreTotal = 0, coreMet = 0, coreRiskCount = 0;
  let conclusiveCount = 0, inconclusiveCount = 0, inconclusiveWithRiskCount = 0;
  let hintedStrongCount = 0;
  for (const objective of interviewedObjectives) {
    const isCore = Boolean(objective.is_core || (objective.importance_weight ?? 0) >= 0.7);
    const weight = isCore ? 2 : 1;
    const status = assessmentStatus(objective.assessment);
    const isHinted = needsIndependentCheck(objective);
    if (status === 'strong' || status === 'weak') {
      conclusiveCount++;
      if (isCore) {
        coreTotal++;
        if (status === 'strong') coreMet++;
      }
      weightedTotal += weight;
      provisionalTotal += weight;
      if (status === 'strong') {
        weightedMet += weight;
        if (isHinted) hintedStrongCount++;
      }
    } else if (status === 'partial') {
      inconclusiveCount++;
      if (objectiveHasObservedRisk(objective)) {
        inconclusiveWithRiskCount++;
        provisionalTotal += weight;
        if (isCore) coreRiskCount++;
      }
    }
  }
  const interviewedTotal = interviewedObjectives.length;
  const coveragePercent = interviewedTotal > 0 ? Math.round((conclusiveCount / interviewedTotal) * 100) : 0;
  const conclusivePercent = weightedTotal > 0 ? Math.round((weightedMet / weightedTotal) * 100) : null;
  const provisionalPercent = provisionalTotal > 0 ? Math.round((weightedMet / provisionalTotal) * 100) : null;
  const weightedReadiness = {
    percent: conclusivePercent,
    provisionalPercent,
    coreTotal,
    coreMet,
    coreRiskCount,
    conclusiveCount,
    inconclusiveCount,
    inconclusiveWithRiskCount,
    interviewedTotal,
    coveragePercent,
    hintedStrongCount,
    hasCoreWeight: interviewedObjectives.some(o => typeof o.is_core === 'boolean' || typeof o.importance_weight === 'number'),
  };

  const hasAbove = interviewedObjectives.some(o => o.assessment === 'DEMONSTRATED_ABOVE_TARGET');
  const coreFailed = coreTotal - coreMet;
  const effectivePercent = provisionalPercent ?? conclusivePercent ?? 0;
  let hiringSignal: HiringSignal;
  if (conclusiveCount === 0) {
    hiringSignal = inconclusiveWithRiskCount > 0
      ? {
          key: 'NEEDS_PREP',
          label: 'Cần củng cố thêm',
          description: 'Chưa kết luận đủ lượt nhưng đã ghi nhận lỗi hoặc thiếu sót ở nội dung đã hỏi.',
          tone: 'bg-orange-100/90 text-orange-900 border-orange-200/80 dark:bg-orange-500/20 dark:text-orange-200',
        }
      : {
          key: 'INCOMPLETE',
          label: 'Chưa đủ dữ liệu đánh giá',
          description: 'Cần thêm câu trả lời để kết luận chính xác mức độ sẵn sàng.',
          tone: 'bg-slate-100 text-slate-700 border-slate-200/80 dark:bg-muted dark:text-muted-foreground',
        };
  } else if (
    coreFailed === 0 && coreRiskCount === 0 && inconclusiveWithRiskCount === 0
    && coveragePercent >= 80 && effectivePercent >= 90 && hasAbove && hintedStrongCount === 0
  ) {
    hiringSignal = {
      key: 'STRONG_HIRE',
      label: 'Rất sẵn sàng phỏng vấn',
      description: 'Đáp ứng toàn bộ mục tiêu cốt lõi và có minh chứng vượt chuẩn mở rộng.',
      tone: 'bg-emerald-100 text-emerald-900 border-emerald-300/80 dark:bg-emerald-500/20 dark:text-emerald-200',
    };
  } else if (
    coreFailed === 0 && coreRiskCount === 0 && inconclusiveWithRiskCount === 0
    && coveragePercent >= 70 && effectivePercent >= 80 && hintedStrongCount === 0
  ) {
    hiringSignal = {
      key: 'HIRE',
      label: 'Sẵn sàng phỏng vấn',
      description: 'Các mục tiêu cốt lõi đã kiểm tra đều đạt yêu cầu độc lập theo JD.',
      tone: 'bg-emerald-50 text-emerald-800 border-emerald-200/80 dark:bg-emerald-500/15 dark:text-emerald-200',
    };
  } else if (effectivePercent >= 55 && coreFailed === 0 && coreRiskCount === 0) {
    hiringSignal = {
      key: 'BORDERLINE',
      label: 'Tiềm năng — cần rà thêm',
      description: hintedStrongCount > 0
        ? 'Bạn đã nắm hướng giải nhưng còn nội dung cần dùng gợi ý — hãy luyện lại độc lập.'
        : inconclusiveWithRiskCount > 0 || coveragePercent < 70
          ? 'Phần đã kết luận khá ổn nhưng còn nội dung chưa đủ lượt hoặc có dấu hiệu thiếu sót.'
          : 'Đạt kỹ năng cốt lõi nhưng còn điểm bổ trợ cần cải thiện.',
      tone: 'bg-amber-50 text-amber-900 border-amber-200/80 dark:bg-amber-500/15 dark:text-amber-200',
    };
  } else {
    hiringSignal = {
      key: 'NEEDS_PREP',
      label: 'Cần ôn thêm trước khi ứng tuyển',
      description: coreFailed > 0 || coreRiskCount > 0
        ? 'Còn kỹ năng cốt lõi chưa đạt hoặc có dấu hiệu yếu — ưu tiên ôn kỹ nhóm này trước.'
        : 'Tỷ lệ đạt phiên này còn thấp — nên xem lại đáp án mẫu và làm lượt luyện tập mới.',
      tone: 'bg-orange-100/90 text-orange-900 border-orange-200/80 dark:bg-orange-500/20 dark:text-orange-200',
    };
  }

  const byMode = new Map<string, { total: number; strong: number; weak: number; partial: number }>();
  for (const item of questions) {
    const mode = item.turn.mode;
    if (!mode) continue;
    const entry = byMode.get(mode) ?? { total: 0, strong: 0, weak: 0, partial: 0 };
    entry.total++;
    if (item.status === 'strong') entry.strong++;
    else if (item.status === 'weak') entry.weak++;
    else entry.partial++;
    byMode.set(mode, entry);
  }
  const modeBreakdown: ModeBreakdownItem[] = Array.from(byMode.entries())
    .sort((a, b) => {
      const idxA = MODE_DISPLAY_ORDER.indexOf(a[0] as typeof MODE_DISPLAY_ORDER[number]);
      const idxB = MODE_DISPLAY_ORDER.indexOf(b[0] as typeof MODE_DISPLAY_ORDER[number]);
      return (idxA === -1 ? 99 : idxA) - (idxB === -1 ? 99 : idxB);
    })
    .map(([mode, stats]) => {
      const decided = stats.strong + stats.weak;
      return {
        mode,
        label: modeDisplayLabels[mode] ?? mode,
        ...stats,
        passRate: decided > 0 ? Math.round((stats.strong / decided) * 100) : null,
      };
    });

  return {
    coverage,
    weightedReadiness,
    hiringSignal,
    modeBreakdown,
    skills,
    questions,
    coaching,
    strongSkillCount: skills.filter(skill => skill.status === 'strong').length,
    weakSkillCount: skills.filter(skill => skill.status === 'weak').length,
    partialSkillCount: skills.filter(skill => skill.status === 'partial').length,
    assessedCount: interviewedObjectives.filter(objective => ['strong', 'weak'].includes(assessmentStatus(objective.assessment))).length,
    achievedCount: interviewedObjectives.filter(objective => assessmentStatus(objective.assessment) === 'strong').length,
    strengths: uniqueFindings(interviewedObjectives.flatMap(objective => objective.strengths)),
    weaknesses: uniqueFindings(interviewedObjectives.flatMap(objective => objective.weaknesses)),
    // Global recommendations also include untouched objectives in the plan.
    recommendations: uniqueFindings(interviewedObjectives.flatMap(objective => objective.study_recommendations ?? [])),
  };
}

export type ResultData = ReturnType<typeof buildResult>;
