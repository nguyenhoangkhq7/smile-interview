'use client';

import { useState } from 'react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { useAdminInterviews } from '@/hooks/useAdminInterviews';
import AdminInterviewDetail from './AdminInterviewDetail';
import InterviewSessionList from './InterviewSessionList';
import SessionsFilterBar from './SessionsFilterBar';
import SessionsHeader from './SessionsHeader';
import themeStyles from '../layout/admin-theme.module.css';
import type { InterviewFilter } from './types';

export default function SessionInspectorView() {
  const [status, setStatus] = useState<InterviewFilter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const { catalog, detail, reload } = useAdminInterviews(search.trim(), status, page, selected);
  const current = selected ? detail : catalog;

  return (
    <div className={`flex w-full flex-col gap-5 pb-8 ${themeStyles.surface}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SessionsHeader />
        {!selected && <button type="button" onClick={reload} disabled={!catalog}
          className="flex items-center gap-2 rounded-lg bg-white dark:bg-card px-3 py-2 text-sm text-[#186392] dark:text-sky-300 disabled:opacity-50">
          <RefreshCw className="size-4" /> Làm mới
        </button>}
      </div>
      {selected
        ? <button type="button" onClick={() => setSelected(null)}
            className="flex w-fit items-center gap-2 rounded-lg bg-white dark:bg-card px-3 py-2 text-sm font-medium text-[#186392] dark:text-sky-300">
            <ArrowLeft className="size-4" /> Về danh sách phiên
          </button>
        : <SessionsFilterBar status={status} search={search} counts={catalog?.data?.counts}
            setStatus={(next) => { setStatus(next); setPage(1); }}
            setSearch={(next) => { setSearch(next); setPage(1); }} />}
      {current?.failed && <p role="alert" className="rounded-xl bg-white dark:bg-card p-5 text-sm text-red-700 dark:text-red-300">
        {selected ? 'Không thể tải chi tiết phiên.' : 'Không thể tải danh sách phiên.'}
        <button type="button" onClick={reload} className="ml-3 underline">Thử lại</button>
      </p>}
      {!current && <p role="status" className="rounded-xl bg-white dark:bg-card p-5 text-sm">
        {selected ? 'Đang tải chi tiết phiên…' : 'Đang tải danh sách phiên…'}
      </p>}
      {selected && detail?.data && <AdminInterviewDetail key={selected} detail={detail.data} onRefresh={reload} />}
      {!selected && catalog?.data && <InterviewSessionList data={catalog.data} onPage={setPage} onSelect={setSelected} />}
    </div>
  );
}
