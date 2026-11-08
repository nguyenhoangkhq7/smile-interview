'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, CheckCircle2, ChevronDown, CircleHelp, Focus, Info, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { applicationProfiles, CompetencyStatus, CurrentCompetency, CompetencySource, CompetencyCriterion } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import { formatProfileDate, searchText, skillLabel } from './applicationUi';

const labels: Record<CompetencyStatus, string> = {
  NOT_ASSESSED: 'Chưa được kiểm tra', INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng',
  NOT_DEMONSTRATED: 'Chưa thể hiện được', DEMONSTRATED_BELOW_TARGET: 'Dưới yêu cầu đã kiểm tra',
  DEMONSTRATED_AT_TARGET: 'Đáp ứng yêu cầu đã kiểm tra', DEMONSTRATED_ABOVE_TARGET: 'Vượt yêu cầu đã kiểm tra',
  NEEDS_VERIFICATION: 'Cần kiểm chứng lại', PARTIALLY_ASSESSED: 'Chưa kiểm tra đầy đủ',
};
const shortLabels: Record<CompetencyStatus, string> = {
  NOT_ASSESSED: 'Chưa kiểm tra', INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng',
  NOT_DEMONSTRATED: 'Chưa thể hiện được', DEMONSTRATED_BELOW_TARGET: 'Dưới yêu cầu',
  DEMONSTRATED_AT_TARGET: 'Đáp ứng yêu cầu', DEMONSTRATED_ABOVE_TARGET: 'Vượt yêu cầu',
  NEEDS_VERIFICATION: 'Cần kiểm chứng', PARTIALLY_ASSESSED: 'Chưa đánh giá đủ',
};
const meets = (value: CompetencyStatus) => ['DEMONSTRATED_AT_TARGET', 'DEMONSTRATED_ABOVE_TARGET'].includes(value);
const needsFocus = (value: CompetencyStatus) => ['NEEDS_VERIFICATION', 'DEMONSTRATED_BELOW_TARGET', 'NOT_DEMONSTRATED'].includes(value);

