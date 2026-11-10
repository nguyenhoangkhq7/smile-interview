'use client';

import React from 'react';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { AnalyzeWithReportResponse, SkillGapResult } from '@/services/cvJdMatching';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { GnnScoreMetric } from '@/components/features/interview/GnnScoreMetric';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  RotateCcw,
  Play,
  Briefcase,
  Quote,
  FileText,
  Sparkles,
} from 'lucide-react';

interface SkillGapResultPanelProps {
  analysis: AnalyzeWithReportResponse;
  roleTitle: string;
  analyzing: boolean;
  startingInterview: boolean;
  onRefresh: () => void;
  onReset: () => void;
  onStartInterview: () => void;
}

function getAlignmentBadge(alignment: SkillGapResult['semantic_alignment']) {
  if (alignment === 'MATCH') {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 font-semibold gap-1">
        <CheckCircle2 size={12} /> MATCH
      </Badge>
    );
  }
  if (alignment === 'PARTIAL') {
    return (
      <Badge className="bg-amber-500/15 text-amber-700 border-amber-500/30 font-semibold gap-1">
        <AlertTriangle size={12} /> PARTIAL (Thay thế)
      </Badge>
    );
  }
  return (
    <Badge className="bg-rose-500/15 text-rose-700 border-rose-500/30 font-semibold gap-1">
      <XCircle size={12} /> MISSING
    </Badge>
  );
}

function getStrategyBadge(strategy: SkillGapResult['suggested_strategy']) {
  switch (strategy) {
    case 'PROBE_DEPTH':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200">
          PROBE_DEPTH (Đào sâu thực chiến)
        </span>
      );
    case 'COMPARE_SUBSTITUTE':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
          COMPARE_SUBSTITUTE (Đối chiếu chuyển giao)
        </span>
      );
    case 'LEARNING_AGILITY':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-200">
          LEARNING_AGILITY (Tư duy thích ứng)
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
          NONE (Đạt chuẩn — Context Anchor)
        </span>
      );
  }
}

