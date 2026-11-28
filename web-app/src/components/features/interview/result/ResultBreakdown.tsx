'use client';

import { useState } from 'react';
import Link from 'next/link';
import { BookOpen, ChevronDown, CircleCheck, Clock3, MessageSquare, RotateCcw, TriangleAlert } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  assessmentLabels, assessmentStatus, cleanStudyRecommendation, depthLevelLabels, evidenceDepthLabels,
  isBoilerplateClaim, looksLikeRawCode, modeDisplayLabels, normalizeSameText, questionBadge, resultReasons,
  skillStatuses, uniqueFindings, type ResultData,
} from './resultData';

export const resultPanel = 'min-w-0 rounded-2xl border border-slate-200/80 dark:border-border/80 bg-card p-4 shadow-xs sm:p-5';
export const resultSection = 'scroll-mt-(--result-scroll-mt,5rem) space-y-3';

export function AnswerContent({ content, mode, compact = false }: { content: string; mode?: string; compact?: boolean }) {
  if (looksLikeRawCode(content, mode)) {
    return (
      <pre className={cn(
        'max-w-full overflow-x-auto whitespace-pre rounded-lg bg-slate-900 font-mono text-xs leading-relaxed text-slate-100',
        compact ? 'p-2.5' : 'p-3.5',
      )}>
        <code>{content.trimEnd()}</code>
      </pre>
    );
  }
  return <MarkdownContent content={content} />;
}

