'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, RotateCcw, Trash2 } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Button, buttonVariants } from '@/components/ui/button';
import { applicationProfiles, type ApplicationTrashEntry } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import { formatProfileDate } from '@/components/features/applications/applicationUi';

function TrashProfiles() {
  const [entries, setEntries] = useState<ApplicationTrashEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setEntries(await applicationProfiles.trash());
    } catch (cause) {
      setError(interviewError(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function restore(id: string) {
    setRestoringId(id);
    setError('');
    try {
      await applicationProfiles.restore(id);
      setEntries((current) => current.filter((entry) => entry.profile.id !== id));
    } catch (cause) {
      setError(interviewError(cause));
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-7 sm:px-6 sm:py-9">
      <Link href="/applications" className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground">
        <ArrowLeft size={15} aria-hidden="true" />Hồ sơ ứng tuyển
      </Link>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Thùng rác</h1>
          <p className="mt-2 text-sm text-muted-foreground">Hồ sơ được giữ 30 ngày trước khi xóa vĩnh viễn.</p>
        </div>
        <Trash2 className="text-muted-foreground" size={22} aria-hidden="true" />
      </header>

      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><p>{error}</p><Button type="button" variant="outline" onClick={() => void load()}>Thử lại</Button></div>}
      {loading && <p role="status" className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">Đang tải thùng rác…</p>}
      {!loading && !entries.length && <section className="rounded-2xl border bg-card px-6 py-14 text-center">
        <Trash2 className="mx-auto mb-3 text-muted-foreground" size={24} aria-hidden="true" />
        <h2 className="font-semibold">Thùng rác đang trống</h2>
        <p className="mt-2 text-sm text-muted-foreground">Hồ sơ bạn xóa sẽ xuất hiện ở đây trong 30 ngày.</p>
        <Link href="/applications" className={`${buttonVariants({ variant: 'outline' })} mt-5`}>Quay lại hồ sơ</Link>
      </section>}
      {!loading && entries.length > 0 && <ul className="grid gap-3 md:grid-cols-2">
        {entries.map(({ profile, deletedAt, expiresAt }) => (
          <li key={profile.id} className="flex min-w-0 flex-col justify-between gap-5 rounded-2xl border bg-card p-5 sm:flex-row sm:items-center">
            <div className="min-w-0">
              <h2 className="truncate font-semibold" title={profile.title}>{profile.title}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{profile.company || 'Chưa thêm công ty'}</p>
              <p className="mt-3 truncate text-xs text-muted-foreground" title={profile.cvFilename}>CV: {profile.cvFilename}</p>
              <p className="mt-1 truncate text-xs text-muted-foreground" title={profile.jdFilename || profile.jdTitle}>JD: {profile.jdFilename || profile.jdTitle}</p>
              <p className="mt-3 text-xs text-muted-foreground">Đã xóa {formatProfileDate(deletedAt)} · Xóa vĩnh viễn sau {formatProfileDate(expiresAt)}</p>
            </div>
            <Button type="button" variant="outline" className="shrink-0" disabled={restoringId === profile.id} onClick={() => void restore(profile.id)}>
              <RotateCcw size={15} aria-hidden="true" />{restoringId === profile.id ? 'Đang khôi phục…' : 'Khôi phục'}
            </Button>
          </li>
        ))}
      </ul>}
    </main>
  );
}

export default function ApplicationTrashPage() {
  return <ProtectedRoute><TrashProfiles /></ProtectedRoute>;
}
