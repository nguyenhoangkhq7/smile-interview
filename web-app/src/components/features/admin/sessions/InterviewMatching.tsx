'use client';

import { useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { percent } from '@/components/features/interview/result/resultData';
import { useAdminSessionResource } from '@/hooks/useAdminSessionResource';
import { skillLabel } from '@/lib/skillLabels';
import { adminInterviews } from '@/services/adminInterviews';
import type { InterviewMatchingSkill, InterviewMatchingTask } from './types';

const alignmentLabels = new Map([
  ['MATCH', ['Phù hợp', 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200']],
  ['PARTIAL', ['Liên quan', 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200']],
  ['MISSING', ['CV chưa thể hiện', 'bg-muted text-muted-foreground']],
]);

function Quotes({ title, items }: { title: string; items: string[] }) {
  return <div className="min-w-0 space-y-1.5">
    <h4 className="text-xs font-semibold text-muted-foreground">{title}</h4>
    {items.length ? [...new Set(items)].map((quote) =>
      <blockquote key={quote} className="border-l-2 border-border pl-2.5 whitespace-pre-wrap wrap-anywhere">{quote}</blockquote>
    ) : <p className="text-muted-foreground">Chưa có trích dẫn đã lưu.</p>}
  </div>;
}

function level(value: number | null) {
  return value != null && value >= 1 && value <= 5 ? `${value.toLocaleString('vi-VN')}/5` : null;
}

function TaskList({ tasks }: { tasks: InterviewMatchingTask[] }) {
  return <div className="space-y-2">
    <h4 className="font-semibold">Nhiệm vụ trong JD</h4>
    <ul className="space-y-2">
      {tasks.map((task, index) => <li key={index} className="space-y-1.5 rounded-lg border p-3">
        <p className="font-medium wrap-anywhere">{task.description}</p>
        <p className="text-xs text-muted-foreground">
          {[
            task.requirement === 'REQUIRED' ? 'Bắt buộc' : task.requirement === 'OPTIONAL' ? 'Tùy chọn' : null,
            level(task.requiredLevel) && 'Mức yêu cầu ' + level(task.requiredLevel),
          ].filter(Boolean).join(' · ')}
        </p>
        <Quotes title="Trích dẫn từ JD" items={task.evidence} />
      </li>)}
    </ul>
  </div>;
}

function SkillRow({ skill }: { skill: InterviewMatchingSkill }) {
  const [label, tone] = alignmentLabels.get(skill.alignment ?? '') ?? ['Chưa xác định', 'bg-muted text-muted-foreground'];
  const name = skillLabel(skill.id, skill.name, [...skill.jdEvidence, ...skill.tasks.flatMap(task => task.evidence)]);
  const priority = percent(skill.priority);
  const importance = percent(skill.importance);
  return <details className="group">
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-3 hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary sm:px-4 [&::-webkit-details-marker]:hidden">
      <span className="min-w-0 flex-1 wrap-anywhere font-medium">{name}</span>
      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{label}</span>
      <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground group-open:rotate-180" />
    </summary>
    <div className="space-y-3 border-t bg-muted/25 px-3 py-3 text-sm sm:px-4">
      <dl className="flex flex-wrap gap-x-6 gap-y-2">
        {([
          ['Kỹ năng đối chiếu trong CV', skill.cvSkill ? skillLabel(skill.cvSkill, skill.cvSkill, skill.cvEvidence) : null],
          ['Mức yêu cầu', level(skill.requiredLevel)],
          ['Ưu tiên ôn tập', priority == null ? null : `${priority}%`],
          ['Trọng số trong JD', importance == null ? null : `${importance}%`],
        ] as const).map(([title, value]) => value != null && <div key={title}>
          <dt className="text-xs text-muted-foreground">{title}</dt><dd className="wrap-anywhere">{value}</dd>
        </div>)}
      </dl>
      {skill.context && <p className="whitespace-pre-wrap wrap-anywhere text-muted-foreground">{skill.context}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Quotes title="Trích dẫn từ CV" items={skill.cvEvidence} />
        {(!skill.tasks.length || skill.jdEvidence.length > 0) && <Quotes title="Trích dẫn từ JD" items={skill.jdEvidence} />}
      </div>
      {skill.tasks.length > 0 && <TaskList tasks={skill.tasks} />}
    </div>
  </details>;
}

export default function InterviewMatching({ id }: { id: string }) {
  const load = useCallback((signal: AbortSignal) => adminInterviews.matching(id, signal), [id]);
  const { state, retry } = useAdminSessionResource(load);
  if (state.status === 'loading') return <p role="status" className="rounded-xl bg-white p-5 text-sm">Đang tải kết quả đối sánh…</p>;
  if (state.status === 'error') return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl bg-white p-5 text-sm">
    <p>Không tải được kết quả đối sánh.</p><Button variant="outline" size="sm" onClick={retry}>Thử lại</Button>
  </div>;

  const { score, degraded, available, skills } = state.data;
  const match = percent(score);
  return <section className="space-y-4 rounded-xl bg-white p-5 shadow-xs">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <h2 className="font-semibold">Kết quả đối sánh</h2>
      {match != null && <div className="rounded-lg bg-[#edf0ff] px-3 py-2 text-sm">
        Độ khớp CV–JD <strong className="ml-1 tabular-nums">{match}%</strong>
      </div>}
    </div>
    {degraded && <p className="rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/60 dark:text-amber-200">Một phần phân tích chưa đầy đủ.</p>}
    {skills.length ? <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">Kỹ năng theo JD</h3>
        <span className="text-xs text-muted-foreground">{skills.length} kỹ năng · Chọn để xem chi tiết</span>
      </div>
      <div className="divide-y overflow-hidden rounded-lg border">
        {skills.map((skill, index) => <SkillRow key={`${skill.id}-${index}`} skill={skill} />)}
      </div>
    </> : <p className="text-sm text-muted-foreground">
      {available ? 'Kết quả đã lưu chưa có chi tiết theo kỹ năng.' : 'Phiên chưa có kết quả phân tích.'}
    </p>}
  </section>;
}
