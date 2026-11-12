'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, BookOpen, ChevronDown, CircleCheck, ListChecks, MessageSquare, TriangleAlert } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { assessmentLabels, assessmentStatus, resultReasons, skillStatuses, uniqueFindings, type ResultData } from './resultData';

export const resultPanel = 'min-w-0 rounded-2xl border border-slate-200/70 bg-card p-4 shadow-xs sm:p-6';
export const resultSection = 'scroll-mt-36 space-y-4';

export function FindingList({ items, empty, preview = 3 }: { items: readonly string[]; empty?: string; preview?: number }) {
  if (!items.length) return empty ? <p className="text-sm text-muted-foreground">{empty}</p> : null;
  return (
    <div className="space-y-2">
      <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed wrap-anywhere">
        {items.slice(0, preview).map(item => <li key={item}><MarkdownContent content={item} /></li>)}
      </ul>
      {items.length > preview && <details className="group/findings">
        <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-semibold underline-offset-4 hover:underline">
          Xem thêm ({items.length - preview}) <ChevronDown size={14} className="group-open/findings:rotate-180" />
        </summary>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed wrap-anywhere">
          {items.slice(preview).map(item => <li key={item}><MarkdownContent content={item} /></li>)}
        </ul>
      </details>}
    </div>
  );
}

export function ResultFeedback({ data }: { data: ResultData }) {
  return (
    <section id="feedback" className={cn(resultPanel, resultSection)}>
      <h2 className="flex items-center gap-2 text-xl font-bold"><MessageSquare size={21} className="text-orange-700" /> Nhận xét từ AI</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-2 rounded-xl bg-emerald-50 p-4 text-emerald-950">
          <h3 className="flex items-center gap-2 font-semibold"><CircleCheck size={17} /> Điểm mạnh</h3>
          <FindingList items={data.strengths} empty="Chưa có đủ thông tin để ghi nhận điểm mạnh cụ thể." />
        </div>
        <div className="space-y-2 rounded-xl bg-orange-50 p-4 text-orange-950">
          <h3 className="flex items-center gap-2 font-semibold"><TriangleAlert size={17} /> Điểm cần cải thiện</h3>
          <FindingList items={data.weaknesses} empty="Chưa ghi nhận điểm cần cải thiện trong phần đã hỏi." />
        </div>
      </div>
    </section>
  );
}

type Filter = 'all' | keyof typeof skillStatuses;

function ResultFilters({ filters, value, onChange, label }: {
  filters: { id: Filter; label: string; count: number }[];
  value: Filter;
  onChange: (value: Filter) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1 text-xs">
      {filters.map(filter => (
        <button type="button" key={filter.id} aria-pressed={value === filter.id} onClick={() => onChange(filter.id)}
          className="cursor-pointer rounded-lg px-2.5 py-1.5 font-medium text-slate-700 hover:bg-white/60 aria-pressed:bg-white aria-pressed:text-[#a02707] aria-pressed:shadow-xs">
          {filter.label} ({filter.count})
        </button>
      ))}
    </div>
  );
}

