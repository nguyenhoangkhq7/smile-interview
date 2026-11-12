'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatStudyPercent, type StudyChecklistItem } from './studyPlan';

export interface StudyTaskChecklistActions {
  add: (content: string, sortOrder: number) => Promise<boolean>;
  update: (item: StudyChecklistItem) => Promise<boolean>;
  remove: (item: StudyChecklistItem) => void;
}

export function StudyTaskChecklist({ items, actions, disabled }: {
  items: readonly StudyChecklistItem[];
  actions: StudyTaskChecklistActions;
  disabled: boolean;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const count = items.filter((item) => item.isCompleted).length;

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

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold">Danh sách kiểm tra{items.length > 0 && ` (${count}/${items.length})`}</h4>
        {items.length > 0 && <span className="text-xs font-semibold text-(--practice-primary)">{formatStudyPercent(count / items.length * 100)}</span>}
      </div>
      {items.length ? (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item.id} className="rounded-lg border border-(--practice-blue-strong) p-2">
              {editingId === item.id ? (
                <form className="space-y-2" onSubmit={(event) => void submit(event, item)}>
                  <Input name="content" aria-label="Sửa mục checklist" defaultValue={item.content} required pattern=".*\S.*" maxLength={500} disabled={disabled} />
                  <div className="flex justify-end gap-2">
                    <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>Hủy</Button>
                    <Button type="submit" size="sm" disabled={disabled}>Lưu checklist</Button>
                  </div>
                </form>
              ) : (
                <div className="flex items-center gap-1">
                  <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-2">
                    <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-(--practice-primary)" checked={item.isCompleted}
                      disabled={disabled} onChange={(event) => void actions.update({ ...item, isCompleted: event.target.checked })} />
                    <span className={cn('text-xs leading-5 wrap-anywhere', item.isCompleted && 'text-(--practice-muted) line-through')}>{item.content}</span>
                  </label>
                  <Button type="button" variant="ghost" size="icon-xs" aria-label={`Sửa mục ${item.content}`} disabled={disabled} onClick={() => setEditingId(item.id)}>
                    <Pencil aria-hidden="true" />
                  </Button>
                  <Button type="button" variant="ghost" size="icon-xs" aria-label={`Xóa mục ${item.content}`} disabled={disabled} onClick={() => actions.remove(item)}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              )}
              {item.sourceSessionId && <Link href={`/interview/session/${encodeURIComponent(item.sourceSessionId)}/result`}
                className="mt-1 block text-xs text-(--practice-primary) hover:underline">Nguồn: lượt {item.sourceAttemptNumber ?? 'phỏng vấn'}</Link>}
            </li>
          ))}
        </ul>
      ) : <p className="text-xs text-(--practice-muted)">Chưa có mục kiểm tra.</p>}
      <form className="flex flex-wrap items-center gap-2" onSubmit={(event) => void submit(event)}>
        <Input name="content" aria-label="Mục checklist mới" placeholder="Nhập một bước thực hiện" className="min-w-0 flex-1" required pattern=".*\S.*" maxLength={500} disabled={disabled} />
        <Button type="submit" size="sm" variant="outline" disabled={disabled}>Thêm mục</Button>
      </form>
    </div>
  );
}
