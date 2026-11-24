'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, BriefcaseBusiness, CalendarDays, ChartNoAxesCombined, Clock3, FileText, History, Play, RotateCcw, Trash2 } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Button, buttonVariants } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ApplicationProfile, applicationProfiles } from '@/services/applicationProfiles';
import { evidenceInterview, interviewError } from '@/services/evidenceInterview';
import { ApplicationDocumentsPanel } from '@/components/features/applications/ApplicationDocumentsPanel';
import { CurrentCompetencyPanel } from '@/components/features/applications/CurrentCompetencyPanel';
import { activeAttempt, AttemptBadge, finishedAttempt, formatProfileDate } from '@/components/features/applications/applicationUi';

const tabClass = 'gap-1.5 px-1 text-xs sm:gap-2 sm:px-0 sm:text-sm group-data-horizontal/tabs:after:bottom-0 after:bg-brand-orange data-active:text-brand-orange';

function InterviewHistory({ profile }: { profile: ApplicationProfile }) {
  const [limit, setLimit] = useState(8);
  const attempts = [...profile.attempts].sort((a, b) => b.number - a.number);
  return <section id="history" className="scroll-mt-24 rounded-2xl border bg-card">
    <header className="border-b px-5 py-5 sm:px-6"><h2 className="text-lg font-semibold">Các lượt phỏng vấn</h2><p className="mt-1 text-sm text-muted-foreground">Mỗi lượt giữ riêng câu trả lời và kết quả đánh giá.</p></header>
    {!attempts.length && <div className="px-6 py-12 text-center"><History className="mx-auto mb-3 text-muted-foreground" size={25} /><h3 className="font-medium">Chưa có lượt phỏng vấn</h3><p className="mt-2 text-sm text-muted-foreground">Bắt đầu một lượt mới để kiểm chứng năng lực theo JD.</p></div>}
    <div>{attempts.slice(0, limit).map(attempt => {
      const finished = finishedAttempt(attempt);
      const action = finished ? (attempt.answeredCount > 0 ? 'Xem kết quả' : 'Xem chi tiết lượt') : 'Mở lượt phỏng vấn';
      return <article key={attempt.id} className="flex flex-wrap items-center justify-between gap-4 border-b px-5 py-5 last:border-b-0 sm:px-6">
        <div className="flex min-w-0 items-start gap-4"><span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted/60 text-sm font-semibold tabular-nums">{String(attempt.number).padStart(2, '0')}</span><div className="space-y-2"><div className="flex flex-wrap items-center gap-2.5"><h3 className="font-medium">Lượt {attempt.number}</h3><AttemptBadge attempt={attempt} /></div><p className="text-xs leading-5 text-muted-foreground">{formatProfileDate(attempt.startedAt, true)}<span className="mx-2">·</span>{attempt.answeredCount} câu đã trả lời</p></div></div>
        <Link href={`/interview/session/${attempt.id}${finished ? '/result' : ''}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>{action}<ArrowRight size={14} aria-hidden="true" /></Link>
      </article>;
    })}</div>
    {attempts.length > limit && <div className="border-t p-4 text-center"><Button variant="ghost" onClick={() => setLimit(limit + 8)}>Xem thêm lượt phỏng vấn ({attempts.length - limit})</Button></div>}
  </section>;
}

function ProfileDetail({ id }: { id: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<ApplicationProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [tab, setTab] = useState('competency');
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setProfile(await applicationProfiles.get(id)); }
    catch (cause) { setError(interviewError(cause)); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const sync = () => { const hash = window.location.hash.slice(1); if (['competency', 'history', 'documents'].includes(hash)) setTab(hash); };
    sync(); window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  const active = profile ? activeAttempt(profile.attempts) : undefined;
  async function begin(restart = false) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      if (restart && active?.status === 'In progress') {
        const current = await evidenceInterview.get(active.id);
        if (current && !current.is_finished) await evidenceInterview.stop(current, crypto.randomUUID());
      }
      const attempt = await applicationProfiles.newAttempt(id);
      router.push(`/interview/session/${attempt.id}`);
    } catch (cause) { setError(interviewError(cause)); }
    finally { setBusy(false); setConfirmRestart(false); }
  }

  async function deleteProfile() {
    if (deleting) return;
    setDeleting(true);
    setError('');
    try {
      await applicationProfiles.delete(id);
      router.replace('/applications');
    } catch (cause) {
      setError(interviewError(cause));
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  const firstAttempt = profile?.attempts.length === 0;
  const activeHint = active?.status === 'In progress' ? 'Tiếp tục từ câu hỏi đã lưu.' : 'Chọn hình thức và thời lượng trước khi bắt đầu.';
  const nextHint = active ? activeHint : firstAttempt ? 'Hoàn thành một lượt phỏng vấn để nhận đánh giá theo JD.' : undefined;
  const interviewAction = active ? (
    <Link className={`${buttonVariants({ size: 'lg' })} min-h-11 w-full sm:min-h-0 sm:w-auto`} href={`/interview/session/${active.id}`}>
      <Play size={16} aria-hidden="true" />
      {active.status === 'Not started' ? `Bắt đầu lượt ${active.number}` : `Tiếp tục lượt ${active.number}`}
    </Link>
  ) : (
    <Button size="lg" className="min-h-11 w-full sm:min-h-0 sm:w-auto" disabled={busy} onClick={() => void begin()}>
      <Play size={16} aria-hidden="true" />
      {busy ? 'Đang tạo lượt…' : firstAttempt ? 'Bắt đầu lượt đầu' : 'Phỏng vấn lượt mới'}
    </Button>
  );
  const restartAction = active?.status === 'In progress' && (
    <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmRestart(true)}>
      <RotateCcw size={14} aria-hidden="true" />Bắt đầu lại
    </Button>
  );

  return <div className="mx-auto max-w-6xl space-y-6 px-4 py-7 sm:px-6 sm:py-9">
    <Link className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground" href="/applications"><ArrowLeft size={15} />Hồ sơ ứng tuyển</Link>
    {loading && !profile && <div role="status" aria-label="Đang tải hồ sơ" className="space-y-5"><div className="h-28 animate-pulse rounded-2xl bg-muted/50" /><div className="h-96 animate-pulse rounded-2xl bg-muted/30" /></div>}
    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><p>{error}</p><Button variant="outline" disabled={loading} onClick={() => void load()}>Tải lại hồ sơ</Button></div>}
    {profile && <>
      <header className="flex flex-wrap items-center justify-between gap-3 sm:gap-6">
        <div className="flex min-w-0 flex-1 items-start gap-4"><span className="hidden size-14 shrink-0 items-center justify-center rounded-2xl border bg-card text-muted-foreground sm:flex"><BriefcaseBusiness size={25} /></span><div className="min-w-0 space-y-2"><h1 className="break-words text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{profile.title}</h1><p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">{profile.company && <span className="inline-flex items-center gap-1.5"><BriefcaseBusiness size={14} />{profile.company}</span>}<span className="inline-flex items-center gap-1.5"><CalendarDays size={14} />Tạo {formatProfileDate(profile.createdAt)}</span><span>{profile.skills.length} kỹ năng theo JD</span></p></div></div>
        <div className={tab === 'competency' ? 'flex shrink-0 self-start sm:self-auto' : 'flex w-full flex-col gap-2 sm:w-auto sm:flex-row'}>
          {tab !== 'competency' && interviewAction}
          <Button
            type="button"
            variant={tab === 'competency' ? 'ghost' : 'outline'}
            className={tab === 'competency'
              ? 'min-h-11 min-w-11 shrink-0 text-muted-foreground hover:text-destructive sm:min-h-0 sm:min-w-0'
              : 'w-full shrink-0 text-destructive hover:bg-destructive/5 hover:text-destructive sm:w-auto'}
            disabled={deleting}
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 size={15} aria-hidden="true" />
            <span className={tab === 'competency' ? 'sr-only sm:not-sr-only' : undefined}>Xóa hồ sơ</span>
          </Button>
        </div>
      </header>

      {active && tab !== 'competency' && <aside className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-orange-200/60 bg-orange-50/60 px-4 py-3"><div className="flex items-start gap-2.5"><Clock3 className="mt-0.5 shrink-0 text-brand-orange" size={17} /><p className="text-sm"><span className="font-medium">{active.status === 'In progress' ? `Lượt ${active.number} đang diễn ra.` : `Lượt ${active.number} đã sẵn sàng.`}</span><span className="ml-1 text-muted-foreground">{activeHint}</span></p></div>{restartAction}</aside>}

      <Tabs value={tab} onValueChange={value => { if (typeof value === 'string') { setTab(value); window.history.replaceState(null, '', `#${value}`); } }} className="gap-5">
        <div className="border-b"><TabsList variant="line" aria-label="Nội dung hồ sơ ứng tuyển" className="h-12 w-full gap-2 p-0 sm:w-fit sm:gap-5"><TabsTrigger value="competency" className={tabClass}><ChartNoAxesCombined size={16} /><span className="sm:hidden">Năng lực</span><span className="hidden sm:inline">Năng lực hiện tại</span></TabsTrigger><TabsTrigger value="history" className={tabClass}><History size={16} /><span className="sm:hidden">Lịch sử</span><span className="hidden sm:inline">Lịch sử phỏng vấn</span><span className="hidden rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums sm:inline">{profile.attempts.length}</span></TabsTrigger><TabsTrigger value="documents" className={tabClass}><FileText size={16} />CV & JD</TabsTrigger></TabsList></div>
        <TabsContent value="competency">
          <CurrentCompetencyPanel
            profileId={id}
            baselineSkills={profile.skills}
            refreshKey={profile.attempts.map(attempt => `${attempt.id}:${attempt.status}:${attempt.answeredCount}`).join('|')}
            nextHint={nextHint}
            nextAction={<div className="flex flex-wrap items-center gap-2 pt-1">{interviewAction}{restartAction}</div>}
          />
        </TabsContent>
        <TabsContent value="history"><InterviewHistory profile={profile} /></TabsContent>
        <TabsContent value="documents"><ApplicationDocumentsPanel profile={profile} /></TabsContent>
      </Tabs>
    </>}
    <Dialog open={confirmRestart} onOpenChange={open => !busy && setConfirmRestart(open)}><DialogContent><DialogHeader><DialogTitle>Kết thúc lượt hiện tại và bắt đầu lại?</DialogTitle><DialogDescription>Các câu trả lời đã gửi được giữ trong lịch sử. Bạn sẽ bắt đầu một lượt mới với cùng CV/JD. Câu trả lời chưa gửi sẽ không được tính.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" disabled={busy} onClick={() => setConfirmRestart(false)}>Quay lại</Button><Button disabled={busy} onClick={() => void begin(true)}>{busy ? 'Đang xử lý…' : 'Kết thúc và tạo lượt mới'}</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={confirmDelete} onOpenChange={open => !deleting && setConfirmDelete(open)}><DialogContent><DialogHeader><DialogTitle>Chuyển hồ sơ vào thùng rác?</DialogTitle><DialogDescription>“{profile?.title}” sẽ được giữ trong thùng rác 30 ngày. Bạn có thể khôi phục trong thời gian này; sau đó hồ sơ, lượt phỏng vấn và kế hoạch ôn tập sẽ bị xóa vĩnh viễn. CV/JD đã lưu trong thư viện tài liệu vẫn được giữ lại.</DialogDescription></DialogHeader><DialogFooter><Button type="button" variant="outline" disabled={deleting} onClick={() => setConfirmDelete(false)}>Hủy</Button><Button type="button" variant="destructive" disabled={deleting} onClick={() => void deleteProfile()}>{deleting ? 'Đang chuyển…' : 'Chuyển vào thùng rác'}</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

export default function ApplicationProfilePage() {
  const { id } = useParams<{ id: string }>();
  return <ProtectedRoute><ProfileDetail id={id} key={id} /></ProtectedRoute>;
}
