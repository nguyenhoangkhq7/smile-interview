import { Search, X } from 'lucide-react';
import { statusLabels } from './sessionDisplay';
import type { InterviewFilter, InterviewPage } from './types';

const tabs: InterviewFilter[] = ['all', 'COMPLETED', 'IN_PROGRESS', 'ANOMALY', 'NOT_STARTED', 'OTHER'];

export default function SessionsFilterBar({ status, setStatus, search, setSearch, counts }: {
  status: InterviewFilter;
  setStatus: (status: InterviewFilter) => void;
  search: string;
  setSearch: (search: string) => void;
  counts?: InterviewPage['counts'];
}) {
  const total = counts && Object.values(counts).reduce((sum, count) => sum + count, 0);
  return (
    <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white dark:bg-card p-3 shadow-xs xl:flex-row xl:items-center">
      <div role="group" aria-label="Lọc trạng thái phiên" className="flex flex-wrap gap-1.5">
        {tabs.filter((tab) => tab !== 'OTHER' || tab === status || Boolean(counts?.OTHER)).map((tab) => {
          const count = tab === 'all' ? total : counts?.[tab] ?? (counts ? 0 : undefined);
          return <button key={tab} type="button" aria-pressed={status === tab} onClick={() => setStatus(tab)}
            className={status === tab
              ? 'inline-flex items-center gap-2 rounded-lg bg-[#ad2c00] px-3 py-2 text-xs font-semibold text-white'
              : 'inline-flex items-center gap-2 rounded-lg bg-[#f1f3ff] dark:bg-muted px-3 py-2 text-xs text-[#293041] dark:text-foreground hover:bg-[#e0e8ff] dark:hover:bg-secondary'}>
            {tab === 'all' ? 'Tất cả phiên' : statusLabels[tab]}
            <span className="font-mono tabular-nums">{count?.toLocaleString('vi-VN') ?? '—'}</span>
          </button>;
        })}
      </div>
      <label className="relative block w-full shrink-0 xl:w-64">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#5c4039] dark:text-muted-foreground" />
        <input aria-label="Tìm mã phiên, ứng viên hoặc vị trí"
          value={search} maxLength={200} onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm mã phiên, ứng viên, vị trí…"
          className="w-full rounded-lg bg-[#f1f3ff] dark:bg-muted py-2 pl-9 pr-9 text-sm" />
        {search && <button type="button" aria-label="Xóa tìm kiếm" onClick={() => setSearch('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[#5c4039] dark:text-muted-foreground hover:text-[#ad2c00] dark:hover:text-orange-300">
          <X className="size-4" />
        </button>}
      </label>
    </div>
  );
}
