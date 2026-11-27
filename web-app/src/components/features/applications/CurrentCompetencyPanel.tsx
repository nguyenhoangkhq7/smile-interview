'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowUpRight, ChevronDown, Info, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { jdSkillLabel } from '@/lib/skillLabels';
import { cn } from '@/lib/utils';
import {
  applicationProfiles, competencySummary, skillLastChecked,
  type CompetencyCriterion, type CompetencyObjective, type CompetencySource, type CompetencyStatus, type CurrentCompetency,
} from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import type { SkillGapResult } from '@/services/cvJdMatching';
import { searchText, skillLabel } from './applicationUi';

const groupOrder = ['verify', 'review', 'incomplete', 'unassessed', 'met'] as const;
type Group = typeof groupOrder[number];
type Filter = 'all' | Group;
type SelectedEvidence = { skillId: string; objectiveId: string; criterionId: string };

const presentation: Record<CompetencyStatus, { group: Group; label: string; criterionLabel?: string }> = {
  NOT_ASSESSED: { group: 'unassessed', label: 'Chưa có dữ liệu', criterionLabel: 'Chưa có bằng chứng đánh giá' },
  INSUFFICIENT_EVIDENCE: { group: 'incomplete', label: 'Chưa đủ bằng chứng' },
  PARTIALLY_ASSESSED: { group: 'incomplete', label: 'Đã kiểm tra một phần' },
  NOT_DEMONSTRATED: { group: 'review', label: 'Chưa thể hiện được' },
  DEMONSTRATED_BELOW_TARGET: { group: 'review', label: 'Dưới yêu cầu', criterionLabel: 'Có bằng chứng dưới yêu cầu' },
  DEMONSTRATED_AT_TARGET: { group: 'met', label: 'Đáp ứng yêu cầu', criterionLabel: 'Có bằng chứng đáp ứng' },
  DEMONSTRATED_ABOVE_TARGET: { group: 'met', label: 'Vượt yêu cầu' },
  NEEDS_VERIFICATION: { group: 'verify', label: 'Cần kiểm chứng lại' },
};

const groupLabel: Record<Group, string> = {
  verify: 'Cần kiểm chứng lại',
  review: 'Dưới yêu cầu',
  incomplete: 'Chưa đủ bằng chứng',
  unassessed: 'Chưa có dữ liệu',
  met: 'Đáp ứng yêu cầu',
};
const groupColor: Record<Group, string> = {
  verify: 'bg-amber-50 text-amber-900 dark:bg-amber-500/15 dark:text-amber-200',
  review: 'bg-orange-50 text-orange-900 dark:bg-orange-500/15 dark:text-orange-200',
  incomplete: 'bg-muted text-muted-foreground',
  unassessed: 'bg-muted text-muted-foreground',
  met: 'bg-emerald-50 text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-200',
};
const skillPageSize = 6;
const linkClass = 'inline-flex items-center gap-1 rounded-sm text-xs font-medium text-brand-green underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring';

function Status({ value, criterion = false }: { value: CompetencyStatus; criterion?: boolean }) {
  const { label, criterionLabel, group } = presentation[value];
  return (
    <span className={cn('inline-flex max-w-full rounded-md px-2 py-1 text-xs font-medium', groupColor[group])}>
      {criterion ? (criterionLabel ?? label) : label}
    </span>
  );
}

function SourceLink({ source, children }: { source: CompetencySource; children?: ReactNode }) {
  return (
    <Link prefetch={false} className={linkClass} href={`/interview/session/${source.sessionId}/result`}>
      {children ?? `Lượt ${source.attemptNumber}`}
      <ArrowUpRight size={13} className="shrink-0" aria-hidden="true" />
    </Link>
  );
}

