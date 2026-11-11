'use client';

import { useRef, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';

export function DeleteStudyTaskDialog({ title, disabled, onConfirm }: {
  title: string;
  disabled: boolean;
  onConfirm: () => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);
  const cancel = useRef<HTMLButtonElement>(null);

  async function confirm() {
    if (deleting || disabled) return;
    setDeleting(true);
    setFailed(false);
    try {
      if (await onConfirm()) setOpen(false);
      else setFailed(true);
    } catch {
      setFailed(true);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (deleting) return;
      setFailed(false);
      setOpen(nextOpen);
    }}>
      <DialogTrigger render={<Button type="button" variant="ghost" size="icon" aria-label="Xóa đầu việc" disabled={disabled} />}>
        <Trash2 aria-hidden="true" />
      </DialogTrigger>
      <DialogContent showCloseButton={false} initialFocus={cancel} overlayClassName="bg-slate-950/45"
        className="sm:max-w-md">
        <DialogHeader>
          <span className="mb-1 grid size-10 place-items-center rounded-xl bg-destructive/10 text-destructive">
            <Trash2 size={19} aria-hidden="true" />
          </span>
          <DialogTitle className="font-bold">Xóa đầu việc?</DialogTitle>
          <DialogDescription className="leading-relaxed wrap-anywhere">
            Đầu việc <strong>“{title}”</strong> sẽ bị xóa cùng checklist và tài liệu đính kèm.
          </DialogDescription>
        </DialogHeader>
        {failed && <p role="alert" className="rounded-lg bg-destructive/10 p-2.5 text-destructive">
          Không xóa được đầu việc. Vui lòng thử lại.
        </p>}
        <DialogFooter>
          <DialogClose render={<Button ref={cancel} type="button" variant="outline" disabled={deleting} />}>Hủy</DialogClose>
          <Button type="button" variant="destructive" disabled={deleting || disabled} onClick={() => void confirm()}>
            {deleting ? 'Đang xóa…' : 'Xóa đầu việc'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
