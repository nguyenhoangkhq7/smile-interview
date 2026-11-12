'use client';

import { useId, useRef, useState, type FormEvent } from 'react';
import { ChevronDown, CirclePlus, Link2, Plus, Square, X } from 'lucide-react';
import { skillLabel } from '@/components/features/applications/applicationUi';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { getStudyReferenceUrl, type NewStudyTask } from './studyPlan';
import styles from './practice.module.css';

const inputStyle = 'h-10 rounded-xl border-(--practice-blue-strong) bg-(--practice-pale)/60 px-3 text-sm focus-visible:border-(--practice-primary)';
const actionStyle = 'h-9 rounded-full bg-[#315f86] px-4 font-semibold text-white hover:bg-[#294f70]';

function ChecklistFields() {
  const [items, setItems] = useState<number[]>([]);
  const nextId = useRef(0);
  const focusId = useRef<number | null>(null);

  function addItem() {
    const id = nextId.current++;
    focusId.current = id;
    setItems((current) => [...current, id]);
  }

  return (
    <fieldset className="space-y-2">
      <legend className="w-full text-sm font-medium">
        <span className="flex justify-between gap-2">Checklist nhiệm vụ con <span className="text-xs font-normal text-(--practice-muted)">{items.length} mục</span></span>
      </legend>
      {items.map((id, index) => (
        <div key={id} className="flex items-center gap-2 rounded-lg border border-(--practice-blue-strong) bg-(--practice-pale)/60 px-2">
          <Square size={14} className="shrink-0 text-(--practice-primary)" aria-hidden="true" />
          <Input
            name="checklist"
            aria-label={`Mục checklist ${index + 1}`}
            placeholder="Nhập một bước cần thực hiện"
            maxLength={250}
            className="border-0 bg-transparent px-1 text-sm"
            ref={(input) => {
              if (input && focusId.current === id) {
                focusId.current = null;
                input.focus();
              }
            }}
          />
          <Button type="button" variant="ghost" size="icon-xs" aria-label={`Xóa mục checklist ${index + 1}`}
            onClick={() => setItems((current) => current.filter((item) => item !== id))}>
            <X aria-hidden="true" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="ghost" size="sm" className="px-0 text-(--practice-primary) hover:bg-transparent hover:underline"
        disabled={items.length >= 50} onClick={addItem}>
        <Plus aria-hidden="true" /> Thêm mục checklist
      </Button>
    </fieldset>
  );
}

interface CreateStudyTaskProps {
  skillIds: readonly string[];
  onCreate: (task: NewStudyTask) => Promise<boolean>;
  disabled: boolean;
  parent?: { id: number; title: string; skillId?: string | null };
  branch?: { title: string; skillId?: string | null };
  connector?: { color: string; filled?: boolean };
}

function StudyTaskForm({ skillIds, onCreate, disabled, parent, branch }: CreateStudyTaskProps) {
  const id = useId();
  const [error, setError] = useState<{ field: 'title' | 'reference'; message: string }>();
  const [saveFailed, setSaveFailed] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const value = (field: string) => String(data.get(field) ?? '').trim();
    const title = value('title');
    const reference = value('reference');
    const referenceUrl = reference ? getStudyReferenceUrl(reference) : null;
    const invalid = !title ? { field: 'title' as const, message: 'Hãy nhập tên đầu việc.' }
      : reference && !referenceUrl ? { field: 'reference' as const, message: 'Đường dẫn cần bắt đầu bằng http:// hoặc https://.' } : null;

    if (invalid) {
      setError(invalid);
      const field = form.elements.namedItem(invalid.field);
      if (field instanceof HTMLInputElement) field.focus();
      return;
    }

    setError(undefined);
    setSaveFailed(false);
    const saved = await onCreate({
      title,
      status: 'TODO',
      parentTaskId: parent?.id,
      skillId: branch?.skillId === undefined ? value('skill') || undefined : branch.skillId,
      notes: value('notes') || undefined,
      checklist: data.getAll('checklist').map((item) => String(item).trim()).filter(Boolean),
      referenceUrl: referenceUrl ?? undefined,
    });
    if (!saved) setSaveFailed(true);
  }

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4 sm:px-6">
        <div className="space-y-1.5">
          <label htmlFor={`${id}-title`} className="block font-medium">Tên đầu việc <span aria-hidden="true" className="text-destructive">*</span></label>
          <Input id={`${id}-title`} name="title" required maxLength={160} className={inputStyle}
            aria-invalid={error?.field === 'title'} aria-describedby={error?.field === 'title' ? `${id}-error` : undefined}
            placeholder="Ví dụ: Ôn tập Git Rebase và xử lý conflict" />
          {error?.field === 'title' && <p id={`${id}-error`} role="alert" className="text-xs text-destructive">{error.message}</p>}
        </div>
        <div className="space-y-1.5">
          <label htmlFor={`${id}-skill`} className="block font-medium">Kỹ năng liên quan</label>
          <div className="relative">
            <select id={`${id}-skill`} name="skill" defaultValue={parent?.skillId ?? branch?.skillId ?? ''}
              disabled={branch?.skillId !== undefined} className={cn(inputStyle, 'w-full appearance-none border pr-9')}>
              <option value="">Không chọn kỹ năng</option>
              {skillIds.map((skill) => <option key={skill} value={skill}>{skillLabel(skill)}</option>)}
            </select>
            <ChevronDown size={16} className="pointer-events-none absolute inset-y-0 right-3 my-auto text-(--practice-muted)" aria-hidden="true" />
          </div>
        </div>
        <div className="space-y-1.5">
          <label htmlFor={`${id}-notes`} className="block font-medium">Ghi chú ôn tập ban đầu</label>
          <Textarea id={`${id}-notes`} name="notes" rows={3} maxLength={2000}
            className="min-h-20 rounded-xl border-(--practice-blue-strong) bg-(--practice-pale)/60 px-3 text-sm"
            placeholder="Ghi lại kiến thức cần nắm hoặc cách bạn sẽ thực hành…" />
        </div>
        <ChecklistFields />
        <div className="space-y-1.5">
          <label htmlFor={`${id}-reference`} className="block font-medium">Tài liệu tham khảo</label>
          <div className="relative">
            <Link2 size={16} className="pointer-events-none absolute inset-y-0 left-3 my-auto text-(--practice-muted)" aria-hidden="true" />
            <Input id={`${id}-reference`} name="reference" type="url" maxLength={2048} placeholder="https://… (tùy chọn)"
              className={cn(inputStyle, 'pl-9')} aria-invalid={error?.field === 'reference'}
              aria-describedby={error?.field === 'reference' ? `${id}-error` : undefined} />
          </div>
          {error?.field === 'reference' && <p id={`${id}-error`} role="alert" className="text-xs text-destructive">{error.message}</p>}
        </div>
      </div>
      <div className="flex shrink-0 justify-end gap-2 border-t bg-(--practice-pale)/70 px-5 py-3 sm:px-6">
        {saveFailed && <p role="alert" className="mr-auto self-center text-xs text-destructive">Không tạo được đầu việc. Bạn có thể thử lại.</p>}
        <DialogClose render={<Button type="button" variant="outline" className="h-9 rounded-full px-4" disabled={disabled} />}>Hủy</DialogClose>
        <Button type="submit" className={actionStyle} disabled={disabled}>{disabled ? 'Đang lưu…' : parent ? 'Tạo đầu việc con' : 'Tạo đầu việc'}</Button>
      </div>
    </form>
  );
}

export function StudyTaskCreateDialog({ skillIds, onCreate, disabled, parent, branch, connector }: CreateStudyTaskProps) {
  const [open, setOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (disabled) return;
      if (nextOpen) setFormKey((current) => current + 1);
      setOpen(nextOpen);
    }}>
      {parent || branch ? (
        <DialogTrigger render={<button type="button" disabled={disabled}
          aria-label={parent ? `Thêm đầu việc con cho ${parent.title}` : `Thêm đầu việc vào ${branch?.title}`}
          title={parent ? 'Thêm đầu việc con' : 'Thêm đầu việc'}
          style={connector?.filled ? { backgroundColor: connector.color, color: 'white', borderColor: 'white' }
            : connector ? { color: connector.color, borderColor: connector.color } : undefined}
          className="absolute top-1/2 right-0 z-10 grid size-5 translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-(--practice-blue-strong) bg-card text-(--practice-primary) shadow-xs hover:border-(--practice-primary) hover:bg-(--practice-orange) hover:shadow-sm focus-visible:outline-2 disabled:opacity-50" />}>
          <Plus size={12} aria-hidden="true" />
        </DialogTrigger>
      ) : (
        <DialogTrigger render={<Button type="button" className={actionStyle} disabled={disabled} />}>
          <Plus size={16} aria-hidden="true" /> Tạo đầu việc
        </DialogTrigger>
      )}
      <DialogContent showCloseButton={false} overlayClassName="z-60 bg-slate-900/55 supports-backdrop-filter:backdrop-blur-sm"
        className={cn(styles.taskDialog, 'z-60 flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-2xl sm:max-w-[620px]')}>
        <div className="flex shrink-0 items-start gap-3 border-b px-5 py-4 sm:px-6">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-(--practice-orange) text-(--practice-primary)">
            <CirclePlus size={22} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <DialogTitle className="text-base leading-tight font-bold sm:text-lg">{parent ? 'Tạo đầu việc con' : 'Tạo đầu việc ôn tập mới'}</DialogTitle>
            <DialogDescription className="text-xs leading-5 sm:text-sm">
              {parent ? `Đầu việc cha: ${parent.title}` : branch ? `Nhánh: ${branch.title}` : 'Thêm mục tiêu ôn luyện để củng cố kiến thức trước buổi phỏng vấn tiếp theo.'}
            </DialogDescription>
          </div>
          <DialogClose render={<Button type="button" variant="ghost" size="icon-sm" aria-label="Đóng form tạo đầu việc" disabled={disabled} />}>
            <X aria-hidden="true" />
          </DialogClose>
        </div>
        <StudyTaskForm key={formKey} skillIds={skillIds} disabled={disabled} parent={parent} branch={branch} onCreate={async (task) => {
          const saved = await onCreate(task);
          if (saved) setOpen(false);
          return saved;
        }} />
      </DialogContent>
    </Dialog>
  );
}
