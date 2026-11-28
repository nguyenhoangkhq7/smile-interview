'use client';

import { useId, useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, FileText, Search, Sparkles } from 'lucide-react';
import { searchText, skillLabel } from './applicationUi';
import { getTaskPreparation } from './taskPreparation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { jdSkillLabel } from '@/lib/skillLabels';
import { EligibilityPanel } from './eligibility/EligibilityPanel';
import type { ExtractedCvSkill, SkillGapResult, SkillGapReport } from '@/services/cvJdMatching';

const alignmentInfo = {
  MATCH: { label: 'Phù hợp', profileLabel: 'CV có nội dung phù hợp', tone: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200', order: 2 },
  PARTIAL: { label: 'Liên quan', profileLabel: 'CV có nội dung liên quan', tone: 'bg-amber-50 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200', order: 1 },
  MISSING: { label: 'CV chưa thể hiện', profileLabel: 'CV chưa thể hiện', tone: 'bg-muted text-muted-foreground', order: 0 },
};

type Filter = 'all' | SkillGapResult['semantic_alignment'];
const pageSize = 5;
const cvLabel = (skill: SkillGapResult) => skill.matched_cv_skill_id
  ? skillLabel(skill.matched_cv_skill_id, skill.matched_cv_skill_name, skill.cv_evidence_spans ?? []) : '';

function hasQuote(spans?: readonly string[]) {
  return spans?.some(span => span.trim()) ?? false;
}

function skillRow(skill: SkillGapResult, profileView: boolean) {
  const requiredTask = profileView
    ? skill.job_tasks?.find(task => task.requirement_kind === 'REQUIRED' && hasQuote(task.evidence_spans))
    : undefined;
  return {
    skill,
    name: jdSkillLabel(skill),
    relatedName: cvLabel(skill),
    requiredTask,
    reviewFirst: Boolean(requiredTask && skill.semantic_alignment !== 'MATCH'),
  };
}

function distinctQuotes(spans: readonly string[]) {
  return [...new Set(spans.map(span => span.trim()).filter(Boolean))];
}

function DocumentEvidence({ title, quotes, empty, children }: {
  title: string;
  quotes: string[];
  empty: string;
  children?: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground">{title}</h3>
      {quotes.length ? (
        <ul className="space-y-2 border-l-2 border-brand-orange/25 pl-3">
          {quotes.map(quote => <li key={quote}><blockquote className="whitespace-pre-wrap wrap-anywhere">“{quote}”</blockquote></li>)}
        </ul>
      ) : <p className="text-muted-foreground">{empty}</p>}
      {children}
    </div>
  );
}

function ProfileSkillRow({ row, group }: { row: ReturnType<typeof skillRow>; group: string }) {
  const { skill, name, relatedName, requiredTask } = row;
  const alignment = alignmentInfo[skill.semantic_alignment];
  const tasks = skill.job_tasks ?? [];
  const preparation = skill.semantic_alignment === 'MATCH' ? undefined : getTaskPreparation(tasks);
  const jdQuotes = distinctQuotes([
    ...(preparation ? [preparation.jdQuote] : []),
    ...(requiredTask?.evidence_spans ?? []),
    ...tasks.flatMap(task => task.evidence_spans ?? []),
    ...(skill.jd_evidence_spans ?? []),
  ]);
  const cvQuotes = distinctQuotes(skill.cv_evidence_spans ?? []);

  return (
    <details name={group} className="group/evidence">
      <summary
        data-cv-skill={skill.jd_skill_id}
        className="grid min-h-14 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-3 py-3 transition-colors hover:bg-muted/30 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:px-4 [&::-webkit-details-marker]:hidden"
      >
        <span className="col-start-1 row-start-1 min-w-0">
          <span className="block text-sm font-semibold wrap-anywhere">{name}</span>
          {requiredTask && <span className="mt-0.5 block text-xs text-muted-foreground">Có yêu cầu bắt buộc</span>}
        </span>
        <span className={`col-start-1 row-start-2 justify-self-start rounded-md px-2 py-1 text-xs font-medium sm:col-start-2 sm:row-start-1 ${alignment.tone}`}>
          {alignment.profileLabel}
        </span>
        <ChevronDown aria-hidden="true" size={16} className="col-start-2 row-span-2 row-start-1 text-muted-foreground transition-transform group-open/evidence:rotate-180 sm:col-start-3 sm:row-span-1" />
      </summary>
      <div
        role="region"
        aria-label={`Căn cứ đối chiếu ${name}`}
        tabIndex={0}
        className="mx-2 mb-2 max-h-[min(28rem,55dvh)] overflow-y-auto overscroll-contain rounded-lg bg-muted/35 p-3 text-sm leading-6 focus-visible:outline-2 focus-visible:outline-brand-orange sm:mx-3 sm:mb-3 sm:p-4"
      >
        <div className="grid gap-4 sm:grid-cols-2 sm:gap-5">
          <DocumentEvidence title="Yêu cầu trong JD" quotes={jdQuotes} empty="Chưa có trích dẫn từ JD.">
            {!jdQuotes.length && skill.context_job && <p className="wrap-anywhere">Bối cảnh công việc · {skill.context_job}</p>}
          </DocumentEvidence>
          <DocumentEvidence
            title="Căn cứ trong CV"
            quotes={cvQuotes}
            empty={skill.semantic_alignment === 'MISSING' ? 'Chưa tìm thấy nội dung tương ứng trong CV.' : 'Chưa có trích dẫn từ CV.'}
          >
            {relatedName && skill.matched_cv_skill_id !== skill.jd_skill_id && <p className="wrap-anywhere">Kỹ năng liên quan · {relatedName}</p>}
          </DocumentEvidence>
        </div>
        {preparation && (
          <div className="mt-3 border-t pt-3">
            <h3 className="text-xs font-semibold">Gợi ý chuẩn bị</h3>
            <p className="mt-1 font-semibold">{preparation.title}</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground wrap-anywhere">Theo nhiệm vụ “{preparation.taskDescription}”</p>
            <p className="mt-1">Nếu từng làm nhiệm vụ này, {preparation.exercise}</p>
          </div>
        )}
      </div>
    </details>
  );
}

// Candidate pages use structured fields instead of the internal audit Markdown.
type SummaryProps = {
  skills: SkillGapResult[];
  report: SkillGapReport;
  view?: 'analysis' | 'profile';
};

export function CandidateCvJdSummary(props: SummaryProps) {
  const cvSkills = props.report?.cv_skills;
  return <Tabs defaultValue="jd">
    <TabsList aria-label="Kết quả phân tích" className="max-w-full">
      <TabsTrigger value="jd">Đối chiếu với JD</TabsTrigger>
      <TabsTrigger value="cv">Kỹ năng từ CV{cvSkills && <span className="tabular-nums">({cvSkills.length})</span>}</TabsTrigger>
    </TabsList>
    <TabsContent value="jd" className="space-y-4">
      <JdComparison {...props} />
      {props.report?.eligibility && <EligibilityPanel report={props.report.eligibility} />}
    </TabsContent>
    <TabsContent value="cv"><CvSkillList skills={cvSkills} /></TabsContent>
  </Tabs>;
}

function CvSkillList({ skills }: { skills?: ExtractedCvSkill[] | null }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const panelId = useId();
  if (!skills?.length) {
    return <p className="rounded-xl border px-4 py-6 text-sm text-muted-foreground">
      {skills ? 'Lần phân tích này chưa trích xuất được kỹ năng nào từ CV.' : 'Lần phân tích này chưa lưu danh sách kỹ năng từ CV.'}
    </p>;
  }
  return <div className="divide-y rounded-xl border bg-card">
    {(['explicit', 'implicit'] as const).map(type => {
      const group = skills.filter(skill => skill.type === type);
      if (!group.length) return null;
      const direct = type === 'explicit';
      const Icon = direct ? FileText : Sparkles;
      const selected = group.find(skill => skill.skill_id === selectedId);
      const evidenceId = `${panelId}-${type}`;
      return <section key={type} className="space-y-3 px-4 py-4 sm:px-5">
        <div className="flex items-center gap-2">
          <Icon aria-hidden="true" size={16} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold">{direct ? 'Nêu trực tiếp' : 'Suy ra từ ngữ cảnh'}</h3>
          <span className="rounded-full bg-muted px-2 text-xs tabular-nums text-muted-foreground">{group.length}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {group.map(skill => {
            const active = selected?.skill_id === skill.skill_id;
            return <button key={skill.skill_id} type="button" aria-expanded={active} aria-controls={evidenceId}
              onClick={() => setSelectedId(active ? null : skill.skill_id)}
              className="inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-left text-sm font-medium transition-colors hover:border-brand-orange/50 hover:bg-muted/35 focus-visible:outline-2 focus-visible:outline-brand-orange aria-expanded:border-brand-orange/50 aria-expanded:bg-brand-orange/10">
              <span className="min-w-0 wrap-anywhere">{skillLabel(skill.skill_id, skill.skill_name, skill.evidence_spans)}</span>
              <ChevronDown aria-hidden="true" size={13} className={`shrink-0 text-muted-foreground ${active ? 'rotate-180' : ''}`} />
            </button>;
          })}
        </div>
        <div id={evidenceId} hidden={!selected} className="rounded-lg bg-muted/45 p-3 text-sm leading-6">
          {selected && <DocumentEvidence title={`Trích dẫn từ CV · ${skillLabel(selected.skill_id, selected.skill_name, selected.evidence_spans)}`}
            quotes={distinctQuotes(selected.evidence_spans ?? [])} empty="Chưa có trích dẫn từ CV cho kỹ năng này." />}
        </div>
      </section>;
    })}
  </div>;
}

function JdComparison({ skills, report, view = 'analysis' }: SummaryProps) {
  const profileView = view === 'profile';
  const showControls = !profileView || skills.length > pageSize;
  const group = useId();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const rows = useMemo(() => skills.map(skill => skillRow(skill, profileView))
    .sort((a, b) => Number(b.reviewFirst) - Number(a.reviewFirst)
      || alignmentInfo[a.skill.semantic_alignment].order - alignmentInfo[b.skill.semantic_alignment].order), [skills, profileView]);
  const selected = rows.find(row => row.skill.jd_skill_id === selectedId);
  const search = searchText(query.trim());
  const filtered = rows.filter(({ skill, name, relatedName }) => (filter === 'all' || skill.semantic_alignment === filter)
    && searchText(`${name} ${relatedName}`).includes(search));
  const totalPages = Math.ceil(filtered.length / pageSize);
  const currentPage = Math.min(page, Math.max(0, totalPages - 1));
  const offset = currentPage * pageSize;
  const score = report?.matching_score;
  const hasScore = typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1;
  const emptyMessage = profileView ? 'Chưa có kết quả đối chiếu kỹ năng.' : 'Chưa có kết quả đối chiếu kỹ năng. Hãy kiểm tra tài liệu rồi phân tích lại.';
  const filters: { value: Filter; label: string; count: number }[] = [
    { value: 'all', label: 'Tất cả', count: skills.length },
    ...(['MISSING', 'PARTIAL', 'MATCH'] as const).map(value => ({ value, label: alignmentInfo[value].label, count: skills.filter(skill => skill.semantic_alignment === value).length })),
  ];

  return <div className="space-y-4" aria-label="Kết quả đối chiếu CV và mô tả công việc">
    {!profileView && <div className="flex items-center gap-4 rounded-xl border border-emerald-100 bg-emerald-50/40 px-4 py-3">
      <p className="shrink-0 text-3xl font-semibold tabular-nums text-emerald-800">{hasScore ? `${Math.round(score * 100)}%` : '—'}</p>
      <div className="min-w-0"><p className="text-sm font-medium">Mức phù hợp CV–JD</p><p className="mt-0.5 text-xs leading-5 text-muted-foreground">{hasScore ? 'Ước tính từ tài liệu, chưa phải kết quả đánh giá qua phỏng vấn.' : 'Chưa có điểm phù hợp từ tài liệu.'}</p></div>
    </div>}
    {!profileView && report?.degraded && <p role="status" className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200">Một phần phân tích chưa đầy đủ. Bạn có thể kiểm tra tài liệu hoặc phân tích lại.</p>}
    {showControls && <div className="flex flex-wrap items-center justify-between gap-3">
      <div role="group" aria-label="Lọc đối chiếu kỹ năng" className="flex flex-wrap gap-1">
        {filters.map(item => <button key={item.value} type="button" aria-pressed={filter === item.value}
          onClick={() => { setFilter(item.value); setPage(0); }}
          className={`rounded-lg px-2.5 py-2 text-xs transition focus-visible:outline-2 focus-visible:outline-brand-orange ${filter === item.value ? 'bg-foreground font-medium text-background' : 'bg-muted/40 text-muted-foreground hover:bg-muted'}`}>
          {item.label}<span className="ml-1.5 tabular-nums opacity-70">{item.count}</span>
        </button>)}
      </div>
      <div className="flex w-full items-center gap-2 rounded-lg border px-3 focus-within:ring-2 focus-within:ring-brand-orange/20 sm:w-48">
        <Search size={14} className="shrink-0 text-muted-foreground" aria-hidden="true" />
        <input aria-label="Tìm kỹ năng trong CV và JD" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder="Tìm kỹ năng…" className="h-9 min-w-0 w-full bg-transparent text-xs outline-none" />
      </div>
    </div>}
    <div className="overflow-hidden rounded-xl border">
      {!profileView && <div className="flex items-center justify-between gap-2 border-b bg-muted/25 px-3 py-2 text-xs text-muted-foreground sm:px-4"><h3 className="font-medium">Kỹ năng theo JD</h3><span>Chọn để xem chi tiết</span></div>}
      <div aria-live={profileView ? undefined : 'polite'} className="divide-y">
        {filtered.slice(offset, offset + pageSize).map(row => profileView ? (
          <ProfileSkillRow key={row.skill.jd_skill_id} row={row} group={group} />
        ) : <button key={row.skill.jd_skill_id} type="button" data-cv-skill={row.skill.jd_skill_id}
          aria-haspopup="dialog" onClick={() => setSelectedId(row.skill.jd_skill_id)}
          className="flex min-h-14 w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-muted/30 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange sm:px-4">
          <span className="min-w-0 flex-1 break-words text-sm font-medium">{row.name}</span>
          <span className={`shrink-0 rounded-md px-2 py-1 text-[11px] font-medium ${alignmentInfo[row.skill.semantic_alignment].tone}`}>{alignmentInfo[row.skill.semantic_alignment].label}</span>
          <ChevronRight size={15} className="shrink-0 text-muted-foreground" aria-hidden="true" />
        </button>)}
        {!filtered.length && <div className="space-y-2 px-4 py-6 text-center text-sm text-muted-foreground">
          <p>{skills.length ? 'Không có kỹ năng phù hợp với bộ lọc.' : emptyMessage}</p>
          {skills.length > 0 && <Button variant="ghost" size="sm" onClick={() => { setFilter('all'); setQuery(''); setPage(0); }}>Xóa bộ lọc</Button>}
        </div>}
      </div>
      {filtered.length > 0 && showControls && <div className="flex items-center justify-between gap-2 border-t px-3 py-2 text-xs text-muted-foreground sm:px-4">
        <p role="status">{offset + 1}–{Math.min(offset + pageSize, filtered.length)} / {filtered.length} kỹ năng</p>
        {totalPages > 1 && <nav aria-label="Trang kỹ năng" className="flex items-center gap-1">
          <Button variant="ghost" size="sm" aria-label="Trang kỹ năng trước" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={15} /></Button>
          <span className="min-w-8 text-center tabular-nums">{currentPage + 1}/{totalPages}</span>
          <Button variant="ghost" size="sm" aria-label="Trang kỹ năng tiếp" disabled={currentPage === totalPages - 1} onClick={() => setPage(currentPage + 1)}><ChevronRight size={15} /></Button>
        </nav>}
      </div>}
    </div>
    {!profileView && <p className="text-xs leading-5 text-muted-foreground">CV chưa thể hiện một kỹ năng không có nghĩa là bạn chưa có kỹ năng đó.</p>}
    {!profileView && <Dialog open={Boolean(selected)} onOpenChange={open => !open && setSelectedId(null)}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader><DialogTitle>{selected?.name}</DialogTitle><DialogDescription>Chi tiết đối chiếu thông tin CV với yêu cầu công việc.</DialogDescription></DialogHeader>
        {selected && <div className="max-h-[60dvh] space-y-4 overflow-y-auto overscroll-contain pr-1 text-sm leading-6">
          <span className={`inline-block rounded-md px-2 py-1 text-xs font-medium ${alignmentInfo[selected.skill.semantic_alignment].tone}`}>{alignmentInfo[selected.skill.semantic_alignment].label}</span>
          {selected.relatedName && selected.skill.matched_cv_skill_id !== selected.skill.jd_skill_id && <p><span className="text-muted-foreground">Kỹ năng liên quan trong CV: </span><strong>{selected.relatedName}</strong></p>}
          {selected.skill.context_job && <div><h4 className="mb-1 font-medium">Ứng dụng trong công việc</h4><p className="whitespace-pre-wrap break-words text-muted-foreground">{selected.skill.context_job}</p></div>}
          <div><h4 className="mb-2 font-medium">Thông tin từ CV</h4>
            {selected.skill.cv_evidence_spans?.length ? <ul className="space-y-3 border-l-2 border-brand-orange/30 pl-3 text-muted-foreground">
              {selected.skill.cv_evidence_spans.map((span, index) => <li key={index} className="whitespace-pre-wrap break-words">“{span}”</li>)}
            </ul> : <p className="text-muted-foreground">Chưa tìm thấy trích dẫn tương ứng. Bạn có thể bổ sung dự án hoặc kinh nghiệm liên quan vào CV nếu có.</p>}
          </div>
        </div>}
      </DialogContent>
    </Dialog>}
  </div>;
}
