'use client';

import {
  CheckCircle,
  AlertCircle,
  XCircle,
  RefreshCw,
  BarChart2,
  Lock,
  ShieldCheck,
  Star,
  Cpu,
  Layers,
  ClipboardList,
  TrendingUp,
  Lightbulb,
  AlignLeft,
  Zap,
  Target,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import HighlightedText from '@/components/HighlightedText';
import type { AssessmentResponse } from '@/services/cvJdMatching';
import type { CriteriaFilter, ActiveView } from '@/hooks/useNewInterview';
import { extractKeywordsFromEvaluation, getDisplayRoleTitle } from '@/hooks/useNewInterview';
import { useCallback } from 'react';

interface KeywordMetadata {
  matching_skills?: string[];
  variation_skills?: string[];
  missing_skills?: string[];
  matchingSkills?: string[];
  variationSkills?: string[];
  missingSkills?: string[];
  [key: string]: unknown;
}

interface Criterion {
  status: string;
  criteria_name: string;
  importance?: string;
  weight_used?: number;
  score_contribution?: number;
  jd_requirement?: string;
  cv_evidence?: string;
  reasoning?: string;
}

interface GateCheck {
  passed: boolean;
  description?: string;
  criterion?: string;
}

interface Improvement {
  suggestion?: string;
  description?: string;
}

interface Props {
  assessment: AssessmentResponse;
  roleTitle: string;
  analyzing: boolean;
  generating: boolean;
  rawCvText: string | null;
  rawJdText: string | null;
  cvDisplayName: string;
  jdDisplayName: string;
  keywordMetadata: KeywordMetadata | null | undefined;
  criteriaFilter: CriteriaFilter;
  activeView: ActiveView;
  onCriteriaFilter: (v: CriteriaFilter) => void;
  onActiveView: (v: ActiveView) => void;
  onRefreshAssessment: () => void;
  onReset: () => void;
  onContinue: () => void;
}


function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const radius = 50;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative size-32">
        <svg className="size-full -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor" className="text-muted/40" strokeWidth="10" />
          <circle cx="60" cy="60" r={radius} fill="none" stroke={color} strokeWidth="10"
            strokeDasharray={circ} strokeDashoffset={offset}
            strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-extrabold text-foreground">{score}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
      </div>
      <span className="text-center text-xs font-semibold text-muted-foreground">{label}</span>
    </div>
  );
}


