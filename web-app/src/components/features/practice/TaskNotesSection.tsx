'use client';

import { useEffect, useRef, useState } from 'react';
import { AlignLeft, Check, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { StudyTask, StudyTaskUpdate } from './studyPlan';

interface TaskNotesSectionProps {
  task: StudyTask;
  disabled: boolean;
  onUpdate: (update: StudyTaskUpdate) => Promise<boolean>;
}

export function TaskNotesSection({ task, disabled, onUpdate }: TaskNotesSectionProps) {
  const [notesDraft, setNotesDraft] = useState(task.notes ?? '');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setNotesDraft(task.notes ?? '');
    setEditing(false);
    setJustSaved(false);
  }, [task.id, task.notes]);

  const isDirty = notesDraft.trim() !== (task.notes ?? '').trim();

  async function saveNotes() {
    if (disabled || saving) return;
    setSaving(true);
    try {
      const ok = await onUpdate({ notes: notesDraft.trim() || null });
      if (ok) {
        setEditing(false);
        setJustSaved(true);
        window.setTimeout(() => setJustSaved(false), 2000);
      }
    } finally {
      setSaving(false);
    }
  }

  function startEditing() {
    setEditing(true);
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  }

  return (
    <section className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
          <AlignLeft size={17} className="text-(--practice-muted)" aria-hidden="true" />
          Mô tả / Ghi chú trọng tâm
        </h3>
        {!editing && !disabled && (
          <button
            type="button"
            onClick={startEditing}
            className="rounded-lg px-2.5 py-1 text-xs font-semibold text-(--practice-muted) transition-colors hover:bg-slate-100 dark:hover:bg-muted hover:text-(--practice-primary)"
          >
            Chỉnh sửa
          </button>
        )}
      </div>

      <div
        className={cn(
          'rounded-xl border p-3.5 transition-all duration-150',
          editing
            ? 'border-(--practice-primary)/35 bg-card shadow-xs ring-2 ring-(--practice-primary)/10'
            : 'border-slate-200/70 dark:border-border/70 bg-(--practice-pale)/55 hover:border-slate-300/80 dark:hover:border-border/80',
        )}
      >
        {editing ? (
          <div className="space-y-2.5">
            <Textarea
              ref={textareaRef}
              aria-label="Ghi chú ôn tập"
              disabled={disabled || saving}
              rows={5}
              maxLength={10000}
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                  event.preventDefault();
                  void saveNotes();
                } else if (event.key === 'Escape') {
                  event.stopPropagation();
                  setNotesDraft(task.notes ?? '');
                  setEditing(false);
                }
              }}
              placeholder="Thêm mô tả chi tiết, kiến thức trọng tâm hoặc câu hỏi cần ôn..."
              className="min-h-24 resize-y border-0 bg-transparent p-0 text-sm leading-relaxed shadow-none focus-visible:ring-0"
            />
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 dark:border-border pt-2.5">
              <span className="inline-flex items-center gap-1 text-[11px] text-(--practice-muted)">
                <Sparkles size={12} aria-hidden="true" />
                Nhấn Ctrl + Enter để lưu nhanh
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={saving}
                  onClick={() => {
                    setNotesDraft(task.notes ?? '');
                    setEditing(false);
                  }}
                >
                  Hủy
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={disabled || saving || !isDirty}
                  onClick={() => void saveNotes()}
                  className="rounded-full bg-(--practice-primary) px-4 hover:bg-(--practice-primary-hover)"
                >
                  {saving ? 'Đang lưu…' : 'Lưu ghi chú'}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div
            role={disabled ? undefined : 'button'}
            tabIndex={disabled ? undefined : 0}
            onClick={() => !disabled && startEditing()}
            onKeyDown={(event) => {
              if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                startEditing();
              }
            }}
            className={cn(
              'min-h-14 text-sm leading-relaxed whitespace-pre-wrap wrap-anywhere',
              task.notes ? 'text-foreground' : 'text-(--practice-muted)',
              !disabled && 'cursor-text',
            )}
          >
            {task.notes || 'Chưa có ghi chú. Nhấn để thêm kiến thức trọng tâm cần ôn tập...'}
          </div>
        )}

        {justSaved && (
          <p role="status" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <Check size={13} aria-hidden="true" />
            Đã lưu ghi chú
          </p>
        )}
      </div>
    </section>
  );
}

