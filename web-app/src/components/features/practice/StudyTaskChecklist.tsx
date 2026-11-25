'use client';

import { useState, type FormEvent, type RefObject } from 'react';
import Link from 'next/link';
import { Check, CheckCircle2, ListChecks, Pencil, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatStudyPercent, type StudyChecklistItem } from './studyPlan';
import styles from './practice.module.css';

export interface StudyTaskChecklistActions {
  add: (content: string, sortOrder: number) => Promise<boolean>;
  update: (item: StudyChecklistItem) => Promise<boolean>;
  remove: (item: StudyChecklistItem) => void;
}

export function StudyTaskChecklist({ items, actions, disabled, inputRef }: {
  items: readonly StudyChecklistItem[];
  actions: StudyTaskChecklistActions;
  disabled: boolean;
  inputRef?: RefObject<HTMLInputElement | null>;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [addingOpen, setAddingOpen] = useState(false);
  const count = items.filter((item) => item.isCompleted).length;
  const percent = items.length > 0 ? Math.round((count / items.length) * 100) : 0;
  const allDone = items.length > 0 && count === items.length;

  async function submit(event: FormEvent<HTMLFormElement>, item?: StudyChecklistItem) {
    event.preventDefault();
    const form = event.currentTarget;
    const content = String(new FormData(form).get('content') ?? '').trim();
    if (!content) return;
    if (item) {
      if (await actions.update({ ...item, content })) setEditingId(null);
    } else if (await actions.add(content, (items.at(-1)?.sortOrder ?? -1) + 1)) {
      form.reset();
    }
  }

  function openAddInput() {
    setAddingOpen(true);
    window.requestAnimationFrame(() => inputRef?.current?.focus());
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
            <ListChecks size={17} className="text-(--practice-muted)" aria-hidden="true" />
            Danh sách kiểm tra
          </h3>
          {items.length > 0 && (
            <span className="text-xs font-medium text-(--practice-muted)">
              ({count}/{items.length} hoàn thành)
            </span>
          )}
          {allDone && (
            <span className={cn(styles.checklistAllDoneBadge, 'inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-800')}>
              <CheckCircle2 size={12} aria-hidden="true" />
              Hoàn thành xuất sắc
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {items.length > 0 && (
            <span className={cn('text-xs font-bold tabular-nums transition-colors duration-300', allDone ? 'text-emerald-700' : 'text-(--practice-primary)')}>
              {formatStudyPercent(percent)}
            </span>
          )}
          {!addingOpen && !disabled && (
            <button
              type="button"
              onClick={openAddInput}
              className="inline-flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-muted px-2.5 py-1 text-xs font-semibold text-foreground transition-colors hover:bg-slate-200/80 dark:hover:bg-muted/80"
            >
              <Plus size={13} aria-hidden="true" />
              Thêm mục
            </button>
          )}
        </div>
      </div>

      {/* Checklist Progress Bar */}
      {items.length > 0 && (
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200/80 dark:bg-muted/80 shadow-inner">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-300 ease-out',
              allDone ? 'bg-emerald-600' : 'bg-(--practice-primary)',
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
      )}

      {items.length > 0 ? (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.id} className="group rounded-xl p-2 transition-colors hover:bg-(--practice-pale)/70">
              {editingId === item.id ? (
                <form className="space-y-2" onSubmit={(event) => void submit(event, item)}>
                  <Input
                    name="content"
                    aria-label="Sửa mục checklist"
                    defaultValue={item.content}
                    required
                    pattern=".*\S.*"
                    maxLength={500}
                    disabled={disabled}
                  />
                  <div className="flex justify-end gap-2">
                    <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>Hủy</Button>
                    <Button type="submit" size="sm" disabled={disabled} className="bg-(--practice-primary) hover:bg-(--practice-primary-hover)">
                      Lưu checklist
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="flex items-start gap-2.5">
                  <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2.5 select-none">
                    <input
                      type="checkbox"
                      className="peer sr-only"
                      checked={item.isCompleted}
                      disabled={disabled}
                      onChange={(event) => void actions.update({ ...item, isCompleted: event.target.checked })}
                    />
                    <span
                      aria-hidden="true"
                      className={cn(
                        styles.checklistCheckbox,
                        'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border shadow-2xs',
                        item.isCompleted
                          ? 'scale-105 border-(--practice-primary) bg-(--practice-primary) text-white'
                          : 'border-slate-300 dark:border-border bg-white dark:bg-card text-transparent hover:border-(--practice-primary)',
                      )}
                    >
                      <Check size={13} strokeWidth={3} />
                    </span>
                    <span className={cn('text-sm leading-snug wrap-anywhere transition-all duration-200', item.isCompleted ? 'text-(--practice-muted) line-through' : 'text-foreground')}>
                      {item.content}
                    </span>
                  </label>
                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Sửa mục ${item.content}`}
                      disabled={disabled}
                      onClick={() => setEditingId(item.id)}
                    >
                      <Pencil aria-hidden="true" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Xóa mục ${item.content}`}
                      disabled={disabled}
                      onClick={() => actions.remove(item)}
                      className="hover:text-destructive"
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              )}
              {item.sourceSessionId && (
                <Link
                  href={`/interview/session/${encodeURIComponent(item.sourceSessionId)}/result`}
                  className="mt-1 ml-7.5 block text-xs text-(--practice-primary) hover:underline"
                >
                  Nguồn: lượt {item.sourceAttemptNumber ?? 'phỏng vấn'}
                </Link>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-(--practice-muted)">Chưa có mục kiểm tra.</p>
      )}

      {(addingOpen || items.length === 0) && (
        <form className="flex flex-wrap items-center gap-2 pt-1" onSubmit={(event) => void submit(event)}>
          <Input
            ref={inputRef}
            name="content"
            aria-label="Mục checklist mới"
            placeholder="Nhập một bước thực hiện mới và nhấn Enter..."
            className="min-w-0 flex-1 rounded-xl"
            required
            pattern=".*\S.*"
            maxLength={500}
            disabled={disabled}
            onKeyDown={(event) => {
              if (event.key === 'Escape' && addingOpen) {
                event.stopPropagation();
                setAddingOpen(false);
              }
            }}
          />
          <Button
            type="submit"
            size="sm"
            disabled={disabled}
            className="rounded-xl bg-(--practice-primary) hover:bg-(--practice-primary-hover)"
          >
            Thêm
          </Button>
          {addingOpen && items.length > 0 && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setAddingOpen(false)}>
              Hủy
            </Button>
          )}
        </form>
      )}
    </section>
  );
}
