import type { Metadata } from 'next';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import InterviewDocumentReader from '@/components/features/admin/sessions/InterviewDocumentReader';

export const metadata: Metadata = { title: 'Tài liệu phiên phỏng vấn', robots: { index: false } };

export default async function AdminDocumentPage({ searchParams }: {
  searchParams: Promise<{ id?: string | string[]; kind?: string | string[] }>;
}) {
  const { id, kind } = await searchParams;
  return <ProtectedRoute requiredRole="ADMIN">
    {typeof id === 'string' && id.trim() && id.length <= 128 && (kind === 'CV' || kind === 'JD')
      ? <InterviewDocumentReader key={JSON.stringify([id, kind])} id={id} kind={kind} />
      : <p role="alert" className="mx-auto max-w-4xl p-6">Liên kết tài liệu không hợp lệ.</p>}
  </ProtectedRoute>;
}
