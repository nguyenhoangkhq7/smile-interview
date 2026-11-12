'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { searchText, skillLabel } from './applicationUi';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import type { SkillGapResult, StaticGapAuditReport } from '@/services/cvJdMatching';

const alignmentInfo = {
  MATCH: { label: 'Phù hợp', tone: 'bg-emerald-50 text-emerald-800', order: 2 },
  PARTIAL: { label: 'Liên quan', tone: 'bg-amber-50 text-amber-900', order: 1 },
  MISSING: { label: 'CV chưa thể hiện', tone: 'bg-slate-100 text-slate-700', order: 0 },
};

type Filter = 'all' | SkillGapResult['semantic_alignment'];
const pageSize = 5;
const jdLabel = (skill: SkillGapResult) => skillLabel(skill.jd_skill_id, skill.jd_skill_name, skill.jd_evidence_spans);
const cvLabel = (skill: SkillGapResult) => skill.matched_cv_skill_id
  ? skillLabel(skill.matched_cv_skill_id, skill.matched_cv_skill_name, skill.cv_evidence_spans) : '';

// Candidate pages use structured fields instead of the internal audit Markdown.
export function CandidateCvJdSummary({ skills, report }: {
  skills: SkillGapResult[];
  report: Pick<StaticGapAuditReport, 'matching_score' | 'degraded'>;
}) {
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = skills.find(skill => skill.jd_skill_id === selectedId);
  const filtered = skills.filter(skill => (filter === 'all' || skill.semantic_alignment === filter)
    && searchText(`${jdLabel(skill)} ${cvLabel(skill)}`).includes(searchText(query.trim())))
    .sort((a, b) => alignmentInfo[a.semantic_alignment].order - alignmentInfo[b.semantic_alignment].order);
  const totalPages = Math.ceil(filtered.length / pageSize);
  const currentPage = Math.min(page, Math.max(0, totalPages - 1));
  const offset = currentPage * pageSize;
  const score = report.matching_score;
  const hasScore = typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1;
  const filters: { value: Filter; label: string; count: number }[] = [
    { value: 'all', label: 'Tất cả', count: skills.length },
    ...(['MISSING', 'PARTIAL', 'MATCH'] as const).map(value => ({ value, label: alignmentInfo[value].label, count: skills.filter(skill => skill.semantic_alignment === value).length })),
  ];

  return <div className="space-y-4" aria-label="Kết quả đối chiếu CV và mô tả công việc">
    <div className="flex items-center gap-4 rounded-xl border border-emerald-100 bg-emerald-50/40 px-4 py-3">
      <p className="shrink-0 text-3xl font-semibold tabular-nums text-emerald-800">{hasScore ? `${Math.round(score * 100)}%` : '—'}</p>
      <div className="min-w-0"><p className="text-sm font-medium">Mức phù hợp CV–JD</p><p className="mt-0.5 text-xs leading-5 text-muted-foreground">{hasScore ? 'Ước tính từ tài liệu, chưa phải kết quả đánh giá qua phỏng vấn.' : 'Chưa có điểm phù hợp từ tài liệu.'}</p></div>
    </div>
    {(report.degraded || skills.some(skill => skill.degraded)) && <p role="status" className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">Một phần phân tích chưa đầy đủ. Bạn có thể kiểm tra tài liệu hoặc phân tích lại.</p>}
    <div className="flex flex-wrap items-center justify-between gap-3">
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
    </div>
    <div className="overflow-hidden rounded-xl border">
      <div className="flex items-center justify-between gap-2 border-b bg-muted/25 px-3 py-2 text-xs text-muted-foreground sm:px-4"><h3 className="font-medium">Kỹ năng theo JD</h3><span>Chọn để xem chi tiết</span></div>
      <div aria-live="polite" aria-atomic="false" className="divide-y">
        {filtered.slice(offset, offset + pageSize).map(skill => <button key={skill.jd_skill_id} type="button" data-cv-skill={skill.jd_skill_id}
          aria-haspopup="dialog" onClick={() => setSelectedId(skill.jd_skill_id)}
          className="flex min-h-14 w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-muted/30 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange sm:px-4">
          <span className="min-w-0 flex-1 break-words text-sm font-medium">{jdLabel(skill)}</span>
          <span className={`shrink-0 rounded-md px-2 py-1 text-[11px] font-medium ${alignmentInfo[skill.semantic_alignment].tone}`}>{alignmentInfo[skill.semantic_alignment].label}</span>
          <ChevronRight size={15} className="shrink-0 text-muted-foreground" aria-hidden="true" />
        </button>)}
        {!filtered.length && <div className="space-y-2 px-4 py-6 text-center text-sm text-muted-foreground">
          <p>{skills.length ? 'Không có kỹ năng phù hợp với bộ lọc.' : 'Chưa có kết quả đối chiếu kỹ năng. Hãy kiểm tra tài liệu rồi phân tích lại.'}</p>
          {skills.length > 0 && <Button variant="ghost" size="sm" onClick={() => { setFilter('all'); setQuery(''); setPage(0); }}>Xóa bộ lọc</Button>}
        </div>}
      </div>
      {filtered.length > 0 && <div className="flex items-center justify-between gap-2 border-t px-3 py-2 text-xs text-muted-foreground sm:px-4">
        <p role="status">{offset + 1}–{Math.min(offset + pageSize, filtered.length)} / {filtered.length} kỹ năng</p>
        {totalPages > 1 && <nav aria-label="Trang kỹ năng" className="flex items-center gap-1">
          <Button variant="ghost" size="sm" aria-label="Trang kỹ năng trước" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={15} /></Button>
          <span className="min-w-8 text-center tabular-nums">{currentPage + 1}/{totalPages}</span>
          <Button variant="ghost" size="sm" aria-label="Trang kỹ năng tiếp" disabled={currentPage === totalPages - 1} onClick={() => setPage(currentPage + 1)}><ChevronRight size={15} /></Button>
        </nav>}
      </div>}
    </div>
    <p className="text-xs leading-5 text-muted-foreground">CV chưa thể hiện một kỹ năng không có nghĩa là bạn chưa có kỹ năng đó.</p>
    <Dialog open={Boolean(selected)} onOpenChange={open => !open && setSelectedId(null)}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader><DialogTitle>{selected && jdLabel(selected)}</DialogTitle><DialogDescription>Chi tiết đối chiếu thông tin CV với yêu cầu công việc.</DialogDescription></DialogHeader>
        {selected && <div className="max-h-[60dvh] space-y-4 overflow-y-auto overscroll-contain pr-1 text-sm leading-6">
          <span className={`inline-block rounded-md px-2 py-1 text-xs font-medium ${alignmentInfo[selected.semantic_alignment].tone}`}>{alignmentInfo[selected.semantic_alignment].label}</span>
          {selected.matched_cv_skill_id && selected.matched_cv_skill_id !== selected.jd_skill_id && <p><span className="text-muted-foreground">Kỹ năng liên quan trong CV: </span><strong>{cvLabel(selected)}</strong></p>}
          {selected.context_job && <div><h4 className="mb-1 font-medium">Ứng dụng trong công việc</h4><p className="whitespace-pre-wrap break-words text-muted-foreground">{selected.context_job}</p></div>}
          <div><h4 className="mb-2 font-medium">Thông tin từ CV</h4>
            {selected.cv_evidence_spans?.length ? <ul className="space-y-3 border-l-2 border-brand-orange/30 pl-3 text-muted-foreground">
              {selected.cv_evidence_spans.map((span, index) => <li key={index} className="whitespace-pre-wrap break-words">“{span}”</li>)}
            </ul> : <p className="text-muted-foreground">Chưa tìm thấy trích dẫn tương ứng. Bạn có thể bổ sung dự án hoặc kinh nghiệm liên quan vào CV nếu có.</p>}
          </div>
        </div>}
      </DialogContent>
    </Dialog>
  </div>;
}
