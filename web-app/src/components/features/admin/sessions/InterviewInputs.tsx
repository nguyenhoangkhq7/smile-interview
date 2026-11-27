'use client';

import { useCallback, useState } from 'react';
import { ExternalLink, Eye } from 'lucide-react';
import { Button, buttonVariants } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useAdminSessionResource } from '@/hooks/useAdminSessionResource';
import { adminInterviews } from '@/services/adminInterviews';
import type { InterviewDetail, InterviewDocumentKind } from './types';

function DocumentExcerpt({ id, kind }: { id: string; kind: InterviewDocumentKind }) {
  const load = useCallback((signal: AbortSignal) => adminInterviews.document(id, kind, true, signal), [id, kind]);
  const { state, retry } = useAdminSessionResource(load);
  if (state.status === 'loading') return <p role="status" className="text-muted-foreground">Đang tải bản xem trước…</p>;
  if (state.status === 'error') return <p role="alert" className="text-destructive">
    Không tải được tài liệu. <button type="button" className="underline" onClick={retry}>Thử lại</button>
  </p>;
  return <div tabIndex={0} role="region" aria-label={`Nội dung xem trước ${kind}`}
    className="max-h-[min(19rem,40dvh)] overflow-y-auto overscroll-contain whitespace-pre-wrap wrap-anywhere rounded-lg bg-muted p-3 leading-relaxed">
    {state.data.text || (state.data.originalAvailable
      ? 'Phiên này chỉ lưu tệp gốc. Mở trang đầy đủ để tải tệp.'
      : 'Phiên này chưa có nội dung văn bản đã lưu.')}
  </div>;
}

function DocumentField({ id, kind, name }: { id: string; kind: InterviewDocumentKind; name: string | null }) {
  const [open, setOpen] = useState(false);
  const query = new URLSearchParams({ id, kind });
  return <div className="min-w-0">
    <dt className="text-xs text-[#5c4039]">{kind === 'CV' ? 'Tên tệp CV' : 'Tiêu đề mô tả công việc'}</dt>
    <dd className="flex items-center gap-2">
      <span className="min-w-0 wrap-anywhere text-sm font-medium">{name?.trim() || 'Chưa có tên tài liệu'}</span>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger render={<Button variant="ghost" size="icon-sm" className="shrink-0 text-[#186392]"
          aria-label={`Xem trước ${kind}`} title={`Xem trước ${kind}`} />}>
          <Eye aria-hidden="true" className="size-4" />
        </DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="pr-8">
            <DialogTitle>Xem trước {kind}</DialogTitle>
            <DialogDescription className="wrap-anywhere">{name?.trim() || 'Tài liệu đầu vào của phiên'}</DialogDescription>
          </DialogHeader>
          {open && <DocumentExcerpt id={id} kind={kind} />}
          <a className={buttonVariants({ variant: 'outline', size: 'sm', className: 'justify-self-end' })}
            href={'/admin/documents?' + query} target="_blank" rel="noopener noreferrer">
            <ExternalLink aria-hidden="true" className="size-4" /> Xem đầy đủ
          </a>
        </DialogContent>
      </Dialog>
    </dd>
  </div>;
}

export default function InterviewInputs({ id, inputs }: { id: string; inputs: InterviewDetail['inputs'] }) {
  return <section className="space-y-3 rounded-xl bg-white p-5 shadow-xs">
    <h2 className="font-semibold">Hồ sơ đầu vào</h2>
    <dl className="grid gap-4 sm:grid-cols-2">
      <DocumentField id={id} kind="CV" name={inputs.cvName} />
      <DocumentField id={id} kind="JD" name={inputs.jdTitle} />
      {inputs.company?.trim() && <div>
        <dt className="text-xs text-[#5c4039]">Công ty</dt>
        <dd className="wrap-anywhere text-sm font-medium">{inputs.company}</dd>
      </div>}
    </dl>
  </section>;
}
