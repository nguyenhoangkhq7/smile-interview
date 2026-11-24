'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { ApplicationDocumentViewer } from '@/components/features/applications/ApplicationDocumentViewer';

function ApplicationDocumentsPage({ id }: { id: string }) {
  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-7 sm:px-6 sm:py-9">
      <Link href={`/applications/${id}`} className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground">
        <ArrowLeft size={15} aria-hidden="true" />Quay lại hồ sơ
      </Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">CV &amp; JD</h1>
        <p className="mt-2 text-sm text-muted-foreground">Tài liệu đã dùng để phân tích hồ sơ ứng tuyển.</p>
      </header>

      <ApplicationDocumentViewer profileId={id} />
    </main>
  );
}

export default function ApplicationDocumentsRoute() {
  const { id } = useParams<{ id: string }>();
  return <ProtectedRoute><ApplicationDocumentsPage id={id} key={id} /></ProtectedRoute>;
}