function Status({ value, observed = false }: { value: CompetencyStatus; observed?: boolean }) {
  const color = value === 'NEEDS_VERIFICATION' ? 'bg-amber-50 text-amber-800'
    : meets(value) ? 'bg-emerald-50 text-emerald-800'
      : needsFocus(value) ? 'bg-orange-50 text-orange-800' : 'bg-muted/70 text-muted-foreground';
  const label = observed && value === 'DEMONSTRATED_BELOW_TARGET' ? 'Có bằng chứng dưới yêu cầu'
    : observed && value === 'DEMONSTRATED_AT_TARGET' ? 'Có bằng chứng đáp ứng' : labels[value];
  return <span className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${color}`}><span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />{observed ? label : <><span className="sm:hidden">{shortLabels[value]}</span><span className="hidden sm:inline">{label}</span></>}</span>;
}

function SourceLink({ source }: { source: CompetencySource }) {
  return <Link className="inline-flex items-center gap-0.5 font-medium text-brand-orange hover:underline" href={`/interview/session/${source.sessionId}/result`}>Lượt {source.attemptNumber}<ArrowUpRight size={12} /></Link>;
}

type Filter = 'all' | 'focus' | 'met' | 'pending';
type SelectedEvidence = { skillId: string; objectiveId: string; criterionId: string };

function EvidenceContent({ criterion }: { criterion: CompetencyCriterion }) {
  return <div className="max-h-[60dvh] space-y-5 overflow-y-auto overscroll-contain pr-1">
    <div className="rounded-xl bg-muted/40 p-3.5"><p className="mb-1.5 text-xs font-medium text-muted-foreground">Tiêu chí đang xem</p><MarkdownContent className="font-medium" content={criterion.description} /></div>
    {[...criterion.evidence].reverse().map(evidence => <article key={`${evidence.source.sessionId}:${evidence.turnId}`} className="space-y-3 border-b pb-5 last:border-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><SourceLink source={evidence.source} /><span className={evidence.performance === 'BELOW' ? 'text-orange-800' : 'text-brand-green'}>{evidence.performance === 'BELOW' ? 'Bằng chứng dưới yêu cầu' : 'Bằng chứng đáp ứng ở mức yêu cầu'}</span></div>
      <blockquote className="rounded-xl border-l-2 border-brand-orange/40 bg-muted/30 p-4 text-sm leading-6"><p className="whitespace-pre-wrap break-words">“{evidence.responseExcerpt}”</p></blockquote>
      <MarkdownContent className="text-muted-foreground" content={evidence.rationale} />
      <details className="rounded-lg border p-3"><summary className="cursor-pointer text-xs font-medium text-muted-foreground">Câu hỏi làm căn cứ</summary><MarkdownContent className="mt-3" content={evidence.question} /></details>
    </article>)}
  </div>;
}

export function CurrentCompetencyPanel({ profileId, refreshKey }: { profileId: string; refreshKey: string }) {
  const [data, setData] = useState<CurrentCompetency | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [limit, setLimit] = useState(6);
  const [selected, setSelected] = useState<SelectedEvidence | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setData(await applicationProfiles.competency(profileId)); }
    catch (cause) { setError(interviewError(cause)); }
    finally { setLoading(false); }
  }, [profileId]);
  useEffect(() => { void load(); }, [load, refreshKey]);

  const filtered = (data?.skills || []).filter(skill => {
    const matches = filter === 'all' || (filter === 'focus' && needsFocus(skill.assessment))
      || (filter === 'met' && meets(skill.assessment)) || (filter === 'pending' && !meets(skill.assessment) && !needsFocus(skill.assessment));
    return matches && searchText(`${skill.skillId} ${skillLabel(skill.skillId)}`).includes(searchText(query.trim()));
  }).sort((a, b) => {
    const rank = (value: CompetencyStatus) => value === 'NEEDS_VERIFICATION' ? 0 : needsFocus(value) ? 1 : meets(value) ? 3 : 2;
    return rank(a.assessment) - rank(b.assessment);
  });
  const selectedSkill = data?.skills.find(skill => skill.skillId === selected?.skillId);
  const selectedObjective = selectedSkill?.objectives.find(objective => objective.id === selected?.objectiveId);
  const selectedCriterion = selectedObjective?.criteria.find(criterion => criterion.id === selected?.criterionId);
  const focusCount = data ? data.summary.belowTarget + data.summary.needsVerification : 0;
  const pendingCount = data ? data.summary.incomplete + data.summary.notAssessed : 0;

  return <section id="competency" aria-labelledby="competency-title" aria-busy={loading} className="scroll-mt-24 overflow-hidden rounded-2xl border bg-card">
    <header className="flex items-start justify-between gap-3 px-5 py-5 sm:px-6"><div className="min-w-0 max-w-2xl flex-1 space-y-1"><h2 id="competency-title" className="text-lg font-semibold">Năng lực hiện tại theo JD</h2><p className="text-sm leading-6 text-muted-foreground">Dựa trên câu trả lời qua phỏng vấn, tách biệt với chẩn đoán từ CV.</p></div><Button aria-label="Cập nhật" title="Cập nhật đánh giá" className="shrink-0" variant="outline" size="sm" disabled={loading} onClick={() => void load()}><RefreshCw size={13} className={loading ? 'animate-spin' : ''} /><span className="hidden sm:inline">Cập nhật</span></Button></header>
    {loading && <p role="status" className="px-5 pb-4 text-sm text-muted-foreground sm:px-6">Đang tổng hợp bằng chứng…</p>}
    {error && <div role="alert" className="mx-5 mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm sm:mx-6"><p>{error}</p><Button variant="outline" size="sm" onClick={() => void load()}>Thử lại</Button></div>}
    {!error && data && <>
      {!data.completedAttempts ? <div className="mx-5 mb-6 rounded-xl border border-dashed bg-muted/15 px-5 py-9 text-center sm:mx-6"><CircleHelp className="mx-auto mb-3 text-muted-foreground" size={28} /><h3 className="font-semibold">Chưa có đánh giá qua phỏng vấn</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">Hoàn thành một lượt phỏng vấn để biết kỹ năng nào đã đáp ứng yêu cầu và nội dung nào cần kiểm chứng thêm.</p>{data.skills.length > 0 && <div className="mt-5 flex flex-wrap justify-center gap-2">{data.skills.slice(0, 6).map(skill => <span key={skill.skillId} className="rounded-lg border bg-card px-2.5 py-1 text-xs text-muted-foreground">{skillLabel(skill.skillId)}</span>)}{data.skills.length > 6 && <span className="px-2 py-1 text-xs text-muted-foreground">+{data.skills.length - 6} kỹ năng</span>}</div>}</div> : <>
        <div className="mx-5 grid grid-cols-3 gap-2 sm:mx-6 sm:gap-3" aria-label="Tổng quan năng lực">
          <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3 sm:p-4"><p className="flex min-h-8 items-start gap-2 text-xs font-medium text-emerald-800 sm:min-h-0 sm:items-center"><CheckCircle2 className="hidden sm:block" size={15} />Đáp ứng yêu cầu</p><p className="mt-2 text-2xl font-semibold tabular-nums sm:text-3xl">{data.summary.meetingTarget}<span className="ml-2 hidden text-sm font-normal text-muted-foreground sm:inline">kỹ năng</span></p><p className="mt-1 hidden text-xs text-muted-foreground sm:block">Theo phần đã được kiểm chứng</p></div>
          <div className={`rounded-xl border p-3 sm:p-4 ${focusCount ? 'border-amber-200/70 bg-amber-50/50' : 'bg-muted/20'}`}><p className="flex min-h-8 items-start gap-2 text-xs font-medium text-amber-800 sm:min-h-0 sm:items-center"><Focus className="hidden sm:block" size={15} />Cần tập trung</p><p className="mt-2 text-2xl font-semibold tabular-nums sm:text-3xl">{focusCount}<span className="ml-2 hidden text-sm font-normal text-muted-foreground sm:inline">kỹ năng</span></p><p className="mt-1 hidden text-xs text-muted-foreground sm:block">{data.summary.belowTarget} dưới yêu cầu · {data.summary.needsVerification} cần kiểm chứng</p></div>
          <div className="rounded-xl border bg-muted/20 p-3 sm:p-4"><p className="flex min-h-8 items-start gap-2 text-xs font-medium text-muted-foreground sm:min-h-0 sm:items-center"><CircleHelp className="hidden sm:block" size={15} />Cần đánh giá thêm</p><p className="mt-2 text-2xl font-semibold tabular-nums sm:text-3xl">{pendingCount}<span className="ml-2 hidden text-sm font-normal text-muted-foreground sm:inline">kỹ năng</span></p><p className="mt-1 hidden text-xs text-muted-foreground sm:block">Chưa kiểm tra hoặc chưa đủ bằng chứng</p></div>
        </div>
        <p className="mx-5 mt-4 flex flex-wrap items-center gap-x-1 gap-y-1 text-xs leading-5 text-muted-foreground sm:mx-6">{data.completedAttempts} lượt có câu trả lời đã kết thúc.{data.lastAssessment && <> Bằng chứng mới nhất: <SourceLink source={data.lastAssessment} />{data.lastAssessment.assessedAt && <span>· {formatProfileDate(data.lastAssessment.assessedAt)}</span>}</>}</p>
        {data.incompatibleAssessments > 0 && <p className="mx-5 mt-4 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900 sm:mx-6">{data.incompatibleAssessments} đánh giá có bộ tiêu chí khác nên chưa được gộp vào kết quả hiện tại.</p>}

        <div className="mt-6 border-y bg-muted/10 px-5 py-4 sm:px-6"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-1" role="group" aria-label="Lọc đánh giá kỹ năng">{[
          { value: 'all', label: 'Tất cả', count: data.summary.totalSkills }, { value: 'focus', label: 'Cần tập trung', count: focusCount },
          { value: 'met', label: 'Đáp ứng', count: data.summary.meetingTarget }, { value: 'pending', label: 'Chưa đủ đánh giá', count: pendingCount },
        ].map(item => <button key={item.value} aria-pressed={filter === item.value} onClick={() => { setFilter(item.value as Filter); setLimit(6); }} className={`rounded-lg px-2.5 py-2 text-xs transition focus-visible:outline-2 focus-visible:outline-brand-orange ${filter === item.value ? 'bg-foreground font-medium text-background' : 'text-muted-foreground hover:bg-muted'}`}>{item.label}<span className="ml-1.5 opacity-70">{item.count}</span></button>)}</div><div className="flex min-w-0 items-center gap-2 rounded-lg border bg-card px-3 focus-within:border-brand-orange focus-within:ring-2 focus-within:ring-brand-orange/10"><Search size={14} className="shrink-0 text-muted-foreground" /><input aria-label="Tìm kỹ năng" className="h-9 min-w-0 flex-1 bg-transparent text-xs outline-none sm:w-32" placeholder="Tìm kỹ năng…" value={query} onChange={e => { setQuery(e.target.value); setLimit(6); }} /></div></div></div>

        {!filtered.length && <div className="px-5 py-10 text-center"><p className="text-sm font-medium">Không có kỹ năng phù hợp</p><p className="mt-2 text-xs text-muted-foreground">Thử tìm kiếm khác hoặc chọn tất cả kỹ năng.</p><Button variant="ghost" size="sm" className="mt-3" onClick={() => { setQuery(''); setFilter('all'); }}>Xóa bộ lọc</Button></div>}
        <div className="divide-y">{filtered.slice(0, limit).map(skill => <details key={skill.skillId} data-skill={skill.skillId} className="group/skill">
          <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-5 py-4 transition hover:bg-muted/20 focus-visible:outline-2 focus-visible:outline-brand-orange sm:px-6"><div className="min-w-0"><h3 className="text-sm font-semibold">{skillLabel(skill.skillId)}</h3><p className="mt-1 text-xs leading-5 text-muted-foreground"><span className="sm:hidden">{skill.evidencedCriteria}/{skill.totalCriteria} tiêu chí</span><span className="hidden sm:inline">{skill.evidencedCriteria}/{skill.totalCriteria} tiêu chí có bằng chứng độc lập</span>{skill.lastChecked && ` · Lượt ${skill.lastChecked.attemptNumber}`}</p></div><div className="flex max-w-full items-center gap-2 sm:gap-3"><Status value={skill.assessment} /><ChevronDown className="shrink-0 text-muted-foreground transition group-open/skill:rotate-180" size={15} /></div></summary>
          <div className="border-t bg-muted/10 px-5 py-5 sm:px-6"><p className="mb-5 text-xs leading-5 text-muted-foreground">Mốc CV–JD: {skill.baselineAlignment === 'MATCH' ? 'Có bằng chứng phù hợp trong CV' : skill.baselineAlignment === 'PARTIAL' ? 'Có bằng chứng liên quan trong CV' : 'Chưa có bằng chứng tương ứng trong CV'}.</p>
            {!skill.objectives.length && <p className="text-sm text-muted-foreground">Chưa có bộ tiêu chí phỏng vấn cho kỹ năng này.</p>}
            <div className="space-y-5">{skill.objectives.map(objective => <article key={objective.id} className="space-y-3 border-b pb-5 last:border-0 last:pb-0"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><MarkdownContent className="font-medium" content={objective.claim} /></div>{skill.objectives.length > 1 && <Status value={objective.assessment} />}</div><p className="text-xs leading-6 text-muted-foreground">{objective.explanation}</p>
              {objective.lastAssessment && <p className="text-xs text-muted-foreground">Căn cứ đánh giá: <SourceLink source={objective.lastAssessment} /></p>}
              <div className="divide-y rounded-xl border bg-card">{objective.criteria.map(criterion => <div key={criterion.id} className="space-y-2 p-3.5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><MarkdownContent className="text-sm" content={criterion.description} /><p className="mt-1 text-xs text-muted-foreground">{criterion.essential ? 'Tiêu chí cốt lõi' : 'Tiêu chí bổ sung'}</p></div><Status value={criterion.assessment} observed /></div>{criterion.evidence.length > 0 ? <Button variant="ghost" size="sm" className="-ml-2 h-8 text-xs text-brand-orange" onClick={() => setSelected({ skillId: skill.skillId, objectiveId: objective.id, criterionId: criterion.id })}>Xem bằng chứng ({criterion.evidence.length})<ArrowUpRight size={13} /></Button> : <p className="text-xs text-muted-foreground">Chưa có bằng chứng độc lập cho tiêu chí này.</p>}</div>)}</div>
            </article>)}</div>
          </div>
        </details>)}</div>
        {filtered.length > limit && <div className="border-t px-5 py-3 text-center"><Button variant="ghost" size="sm" onClick={() => setLimit(limit + 6)}>Xem thêm kỹ năng ({filtered.length - limit})</Button></div>}
      </>}

      <details className="border-t px-5 py-4 text-xs text-muted-foreground sm:px-6"><summary className="flex cursor-pointer list-none items-center gap-2 font-medium"><Info size={14} />Cách hệ thống cập nhật đánh giá<ChevronDown size={13} /></summary><ul className="mt-3 max-w-3xl list-disc space-y-2 pl-5 leading-6"><li>Chỉ tổng hợp các lượt đã kết thúc và có câu trả lời. Lượt đang diễn ra hoặc hủy trước khi trả lời không làm thay đổi kết quả.</li><li>Nội dung chưa được hỏi lại giữ đánh giá đã có. Kỹ năng chưa được kiểm tra không được xem là điểm yếu.</li><li>Bằng chứng trái ngược cần hai lượt xác nhận nhất quán về sau ở bối cảnh độc lập. Việc lặp lại cùng bối cảnh không đủ.</li><li>Câu trả lời có gợi ý hoặc ở mức dễ hơn không xác nhận đáp ứng yêu cầu JD. Kết quả từng tiêu chí chỉ áp dụng cho phần đã được kiểm chứng.</li></ul></details>
    </>}
    <Dialog open={Boolean(selectedCriterion)} onOpenChange={open => !open && setSelected(null)}><DialogContent className="sm:max-w-2xl"><DialogHeader><DialogTitle>Bằng chứng đánh giá · {selectedSkill && skillLabel(selectedSkill.skillId)}</DialogTitle><DialogDescription>Trích đoạn câu trả lời và nhận xét theo tiêu chí đã chọn.</DialogDescription></DialogHeader>{selectedCriterion && <EvidenceContent criterion={selectedCriterion} />}<DialogFooter><Button variant="outline" onClick={() => setSelected(null)}>Đóng bằng chứng</Button></DialogFooter></DialogContent></Dialog>
  </section>;
}
