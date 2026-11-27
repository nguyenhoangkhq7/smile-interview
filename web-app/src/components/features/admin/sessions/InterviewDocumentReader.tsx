'use client';

import { useCallback } from 'react';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAdminSessionResource } from '@/hooks/useAdminSessionResource';
import { useAdminDocumentDownload } from '@/hooks/useAdminDocumentDownload';
import { adminInterviews } from '@/services/adminInterviews';
import type { InterviewDocumentKind } from './types';

export default function InterviewDocumentReader({ id, kind }: { id: string; kind: InterviewDocumentKind }) {
  const load = useCallback((signal: AbortSignal) => adminInterviews.document(id, kind, false, signal), [id, kind]);
  const { state, retry } = useAdminSessionResource(load);
  const { pending, failed, download } = useAdminDocumentDownload(id, kind);

  return <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
    {state.status === 'loading' && <p role="status">Đang tải tài liệu…</p>}
    {state.status === 'error' && <p role="alert" className="text-sm text-destructive">
      Không tải được tài liệu. <button type="button" onClick={retry} className="underline">Thử lại</button>
    </p>}
    {state.status === 'ready' && <article className="overflow-hidden rounded-xl border bg-card">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b px-5 py-4 sm:px-7">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{kind === 'CV' ? 'CV của phiên' : 'Mô tả công việc của phiên'}</p>
          <h1 className="wrap-anywhere text-xl font-semibold">{state.data.name}</h1>
        </div>
        {state.data.originalAvailable && <Button type="button" variant="outline" disabled={pending} onClick={() => void download()}>
          <Download aria-hidden="true" className="size-4" /> {pending ? 'Đang tải…' : 'Tải tệp gốc'}
        </Button>}
        {failed && <p role="alert" className="w-full text-sm text-destructive">Không tải được tệp gốc. Vui lòng thử lại.</p>}
      </header>
      <div className="whitespace-pre-wrap wrap-anywhere px-5 py-5 text-sm leading-7 sm:px-7">
        {state.data.text || <p className="text-muted-foreground">Phiên này chưa có nội dung văn bản đã lưu.</p>}
      </div>
    </article>}
  </div>;
}
