'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, BriefcaseBusiness, FileText, Plus, Search, SlidersHorizontal, Trash2 } from 'lucide-react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { Button, buttonVariants } from '@/components/ui/button';
import { ApplicationProfile, applicationProfiles } from '@/services/applicationProfiles';
import { interviewError } from '@/services/evidenceInterview';
import { activeAttempt, finishedAttempt, searchText } from '@/components/features/applications/applicationUi';
import { ApplicationFolderCard } from '@/components/features/applications/ApplicationFolderCard';

type Filter = 'all' | 'active' | 'ready' | 'results';
const filters: { value: Filter; label: string }[] = [
  { value: 'all', label: 'Tất cả' }, { value: 'active', label: 'Đang phỏng vấn' },
  { value: 'ready', label: 'Chưa bắt đầu' }, { value: 'results', label: 'Đã có kết quả' },
];

function Profiles() {
  const [profiles, setProfiles] = useState<ApplicationProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setProfiles(await applicationProfiles.list()); }
    catch (cause) { setError(interviewError(cause)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const filtered = profiles.filter(profile => {
    const active = activeAttempt(profile.attempts);
    const matches = filter === 'all' || (filter === 'active' && active?.status === 'In progress')
      || (filter === 'ready' && active?.status === 'Not started')
      || (filter === 'results' && profile.attempts.some(a => finishedAttempt(a) && a.answeredCount > 0));
    return matches && searchText([profile.title, profile.company, profile.roleTitle].filter(Boolean).join(' ')).includes(searchText(query.trim()));
  });

  return <div className="mx-auto max-w-6xl space-y-7 px-4 py-8 sm:px-6 sm:py-10">
    <header className="flex flex-wrap items-center justify-between gap-5">
      <div className="space-y-2"><h1 className="text-3xl font-semibold tracking-tight">Hồ sơ ứng tuyển</h1>
        <p className="max-w-xl text-sm leading-6 text-muted-foreground">Chuẩn bị cho từng vị trí. Phỏng vấn nhiều lượt và theo dõi kết quả trong cùng một hồ sơ.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Link className={`${buttonVariants({ variant: 'outline' })} shrink-0`} href="/applications/trash"><Trash2 size={15} />Thùng rác</Link>
        <Link className={`${buttonVariants()} shrink-0`} href="/interview/new"><Plus size={16} />Tạo hồ sơ ứng tuyển</Link>
      </div>
    </header>

    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm"><p>{error}</p><Button variant="outline" onClick={() => void load()}>Thử lại</Button></div>}

    {profiles.length > 0 && <section aria-label="Tìm và lọc hồ sơ" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border bg-card px-3.5 focus-within:border-brand-orange focus-within:ring-2 focus-within:ring-brand-orange/10 sm:max-w-sm"><Search className="shrink-0 text-muted-foreground" size={17} /><input aria-label="Tìm hồ sơ ứng tuyển" className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Tìm theo vị trí hoặc công ty…" value={query} onChange={e => setQuery(e.target.value)} /></div>
        <p className="text-sm text-muted-foreground">{filtered.length} hồ sơ</p>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Lọc trạng thái hồ sơ">{filters.map(item => <button key={item.value} aria-pressed={filter === item.value} onClick={() => setFilter(item.value)} className={`rounded-lg px-3 py-2 text-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange ${filter === item.value ? 'bg-foreground font-medium text-background' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}>{item.label}</button>)}</div>
    </section>}

    {loading && !profiles.length && <div role="status" aria-label="Đang tải hồ sơ" className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map(item => <div key={item} className="h-56 animate-pulse rounded-2xl border bg-muted/30 p-6"><div className="mb-5 h-5 w-2/3 rounded bg-muted" /><div className="mb-3 h-3 w-1/2 rounded bg-muted" /><div className="h-3 w-4/5 rounded bg-muted" /></div>)}</div>}

    {!loading && !error && !profiles.length && <section className="rounded-2xl border bg-card px-6 py-14 text-center sm:py-20">
      <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-2xl bg-brand-orange/8 text-brand-orange"><BriefcaseBusiness size={26} /></div>
      <h2 className="text-xl font-semibold">Bạn đang chuẩn bị ứng tuyển ở đâu?</h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">Bắt đầu với CV và mô tả công việc. Mỗi hồ sơ sẽ lưu bản phân tích và các lượt phỏng vấn của bạn.</p>
      <Link className={`${buttonVariants()} mt-6`} href="/interview/new">Tạo hồ sơ đầu tiên<ArrowRight size={16} /></Link>
      <div className="mx-auto mt-10 grid max-w-lg gap-4 border-t pt-6 text-left text-sm sm:grid-cols-3">{['Chọn CV & JD', 'Phỏng vấn', 'Xem kết quả'].map((label, index) => <p className="flex items-center gap-2 text-muted-foreground" key={label}><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">{index + 1}</span>{label}</p>)}</div>
    </section>}

    {profiles.length > 0 && !filtered.length && <div className="rounded-2xl border border-dashed py-14 text-center"><SlidersHorizontal className="mx-auto mb-3 text-muted-foreground" size={24} /><h2 className="font-semibold">Không tìm thấy hồ sơ phù hợp</h2><p className="mt-2 text-sm text-muted-foreground">Thử tên vị trí khác hoặc bỏ bộ lọc.</p><Button variant="outline" className="mt-5" onClick={() => { setQuery(''); setFilter('all'); }}>Xóa bộ lọc</Button></div>}

    <div className="grid gap-5 md:grid-cols-2">{filtered.map((profile, index) => (
      <ApplicationFolderCard key={profile.id} profile={profile} index={index} />
    ))}</div>
  </div>;
}

export default function ApplicationsPage() { return <ProtectedRoute><Profiles /></ProtectedRoute>; }
