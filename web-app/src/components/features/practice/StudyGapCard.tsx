'use client';

import type { RefObject } from 'react';
import Link from 'next/link';
import { GripVertical, Plus } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { cn } from '@/lib/utils';

export const studyGapDragType = 'application/x-smile-study-gap';

export interface StudyGap {
  skillId: string;
  notes: readonly string[];
  source?: { sessionId: string; attemptNumber: number } | null;
}

export interface StudyGapActions {
  source: RefObject<StudyGap | null>;
  disabled: boolean;
  add: (gap: StudyGap) => Promise<boolean>;
}

export function StudyGapCard({ gap, actions, list = false }: {
  gap: StudyGap;
  actions?: StudyGapActions;
  list?: boolean;
}) {
  const label = skillLabel(gap.skillId);
  const draggable = Boolean(actions && !actions.disabled);
  return (
    <article draggable={draggable}
      onDragStart={(event) => {
        if (!actions || actions.disabled) {
          event.preventDefault();
          return;
        }
        actions.source.current = gap;
        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData(studyGapDragType, gap.skillId);
      }}
      onDragEnd={() => { if (actions) actions.source.current = null; }}
      className={cn('space-y-1.5 rounded-xl border border-(--practice-blue-strong) bg-(--practice-pale) p-3 text-xs wrap-anywhere shadow-xs',
        draggable && 'cursor-grab active:cursor-grabbing')}>
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold">{label}</p>
        {draggable && <GripVertical size={15} className="shrink-0 text-(--practice-muted)" aria-hidden="true" />}
      </div>
      {list ? (
        <ul className="list-disc space-y-1 pl-4 text-(--practice-muted)">
          {gap.notes.map(note => <li key={note}>{note}</li>)}
        </ul>
      ) : gap.notes[0] && <p className="text-(--practice-muted)">{gap.notes[0]}</p>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {gap.source && <Link draggable={false} className="font-medium text-(--practice-primary) hover:underline"
          href={`/interview/session/${encodeURIComponent(gap.source.sessionId)}/result`}>
          Xem kết quả lượt {gap.source.attemptNumber}
        </Link>}
        {actions && <button type="button" draggable={false} disabled={actions.disabled}
          onClick={() => void actions.add(gap)} aria-label={`Thêm đầu việc cho ${label}`}
          className="inline-flex items-center gap-1 rounded-md bg-card px-2 py-1 font-medium text-(--practice-primary) hover:underline disabled:opacity-50">
          <Plus size={13} aria-hidden="true" /> Thêm đầu việc
        </button>}
      </div>
    </article>
  );
}