function ObjectiveDetails({
  objective, showStatus, onEvidence,
}: {
  objective: CompetencyObjective;
  showStatus: boolean;
  onEvidence: (criterionId: string) => void;
}) {
  const { lastChecked, lastAssessment } = objective;
  const resultSource = lastChecked ?? lastAssessment;
  const assessmentFromEarlierAttempt = Boolean(lastChecked && lastAssessment && lastAssessment.sessionId !== lastChecked.sessionId);

  return (
    <article className="space-y-3 border-b border-border pb-4 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1 basis-48">
          <p className="text-xs font-medium text-muted-foreground">Mục tiêu</p>
          <MarkdownContent className="mt-1 text-sm font-semibold [overflow-wrap:anywhere]" content={objective.claim} />
        </div>
        {showStatus && <Status value={objective.assessment} />}
      </div>
      {(objective.assessment === 'NEEDS_VERIFICATION' || assessmentFromEarlierAttempt) && objective.explanation && (
        <p className="text-xs leading-relaxed text-muted-foreground">{objective.explanation}</p>
      )}
      {objective.criteria.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Tiêu chí đánh giá</p>
          <ul className="divide-y divide-border">
            {objective.criteria.map(criterion => {
              const atTarget = criterion.atTarget?.trim();
              return (
                <li key={criterion.id} className="space-y-1.5 py-2.5 first:pt-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <MarkdownContent className="min-w-0 flex-1 basis-56 text-sm [overflow-wrap:anywhere]" content={criterion.description} />
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn('rounded-md px-2 py-1 text-xs font-medium', criterion.essential ? 'bg-brand-green/10 text-brand-green' : 'bg-muted text-muted-foreground')}>
                        {criterion.essential ? 'Cần đạt' : 'Bổ sung'}
                      </span>
                      <Status value={criterion.assessment} criterion />
                    </div>
                  </div>
                  {criterion.trend && <p className="text-xs text-muted-foreground">{criterion.trend === 'IMPROVING'
                    ? 'Lượt này đã đạt; cần thêm một tình huống để xác nhận.'
                    : 'Lượt này dưới yêu cầu; cần thêm một tình huống để xác nhận.'}</p>}
                  {atTarget && atTarget !== criterion.description.trim() && (
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs leading-relaxed">
                      <span className="font-semibold text-foreground">Đạt khi</span>
                      <MarkdownContent className="min-w-0 flex-1 basis-48 text-sm! text-muted-foreground [overflow-wrap:anywhere]" content={atTarget} />
                    </div>
                  )}
                  {criterion.evidence.length > 0 && (
                    <Button variant="ghost" size="sm" className="-ml-2 text-xs text-brand-green" onClick={() => onEvidence(criterion.id)}>
                      Xem bằng chứng ({criterion.evidence.length})
                      <ArrowUpRight size={13} aria-hidden="true" />
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {resultSource && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <SourceLink source={resultSource}>Xem kết quả lượt {resultSource.attemptNumber}</SourceLink>
          {assessmentFromEarlierAttempt && lastAssessment && (
            <SourceLink source={lastAssessment}>Căn cứ từ lượt {lastAssessment.attemptNumber}</SourceLink>
          )}
        </div>
      )}
    </article>
  );
}

function EvidenceContent({ criterion }: { criterion: CompetencyCriterion }) {
  return (
    <div className="max-h-[60dvh] space-y-5 overflow-y-auto overscroll-contain pr-1">
      <div className="rounded-xl bg-muted/40 p-3.5">
        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Tiêu chí đang xem</p>
        <MarkdownContent className="font-medium [overflow-wrap:anywhere]" content={criterion.description} />
      </div>
      {[...criterion.evidence].reverse().map(evidence => (
        <article key={`${evidence.source.sessionId}:${evidence.turnId}`} className="space-y-3 border-b pb-5 last:border-0 last:pb-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SourceLink source={evidence.source} />
            <Status value={evidence.performance === 'BELOW' ? 'DEMONSTRATED_BELOW_TARGET' : 'DEMONSTRATED_AT_TARGET'} criterion />
          </div>
          <blockquote className="rounded-xl border-l-2 border-brand-orange/40 bg-muted/30 p-4 text-sm leading-6">
            <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">“{evidence.responseExcerpt}”</p>
          </blockquote>
          <MarkdownContent className="text-muted-foreground [overflow-wrap:anywhere]" content={evidence.rationale} />
          <details className="rounded-lg border p-3">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Câu hỏi làm căn cứ</summary>
            <MarkdownContent className="mt-3 [overflow-wrap:anywhere]" content={evidence.question} />
          </details>
        </article>
      ))}
    </div>
  );
}

export function CurrentCompetencyPanel({
  profileId, refreshKey, baselineSkills, nextAction, nextHint,
}: {
  profileId: string;
  refreshKey: string;
  baselineSkills: SkillGapResult[];
  nextAction: ReactNode;
  nextHint?: string;
}) {
  const [revision, setRevision] = useState(0);
  const [request, setRequest] = useState<{ key: string; data: CurrentCompetency | null; error: string } | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter | null>(null);
  const [limit, setLimit] = useState(skillPageSize);
  const [selected, setSelected] = useState<SelectedEvidence | null>(null);
  const requestKey = `${profileId}:${refreshKey}:${revision}`;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    void applicationProfiles.competency(profileId, signal).then(
      data => {
        if (!signal.aborted) setRequest({ key: requestKey, data, error: '' });
      },
      cause => {
        if (!signal.aborted) setRequest({ key: requestKey, data: null, error: interviewError(cause) });
      },
    );

    return () => controller.abort();
  }, [profileId, requestKey]);

  const loading = request?.key !== requestKey;
  const data = request?.data;
  const error = loading ? '' : (request?.error ?? '');
  const baselineById = new Map(baselineSkills.map(skill => [skill.jd_skill_id, skill]));
  const summary = competencySummary(data?.skills ?? []);
  const groupCounts: Record<Group, number> = {
    verify: summary.needsVerification,
    review: summary.belowTarget,
    incomplete: summary.incomplete,
    unassessed: summary.notAssessed,
    met: summary.meetingTarget,
  };
  const suggestedFilter = groupOrder.find(group => group !== 'unassessed' && group !== 'met' && groupCounts[group] > 0);
  const activeFilter = filter ?? suggestedFilter ?? 'all';
  const filterOptions = groupOrder.filter(group => groupCounts[group] > 0 || group === activeFilter);
  const rows = (data?.skills ?? []).map(skill => {
    const baseline = baselineById.get(skill.skillId);
    return {
      skill,
      name: baseline ? jdSkillLabel(baseline) : skillLabel(skill.skillId),
      checked: skillLastChecked(skill),
      importance: baseline?.importance_weight ?? 0,
      status: presentation[skill.assessment],
    };
  });
  const checkedCount = rows.filter(row => row.checked).length;
  const normalizedQuery = searchText(query.trim());
  const filtered = rows.filter(({ skill, name, status }) => (
    (activeFilter === 'all' || status.group === activeFilter)
      && searchText(`${skill.skillId} ${name}`).includes(normalizedQuery)
  )).sort((a, b) => (
    groupOrder.indexOf(a.status.group) - groupOrder.indexOf(b.status.group)
      || b.importance - a.importance
      || (b.checked?.attemptNumber ?? 0) - (a.checked?.attemptNumber ?? 0)
  ));

  const selectedRow = rows.find(row => row.skill.skillId === selected?.skillId);
  const selectedObjective = selectedRow?.skill.objectives.find(objective => objective.id === selected?.objectiveId);
  const selectedCriterion = selectedObjective?.criteria.find(criterion => criterion.id === selected?.criterionId);
  const hasConclusions = summary.meetingTarget + summary.belowTarget > 0;

  function refresh() {
    setRevision(current => current + 1);
  }

  function selectFilter(value: Filter) {
    setFilter(value);
    setLimit(skillPageSize);
  }

  return (
    <section id="competency" aria-labelledby="competency-title" aria-busy={loading} className="scroll-mt-24 space-y-5 rounded-2xl border bg-card p-4 sm:space-y-6 sm:p-6">
      <header className="flex items-center justify-between gap-3">
        <h2 id="competency-title" className="text-lg font-semibold tracking-tight sm:text-xl">Năng lực hiện tại theo JD</h2>
        <Button aria-label="Cập nhật" className="shrink-0" variant="outline" size="sm" disabled={loading} onClick={refresh}>
          <RefreshCw size={14} className={loading ? 'animate-spin motion-reduce:animate-none' : ''} aria-hidden="true" />
          <span className="hidden sm:inline">Cập nhật</span>
        </Button>
      </header>

      <div className="grid overflow-hidden rounded-xl border bg-background sm:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <div className="min-w-0 space-y-2 p-4 sm:p-5">
          {error && (
            <div role="alert" className="space-y-2">
              <p className="text-sm text-destructive">{error}</p>
              <Button variant="outline" size="sm" onClick={refresh}>Thử lại</Button>
            </div>
          )}
          {loading && !data && <p role="status" className="text-sm text-muted-foreground">Đang tải đánh giá…</p>}
          {data && (summary.totalSkills > 0 ? (
            <>
              <p className="text-sm font-medium text-muted-foreground">Kỹ năng có câu trả lời được ghi nhận</p>
              <p aria-hidden="true" className="flex items-baseline gap-1.5 font-medium tabular-nums text-muted-foreground">
                <span className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">{checkedCount}</span>
                <span className="text-xl">/ {summary.totalSkills}</span>
              </p>
              <div
                role="meter"
                aria-label="Kỹ năng có câu trả lời được ghi nhận"
                aria-valuemin={0}
                aria-valuemax={summary.totalSkills}
                aria-valuenow={checkedCount}
                aria-valuetext={`${checkedCount} trên ${summary.totalSkills} kỹ năng`}
                className="h-1.5 max-w-64 overflow-hidden rounded-full bg-muted"
              >
                <div aria-hidden="true" className="h-full rounded-full bg-brand-green" style={{ width: `${checkedCount / summary.totalSkills * 100}%` }} />
              </div>
              {data.completedAttempts > 0 ? (
                <a href="#history" className={linkClass}>
                  Từ {data.completedAttempts} lượt có câu trả lời
                  <ArrowUpRight size={13} className="shrink-0" aria-hidden="true" />
                </a>
              ) : <p className="text-xs text-muted-foreground">Chưa có lượt phỏng vấn có câu trả lời.</p>}
            </>
          ) : <p className="text-sm text-muted-foreground">Hồ sơ chưa có kỹ năng theo JD.</p>)}
        </div>
        <div className="min-w-0 space-y-2 border-t bg-brand-green/5 p-4 sm:border-t-0 sm:border-l sm:p-5 dark:bg-brand-green/10">
          <h3 className="font-semibold">Lượt luyện tiếp theo</h3>
          <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
            {nextHint ?? (summary.totalSkills > 0 && summary.meetingTarget === summary.totalSkills
              ? 'Các kỹ năng theo JD đã được xác nhận đáp ứng yêu cầu.'
              : 'Ưu tiên đánh giá thêm những kỹ năng quan trọng trong JD.')}
          </p>
          {nextAction}
        </div>
      </div>

      {data && (
        <>
          {data.incompatibleAssessments > 0 && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900 dark:bg-amber-500/15 dark:text-amber-200">
              {data.incompatibleAssessments} đánh giá có bộ tiêu chí khác nên chưa được gộp vào kết quả hiện tại.
            </p>
          )}

          {summary.totalSkills > 0 && (
            <section aria-labelledby="competency-skills-title" className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 id="competency-skills-title" className="font-semibold">Kỹ năng</h3>
                  {checkedCount > 0 && !hasConclusions && (
                    <p className="mt-0.5 text-xs text-muted-foreground">Chưa có kết luận đáp ứng hoặc dưới yêu cầu.</p>
                  )}
                </div>
                <label className="flex min-w-0 w-full items-center gap-2 rounded-lg border bg-background px-3 focus-within:ring-2 focus-within:ring-ring sm:w-44">
                  <Search size={15} className="shrink-0 text-muted-foreground" aria-hidden="true" />
                  <input
                    aria-label="Tìm kỹ năng"
                    className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none sm:h-9 sm:text-sm"
                    type="search"
                    placeholder="Tìm kỹ năng…"
                    value={query}
                    onChange={event => {
                      setQuery(event.target.value);
                      if (event.target.value.trim()) setFilter('all');
                      setLimit(skillPageSize);
                    }}
                  />
                </label>
              </div>

              <div className="flex flex-wrap gap-1" role="group" aria-label="Lọc đánh giá kỹ năng">
                <button
                  type="button"
                  aria-pressed={activeFilter === 'all'}
                  onClick={() => selectFilter('all')}
                  className="rounded-md px-2.5 py-2 text-xs text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring aria-pressed:bg-brand-green/10 aria-pressed:font-semibold aria-pressed:text-brand-green"
                >
                  Tất cả
                </button>
                {filterOptions.map(group => (
                  <button
                    key={group}
                    type="button"
                    aria-pressed={activeFilter === group}
                    onClick={() => selectFilter(group)}
                    className="rounded-md px-2.5 py-2 text-xs text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring aria-pressed:bg-brand-green/10 aria-pressed:font-semibold aria-pressed:text-brand-green"
                  >
                    {groupLabel[group]} <span className="ml-0.5 tabular-nums">{groupCounts[group]}</span>
                  </button>
                ))}
              </div>

              {filtered.length ? (
                <div className="divide-y overflow-hidden rounded-xl border bg-background">
                  {filtered.slice(0, limit).map(({ skill, name, checked, status }) => (
                    <details key={skill.skillId} name="competency-skills" data-skill={skill.skillId} className="group/skill">
                      <summary className="flex min-h-12 cursor-pointer list-none flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2.5 transition hover:bg-muted/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring sm:px-4 [&::-webkit-details-marker]:hidden">
                        <span className="min-w-0 flex-1 text-sm font-semibold [overflow-wrap:anywhere]">{name}</span>
                        <span className="ml-auto flex max-w-full flex-wrap items-center justify-end gap-2">
                          {checked && <span className="text-xs text-muted-foreground">Lượt {checked.attemptNumber}</span>}
                          {(activeFilter === 'all' || groupLabel[activeFilter] !== status.label) && <Status value={skill.assessment} />}
                          <ChevronDown size={15} className="shrink-0 text-muted-foreground transition group-open/skill:rotate-180" aria-hidden="true" />
                        </span>
                      </summary>
                      <div className="space-y-4 border-t bg-muted/20 p-3 sm:p-4">
                        {skill.objectives.length ? skill.objectives.map(objective => (
                          <ObjectiveDetails
                            key={objective.id}
                            objective={objective}
                            showStatus={skill.objectives.length > 1 || objective.assessment !== skill.assessment}
                            onEvidence={criterionId => setSelected({ skillId: skill.skillId, objectiveId: objective.id, criterionId })}
                          />
                        )) : <p className="text-sm text-muted-foreground">Chưa có tiêu chí phỏng vấn cho kỹ năng này.</p>}
                        {status.group === 'review' && (
                          <Link prefetch={false} className={linkClass} href={`/practice/${profileId}`}>
                            Mở kế hoạch ôn tập
                            <ArrowUpRight size={13} className="shrink-0" aria-hidden="true" />
                          </Link>
                        )}
                      </div>
                    </details>
                  ))}
                  {filtered.length > limit && (
                    <div className="p-2 text-center">
                      <Button variant="ghost" size="sm" onClick={() => setLimit(current => current + skillPageSize)}>
                        Xem thêm kỹ năng ({filtered.length - limit})
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border p-4 text-sm text-muted-foreground">
                  <p>Không có kỹ năng phù hợp.</p>
                  <Button className="-ml-2 mt-1" variant="ghost" size="sm" onClick={() => { setQuery(''); selectFilter('all'); }}>
                    Xóa bộ lọc
                  </Button>
                </div>
              )}
            </section>
          )}

          <details className="border-t pt-3 text-xs text-muted-foreground">
            <summary className="flex w-fit cursor-pointer list-none items-center gap-2 rounded-sm py-1 font-medium focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
              <Info size={14} aria-hidden="true" />
              Cách hệ thống cập nhật đánh giá
              <ChevronDown size={13} aria-hidden="true" />
            </summary>
            <ul className="mt-2 max-w-3xl list-disc space-y-1 pl-5 leading-relaxed">
              <li>Chỉ tổng hợp các lượt đã kết thúc và có câu trả lời.</li>
              <li>Kỹ năng chưa có dữ liệu được giữ ở trạng thái chưa đánh giá.</li>
              <li>Bằng chứng trái ngược cần hai lượt xác nhận nhất quán về sau trong các bối cảnh độc lập.</li>
              <li>Để kết luận một mục tiêu đáp ứng yêu cầu, cần bằng chứng đạt ở mọi tiêu chí cần đạt của mục tiêu trong cùng lượt.</li>
            </ul>
          </details>
        </>
      )}

      <Dialog open={Boolean(selectedCriterion)} onOpenChange={open => !open && setSelected(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Bằng chứng đánh giá · {selectedRow?.name}</DialogTitle>
            <DialogDescription>Trích đoạn câu trả lời và nhận xét theo tiêu chí đã chọn.</DialogDescription>
          </DialogHeader>
          {selectedCriterion && <EvidenceContent criterion={selectedCriterion} />}
          <DialogFooter><Button variant="outline" onClick={() => setSelected(null)}>Đóng bằng chứng</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