export function FindingList({ items, empty, preview = 3 }: { items: readonly string[]; empty?: string; preview?: number }) {
  if (!items.length) return empty ? <p className="text-sm text-muted-foreground">{empty}</p> : null;
  return (
    <div className="space-y-2">
      <ul className="list-disc space-y-1.5 pl-4 text-sm leading-relaxed wrap-anywhere">
        {items.slice(0, preview).map(item => <li key={item}><MarkdownContent content={item} /></li>)}
      </ul>
      {items.length > preview && (
        <details className="group/findings">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-xs font-semibold text-slate-600 dark:text-muted-foreground underline-offset-4 hover:underline">
            Xem thêm {items.length - preview} ý <ChevronDown size={14} className="group-open/findings:rotate-180" />
          </summary>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm leading-relaxed wrap-anywhere">
            {items.slice(preview).map(item => <li key={item}><MarkdownContent content={item} /></li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

export function ResultCoachingSummary({ summary, introFeedback }: { summary: string; introFeedback?: string }) {
  return (
    <div className="space-y-3 rounded-xl border border-indigo-200/70 bg-indigo-50/70 p-4 text-indigo-950 dark:border-indigo-500/30 dark:bg-indigo-950/30 dark:text-foreground">
      <div className="space-y-1.5">
        <h2 className="flex items-center gap-1.5 text-sm font-bold">
          <MessageSquare size={16} className="text-indigo-700 dark:text-indigo-300" /> Nhận xét & Coaching tổng hợp
        </h2>
        <p className="text-sm leading-relaxed text-slate-800 dark:text-foreground">{summary}</p>
      </div>
      {introFeedback && (
        <div className="border-t border-indigo-200/60 pt-2.5 dark:border-indigo-500/30">
          <p className="text-xs font-semibold text-indigo-800 dark:text-indigo-300">Nhận xét phần tự giới thiệu</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-700 dark:text-muted-foreground">{introFeedback}</p>
        </div>
      )}
    </div>
  );
}

export function ResultModeBreakdown({ modes }: { modes: ResultData['modeBreakdown'] }) {
  if (!modes.length) return null;
  return (
    <div className="space-y-2 rounded-xl border border-slate-200/70 bg-slate-50/70 p-3.5 dark:border-border/70 dark:bg-muted/20">
      <p className="text-xs font-semibold tracking-wide text-slate-600 uppercase dark:text-muted-foreground">
        Hiệu suất theo dạng câu hỏi
      </p>
      <div className="flex flex-wrap gap-2">
        {modes.map(item => {
          const tone = item.weak > 0 && item.strong === 0
            ? 'border-orange-200/80 bg-orange-50/80 text-orange-950 dark:border-orange-500/30 dark:bg-orange-500/15 dark:text-orange-200'
            : item.weak > 0 || item.partial > 0
              ? 'border-amber-200/80 bg-amber-50/80 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-200'
              : 'border-emerald-200/80 bg-emerald-50/80 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-200';
          return (
            <div key={item.mode} className={cn('inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs', tone)}>
              <span className="font-semibold">{item.label}</span>
              <span className="tabular-nums font-medium">
                {item.strong}/{item.total} đạt
                {item.weak > 0 ? ` · ${item.weak} cần sửa` : ''}
                {item.partial > 0 ? ` · ${item.partial} làm rõ` : ''}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ResultFeedback({ data }: { data: ResultData }) {
  const partialSkills = data.skills
    .filter(skill => skill.status === 'partial')
    .map(skill => `${skillLabel(skill.id, null, skill.objectives.flatMap(objective => objective.jd_evidence_spans))}: chưa kiểm tra hết tiêu chí trong lượt này.`);
  const mergedStrengths = uniqueFindings([...data.strengths, ...(data.coaching?.top_strengths ?? [])]);
  const mergedWeaknesses = uniqueFindings([...data.weaknesses, ...(data.coaching?.priority_gaps ?? [])]);
  const attentionItems = mergedWeaknesses.length ? mergedWeaknesses : partialSkills;

  return (
    <div id="feedback" className="grid items-start gap-3 md:grid-cols-2">
      <div className="space-y-2 rounded-xl border border-emerald-200/60 bg-emerald-50/70 p-4 text-emerald-950">
        <h2 className="flex items-center gap-1.5 text-sm font-bold"><CircleCheck size={16} className="text-emerald-700" /> Điểm làm tốt</h2>
        <FindingList items={mergedStrengths} preview={3} empty="Chưa có đủ dữ kiện để ghi nhận điểm mạnh nổi bật." />
      </div>
      <div className={cn(
        'space-y-2 rounded-xl border p-4',
        mergedWeaknesses.length ? 'border-orange-200/70 bg-orange-50/70 text-orange-950'
          : attentionItems.length ? 'border-amber-200/70 bg-amber-50/60 text-amber-950'
            : 'border-slate-200/80 dark:border-border/80 bg-slate-50/80 text-slate-700 dark:text-foreground',
      )}>
        <h2 className="flex items-center gap-1.5 text-sm font-bold">
          {mergedWeaknesses.length ? <TriangleAlert size={16} className="text-orange-700" />
            : attentionItems.length ? <Clock3 size={16} className="text-amber-700" />
              : <MessageSquare size={16} className="text-slate-600 dark:text-muted-foreground" />}
          {mergedWeaknesses.length ? 'Cần cải thiện' : 'Lưu ý đánh giá'}
        </h2>
        <FindingList items={attentionItems} preview={2} empty="Không ghi nhận thiếu sót trong các nội dung đã đánh giá." />
      </div>
    </div>
  );
}

type SkillFilter = 'all' | keyof typeof skillStatuses;

function FilterBar<T extends string>({ filters, value, onChange, label }: {
  filters: { id: T; label: string; count: number }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1 rounded-xl bg-slate-100 dark:bg-muted p-1 text-xs">
      {filters.map(filter => (
        <button type="button" key={filter.id} aria-pressed={value === filter.id} onClick={() => onChange(filter.id)}
          className="cursor-pointer rounded-lg px-2.5 py-1 font-medium text-slate-700 dark:text-foreground hover:bg-white/60 dark:hover:bg-card/60 aria-pressed:bg-white dark:aria-pressed:bg-card aria-pressed:text-[#a02707] dark:aria-pressed:text-orange-300 aria-pressed:shadow-xs">
          {filter.label} ({filter.count})
        </button>
      ))}
    </div>
  );
}

function SkillCard({ skill }: { skill: ResultData['skills'][number] }) {
  const status = skillStatuses[skill.status];
  const allCriteria = skill.objectives.flatMap(objective => objective.criteria ?? []);
  const hasEssentialMeta = allCriteria.length > 0 && allCriteria.every(c => typeof c.essential === 'boolean');
  const visibleCriteria = hasEssentialMeta
    ? allCriteria.filter(c => c.essential || c.assessment !== 'NOT_ASSESSED')
    : allCriteria;
  const countedCriteria = hasEssentialMeta ? allCriteria.filter(c => c.essential) : allCriteria;
  const passedCount = countedCriteria.filter(c => c.assessment === 'DEMONSTRATED_AT_TARGET' || c.assessment === 'DEMONSTRATED_ABOVE_TARGET').length;
  const isCore = skill.objectives.some(objective => objective.is_core || (objective.importance_weight ?? 0) >= 0.7);
  const depths = [...new Set(skill.objectives.map(o => o.target_depth).filter((d): d is number => typeof d === 'number' && d in depthLevelLabels))];
  const meaningfulClaims = skill.objectives
    .map(objective => objective.claim)
    .filter(claim => !isBoilerplateClaim(claim, skill.id));
  const incompleteReasons = uniqueFindings(
    skill.objectives
      .filter(objective => objective.assessment === 'INSUFFICIENT_EVIDENCE' && objective.stop_reason && objective.stop_reason !== 'SUFFICIENT_EVIDENCE')
      .map(objective => resultReasons[objective.stop_reason!] ?? ''),
  );

  return (
    <article className={cn(resultPanel, 'flex flex-col justify-between gap-3')}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <h3 className="min-w-0 text-base font-bold wrap-anywhere">
              {skillLabel(skill.id, null, skill.objectives.flatMap(objective => objective.jd_evidence_spans))}
            </h3>
            {isCore && (
              <span className="rounded-md bg-orange-100/90 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-orange-900 uppercase dark:bg-orange-500/20 dark:text-orange-200">
                Cốt lõi
              </span>
            )}
            {depths.map(depth => (
              <span key={depth} className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-muted dark:text-muted-foreground">
                {depthLevelLabels[depth]}
              </span>
            ))}
          </div>
          <span className={cn(
            'rounded-full border px-2.5 py-0.5 text-xs font-semibold',
            skill.status === 'strong' && skill.hinted
              ? 'bg-teal-50 text-teal-800 border-teal-200/70'
              : status.tone,
          )}>
            {skill.status === 'strong' && skill.hinted ? 'Đạt · có gợi ý' : status.label}
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-muted-foreground">
          {skill.questionCount} câu hỏi
          {countedCriteria.length > 0 && ` · Đạt ${passedCount}/${countedCriteria.length} ${hasEssentialMeta ? 'tiêu chí bắt buộc' : 'tiêu chí'}`}
        </p>
        {meaningfulClaims.length > 0 && (
          <p className="line-clamp-2 text-sm text-slate-700 dark:text-foreground">{meaningfulClaims.join('; ')}</p>
        )}
      </div>

      {visibleCriteria.length > 0 && (
        <details className="group border-t border-slate-100 dark:border-border pt-2.5">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-xs font-semibold text-[#a02707] dark:text-orange-300">
            Xem tiêu chí ({visibleCriteria.length})
            <ChevronDown size={15} className="group-open:rotate-180" />
          </summary>
          <div className="mt-2.5 space-y-2">
            {skill.objectives.map(objective => {
              const criteria = (objective.criteria ?? []).filter(
                c => !hasEssentialMeta || c.essential || c.assessment !== 'NOT_ASSESSED',
              );
              const customClaim = !isBoilerplateClaim(objective.claim, objective.skill_id);
              return (
                <div key={objective.objective_id} className="space-y-1.5 text-xs">
                  {customClaim && <p className="font-semibold text-slate-800 dark:text-foreground">{objective.claim}</p>}
                  <ul className="space-y-1.5">
                    {criteria.map(criterion => {
                      const cStatus = skillStatuses[assessmentStatus(criterion.assessment)];
                      const passedWithHint = Boolean(criterion.hinted && !criterion.transfer_verified)
                        && (criterion.assessment === 'DEMONSTRATED_AT_TARGET' || criterion.assessment === 'DEMONSTRATED_ABOVE_TARGET');
                      return (
                        <li key={criterion.criterion_id} className="flex flex-wrap items-start justify-between gap-2 rounded-lg bg-slate-50 dark:bg-muted/40 px-2.5 py-2">
                          <span className="min-w-0 flex-1 leading-relaxed text-slate-700 dark:text-foreground wrap-anywhere">
                            {criterion.description}
                            {hasEssentialMeta && criterion.essential === false && (
                              <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Bổ sung</span>
                            )}
                          </span>
                          <span className={cn(
                            'shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium',
                            passedWithHint ? 'bg-teal-50 text-teal-800 border border-teal-200/70' : cStatus.tone,
                          )}>
                            {passedWithHint ? 'Đạt (có gợi ý)' : assessmentLabels[criterion.assessment]}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
            {incompleteReasons.length > 0 && (
              <p className="text-xs text-amber-800">{incompleteReasons[0]}</p>
            )}
          </div>
        </details>
      )}
    </article>
  );
}

export function ResultSkills({ skills }: { skills: ResultData['skills'] }) {
  const [filter, setFilter] = useState<SkillFilter>('all');
  const [limit, setLimit] = useState(6);
  const filtered = filter === 'all' ? skills : skills.filter(skill => skill.status === filter);
  const filters = [
    { id: 'all' as const, label: 'Tất cả', count: skills.length },
    ...Object.entries(skillStatuses)
      .filter(([id]) => skills.some(skill => skill.status === id))
      .map(([id, status]) => ({
        id: id as keyof typeof skillStatuses,
        label: status.label,
        count: skills.filter(skill => skill.status === id).length,
      })),
  ];

  return (
    <section id="skills" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">
          Đánh giá theo kỹ năng <span className="text-sm font-medium text-muted-foreground">({skills.length})</span>
        </h2>
        {filters.length > 2 && (
          <FilterBar filters={filters} value={filter} label="Lọc kỹ năng" onChange={value => { setFilter(value); setLimit(6); }} />
        )}
      </div>
      <div className="grid items-start gap-3 md:grid-cols-2">
        {filtered.slice(0, limit).map(skill => <SkillCard key={skill.id} skill={skill} />)}
      </div>
      {filtered.length > limit && (
        <Button variant="outline" size="sm" onClick={() => setLimit(limit + 6)}>
          Xem thêm kỹ năng ({filtered.length - limit})
        </Button>
      )}
    </section>
  );
}

type QuestionFilter = 'all' | 'strong' | 'extension' | 'diagnostic' | 'weak' | 'clarified' | 'partial' | 'retry';

export function ResultQuestions({ questions }: { questions: ResultData['questions'] }) {
  const [filter, setFilter] = useState<QuestionFilter>('all');
  const [modeFilter, setModeFilter] = useState<string>('all');
  const [limit, setLimit] = useState(5);
  const annotated = questions.map(item => ({ ...item, badge: item.badge ?? questionBadge(item) }));
  const byMode = modeFilter === 'all' ? annotated : annotated.filter(item => item.turn.mode === modeFilter);
  const filtered = filter === 'all' ? byMode : byMode.filter(item => item.badge.key === filter);
  const filterMeta: { id: Exclude<QuestionFilter, 'all'>; label: string }[] = [
    { id: 'extension', label: 'Vượt yêu cầu' },
    { id: 'strong', label: 'Đạt yêu cầu' },
    { id: 'diagnostic', label: 'Chẩn đoán nền tảng' },
    { id: 'weak', label: 'Cần cải thiện' },
    { id: 'clarified', label: 'Hỏi làm rõ' },
    { id: 'retry', label: 'Làm lại sau góp ý' },
    { id: 'partial', label: 'Chưa kết luận' },
  ];
  const filters = [
    { id: 'all' as const, label: 'Tất cả', count: byMode.length },
    ...filterMeta
      .map(meta => ({ ...meta, count: byMode.filter(item => item.badge.key === meta.id).length }))
      .filter(meta => meta.count > 0),
  ];
  const modeOrder = Object.keys(modeDisplayLabels);
  const presentModes = [...new Set(annotated.map(item => item.turn.mode).filter(Boolean))]
    .sort((a, b) => {
      const idxA = modeOrder.indexOf(a);
      const idxB = modeOrder.indexOf(b);
      return (idxA === -1 ? 99 : idxA) - (idxB === -1 ? 99 : idxB);
    });
  const modeFilters = presentModes.length > 1
    ? [
        { id: 'all', label: 'Mọi dạng', count: annotated.length },
        ...presentModes.map(mode => ({
          id: mode,
          label: modeDisplayLabels[mode] ?? mode,
          count: annotated.filter(item => item.turn.mode === mode).length,
        })),
      ]
    : [];

  return (
    <section id="questions" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">
          Chi tiết câu hỏi <span className="text-sm font-medium text-muted-foreground">({questions.length} câu)</span>
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {modeFilters.length > 0 && (
            <FilterBar
              filters={modeFilters}
              value={modeFilter}
              label="Lọc theo dạng câu hỏi"
              onChange={value => { setModeFilter(value); setFilter('all'); setLimit(5); }}
            />
          )}
          {filters.length > 2 && (
            <FilterBar filters={filters} value={filter} label="Lọc câu hỏi" onChange={value => { setFilter(value); setLimit(5); }} />
          )}
        </div>
      </div>
      <div className="space-y-2.5">
        {filtered.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            <span>Không có câu hỏi nào khớp bộ lọc hiện tại.</span>
            <Button variant="outline" size="sm" onClick={() => { setModeFilter('all'); setFilter('all'); setLimit(5); }}>
              Xóa bộ lọc
            </Button>
          </div>
        ) : filtered.slice(0, limit).map(({ turn, reviews, skillId, index, evidence, badge, depthRole, clarifiedLater }) => {
          const rationales = uniqueFindings(evidence.map(item => item.rationale));
          const excerpts = evidence.filter(item =>
            item.response_excerpt.trim() && !normalizeSameText(item.response_excerpt, turn.answer || ''),
          );
          const hasEvaluation = Boolean(turn.feedback?.trim() || rationales.length || excerpts.length);

          return (
            <details key={turn.turn_id} className="group rounded-xl border border-slate-200/80 dark:border-border/80 bg-card shadow-xs">
              <summary className="flex cursor-pointer list-none items-center gap-3 p-3.5 sm:px-4">
                <span className={cn('grid size-7 shrink-0 place-items-center rounded-lg border text-xs font-bold tabular-nums', badge.tone)}>
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="min-w-0 flex-1 space-y-0.5">
                  <span className="flex flex-wrap items-center gap-2 text-xs">
                    {skillId && <span className="font-semibold text-slate-700 dark:text-foreground">{skillLabel(skillId)}</span>}
                    {turn.mode && (
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-muted dark:text-muted-foreground">
                        {modeDisplayLabels[turn.mode] ?? turn.mode}
                      </span>
                    )}
                    <span className={cn('rounded-full border px-2 py-0.5 text-[11px] font-medium', badge.tone)}>{badge.label}</span>
                  </span>
                  <span className="line-clamp-1 block text-sm font-medium text-slate-900 dark:text-foreground wrap-anywhere">{turn.question}</span>
                </span>
                <ChevronDown size={17} className="shrink-0 text-slate-500 dark:text-muted-foreground group-open:rotate-180" />
              </summary>
              <div className="space-y-3 border-t border-slate-100 dark:border-border bg-slate-50/60 p-4 text-sm wrap-anywhere">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-slate-500 dark:text-muted-foreground uppercase">Câu hỏi</p>
                    {depthRole && depthRole !== 'TARGET' && (
                      <span className="rounded-md bg-slate-200/80 dark:bg-muted/80 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:text-foreground">
                        {evidenceDepthLabels[depthRole]}
                      </span>
                    )}
                  </div>
                  <MarkdownContent content={turn.question} />
                  {Boolean(turn.clarifications?.length) && (
                    <details className="mt-2 rounded-lg border border-slate-200/80 bg-card p-2.5 text-xs dark:border-border">
                      <summary className="cursor-pointer font-semibold text-slate-700 dark:text-foreground">
                        Trao đổi làm rõ đề bài ({turn.clarifications!.length})
                      </summary>
                      <div className="mt-2 space-y-1.5">
                        {turn.clarifications!.map((item, cIdx) => (
                          <div key={cIdx} className="space-y-0.5 rounded-md bg-muted/40 p-2 leading-relaxed">
                            <p className="font-semibold text-foreground">
                              {item.kind === 'HINT' ? 'Gợi ý đã xin' : `Câu hỏi làm rõ: ${item.question}`}
                            </p>
                            <p className="text-muted-foreground">{item.answer}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
                <div className="space-y-1.5 rounded-lg border border-slate-200/70 dark:border-border/70 bg-card p-3">
                  <p className="text-xs font-semibold text-slate-500 dark:text-muted-foreground uppercase">Câu trả lời của bạn</p>
                  {turn.submitted_code ? <>
                    <pre className="overflow-auto whitespace-pre">{turn.submitted_code}</pre>
                    {turn.transcript && <p>Lời giải thích · {turn.transcript}</p>}
                  </> : <AnswerContent content={turn.answer || 'Chưa có câu trả lời.'} mode={turn.mode} />}
                  {turn.coding_checks && (
                    <div className="space-y-1.5 border-t border-slate-100 pt-2 text-xs dark:border-border">
                      <p className="font-medium">
                        Kiểm thử tự động · Đạt {turn.coding_checks.passed}/{turn.coding_checks.total} ca.
                      </p>
                      {turn.coding_checks.compile_error && (
                        <pre className="max-h-28 overflow-auto rounded-md bg-destructive/10 p-2 font-mono text-[11px] whitespace-pre-wrap text-destructive">
                          {turn.coding_checks.compile_error}
                        </pre>
                      )}
                      {Boolean(turn.coding_checks.sample_results?.length) && (
                        <ul className="space-y-1">
                          {turn.coding_checks.sample_results!.map((sample, sIdx) => (
                            <li key={`${sample.name}-${sIdx}`} className="rounded-md border border-slate-200/70 bg-muted/25 px-2.5 py-1.5 dark:border-border">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-medium text-foreground">{sample.name}</span>
                                <span className={cn(
                                  'rounded px-1.5 py-0.5 text-[10px] font-semibold',
                                  sample.passed
                                    ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200'
                                    : 'bg-orange-100 text-orange-900 dark:bg-orange-500/20 dark:text-orange-200',
                                )}>
                                  {sample.passed ? 'Đạt' : 'Chưa đạt'}
                                </span>
                              </div>
                              {sample.error ? (
                                <p className="mt-1 font-mono text-[11px] text-destructive">{sample.error}</p>
                              ) : !sample.passed ? (
                                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                                  Thực tế: <strong className="text-foreground">{sample.actual_output || '(rỗng)'}</strong> · Kỳ vọng: <strong className="text-foreground">{sample.expected_output}</strong>
                                </p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
                {reviews.length > 0 ? reviews.map((review, i) => <div key={i} className="space-y-2 rounded-lg bg-sky-50 p-3 dark:bg-muted">
                  {review.excerpt && <blockquote className="whitespace-pre-wrap border-l-2 pl-3">{review.excerpt}</blockquote>}
                  <p>{review.reason}</p>
                  {Boolean(review.gaps?.length) && <p>Phần còn thiếu · {review.gaps?.join(' · ')}</p>}
                  {Boolean(review.delivery_notes?.length) && (
                    <ul className="space-y-1 rounded-md border border-sky-200/70 bg-white/70 p-2 text-xs text-slate-700 dark:border-border dark:bg-card dark:text-muted-foreground">
                      {review.delivery_notes?.map((note, idx) => <li key={idx}>• {note}</li>)}
                    </ul>
                  )}
                  <p className="font-medium">{review.next_step}</p>
                  {review.reference_answer && (
                    <details className="rounded-md border border-emerald-200/70 bg-emerald-50/70 p-2.5 text-xs dark:border-emerald-500/30 dark:bg-emerald-950/30">
                      <summary className="cursor-pointer font-semibold text-emerald-900 dark:text-emerald-300">
                        Gợi ý khung trả lời chuẩn
                      </summary>
                      <div className="mt-1.5 leading-relaxed text-slate-800 dark:text-foreground">
                        <MarkdownContent content={review.reference_answer} />
                      </div>
                    </details>
                  )}
                  {review.level_up_tip && (
                    <details className="rounded-md border border-indigo-200/70 bg-indigo-50/70 p-2.5 text-xs dark:border-indigo-500/30 dark:bg-indigo-950/30">
                      <summary className="cursor-pointer font-semibold text-indigo-900 dark:text-indigo-300">
                        Cách nâng lên mức Xuất sắc (Senior)
                      </summary>
                      <p className="mt-1.5 leading-relaxed text-slate-800 dark:text-foreground">{review.level_up_tip}</p>
                    </details>
                  )}
                </div>) : hasEvaluation ? (
                  <div className="space-y-1.5 rounded-lg border border-sky-200/60 bg-sky-50/70 p-3 text-slate-800 dark:text-foreground">
                    <p className="text-xs font-semibold text-sky-900 uppercase">Đánh giá từ AI</p>
                    {turn.feedback && <MarkdownContent content={turn.feedback} />}
                    {rationales.map(rationale => (
                      (!turn.feedback || !normalizeSameText(rationale, turn.feedback)) && (
                        <p key={rationale} className="text-sm text-slate-700 dark:text-foreground">{rationale}</p>
                      )
                    ))}
                    {excerpts.map((item, idx) => (
                      <div key={idx} className="border-l-2 border-orange-300 pl-3 text-xs text-slate-600 dark:text-muted-foreground">
                        <p className="mb-1 font-medium text-slate-500 dark:text-muted-foreground">Đoạn được ghi nhận:</p>
                        <AnswerContent content={item.response_excerpt} mode={turn.mode} compact />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 dark:text-muted-foreground">
                    {clarifiedLater
                      ? 'Câu trả lời đúng một phần; người phỏng vấn đã hỏi tiếp ngay sau đó để làm rõ thêm.'
                      : 'Chưa đủ dữ kiện để kết luận cho câu trả lời này.'}
                  </p>
                )}
              </div>
            </details>
          );
        })}
      </div>
      {filtered.length > limit && (
        <Button variant="outline" size="sm" onClick={() => setLimit(limit + 5)}>
          Xem thêm câu hỏi ({filtered.length - limit})
        </Button>
      )}
    </section>
  );
}

export function ResultStudy({
  data, studyHref, profileId, busy, error, onRetry,
}: {
  data: ResultData;
  studyHref: string;
  profileId?: string;
  busy?: boolean;
  error?: string;
  onRetry?: () => void;
}) {
  const groups = data.skills.flatMap(skill => {
    const weaknesses = uniqueFindings(skill.objectives.flatMap(objective => objective.weaknesses));
    const recommendations = uniqueFindings(
      skill.objectives.flatMap(objective => (objective.study_recommendations ?? []).map(cleanStudyRecommendation)),
    );
    return weaknesses.length || recommendations.length ? [{ ...skill, weaknesses, recommendations }] : [];
  });
  const groupedRecommendations = new Set(groups.flatMap(group => group.recommendations));
  const additionalRecommendations = uniqueFindings([
    ...data.recommendations.map(cleanStudyRecommendation),
    ...(data.coaching?.actionable_study_steps ?? []),
  ]).filter(item => !groupedRecommendations.has(item));

  return (
    <section id="study" className={cn(resultPanel, resultSection, 'bg-gradient-to-br from-white to-orange-50/50')}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-lg font-bold">Ôn tập & bước tiếp theo</h2>
          <p className="text-sm text-slate-600 dark:text-muted-foreground">
            {groups.length > 0
              ? 'Tập trung ôn lại các điểm chưa vững trước khi luyện lượt phỏng vấn mới.'
              : 'Buổi này không ghi nhận điểm yếu cần ôn thêm. Bạn có thể mở lộ trình ôn tập hoặc thử sức lượt mới.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={studyHref} className={cn(buttonVariants(), 'rounded-full bg-[#b02700] text-white hover:bg-[#8c2100]')}>
            <BookOpen aria-hidden="true" /> Mở kế hoạch ôn tập
          </Link>
          {profileId && onRetry ? (
            <Button variant="outline" disabled={busy} onClick={onRetry}>
              <RotateCcw aria-hidden="true" /> {busy ? 'Đang tạo lượt…' : 'Phỏng vấn lượt mới'}
            </Button>
          ) : (
            <Link href="/interview/new" className={buttonVariants({ variant: 'outline' })}>
              <RotateCcw aria-hidden="true" /> Phỏng vấn mới
            </Link>
          )}
        </div>
      </div>

      {groups.length > 0 && (
        <div className="grid items-start gap-3 pt-1 md:grid-cols-2">
          {groups.map(group => (
            <article key={group.id} className="space-y-2 rounded-xl border border-slate-200/80 dark:border-border/80 bg-white dark:bg-card p-4">
              <h3 className="flex items-center gap-2 text-sm font-bold wrap-anywhere">
                <BookOpen size={16} className="shrink-0 text-orange-700" />
                {skillLabel(group.id, null, group.objectives.flatMap(objective => objective.jd_evidence_spans))}
              </h3>
              <FindingList items={group.recommendations.length ? group.recommendations : group.weaknesses} preview={2} />
            </article>
          ))}
        </div>
      )}

      {additionalRecommendations.length > 0 && (
        <div className="rounded-xl border border-slate-200/80 dark:border-border/80 bg-white dark:bg-card p-4">
          <FindingList items={additionalRecommendations} preview={3} />
        </div>
      )}

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </section>
  );
}
