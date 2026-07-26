'use client';


import { CheckCircle, AlertCircle, XCircle, RefreshCw } from 'lucide-react';
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
  const config = {
    matched: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Matched', icon: <CheckCircle size={14} /> },
    weak:    { bg: 'bg-amber-50 border-amber-200',   text: 'text-amber-700',   label: 'Weak',    icon: <AlertCircle size={14} /> },
    missing: { bg: 'bg-red-50 border-red-200',       text: 'text-red-700',     label: 'Missing', icon: <XCircle size={14} /> },
  }[item.status as 'matched' | 'weak' | 'missing'] ?? {
    bg: 'bg-slate-50 border-slate-200', text: 'text-slate-600', label: item.status, icon: <AlertCircle size={14} />,
  };

  const importanceBadge = item.importance === 'PREFERRED' ? (
    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 border border-purple-200">
      Ưu tiên (Nice-to-have)
    </span>
  ) : item.importance === 'NOT_APPLICABLE' ? (
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
      <div className="space-y-2 p-3.5 text-xs">
        {item.jd_requirement && (
          <div>
            <p className="mb-1 font-bold text-muted-foreground">Yêu cầu tuyển dụng (JD):</p>
            <div className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-foreground">{item.jd_requirement}</div>
          </div>
        )}
        {item.cv_evidence && (
          <div>
            <p className="mb-1 font-bold text-muted-foreground">Minh chứng trong CV:</p>
            <div className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-foreground">{item.cv_evidence}</div>
          </div>
        )}
        {item.reasoning && (
          <div>
            <p className="mb-1 font-bold text-muted-foreground">Phân tích & Đánh giá của AI:</p>
            <p className="border-l-2 pl-2.5 italic text-foreground/80" style={{ borderColor: 'currentColor' }}>{item.reasoning}</p>
          </div>
        )}
      </div>
    </div>
  );
}


