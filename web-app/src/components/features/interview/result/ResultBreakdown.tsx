'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, BookOpen, ChevronDown, CircleCheck, ListChecks, MessageSquare, TriangleAlert } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { assessmentLabels, assessmentStatus, resultReasons, skillStatuses, uniqueFindings, type ResultData } from './resultData';

export const resultPanel = 'min-w-0 rounded-2xl border border-slate-200/70 bg-card p-4 shadow-xs sm:p-6';
export const resultSection = 'scroll-mt-36 space-y-4';

export function FindingList({ items, empty }: { items: readonly string[]; empty?: string }) {
  if (!items.length) return empty ? <p className="text-sm text-muted-foreground">{empty}</p> : null;
  return (
    <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed wrap-anywhere">
      {items.map(item => <li key={item}><MarkdownContent content={item} /></li>)}
    </ul>
  );
}

export function ResultFeedback({ data, studyHref }: { data: ResultData; studyHref: string }) {
  return (
    <section id="feedback" className={cn(resultPanel, resultSection)}>
      <h2 className="flex items-center gap-2 text-xl font-bold"><MessageSquare size={21} className="text-orange-700" /> Nhận xét chi tiết từ Trợ lý AI</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-2 rounded-xl bg-emerald-50 p-4 text-emerald-950">
          <h3 className="flex items-center gap-2 font-semibold"><CircleCheck size={17} /> Điểm mạnh</h3>
          <FindingList items={data.strengths} empty="Báo cáo chưa ghi nhận điểm mạnh." />
        </div>
        <div className="space-y-2 rounded-xl bg-orange-50 p-4 text-orange-950">
          <h3 className="flex items-center gap-2 font-semibold"><TriangleAlert size={17} /> Điểm cần cải thiện</h3>
          <FindingList items={data.weaknesses} empty="Báo cáo chưa ghi nhận điểm yếu." />
        </div>
      </div>
      {data.recommendations.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#fff0ea] p-4">
          <p className="text-sm font-semibold text-orange-950">Có {data.recommendations.length} đề xuất ôn tập từ phiên này.</p>
          <Link href={studyHref} className={cn(buttonVariants({ size: 'sm' }), 'rounded-full bg-[#b02700] text-white hover:bg-[#8c2100]')}>Mở ôn tập <ArrowRight aria-hidden="true" /></Link>
        </div>
      )}
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
        <h3 className="min-w-0 text-base font-bold wrap-anywhere">{skillLabel(skill.id)}</h3>
        <span className={cn('rounded-full px-2.5 py-1 text-xs font-semibold', status.tone)}>{status.label}</span>
      </div>
      <div>
        <p className="mb-1.5 text-xs text-muted-foreground">{skill.checked}/{skill.objectives.length} mục tiêu đã kiểm tra</p>
        <div className="h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
          <div className={cn('h-full rounded-full', status.bar)} style={{ width: `${skill.checked / skill.objectives.length * 100}%` }} />
        </div>
      </div>
      <details className="group border-t border-slate-100 pt-2">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium text-[#a02707]">
          Chi tiết từng tiêu chí <ChevronDown size={16} className="group-open:rotate-180" />
        </summary>
        <div className="mt-3 space-y-4">
          {skill.objectives.map(objective => {
            const reason = objective.excluded_reason || objective.stop_reason;
            return (
              <div key={objective.objective_id} className="space-y-2 text-sm wrap-anywhere">
                <h4 className="font-semibold">{objective.claim}</h4>
                <p className={cn('inline-block rounded-md px-2 py-1 text-xs', skillStatuses[assessmentStatus(objective.assessment)].tone)}>{assessmentLabels[objective.assessment]}</p>
                {reason && <p className="text-muted-foreground">{resultReasons[reason] ?? reason}</p>}
                {objective.inferred && <p className="text-xs text-muted-foreground">Mục tiêu được suy luận từ mô tả công việc.</p>}
                {objective.criteria?.length ? (
                  <ul className="space-y-1 rounded-lg bg-slate-50 p-3">
                    {objective.criteria.map(criterion => (
                      <li key={criterion.criterion_id}>
                        <p>{criterion.description}: {assessmentLabels[criterion.assessment]} ({criterion.turns_spent} lượt)</p>
                        {criterion.stop_reason && <p className="text-xs text-muted-foreground">{resultReasons[criterion.stop_reason] ?? criterion.stop_reason}</p>}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {!!objective.missing_criteria.length && (
                  <div className="space-y-1">
                    <p className="font-medium">Tiêu chí còn thiếu bằng chứng</p>
                    <FindingList items={objective.missing_criteria} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </details>
    </article>
  );
}

export function ResultSkills({ skills }: { skills: ResultData['skills'] }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [limit, setLimit] = useState(6);
  const filtered = filter === 'all' ? skills : skills.filter(skill => skill.status === filter);
  const filters = [{ id: 'all' as const, label: 'Tất cả', count: skills.length },
    ...Object.entries(skillStatuses).map(([id, status]) => ({
      id: id as keyof typeof skillStatuses, label: status.label, count: skills.filter(skill => skill.status === id).length,
    }))];
  return (
    <section id="skills" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold">Đánh giá theo kỹ năng</h2>
        <ResultFilters filters={filters} value={filter} label="Lọc kỹ năng" onChange={value => { setFilter(value); setLimit(6); }} />
      </div>
      <div className="grid items-start gap-3 md:grid-cols-2">
        {filtered.slice(0, limit).map(skill => <SkillCard key={skill.id} skill={skill} />)}
      </div>
      {!filtered.length && <p className={cn(resultPanel, 'text-sm text-muted-foreground')}>Chưa có kỹ năng trong nhóm này.</p>}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 6)}>Xem thêm kỹ năng ({filtered.length - limit})</Button>}
    </section>
  );
}

const questionLabels = { strong: 'Có bằng chứng đạt', weak: 'Cần cải thiện', partial: 'Chưa có kết luận' } as const;

export function ResultQuestions({ questions }: { questions: ResultData['questions'] }) {
  const [filter, setFilter] = useState<Filter>('all');
  const filtered = filter === 'all' ? questions : questions.filter(item => item.status === filter);
  const filters = [{ id: 'all' as const, label: 'Tất cả', count: questions.length },
    ...Object.entries(questionLabels).map(([id, label]) => ({
      id: id as keyof typeof questionLabels, label, count: questions.filter(item => item.status === id).length,
    }))];
  return (
    <section id="questions" className={resultSection}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold">Chi tiết câu hỏi phỏng vấn <span className="text-sm font-medium text-muted-foreground">({questions.length} câu)</span></h2>
        <ResultFilters filters={filters} value={filter} label="Lọc câu hỏi" onChange={setFilter} />
      </div>
      {filtered.map(({ turn, index, evidence, status }) => (
        <details key={turn.turn_id} className="group rounded-xl border border-slate-200 bg-card shadow-xs" open={index === 0}>
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
              <div className="space-y-2">
                <h3 className="font-semibold">Bằng chứng đánh giá</h3>
                {evidence.map((item, index) => (
                  <blockquote key={index} className="space-y-1 border-l-2 border-orange-300 pl-3">
                    {item.response_excerpt && <MarkdownContent content={item.response_excerpt} />}
                    <MarkdownContent content={item.rationale} />
                  </blockquote>
                ))}
              </div>
            )}
          </div>
        </details>
      ))}
      {!filtered.length && <p className={cn(resultPanel, 'text-sm text-muted-foreground')}>Chưa có câu hỏi trong nhóm này.</p>}
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
      <h2 className="text-xl font-bold">Lỗ hổng kiến thức và hướng cải thiện</h2>
      {groups.length > 0 && <div className="grid items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
        {groups.map(group => (
          <article key={group.id} className={cn(resultPanel, 'space-y-3')}>
            <div className="flex items-center gap-2">
              <BookOpen size={19} className="shrink-0 text-orange-700" /><h3 className="font-bold wrap-anywhere">{skillLabel(group.id)}</h3>
            </div>
            <FindingList items={group.weaknesses} />
            {!!group.recommendations.length && <div className="space-y-1.5 rounded-lg bg-emerald-50 p-3"><p className="font-semibold text-emerald-950">Nên ôn luyện</p><FindingList items={group.recommendations} /></div>}
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