function CriterionItem({ item }: { item: Criterion }) {
  const normalizedStatus = (item.status || '').toLowerCase();

  let configKey: 'matched' | 'weak' | 'missing' = 'matched';
  if (normalizedStatus === 'matched' || normalizedStatus === 'pass' || normalizedStatus === 'passed') {
    configKey = 'matched';
  } else if (normalizedStatus === 'weak') {
    configKey = 'weak';
  } else if (normalizedStatus === 'missing' || normalizedStatus === 'fail' || normalizedStatus === 'failed') {
    configKey = 'missing';
  }

  const isPassFailLabel = normalizedStatus === 'pass' || normalizedStatus === 'passed' || normalizedStatus === 'fail' || normalizedStatus === 'failed';

  const config = {
    matched: {
      bg: 'bg-emerald-50 border-emerald-200',
      text: 'text-emerald-700',
      label: isPassFailLabel ? 'Đạt (Pass)' : 'Khớp (Matched)',
      icon: <CheckCircle size={14} />,
    },
    weak: {
      bg: 'bg-amber-50 border-amber-200',
      text: 'text-amber-700',
      label: 'Còn yếu (Weak)',
      icon: <AlertCircle size={14} />,
    },
    missing: {
      bg: 'bg-red-50 border-red-200',
      text: 'text-red-700',
      label: isPassFailLabel ? 'Không đạt (Fail)' : 'Thiếu (Missing)',
      icon: <XCircle size={14} />,
    },
  }[configKey];

  const importanceUpper = (item.importance || '').toUpperCase();
  const importanceBadge = importanceUpper === 'GATE' ? (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 border border-amber-300">
      Điều kiện tối thiểu
    </span>
  ) : importanceUpper === 'PREFERRED' || importanceUpper === 'PREFER_TO_HAVE' ? (
    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 border border-purple-200">
      Ưu tiên (Nice-to-have)
    </span>
  ) : importanceUpper === 'NOT_APPLICABLE' ? (
    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 border border-slate-200">
      Không áp dụng
    </span>
  ) : (
    <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 border border-blue-200">
      Bắt buộc (Must-have)
    </span>
  );

  return (
    <div className={`overflow-hidden rounded-lg border ${config.bg} bg-white shadow-sm`}>
      <div className={`flex flex-wrap items-center justify-between gap-2 border-b px-3.5 py-2.5 ${config.bg}`}>
        <div className={`flex items-center gap-2 ${config.text}`}>
          {config.icon}
          <strong className="text-sm text-foreground">{item.criteria_name}</strong>
        </div>
        <div className="flex items-center gap-2">
          {importanceBadge}
          {item.weight_used !== undefined && item.weight_used !== null && (
            <span className="rounded bg-white/60 px-1.5 py-0.5 text-[10px] text-muted-foreground border border-black/5">
              Hệ số: <b>{item.weight_used}</b>
              {item.score_contribution !== undefined && item.score_contribution !== null && <> | Điểm: <b>{item.score_contribution}</b></>}
            </span>
          )}
          <Badge variant="outline" className={`text-[10px] font-bold ${config.text} border-current`}>{config.label}</Badge>
        </div>
      </div>
      <div className="space-y-3 p-3.5 text-xs">
        {item.jd_requirement && (
          <div>
            <p className="mb-1.5 font-bold text-muted-foreground uppercase tracking-wide text-[10px]">Yêu cầu tuyển dụng (JD)</p>
            <div className="rounded border border-slate-100 bg-slate-50 px-2.5 py-2 text-foreground leading-relaxed">{item.jd_requirement}</div>
          </div>
        )}
        {item.cv_evidence && (
          <div>
            <p className="mb-1.5 font-bold text-muted-foreground uppercase tracking-wide text-[10px]">Minh chứng trong CV</p>
            <div className="rounded border border-slate-100 bg-slate-50 px-2.5 py-2 text-foreground leading-relaxed">{item.cv_evidence}</div>
          </div>
        )}
        {item.reasoning && (
          <div>
            <p className="mb-1.5 font-bold text-muted-foreground uppercase tracking-wide text-[10px]">Phân tích & Đánh giá của AI</p>
            <p className="border-l-2 border-slate-300 pl-2.5 italic text-foreground/80 leading-relaxed">{item.reasoning}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/** Map raw backend eligibility string to human-readable Vietnamese */
function formatEligibility(raw: string): { label: string; color: 'green' | 'red' | 'amber' } {
  const upper = raw.toUpperCase();
  if (upper === 'ELIGIBLE' || upper === 'ELIGIBILITY' || upper === 'PASS') {
    return { label: 'Đủ điều kiện', color: 'green' };
  }
  if (upper === 'NOT_ELIGIBLE' || upper === 'NOT_ELIGIBILITY' || upper === 'FAIL' || upper === 'FAILED') {
    return { label: 'Chưa đủ điều kiện', color: 'red' };
  }
  if (upper === 'CONDITIONAL' || upper === 'PARTIAL') {
    return { label: 'Đủ điều kiện có điều kiện', color: 'amber' };
  }
  return { label: raw, color: 'amber' };
}

/** Map sectionWiseFeedback keys to display names with icons */
const SECTION_META: Record<string, { label: string; icon: React.ReactNode }> = {
  tech_stack_alignment: { label: 'Kỹ năng công nghệ (Tech Stack)', icon: <Cpu size={14} /> },
  cs_fundamentals: { label: 'Kiến thức nền tảng (CS Fundamentals)', icon: <BarChart2 size={14} /> },
  overall_match_score: { label: 'Độ phù hợp tổng thể', icon: <Star size={14} /> },
  must_have: { label: 'Tiêu chí bắt buộc (Must-Have)', icon: <ClipboardList size={14} /> },
  prefer_to_have: { label: 'Tiêu chí ưu tiên (Prefer-to-Have)', icon: <TrendingUp size={14} /> },
  eligibility: { label: 'Điều kiện tối thiểu (Eligibility Gate)', icon: <ShieldCheck size={14} /> },
  soft_skills: { label: 'Kỹ năng mềm', icon: <Star size={14} /> },
  experience: { label: 'Kinh nghiệm làm việc', icon: <Layers size={14} /> },
};

function getSectionMeta(key: string): { label: string; icon: React.ReactNode } {
  if (SECTION_META[key]) return SECTION_META[key];
  return {
    label: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    icon: <AlignLeft size={14} />,
  };
}

/**
 * Parse raw section feedback text into bullet points.
 * Splits on " | " separators or semicolons followed by capital letters.
 */
function parseSectionText(raw: string): string[] {
  if (!raw) return [];
  // Split on " | " delimiter
  const parts = raw.split(/\s*\|\s*/);
  return parts.map((p) => p.trim()).filter(Boolean);
}


export function MatchingResultPanel({
  assessment, roleTitle, analyzing: _analyzing, generating,
  rawCvText, rawJdText, cvDisplayName, jdDisplayName, keywordMetadata,
  criteriaFilter, activeView, onCriteriaFilter, onActiveView,
  onRefreshAssessment, onReset, onContinue,
}: Props) {
  const gateItems = (assessment.gateEvidenceItems || []) as Criterion[];
  const mustHaveItems = (assessment.mustHaveEvidenceItems || assessment.evidenceItems || []) as Criterion[];
  const preferToHaveItems = (assessment.preferToHaveEvidenceItems || assessment.additionalEvidenceItems || []) as Criterion[];

  const derivedKeywords = extractKeywordsFromEvaluation(
    gateItems,
    mustHaveItems,
    preferToHaveItems,
  );
  const keywords = keywordMetadata ?? { matching_skills: derivedKeywords.matchingSkills, variation_skills: derivedKeywords.variationSkills, missing_skills: derivedKeywords.missingSkills };

  const getSectionName = useCallback((key: string) => {
    return getSectionMeta(key).label;
  }, []);

  const sb = assessment.scoreBreakdown || {};
  const overallScore = sb.final_score ?? sb.overall_match_score ?? sb.overallMatchScore ?? assessment.competencyFitScore ?? 0;
  const mustHaveScore = sb.raw_must_have_score ?? sb.must_have_score ?? sb.mustHaveScore ?? 0;
  const preferToHaveScore = sb.raw_prefer_to_have_score ?? sb.prefer_to_have_score ?? sb.preferToHaveScore ?? 0;

  const mustHaveWeightPct = Math.round(((sb.must_have_weight_ratio ?? sb.mustHaveWeightRatio) || 0.8) * 100);
  const preferToHaveWeightPct = Math.round(((sb.prefer_to_have_weight_ratio ?? sb.preferToHaveWeightRatio) || 0.2) * 100);

  const passesFilter = (item: Criterion) => {
    if (criteriaFilter === 'all') return true;
    const s = (item.status || '').toLowerCase();
    if (criteriaFilter === 'matched') return s === 'matched' || s === 'pass' || s === 'passed';
    if (criteriaFilter === 'weak') return s === 'weak';
    if (criteriaFilter === 'missing') return s === 'missing' || s === 'fail' || s === 'failed';
    return s === criteriaFilter;
  };

  const gateCriteria = gateItems.filter(passesFilter);

  const mustHaveCriteria = mustHaveItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isMust = imp === 'REQUIRED' || imp === 'MUST_HAVE' || (!imp && !gateItems.includes(i) && !preferToHaveItems.includes(i));
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    return isMust && !isNotApp && passesFilter(i);
  });

  const preferToHaveCriteria = preferToHaveItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isPrefer = imp === 'PREFERRED' || imp === 'PREFER_TO_HAVE' || (!imp && preferToHaveItems.includes(i));
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    return isPrefer && !isNotApp && passesFilter(i);
  });

  const allItems = [...gateItems, ...mustHaveItems, ...preferToHaveItems];
  const notApplicableCriteria = allItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    return isNotApp && passesFilter(i);
  });

  const legacyGateChecks = typeof assessment.eligibility === 'object' && assessment.eligibility !== null ? (assessment.eligibility as { gate_checks?: GateCheck[] }).gate_checks : undefined;
  const eligibilityStatusStr = typeof assessment.eligibility === 'string' ? assessment.eligibility : undefined;
  const eligibilityFormatted = eligibilityStatusStr ? formatEligibility(eligibilityStatusStr) : null;

  // Determine overall score color
  const scoreColor = overallScore >= 70 ? '#16a34a' : overallScore >= 50 ? '#ea580c' : '#dc2626';

  // Determine match level badge color
  const matchLevelBadgeClass = (() => {
    const ml = (assessment.matchLevel || '').toLowerCase();
    if (ml.includes('high') || ml.includes('cao') || ml.includes('tốt')) return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    if (ml.includes('medium') || ml.includes('moderate') || ml.includes('trung') || ml.includes('vừa') || ml.includes('khớp')) return 'bg-sky-100 text-sky-800 border-sky-200';
    return 'bg-red-100 text-red-800 border-red-200';
  })();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-2xl font-extrabold text-foreground">Kết quả phân tích độ tương thích</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Vị trí ứng tuyển: <strong>{roleTitle}</strong>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1.5">
            <span className={`size-2 rounded-full ${assessment.cached ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            {assessment.cached ? 'Kết quả từ Cache' : 'Phân tích mới'}
          </Badge>
          {assessment.cached && (
            <Button size="sm" variant="outline" onClick={onRefreshAssessment}
              className="border-brand-orange text-brand-orange hover:bg-brand-orange/5">
              <RefreshCw size={12} className="mr-1.5" /> Đánh giá lại
            </Button>
          )}
        </div>
      </div>

      {/* Switch view — lock Visual Match */}
      {(rawCvText || rawJdText) && (
        <div className="flex justify-center">
          <div className="inline-flex rounded-xl bg-muted p-1 gap-1">
            <button
              type="button"
              onClick={() => onActiveView('ai-cards')}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all flex items-center gap-2 ${activeView === 'ai-cards' ? 'bg-card text-foreground shadow' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <BarChart2 size={15} />
              AI Analysis Cards
            </button>
            <button
              type="button"
              disabled
              title="Tính năng này đang được phát triển"
              className="rounded-lg px-4 py-2 text-sm font-semibold flex items-center gap-2 text-muted-foreground/50 cursor-not-allowed opacity-60 select-none"
            >
              <Lock size={13} />
              Visual Skill Match
              <span className="rounded bg-slate-200 px-1 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-500 ml-0.5">Sắp ra mắt</span>
            </button>
          </div>
        </div>
      )}

      {/* AI Cards View */}
      {activeView === 'ai-cards' && (
        <div className="space-y-8">

          {/* ─── Score Rings + Info Cards ─── */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            {/* Score rings */}
            <div className="flex flex-wrap justify-center gap-8 md:gap-14 mb-6">
              <ScoreRing score={overallScore} label="Tổng điểm phù hợp" color={scoreColor} />
              <ScoreRing score={mustHaveScore} label={`Must-Have (${mustHaveWeightPct}%)`} color="#2563eb" />
              <ScoreRing score={preferToHaveScore} label={`Prefer-To-Have (${preferToHaveWeightPct}%)`} color="#7c3aed" />
            </div>

            {/* Info pills */}
            <div className="border-t border-border pt-4">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground text-center">Thông tin đánh giá</p>
              <div className="flex flex-wrap justify-center gap-2">
                {assessment.roleTypeDetected && (
                  <div className="flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1.5 text-xs">
                    <span className="font-medium text-muted-foreground">Vị trí:</span>
                    <span className="font-semibold text-foreground">{getDisplayRoleTitle(assessment.roleTypeDetected)}</span>
                  </div>
                )}
                {assessment.candidateLevel && (
                  <div className="flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1.5 text-xs">
                    <span className="font-medium text-muted-foreground">Cấp độ:</span>
                    <span className="font-semibold text-foreground">{assessment.candidateLevel}</span>
                  </div>
                )}
                {assessment.yearsOfExperienceEstimate && (
                  <div className="flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1.5 text-xs">
                    <span className="font-medium text-muted-foreground">Kinh nghiệm:</span>
                    <span className="font-semibold text-foreground">{assessment.yearsOfExperienceEstimate}</span>
                  </div>
                )}
                {assessment.matchLevel && (
                  <div className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold ${matchLevelBadgeClass}`}>
                    <span className="font-medium opacity-70">Mức độ phù hợp:</span>
                    <span>{assessment.matchLevel}</span>
                  </div>
                )}
                {eligibilityFormatted && (
                  <div className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold ${eligibilityFormatted.color === 'green'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : eligibilityFormatted.color === 'red'
                        ? 'bg-red-50 border-red-200 text-red-800'
                        : 'bg-amber-50 border-amber-200 text-amber-800'
                    }`}>
                    <ShieldCheck size={11} />
                    <span>{eligibilityFormatted.label}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ─── Eligibility Gate Section ─── */}
          {((gateItems && gateItems.length > 0) || (legacyGateChecks && legacyGateChecks.length > 0)) && (
            <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/60 to-orange-50/30 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold uppercase tracking-wide text-amber-900 flex items-center gap-2">
                  <ShieldCheck size={16} className="text-amber-600" />
                  Tiêu chí điều kiện tối thiểu (Eligibility Gate)
                </h3>
                {eligibilityFormatted && (
                  <span className={`rounded-full px-3 py-1 text-xs font-bold border ${eligibilityFormatted.color === 'green'
                      ? 'bg-emerald-100 border-emerald-300 text-emerald-800'
                      : eligibilityFormatted.color === 'red'
                        ? 'bg-red-100 border-red-300 text-red-800'
                        : 'bg-amber-100 border-amber-300 text-amber-800'
                    }`}>
                    {eligibilityFormatted.label}
                  </span>
                )}
              </div>

              {gateItems.length > 0 ? (
                <div className="space-y-2">
                  {gateItems.map((item, i) => (
                    <CriterionItem key={i} item={item} />
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {legacyGateChecks!.map((check, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {check.passed
                        ? <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                        : <XCircle size={14} className="text-red-500 shrink-0" />}
                      <span>{check.description || check.criterion}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ─── Criteria Matrix ─── */}
          <div>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-bold text-foreground">Ma trận kỹ năng (Criteria Alignment)</h3>
              <div className="flex gap-1 flex-wrap">
                {(['all', 'matched', 'weak', 'missing'] as CriteriaFilter[]).map((f) => (
                  <button key={f} type="button" onClick={() => onCriteriaFilter(f)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${criteriaFilter === f ? 'bg-brand-orange text-white' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
                  >
                    {f === 'all' ? 'Tất cả' : f === 'matched' ? 'Đạt / Khớp' : f === 'weak' ? 'Còn yếu' : 'Thiếu / Chưa đạt'}
                  </button>
                ))}
              </div>
            </div>

            {gateCriteria.length > 0 && gateItems.length === 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <ShieldCheck size={13} className="text-amber-500" />
                  Điều kiện tối thiểu
                </p>
                <div className="space-y-2">{gateCriteria.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}

            {mustHaveCriteria.length > 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <ClipboardList size={13} className="text-blue-600" />
                  Must Have (Bắt buộc)
                </p>
                <div className="space-y-2">{mustHaveCriteria.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
            {preferToHaveCriteria.length > 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <TrendingUp size={13} className="text-purple-600" />
                  Prefer to Have (Điểm cộng / Ưu tiên)
                </p>
                <div className="space-y-2">{preferToHaveCriteria.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
            {notApplicableCriteria.length > 0 && (
              <div>
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <span className="size-2 rounded-full bg-slate-400 inline-block" />
                  Không áp dụng
                </p>
                <div className="space-y-2">{notApplicableCriteria.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
          </div>

          {/* ─── Section-wise Feedback ─── */}
          {assessment.sectionWiseFeedback && Object.keys(assessment.sectionWiseFeedback).length > 0 && (
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <div className="border-b border-border bg-muted/40 px-5 py-3.5">
                <h3 className="font-bold text-foreground flex items-center gap-2">
                  <BarChart2 size={16} className="text-brand-orange" />
                  Phân tích từng phần
                </h3>
              </div>
              <div className="divide-y divide-border">
                {Object.entries(assessment.sectionWiseFeedback).map(([key, val]) => {
                  const meta = getSectionMeta(key);
                  const rawText = typeof val === 'object' ? JSON.stringify(val) : String(val || '');
                  const bullets = parseSectionText(rawText);

                  return (
                    <div key={key} className="px-5 py-4">
                      {/* Section header */}
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-brand-orange">{meta.icon}</span>
                        <p className="text-xs font-bold uppercase tracking-wider text-foreground">{meta.label}</p>
                      </div>

                      {/* Content: bullet list if multiple parts, else paragraph */}
                      {bullets.length > 1 ? (
                        <ul className="space-y-2">
                          {bullets.map((bullet, bi) => (
                            <li key={bi} className="flex items-start gap-2 text-sm text-foreground/80 leading-relaxed">
                              <span className="mt-1 size-1.5 rounded-full bg-brand-orange/60 shrink-0 inline-block" />
                              <span>{bullet}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-foreground/80 leading-relaxed">{rawText}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ─── Actionable Suggestions (Quick Wins & Skill Gaps) ─── */}
          {((assessment.quickWins?.length ?? 0) > 0 || (assessment.skillGaps?.length ?? 0) > 0) ? (
            <div className="space-y-6">
              {/* Quick Wins Card */}
              {(assessment.quickWins?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 overflow-hidden shadow-sm">
                  <div className="border-b border-emerald-200/60 bg-emerald-100/50 px-5 py-3.5 flex items-center justify-between">
                    <h3 className="font-bold text-emerald-900 flex items-center gap-2">
                      <Zap size={16} className="text-emerald-600 fill-emerald-500" />
                      Gợi ý cải thiện nhanh (Quick Wins)
                    </h3>
                    <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-300 text-[11px] font-semibold">
                      {assessment.quickWins!.length} điểm cộng dễ nâng điểm
                    </Badge>
                  </div>
                  <div className="p-5 divide-y divide-emerald-200/50">
                    {assessment.quickWins!.map((item, i) => (
                      <div key={i} className="py-3.5 first:pt-0 last:pb-0 flex items-start gap-3.5 text-sm">
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white mt-0.5 shadow-sm">
                          {item.priority || i + 1}
                        </span>
                        <div className="space-y-1">
                          <p className="font-bold text-emerald-950 text-sm">{item.criteria_name || item.criteriaName}</p>
                          <p className="text-emerald-800/90 leading-relaxed text-xs font-normal">{item.actionable_advice || item.actionableAdvice || item.suggestion}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Skill Gaps Card */}
              {(assessment.skillGaps?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/40 overflow-hidden shadow-sm">
                  <div className="border-b border-amber-200/60 bg-amber-100/50 px-5 py-3.5 flex items-center justify-between">
                    <h3 className="font-bold text-amber-900 flex items-center gap-2">
                      <Target size={16} className="text-amber-600" />
                      Lỗ hổng kỹ năng cần bổ sung (Skill Gaps)
                    </h3>
                    <Badge variant="outline" className="bg-amber-50 text-amber-800 border-amber-300 text-[11px] font-semibold">
                      {assessment.skillGaps!.length} kỹ năng thiếu
                    </Badge>
                  </div>
                  <div className="p-5 divide-y divide-amber-200/50">
                    {assessment.skillGaps!.map((item, i) => (
                      <div key={i} className="py-3.5 first:pt-0 last:pb-0 flex items-start gap-3.5 text-sm">
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-amber-600 text-xs font-bold text-white mt-0.5 shadow-sm">
                          {item.priority || i + 1}
                        </span>
                        <div className="space-y-1">
                          <p className="font-bold text-amber-950 text-sm">{item.criteria_name || item.criteriaName}</p>
                          <p className="text-amber-800/90 leading-relaxed text-xs font-normal">{item.actionable_advice || item.actionableAdvice || item.suggestion}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (((assessment.topPriorityImprovements?.length ?? 0) > 0 || (assessment.actionableImprovementSuggestions?.length ?? 0) > 0) && (
            <div className="rounded-xl border border-brand-orange/20 bg-brand-orange/5 overflow-hidden shadow-sm">
              <div className="border-b border-brand-orange/15 bg-brand-orange/10 px-5 py-3.5">
                <h3 className="font-bold text-foreground flex items-center gap-2">
                  <Lightbulb size={16} className="text-brand-orange" />
                  Gợi ý cải thiện ưu tiên
                </h3>
              </div>
              <div className="p-5">
                <div className="space-y-3">
                  {((assessment.topPriorityImprovements?.length ?? 0) > 0
                    ? assessment.topPriorityImprovements!
                    : assessment.actionableImprovementSuggestions || []
                  ).slice(0, 10).map((item, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-orange text-xs font-bold text-white mt-0.5">{i + 1}</span>
                      <p className="text-foreground/80 leading-relaxed">{typeof item === 'string' ? item : (item as Improvement).suggestion || (item as Improvement).description || JSON.stringify(item)}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Visual Match View (locked) */}
      {activeView === 'visual-match' && rawCvText && rawJdText && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            {keywords.matching_skills?.slice(0, 8).map((s: string) => (
              <span key={s} className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">{s}</span>
            ))}
            {keywords.missing_skills?.slice(0, 5).map((s: string) => (
              <span key={s} className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">{s}</span>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">{cvDisplayName}</p>
              <div className="max-h-[500px] overflow-y-auto text-xs leading-relaxed">
                <HighlightedText
                  text={rawCvText}
                  matches={keywords.matching_skills || []}
                  variations={keywords.variation_skills || keywords.variationSkills || []}
                  missing={keywords.missing_skills || []}
                />
              </div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">{jdDisplayName}</p>
              <div className="max-h-[500px] overflow-y-auto text-xs leading-relaxed">
                <HighlightedText
                  text={rawJdText}
                  matches={keywords.matching_skills || []}
                  variations={keywords.variation_skills || keywords.variationSkills || []}
                  missing={keywords.missing_skills || []}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      { }
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <Button variant="outline" onClick={onReset}>Tải lại tài liệu khác</Button>
        <Button
          onClick={onContinue}
          disabled={generating}
          className="bg-brand-orange text-white hover:bg-brand-orange-hover"
        >
          {generating ? 'Đang tạo ngân hàng câu hỏi...' : 'Bắt đầu Phỏng vấn →'}
        </Button>
      </div>
    </div>
  );
}