export function SkillGapResultPanel({
  analysis,
  roleTitle,
  analyzing,
  startingInterview,
  onRefresh,
  onReset,
  onStartInterview,
}: SkillGapResultPanelProps) {
  const { skills = [], report } = analysis;

  const sortedSkills = [...skills].sort((a, b) => b.priority - a.priority);
  const avgGap =
    skills.length > 0
      ? skills.reduce((acc, s) => acc + s.gap_magnitude, 0) / skills.length
      : 0;
  const overallFitPercent = Math.round(Math.max(0, Math.min(100, (1 - avgGap) * 100)));

  return (
    <div className="space-y-8">
      {/* Header Summary Card */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-border">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-orange">
            <Sparkles size={14} />
            <span>Phân tích kỹ năng</span>
          </div>
          <h2 className="text-2xl font-extrabold text-foreground">
            {roleTitle || 'Phân tích Khoảng trống Kỹ năng CV & JD'}
          </h2>
          <p className="text-xs text-muted-foreground">
            Mã phiên phân tích: <code className="font-mono text-foreground">{analysis.analysis_id}</code>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={analyzing || startingInterview}
            className="gap-1.5"
          >
            <RefreshCw size={14} className={analyzing ? 'animate-spin' : ''} />
            Phân tích lại
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            disabled={analyzing || startingInterview}
            className="gap-1.5"
          >
            <RotateCcw size={14} />
            Đổi CV/JD
          </Button>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <GnnScoreMetric score={report?.matching_score} />
        <div className="rounded-xl border border-border bg-muted/30 p-4 text-center">
          <div className="text-2xl font-black text-brand-orange">{overallFitPercent}%</div>
          <div className="text-[11px] text-muted-foreground font-medium mt-1">Độ khớp năng lực</div>
        </div>
        <div className="rounded-xl border border-border bg-muted/30 p-4 text-center">
          <div className="text-2xl font-bold text-foreground">{report?.total_jd_skills ?? skills.length}</div>
          <div className="text-[11px] text-muted-foreground font-medium mt-1">Tổng kỹ năng JD</div>
        </div>
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
          <div className="text-2xl font-bold text-emerald-600">{report?.matched_count ?? 0}</div>
          <div className="text-[11px] text-emerald-700 font-medium mt-1">MATCH</div>
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-center">
          <div className="text-2xl font-bold text-amber-600">{report?.partial_count ?? 0}</div>
          <div className="text-[11px] text-amber-700 font-medium mt-1">PARTIAL</div>
        </div>
        <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">
            {report?.skills_requiring_probing ??
              skills.filter((s) => s.suggested_strategy !== 'NONE').length}
          </div>
          <div className="text-[11px] text-purple-700 font-medium mt-1">Cần làm rõ trong phỏng vấn</div>
        </div>
      </div>

      {/* Per-Skill Detailed Cards */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-foreground flex items-center gap-2">
          <span>Bảng Định lượng Khoảng trống Năng lực (Sắp xếp theo Priority giảm dần)</span>
        </h3>

        <div className="grid grid-cols-1 gap-4">
          {sortedSkills.map((skill) => {
            const auditItem = report?.items?.find((it) => it.jd_skill_id === skill.jd_skill_id);
            return (
              <div
                key={skill.jd_skill_id}
                className="rounded-xl border border-border bg-background p-5 shadow-sm space-y-3 hover:border-brand-orange/40 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base font-extrabold text-foreground uppercase tracking-tight">
                      {skill.jd_skill_id}
                    </span>
                    {getAlignmentBadge(skill.semantic_alignment)}
                    {skill.matched_cv_skill_id && skill.matched_cv_skill_id !== skill.jd_skill_id && (
                      <span className="text-xs text-muted-foreground">
                        ⇄ Khớp CV: <code className="font-mono font-semibold text-foreground">{skill.matched_cv_skill_id}</code>
                      </span>
                    )}
                  </div>
                  {getStrategyBadge(skill.suggested_strategy)}
                </div>

                {/* Quantitative Bars */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-xs">
                  <div className="rounded-lg bg-muted/40 p-2.5">
                    <span className="text-muted-foreground block">Yêu cầu JD (P_JD)</span>
                    <span className="font-bold text-sm text-foreground">
                      {skill.required_proficiency.toFixed(2)} / 5.0
                    </span>
                  </div>
                  <div className="rounded-lg bg-muted/40 p-2.5">
                    <span className="text-muted-foreground block">Năng lực CV (P_CV)</span>
                    <span className="font-bold text-sm text-foreground">
                      {skill.candidate_proficiency.toFixed(2)} / 5.0
                    </span>
                  </div>
                  <div className="rounded-lg bg-muted/40 p-2.5">
                    <span className="text-muted-foreground block">Độ thiếu hụt (Gap)</span>
                    <span className="font-bold text-sm text-rose-600">
                      {(skill.gap_magnitude * 100).toFixed(1)}% ({skill.gap_magnitude.toFixed(3)})
                    </span>
                  </div>
                  <div className="rounded-lg bg-muted/40 p-2.5">
                    <span className="text-muted-foreground block">Độ ưu tiên hỏi (Priority)</span>
                    <span className="font-bold text-sm text-purple-600">
                      {skill.priority.toFixed(3)}
                    </span>
                  </div>
                </div>

                {/* Static Diagnosis from Report */}
                {auditItem?.static_diagnosis && (
                  <p className="text-xs text-muted-foreground bg-slate-50 dark:bg-slate-900/50 p-3 rounded-lg border border-border/60 leading-relaxed">
                    <strong className="text-foreground">Chẩn đoán tĩnh: </strong>
                    {auditItem.static_diagnosis}
                  </p>
                )}

                {/* Context Job & Verbatim Spans */}
                <div className="space-y-1.5 text-xs">
                  {skill.context_job && (
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Briefcase size={13} className="text-brand-orange shrink-0" />
                      <span>
                        Bối cảnh công việc: <strong className="text-foreground">{skill.context_job}</strong>
                      </span>
                    </div>
                  )}
                  {skill.cv_evidence_spans && skill.cv_evidence_spans.length > 0 && (
                    <div className="flex items-start gap-1.5 text-muted-foreground">
                      <Quote size={13} className="text-emerald-600 shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <span>Trích dẫn nguyên văn từ CV:</span>
                        <ul className="list-disc list-inside text-foreground/90 italic">
                          {skill.cv_evidence_spans.map((span, idx) => (
                            <li key={idx}>&ldquo;{span}&rdquo;</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Static Audit Markdown Summary */}
      {report?.markdown_summary && (
        <details className="rounded-xl border border-border bg-muted/20 p-4">
          <summary className="cursor-pointer text-sm font-bold text-foreground flex items-center gap-2">
            <FileText size={16} className="text-brand-orange" />
            <span>Xem Báo cáo Kiểm toán Chẩn đoán Tĩnh đầy đủ (Markdown)</span>
          </summary>
          <MarkdownContent className="mt-4 rounded-lg border bg-background p-4" content={report.markdown_summary} />
        </details>
      )}

      {/* Action Footer */}
      <div className="pt-4 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-muted-foreground">
          Các câu hỏi sẽ giúp làm rõ những kỹ năng cần đánh giá.
        </div>
        <Button
          size="lg"
          onClick={onStartInterview}
          disabled={startingInterview || analyzing}
          className="bg-brand-orange hover:bg-brand-orange-hover text-white font-bold gap-2 w-full sm:w-auto"
        >
          <Play size={16} />
          {startingInterview ? 'Đang lưu hồ sơ…' : 'Lưu hồ sơ ứng tuyển'}
        </Button>
      </div>
    </div>
  );
}
