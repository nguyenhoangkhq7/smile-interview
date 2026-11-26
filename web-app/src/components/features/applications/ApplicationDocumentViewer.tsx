'use client';

import { useEffect, useState } from 'react';
import { ExternalLink, FileText } from 'lucide-react';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { applicationProfiles, type ApplicationDocuments } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';

type DocumentState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; documents: ApplicationDocuments };

function DocumentPanel({ label, name, text, fileUrl, compact }: {
  label: string;
  name: string;
  text: string;
  fileUrl: string | null;
  compact: boolean;
}) {
  const originalUrl = fileUrl && /^(?:https?:\/\/|\/(?![/\\]))/i.test(fileUrl) ? fileUrl : null;
  const hasText = Boolean(text?.trim());
  const Heading = compact ? 'h3' : 'h2';

  return (
    <section className={cn('min-w-0 rounded-2xl border bg-card', compact && 'rounded-xl')}>
      <header className={cn('flex flex-wrap items-center justify-between gap-3 border-b', compact ? 'px-4 py-3' : 'px-5 py-4 sm:px-6')}>
        <div className="flex min-w-0 items-center gap-3">
          {!compact && <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-orange/10 text-brand-orange"><FileText size={19} aria-hidden="true" /></span>}
          <div className="min-w-0">
            {!compact && <p className="text-xs text-muted-foreground">{label}</p>}
            <Heading className="text-sm font-semibold wrap-anywhere">{compact ? label : name || label}</Heading>
          </div>
        </div>
        {originalUrl && (
          <a
            className={buttonVariants({ size: 'sm', variant: 'outline' })}
            href={originalUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`Mở file gốc của ${label}`}
          >
            <ExternalLink size={14} aria-hidden="true" />Mở file gốc
          </a>
        )}
      </header>
      <div
        role={hasText ? 'region' : undefined}
        aria-label={hasText ? `Nội dung ${label}` : undefined}
        tabIndex={hasText ? 0 : undefined}
        className={cn(
          'overflow-y-auto overscroll-contain focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange',
          compact ? 'max-h-[min(26rem,50dvh)] rounded-b-xl p-4' : 'max-h-[65vh] rounded-b-2xl p-5 sm:p-6',
        )}
      >
        {hasText
          ? <div className="text-sm leading-7 whitespace-pre-wrap wrap-anywhere">{text}</div>
          : <p className="text-sm text-muted-foreground">Chưa có nội dung văn bản được trích xuất.</p>}
      </div>
    </section>
  );
}

export function ApplicationDocumentViewer({ profileId, compact = false }: { profileId: string; compact?: boolean }) {
  const [state, setState] = useState<DocumentState>({ status: 'loading' });
  const [request, setRequest] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const documents = await applicationProfiles.documents(profileId, controller.signal);
        if (!controller.signal.aborted) setState({ status: 'ready', documents });
      } catch (cause) {
        if (!controller.signal.aborted) setState({ status: 'error', message: interviewError(cause) });
      }
    }

    void load();
    return () => controller.abort();
  }, [profileId, request]);

  if (state.status === 'loading') {
    return <p role="status" className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">Đang tải tài liệu…</p>;
  }

  if (state.status === 'error') {
    return (
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm">
        <p>{compact ? 'Chưa tải được tài liệu. Hãy thử lại.' : state.message}</p>
        <Button type="button" variant="outline" onClick={() => {
          setState({ status: 'loading' });
          setRequest(count => count + 1);
        }}>Thử lại</Button>
      </div>
    );
  }

  const { documents } = state;
  return (
    <div className={cn('grid gap-5 lg:grid-cols-2', compact && 'gap-3')}>
      <DocumentPanel
        label={compact ? 'CV' : 'CV đã tải lên'}
        name={documents.cvFilename}
        text={documents.cvText}
        fileUrl={documents.cvFileUrl}
        compact={compact}
      />
      <DocumentPanel
        label={compact ? 'Mô tả công việc' : 'JD đã tải lên hoặc nhập'}
        name={documents.jdFilename || documents.jdTitle}
        text={documents.jdText}
        fileUrl={documents.jdFileUrl}
        compact={compact}
      />
    </div>
  );
}