function SkillCard({ skill }: { skill: ResultData['skills'][number] }) {
  const status = skillStatuses[skill.status];
  return (
    <article className={cn(resultPanel, 'space-y-3')}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="min-w-0 text-base font-bold wrap-anywhere">{skillLabel(skill.id, null, skill.objectives.flatMap(objective => objective.jd_evidence_spans))}</h3>
        <span className={cn('rounded-full px-2.5 py-1 text-xs font-semibold', status.tone)}>{status.label}</span>
      </div>
      <p className="text-xs text-muted-foreground">{skill.questionCount} câu hỏi{skill.objectives.length > 0 && ` · ${skill.objectives.length} nội dung đã phỏng vấn`}</p>
      <p className="text-sm leading-relaxed text-slate-600">{skill.status === 'strong'
        ? 'Bạn đáp ứng yêu cầu ở những nội dung đã hỏi.'
        : skill.status === 'weak' ? 'Có nội dung bạn cần ôn luyện thêm để đáp ứng yêu cầu.'
          : 'Câu trả lời hiện có chưa đủ để kết luận về kỹ năng này.'}</p>
      {skill.objectives.length > 0 && <p className="line-clamp-2 text-sm text-slate-700"><span className="font-medium">Đã hỏi: </span>{skill.objectives.map(objective => objective.claim).join('; ')}</p>}
      {skill.objectives.length > 0 && <details className="group border-t border-slate-100 pt-2">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium text-[#a02707]">
          Xem đánh giá chi tiết <ChevronDown size={16} className="group-open:rotate-180" />
        </summary>
        <div className="mt-3 space-y-4">
          {skill.objectives.map(objective => {
            const criteria = objective.criteria?.filter(criterion => criterion.turns_spent > 0 || criterion.assessment !== 'NOT_ASSESSED') ?? [];
            return (
              <div key={objective.objective_id} className="space-y-2 text-sm wrap-anywhere">
                <h4 className="font-semibold">{objective.claim}</h4>
                <p className={cn('inline-block rounded-md px-2 py-1 text-xs', skillStatuses[assessmentStatus(objective.assessment)].tone)}>{objective.assessment === 'NOT_ASSESSED' ? 'Chưa đủ cơ sở kết luận' : assessmentLabels[objective.assessment]}</p>
                {objective.stop_reason && objective.stop_reason !== 'SUFFICIENT_EVIDENCE' && <p className="text-xs text-muted-foreground">{resultReasons[objective.stop_reason] ?? 'Chưa đủ thông tin để đánh giá thêm nội dung này.'}</p>}
                {criteria.length > 0 && (
                  <ul className="space-y-1 rounded-lg bg-slate-50 p-3">
                    {criteria.map(criterion => (
                      <li key={criterion.criterion_id}>
                        <p>{criterion.description}: {criterion.assessment === 'NOT_ASSESSED' ? 'Chưa đủ cơ sở kết luận' : assessmentLabels[criterion.assessment]}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </details>}
    </article>
  );
}

export function ResultSkills({ skills }: { skills: ResultData['skills'] }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [limit, setLimit] = useState(6);
  const filtered = filter === 'all' ? skills : skills.filter(skill => skill.status === filter);
  const filters = [{ id: 'all' as const, label: 'Tất cả', count: skills.length },
    ...Object.entries(skillStatuses).filter(([id]) => skills.some(skill => skill.status === id)).map(([id, status]) => ({
      id: id as keyof typeof skillStatuses, label: status.label, count: skills.filter(skill => skill.status === id).length,
    }))];
  return (
    <section id="skills" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1"><h2 className="text-xl font-bold">Kỹ năng đã phỏng vấn <span className="text-sm font-medium text-muted-foreground">({skills.length})</span></h2><p className="text-sm text-muted-foreground">Chỉ gồm các kỹ năng được hỏi trong buổi này. Mở từng kỹ năng để xem chi tiết.</p></div>
        {filters.length > 2 && <ResultFilters filters={filters} value={filter} label="Lọc kỹ năng" onChange={value => { setFilter(value); setLimit(6); }} />}
      </div>
      <div className="grid items-start gap-3 md:grid-cols-2">
        {filtered.slice(0, limit).map(skill => <SkillCard key={skill.id} skill={skill} />)}
      </div>
      {!filtered.length && <p className={cn(resultPanel, 'text-sm text-muted-foreground')}>Chưa có kỹ năng trong nhóm này.</p>}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 6)}>Xem thêm kỹ năng ({filtered.length - limit})</Button>}
    </section>
  );
}

const questionLabels = { strong: 'Thể hiện tốt', weak: 'Cần cải thiện', partial: 'Chưa có kết luận' } as const;

export function ResultQuestions({ questions }: { questions: ResultData['questions'] }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [limit, setLimit] = useState(5);
  const filtered = filter === 'all' ? questions : questions.filter(item => item.status === filter);
  const filters = [{ id: 'all' as const, label: 'Tất cả', count: questions.length },
    ...Object.entries(questionLabels).filter(([id]) => questions.some(item => item.status === id)).map(([id, label]) => ({
      id: id as keyof typeof questionLabels, label, count: questions.filter(item => item.status === id).length,
    }))];
  return (
    <section id="questions" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold">Chi tiết câu hỏi phỏng vấn <span className="text-sm font-medium text-muted-foreground">({questions.length} câu)</span></h2>
        {filters.length > 2 && <ResultFilters filters={filters} value={filter} label="Lọc câu hỏi" onChange={value => { setFilter(value); setLimit(5); }} />}
      </div>
      {filtered.slice(0, limit).map(({ turn, index, evidence, status }) => (
        <details key={turn.turn_id} className="group rounded-xl border border-slate-200 bg-card shadow-xs">
          <summary className="flex cursor-pointer list-none items-center gap-3 p-4">
            <span className={cn('grid size-8 shrink-0 place-items-center rounded-lg text-xs font-bold', skillStatuses[status].tone)}>{String(index + 1).padStart(2, '0')}</span>
            <span className="min-w-0 flex-1">
              <span className="mb-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {turn.skill_id && <span>{skillLabel(turn.skill_id)}</span>}
                <span>{questionLabels[status]}</span>
              </span>
              <span className="line-clamp-2 text-sm font-semibold wrap-anywhere">{turn.question}</span>
            </span>
            <ChevronDown size={18} className="shrink-0 group-open:rotate-180" />
          </summary>
          <div className="space-y-4 border-t border-slate-100 bg-slate-50/70 p-4 text-sm wrap-anywhere">
            <div className="space-y-1"><h3 className="font-semibold">Câu hỏi đầy đủ</h3><MarkdownContent content={turn.question} /></div>
            <div className="space-y-1 rounded-lg border bg-card p-3"><h3 className="font-semibold">Câu trả lời của bạn</h3><MarkdownContent content={turn.answer || 'Chưa có câu trả lời.'} /></div>
            {turn.feedback && <div className="space-y-1 rounded-lg bg-sky-50 p-3"><h3 className="font-semibold">Nhận xét từ AI</h3><MarkdownContent content={turn.feedback} /></div>}
            {!!evidence.length && (
              <details className="group/evidence space-y-2">
                <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">Cơ sở đánh giá <ChevronDown size={14} className="group-open/evidence:rotate-180" /></summary>
                {evidence.map((item, index) => (
                  <blockquote key={index} className="space-y-1 border-l-2 border-orange-300 pl-3">
                    {item.response_excerpt && <MarkdownContent content={item.response_excerpt} />}
                    <MarkdownContent content={item.rationale} />
                  </blockquote>
                ))}
              </details>
            )}
          </div>
        </details>
      ))}
      {!filtered.length && <p className={cn(resultPanel, 'text-sm text-muted-foreground')}>Chưa có câu hỏi trong nhóm này.</p>}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 5)}>Xem thêm câu hỏi ({filtered.length - limit})</Button>}
    </section>
  );
}

export function ResultStudy({ data, studyHref }: { data: ResultData; studyHref: string }) {
  const groups = data.skills.flatMap(skill => {
    const weaknesses = uniqueFindings(skill.objectives.flatMap(objective => objective.weaknesses));
    const recommendations = uniqueFindings(skill.objectives.flatMap(objective => objective.study_recommendations ?? []));
    return weaknesses.length || recommendations.length ? [{ ...skill, weaknesses, recommendations }] : [];
  });
  const groupedRecommendations = new Set(groups.flatMap(group => group.recommendations));
  const additionalRecommendations = data.recommendations.filter(item => !groupedRecommendations.has(item));
  return (
    <section id="study" className={resultSection}>
      <div className="space-y-1"><h2 className="text-xl font-bold">Gợi ý ôn tập sau buổi phỏng vấn</h2><p className="text-sm text-muted-foreground">Tập trung vào những nội dung cần cải thiện từ câu trả lời của bạn.</p></div>
      {groups.length > 0 && <div className="grid items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
        {groups.map(group => (
          <article key={group.id} className={cn(resultPanel, 'space-y-3')}>
            <div className="flex items-center gap-2">
              <BookOpen size={19} className="shrink-0 text-orange-700" /><h3 className="font-bold wrap-anywhere">{skillLabel(group.id, null, group.objectives.flatMap(objective => objective.jd_evidence_spans))}</h3>
            </div>
            {!group.recommendations.length && <FindingList items={group.weaknesses} preview={2} />}
            {!!group.recommendations.length && <FindingList items={group.recommendations} preview={2} />}
          </article>
        ))}
      </div>}
      {(!groups.length || additionalRecommendations.length > 0) && <div className={cn(resultPanel, 'space-y-2')}>
        <h3 className="flex items-center gap-2 font-semibold"><ListChecks size={18} className="text-orange-700" /> Đề xuất ôn tập</h3>
        <FindingList items={additionalRecommendations} empty="Báo cáo chưa có đề xuất ôn tập." />
        <Link href={studyHref} className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#a02707] hover:underline">Mở kế hoạch ôn tập <ArrowRight size={15} aria-hidden="true" /></Link>
      </div>}
    </section>
  );
}