export function MatchingResultPanel({
  assessment, roleTitle, analyzing: _analyzing, generating,
  rawCvText, rawJdText, cvDisplayName, jdDisplayName, keywordMetadata,
  criteriaFilter, activeView, onCriteriaFilter, onActiveView,
  onRefreshAssessment, onReset, onContinue,
}: Props) {
  const derivedKeywords = extractKeywordsFromEvaluation(
    assessment.mustHaveEvidenceItems || assessment.evidenceItems || [],
    assessment.preferToHaveEvidenceItems || assessment.additionalEvidenceItems || [],
  );
  const keywords = keywordMetadata ?? { matching_skills: derivedKeywords.matchingSkills, variation_skills: derivedKeywords.variationSkills, missing_skills: derivedKeywords.missingSkills };

  const getSectionName = useCallback((key: string) => {
    const names: Record<string, string> = {
      overall_match_score: 'Độ Phù Hợp Tổng Thể',
      must_have: 'Tiêu Chí Bắt Buộc (Must-Have)',
      prefer_to_have: 'Tiêu Chí Ưu Tiên (Prefer-to-Have)',
      eligibility: 'Điều Kiện Cần (Gate Check)',
    };
    return names[key] || key.replace(/_/g, ' ').toUpperCase();
  }, []);

  const sb = assessment.scoreBreakdown || {};
  const mustHaveScore = sb.raw_must_have_score ?? sb.must_have_score ?? sb.mustHaveScore ?? assessment.competencyFitScore ?? 0;
  const preferToHaveScore = sb.raw_prefer_to_have_score ?? sb.prefer_to_have_score ?? sb.preferToHaveScore ?? assessment.technicalDepthScore ?? 0;

  const mustHaveItems = (assessment.mustHaveEvidenceItems || assessment.evidenceItems || []) as Criterion[];
  const preferToHaveItems = (assessment.preferToHaveEvidenceItems || assessment.additionalEvidenceItems || []) as Criterion[];

  const allItems = [
    ...mustHaveItems,
    ...preferToHaveItems,
  ];

  const mustHaveCriteria = allItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isMust = imp === 'REQUIRED' || imp === 'MUST_HAVE' || (!imp && mustHaveItems.includes(i));
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    const passesFilter = criteriaFilter === 'all' || i.status === criteriaFilter;
    return isMust && !isNotApp && passesFilter;
  });

  const preferToHaveCriteria = allItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isPrefer = imp === 'PREFERRED' || imp === 'PREFER_TO_HAVE' || (!imp && preferToHaveItems.includes(i));
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    const passesFilter = criteriaFilter === 'all' || i.status === criteriaFilter;
    return isPrefer && !isNotApp && passesFilter;
  });

  const notApplicableCriteria = allItems.filter((i) => {
    const imp = i.importance?.toUpperCase();
    const isNotApp = imp === 'NOT_APPLICABLE' || i.status === 'not_applicable';
    const passesFilter = criteriaFilter === 'all' || i.status === criteriaFilter;
    return isNotApp && passesFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-2xl font-extrabold text-foreground">Kết quả phân tích độ tương thích</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Dành cho vị trí <strong>{roleTitle}</strong>
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

      {/* Switch view */}
      {(rawCvText || rawJdText) && (
        <div className="flex justify-center">
          <div className="inline-flex rounded-xl bg-muted p-1 gap-1">
            {(['ai-cards', 'visual-match'] as ActiveView[]).map((v) => (
              <button key={v} type="button" onClick={() => onActiveView(v)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all ${activeView === v ? 'bg-card text-foreground shadow' : 'text-muted-foreground hover:text-foreground'}`}
              >
                {v === 'ai-cards' ? '🤖 AI Analysis Cards' : '🔍 Visual Skill Match'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* AI Cards View */}
      {activeView === 'ai-cards' && (
        <div className="space-y-8">
          {/* Score Rings */}
          <div className="flex flex-wrap justify-center gap-12">
            <ScoreRing score={mustHaveScore} label="Must-Have Score (80%)" color="#ea580c" />
            <ScoreRing score={preferToHaveScore} label="Prefer-To-Have Score (20%)" color="#7c3aed" />
          </div>

          {/* Badges overview */}
          <div className="flex flex-wrap justify-center gap-2">
            {[
              { label: 'Role', value: getDisplayRoleTitle(assessment.roleTypeDetected) },
              { label: 'Level', value: assessment.candidateLevel },
              { label: 'YoE',  value: assessment.yearsOfExperienceEstimate },
              { label: 'Match', value: assessment.matchLevel },
            ].filter((b) => b.value).map((b) => (
              <Badge key={b.label} variant="secondary" className="text-xs">
                <span className="font-normal text-muted-foreground mr-1">{b.label}:</span>
                {b.value}
              </Badge>
            ))}
          </div>

          {/* Gate Checks */}
          {assessment.eligibility?.gate_checks && assessment.eligibility.gate_checks.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-muted-foreground">Kiểm tra điều kiện</h3>
              <div className="space-y-2">
                {(assessment.eligibility.gate_checks as GateCheck[]).map((check, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    {check.passed
                      ? <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                      : <XCircle size={14} className="text-red-500 shrink-0" />}
                    <span>{check.description || check.criterion}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Criteria List */}
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-bold text-foreground">Ma trận kỹ năng (Criteria Alignment)</h3>
              <div className="flex gap-1">
                {(['all', 'matched', 'weak', 'missing'] as CriteriaFilter[]).map((f) => (
                  <button key={f} type="button" onClick={() => onCriteriaFilter(f)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${criteriaFilter === f ? 'bg-brand-orange text-white' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
                  >
                    {f === 'all' ? 'Tất cả' : f}
                  </button>
                ))}
              </div>
            </div>

            {mustHaveCriteria.length > 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <span className="size-2 rounded-full bg-blue-600 inline-block" />
                  Must Have (Bắt buộc)
                </p>
                <div className="space-y-2">{mustHaveCriteria.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
            {preferToHaveCriteria.length > 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                  <span className="size-2 rounded-full bg-purple-600 inline-block" />
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

          {/* Section Wise Feedback */}
          {assessment.sectionWiseFeedback && Object.keys(assessment.sectionWiseFeedback).length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="mb-4 font-bold text-foreground">Phân tích từng phần</h3>
              <div className="space-y-4">
                {Object.entries(assessment.sectionWiseFeedback).map(([key, val]) => (
                  <div key={key}>
                    <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-foreground">{getSectionName(key)}</p>
                    <p className="text-sm leading-relaxed text-foreground/80">{typeof val === 'object' ? JSON.stringify(val) : String(val || '')}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actionable Suggestions */}
          {((assessment.topPriorityImprovements?.length ?? 0) > 0 || (assessment.actionableImprovementSuggestions?.length ?? 0) > 0) && (
            <div className="rounded-xl border border-brand-orange/20 bg-brand-orange/5 p-5">
              <h3 className="mb-4 font-bold text-foreground">Gợi ý cải thiện ưu tiên</h3>
              <div className="space-y-3">
                {((assessment.topPriorityImprovements?.length ?? 0) > 0
                  ? assessment.topPriorityImprovements!
                  : assessment.actionableImprovementSuggestions || []
                ).slice(0, 5).map((item, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-orange text-xs font-bold text-white">{i + 1}</span>
                    <p className="text-foreground/80">{typeof item === 'string' ? item : (item as Improvement).suggestion || (item as Improvement).description || JSON.stringify(item)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {}
      {activeView === 'visual-match' && rawCvText && rawJdText && (
        <div className="space-y-6">
          {}
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

      {}
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
