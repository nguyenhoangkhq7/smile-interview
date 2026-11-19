'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ExternalLink, FileText } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Button, buttonVariants } from '@/components/ui/button';
import { applicationProfiles, type ApplicationDocuments } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';

function DocumentPanel({ label, name, text, fileUrl }: {
  label: string; name: string; text: string; fileUrl: string | null;
}) {
  const safeUrl = fileUrl && (fileUrl.startsWith('/') || /^https?:\/\//i.test(fileUrl)) ? fileUrl : null;

  return (
    <section className="overflow-hidden rounded-2xl border bg-card">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-orange/10 text-brand-orange"><FileText size={19} aria-hidden="true" /></span>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{label}</p>
            <h2 className="break-words text-sm font-semibold">{name}</h2>
          </div>
        </div>
        {safeUrl && <a className={buttonVariants({ size: 'sm', variant: 'outline' })} href={safeUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} />Mở file gốc</a>}
      </header>
      <div className="max-h-[65vh] overflow-y-auto p-5 sm:p-6">
        {text.trim()
          ? <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-foreground">{text}</pre>
          : <p className="text-sm text-muted-foreground">Chưa có nội dung văn bản được trích xuất.</p>}
      </div>
    </section>
  );
}

function ApplicationDocumentsPage({ id }: { id: string }) {
  const [documents, setDocuments] = useState<ApplicationDocuments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setDocuments(await applicationProfiles.documents(id));
    } catch (cause) {
      setError(interviewError(cause));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-7 sm:px-6 sm:py-9">
      <Link href={`/applications/${id}`} className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground">
        <ArrowLeft size={15} aria-hidden="true" />Quay lại hồ sơ
      </Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">CV &amp; JD</h1>
        <p className="mt-2 text-sm text-muted-foreground">Tài liệu đã dùng để phân tích hồ sơ ứng tuyển.</p>
      </header>

      {loading && <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">Đang tải tài liệu…</p>}
      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><p>{error}</p><Button type="button" variant="outline" onClick={() => void load()}>Thử lại</Button></div>}
      {documents && <div className="grid gap-5 lg:grid-cols-2">
        <DocumentPanel label="CV đã tải lên" name={documents.cvFilename} text={documents.cvText} fileUrl={documents.cvFileUrl} />
        <DocumentPanel label="JD đã tải lên hoặc nhập" name={documents.jdFilename || documents.jdTitle} text={documents.jdText} fileUrl={documents.jdFileUrl} />
      </div>}
    </main>
  );
}

export default function ApplicationDocumentsRoute() {
  const { id } = useParams<{ id: string }>();
  return <ProtectedRoute><ApplicationDocumentsPage id={id} key={id} /></ProtectedRoute>;
}
