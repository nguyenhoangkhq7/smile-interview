'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, BriefcaseBusiness, CalendarDays, ChartNoAxesCombined, ChevronRight, Clock3, FileText, History, Play, RotateCcw } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Button, buttonVariants } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ApplicationProfile, applicationProfiles } from '@/services/applicationProfiles';
import { evidenceInterview, interviewError } from '@/services/evidenceInterview';
import { MarkdownContent } from '@/components/common/MarkdownContent';
import { CurrentCompetencyPanel } from '@/components/features/applications/CurrentCompetencyPanel';
import { GnnScoreMetric } from '@/components/features/interview/GnnScoreMetric';
import { activeAttempt, AttemptBadge, finishedAttempt, formatProfileDate, skillLabel } from '@/components/features/applications/applicationUi';

const tabClass = 'gap-1.5 px-1 text-xs sm:gap-2 sm:px-0 sm:text-sm group-data-horizontal/tabs:after:bottom-0 after:bg-brand-orange data-active:text-brand-orange';

function InterviewHistory({ profile }: { profile: ApplicationProfile }) {
  const [limit, setLimit] = useState(8);
  const attempts = [...profile.attempts].sort((a, b) => b.number - a.number);
  return <section className="rounded-2xl border bg-card">
    <header className="border-b px-5 py-5 sm:px-6"><h2 className="text-lg font-semibold">Các lượt phỏng vấn</h2><p className="mt-1 text-sm text-muted-foreground">Mỗi lượt giữ riêng câu trả lời và kết quả đánh giá.</p></header>
    {!attempts.length && <div className="px-6 py-12 text-center"><History className="mx-auto mb-3 text-muted-foreground" size={25} /><h3 className="font-medium">Chưa có lượt phỏng vấn</h3><p className="mt-2 text-sm text-muted-foreground">Bắt đầu một lượt mới để kiểm chứng năng lực theo JD.</p></div>}
    <div>{attempts.slice(0, limit).map(attempt => {
      const finished = finishedAttempt(attempt);
      return <article key={attempt.id} className="flex flex-wrap items-center justify-between gap-4 border-b px-5 py-5 last:border-b-0 sm:px-6">
        <div className="flex min-w-0 items-start gap-4"><span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted/60 text-sm font-semibold tabular-nums">{String(attempt.number).padStart(2, '0')}</span><div className="space-y-2"><div className="flex flex-wrap items-center gap-2.5"><h3 className="font-medium">Lượt {attempt.number}</h3><AttemptBadge attempt={attempt} /></div><p className="text-xs leading-5 text-muted-foreground">{formatProfileDate(attempt.startedAt, true)}<span className="mx-2">·</span>{attempt.answeredCount} câu đã trả lời</p></div></div>
        <Link href={`/interview/session/${attempt.id}${finished ? '/result' : ''}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>{finished ? (attempt.answeredCount ? 'Xem kết quả' : 'Xem lượt đã hủy') : 'Mở lượt phỏng vấn'}<ArrowRight size={14} /></Link>
      </article>;
    })}</div>
    {attempts.length > limit && <div className="border-t p-4 text-center"><Button variant="ghost" onClick={() => setLimit(limit + 8)}>Xem thêm lượt phỏng vấn ({attempts.length - limit})</Button></div>}
  </section>;
}

function Documents({ profile }: { profile: ApplicationProfile }) {
  const counts = { MATCH: 0, PARTIAL: 0, MISSING: 0 };
  profile.skills.forEach(skill => { counts[skill.semantic_alignment]++; });
  return <div className="space-y-5">
    <section className="rounded-2xl border bg-card p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Tài liệu của hồ sơ</h2><p className="mt-1 text-sm text-muted-foreground">CV và JD dùng chung cho tất cả lượt phỏng vấn.</p></div><Link href="/interview/new" className="text-sm font-medium text-brand-orange hover:underline">Tạo hồ sơ với tài liệu mới<ChevronRight className="ml-1 inline" size={14} /></Link></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">{[
        { label: 'CV của bạn', name: profile.cvFilename }, { label: 'Mô tả công việc', name: profile.jdTitle },
      ].map(item => <div key={item.label} className="flex min-w-0 items-center gap-3 rounded-xl border bg-muted/20 p-4"><span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-card text-muted-foreground"><FileText size={19} /></span><div className="min-w-0"><p className="text-xs text-muted-foreground">{item.label}</p><p className="mt-1 break-words text-sm font-medium">{item.name}</p></div></div>)}</div>
    </section>
    <section className="rounded-2xl border bg-card p-5 sm:p-6"><h2 className="text-lg font-semibold">Phân tích CV–JD ban đầu</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Đối chiếu thông tin trong tài liệu. Kết quả năng lực qua câu trả lời phỏng vấn nằm ở tab Năng lực hiện tại.</p>
      <div className="mt-5 sm:w-56"><GnnScoreMetric score={profile.analysis.matching_score} /></div>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 rounded-xl bg-muted/40 px-4 py-3 text-sm"><span><strong className="mr-1 text-brand-green">{counts.MATCH}</strong> Phù hợp</span><span><strong className="mr-1 text-amber-700">{counts.PARTIAL}</strong> Liên quan</span><span><strong className="mr-1">{counts.MISSING}</strong> Chưa có bằng chứng</span></div>
      <div role="region" aria-label="Đối chiếu kỹ năng CV–JD" tabIndex={0} className="mt-4 max-h-80 divide-y overflow-y-auto overscroll-contain pr-1">{profile.skills.map(skill => <div key={skill.jd_skill_id} className="flex flex-wrap items-center justify-between gap-2 py-3"><span className="text-sm font-medium">{skillLabel(skill.jd_skill_id)}</span><span className={`text-xs ${skill.semantic_alignment === 'MATCH' ? 'text-brand-green' : 'text-muted-foreground'}`}>{skill.semantic_alignment === 'MATCH' ? 'Có bằng chứng phù hợp trong CV' : skill.semantic_alignment === 'PARTIAL' ? 'Có bằng chứng liên quan trong CV' : 'Chưa có bằng chứng tương ứng trong CV'}</span></div>)}</div>
      {profile.analysis.markdown_summary && <details className="mt-4 min-w-0 border-t pt-4"><summary className="cursor-pointer text-sm font-medium">Xem bản phân tích đầy đủ</summary><div className="mt-4 max-h-[65dvh] overflow-auto overscroll-contain rounded-xl border p-4"><MarkdownContent content={profile.analysis.markdown_summary} /></div></details>}
    </section>
  </div>;
}

function ProfileDetail({ id }: { id: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<ApplicationProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);
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

  return <div className="mx-auto max-w-6xl space-y-6 px-4 py-7 sm:px-6 sm:py-9">
    <Link className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground" href="/applications"><ArrowLeft size={15} />Hồ sơ ứng tuyển</Link>
    {loading && !profile && <div role="status" aria-label="Đang tải hồ sơ" className="space-y-5"><div className="h-28 animate-pulse rounded-2xl bg-muted/50" /><div className="h-96 animate-pulse rounded-2xl bg-muted/30" /></div>}
    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><p>{error}</p><Button variant="outline" disabled={loading} onClick={() => void load()}>Tải lại hồ sơ</Button></div>}
    {profile && <>
      <header className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex min-w-0 items-start gap-4"><span className="hidden size-14 shrink-0 items-center justify-center rounded-2xl border bg-card text-muted-foreground sm:flex"><BriefcaseBusiness size={25} /></span><div className="min-w-0 space-y-2"><h1 className="break-words text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{profile.title}</h1><p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">{profile.company && <span className="inline-flex items-center gap-1.5"><BriefcaseBusiness size={14} />{profile.company}</span>}<span className="inline-flex items-center gap-1.5"><CalendarDays size={14} />Tạo {formatProfileDate(profile.createdAt)}</span><span>{profile.skills.length} kỹ năng theo JD</span></p></div></div>
        {active ? <Link className={`${buttonVariants()} w-full shrink-0 sm:w-auto`} href={`/interview/session/${active.id}`}><Play size={16} />{active.status === 'Not started' ? `Bắt đầu lượt ${active.number}` : `Tiếp tục lượt ${active.number}`}</Link> : <Button className="w-full shrink-0 sm:w-auto" disabled={busy} onClick={() => void begin()}><Play size={16} />{busy ? 'Đang tạo lượt…' : 'Phỏng vấn lượt mới'}</Button>}
      </header>

      {active && <aside className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-orange-200/60 bg-orange-50/60 px-4 py-3"><div className="flex items-start gap-2.5"><Clock3 className="mt-0.5 shrink-0 text-brand-orange" size={17} /><p className="text-sm"><span className="font-medium">{active.status === 'In progress' ? `Lượt ${active.number} đang diễn ra.` : `Lượt ${active.number} đã sẵn sàng.`}</span><span className="ml-1 text-muted-foreground">{active.status === 'In progress' ? 'Tiếp tục từ câu hỏi đã lưu.' : 'Chọn dạng và thời lượng trước khi bắt đầu.'}</span></p></div>{active.status === 'In progress' && <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmRestart(true)}><RotateCcw size={14} />Bắt đầu lại</Button>}</aside>}

      <Tabs value={tab} onValueChange={value => { if (typeof value === 'string') { setTab(value); window.history.replaceState(null, '', `#${value}`); } }} className="gap-5">
        <div className="border-b"><TabsList variant="line" aria-label="Nội dung hồ sơ ứng tuyển" className="h-12 w-full gap-2 p-0 sm:w-fit sm:gap-5"><TabsTrigger value="competency" className={tabClass}><ChartNoAxesCombined size={16} /><span className="sm:hidden">Năng lực</span><span className="hidden sm:inline">Năng lực hiện tại</span></TabsTrigger><TabsTrigger value="history" className={tabClass}><History size={16} /><span className="sm:hidden">Lịch sử</span><span className="hidden sm:inline">Lịch sử phỏng vấn</span><span className="hidden rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums sm:inline">{profile.attempts.length}</span></TabsTrigger><TabsTrigger value="documents" className={tabClass}><FileText size={16} />CV & JD</TabsTrigger></TabsList></div>
        <TabsContent value="competency"><CurrentCompetencyPanel profileId={id} refreshKey={profile.attempts.map(a => `${a.id}:${a.status}`).join('|')} /></TabsContent>
        <TabsContent value="history"><InterviewHistory profile={profile} /></TabsContent>
        <TabsContent value="documents"><Documents profile={profile} /></TabsContent>
      </Tabs>
    </>}
    <Dialog open={confirmRestart} onOpenChange={open => !busy && setConfirmRestart(open)}><DialogContent><DialogHeader><DialogTitle>Kết thúc lượt hiện tại và bắt đầu lại?</DialogTitle><DialogDescription>Các câu trả lời đã gửi được giữ trong lịch sử. Bạn sẽ bắt đầu một lượt mới với cùng CV/JD. Câu trả lời chưa gửi sẽ không được tính.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" disabled={busy} onClick={() => setConfirmRestart(false)}>Quay lại</Button><Button disabled={busy} onClick={() => void begin(true)}>{busy ? 'Đang xử lý…' : 'Kết thúc và tạo lượt mới'}</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}

export default function ApplicationProfilePage() {
  const { id } = useParams<{ id: string }>();
  return <ProtectedRoute><ProfileDetail id={id} key={id} /></ProtectedRoute>;
}
