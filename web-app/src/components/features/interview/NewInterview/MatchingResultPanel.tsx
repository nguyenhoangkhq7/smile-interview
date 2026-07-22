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

  return (
    <div className={`overflow-hidden rounded-lg border ${config.bg} bg-white shadow-sm`}>
      <div className={`flex flex-wrap items-center justify-between gap-2 border-b px-3.5 py-2.5 ${config.bg}`}>
        <div className={`flex items-center gap-2 ${config.text}`}>
          {config.icon}
          <strong className="text-sm text-foreground">{item.criteria_name}</strong>
        </div>
        <div className="flex items-center gap-2">
          {item.weight_used !== undefined && (
            <span className="rounded bg-white/60 px-1.5 py-0.5 text-[10px] text-muted-foreground border border-black/5">
              Hệ số: <b>{item.weight_used}</b>
              {item.score_contribution !== undefined && <> | Điểm: <b>{item.score_contribution}</b></>}
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
    assessment.evidenceItems || [],
    assessment.additionalEvidenceItems || [],
  );
  const keywords = keywordMetadata ?? { matching_skills: derivedKeywords.matchingSkills, variation_skills: derivedKeywords.variationSkills, missing_skills: derivedKeywords.missingSkills };

  const getSectionName = useCallback((key: string) => {
    const names: Record<string, string> = {
      cs_fundamentals: 'Kiến thức Khoa học Máy tính cốt lõi',
      tech_stack_alignment: 'Mức độ tương thích Tech Stack',
      project_technical_depth: 'Chiều sâu kỹ thuật trong các dự án',
      engineering_practices: 'Quy trình và Thực hành Kỹ nghệ',
      experience_evaluation: 'Đánh giá kinh nghiệm làm việc',
      education_and_certifications: 'Đánh giá học vấn & chứng chỉ',
    };
    return names[key] || key.replace(/_/g, ' ').toUpperCase();
  }, []);

  const filteredEvidence = (assessment.evidenceItems as Criterion[])?.filter((i) =>
    criteriaFilter === 'all' || i.status === criteriaFilter
  ) || [];
  const filteredAdditional = (assessment.additionalEvidenceItems as Criterion[])?.filter((i) =>
    criteriaFilter === 'all' || i.status === criteriaFilter
  ) || [];

  return (
    <div className="space-y-6">
      {}
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

      {}
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

      {}
      {activeView === 'ai-cards' && (
        <div className="space-y-8">
          {}
          <div className="flex flex-wrap justify-center gap-12">
            <ScoreRing score={assessment.competencyFitScore} label="Competency Fit Score" color="#ea580c" />
            <ScoreRing score={assessment.technicalDepthScore} label="Technical Depth Score" color="#7c3aed" />
          </div>

          {}
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

          {}
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

          {}
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

            {filteredEvidence.length > 0 && (
              <div className="mb-6">
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">Must Have</p>
                <div className="space-y-2">{filteredEvidence.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
            {filteredAdditional.length > 0 && (
              <div>
                <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">Prefer to Have</p>
                <div className="space-y-2">{filteredAdditional.map((item, i) => <CriterionItem key={i} item={item} />)}</div>
              </div>
            )}
          </div>

          {}
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
