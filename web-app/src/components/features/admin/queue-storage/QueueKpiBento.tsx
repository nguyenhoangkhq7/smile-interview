import { CircleAlert, CircleCheck, Hourglass, RefreshCw } from 'lucide-react';
import type { QueueKpiStats } from './types';

export default function QueueKpiBento({ stats }: { stats: QueueKpiStats }) {
  const tiles = [
    ['Đang chờ', stats.pendingCount, Hourglass, 'bg-[#f1f3ff] dark:bg-muted text-[#5c4039] dark:text-muted-foreground'],
    ['Đang chạy', stats.runningCount, RefreshCw, 'bg-[#e5f1ff] dark:bg-sky-950 text-[#186392] dark:text-sky-300'],
    ['Thành công', stats.succeededCount, CircleCheck, 'bg-[#daf8e0] dark:bg-emerald-950 text-[#006b2f] dark:text-emerald-300'],
    ['Thất bại', stats.failedCount, CircleAlert, 'bg-[#ffebe8] dark:bg-red-950/55 text-[#ba1a1a] dark:text-red-300'],
  ] as const;
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {tiles.map(([title, count, Icon, color]) => (
        <div key={title} className="flex items-center justify-between gap-2 rounded-xl bg-white dark:bg-card p-4 shadow-xs">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[#5c4039] dark:text-muted-foreground">{title}</h2>
            <strong className="mt-1 block text-2xl tabular-nums text-[#141b2c] dark:text-foreground">{count.toLocaleString('vi-VN')}</strong>
          </div>
          <span className={'grid size-10 shrink-0 place-items-center rounded-xl ' + color}><Icon className="size-5" /></span>
        </div>
      ))}
    </div>
  );
}
