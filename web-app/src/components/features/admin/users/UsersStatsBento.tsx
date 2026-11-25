import { Ban, CircleCheck, Users } from 'lucide-react';
import type { UsersOverviewStats } from './types';

const numbers = new Intl.NumberFormat('vi-VN');
const percents = new Intl.NumberFormat('vi-VN', { style: 'percent', maximumFractionDigits: 1 });

export default function UsersStatsBento({ stats }: { stats: UsersOverviewStats }) {
  const previousTotal = stats.totalUsers - stats.registeredLast30Days;
  const entries = [
    { label: 'Tổng người dùng', value: stats.totalUsers, icon: Users, color: 'text-[#186392] dark:text-sky-300' },
    { label: 'Đang hoạt động', value: stats.activeUsers, icon: CircleCheck, color: 'text-[#006b2f] dark:text-emerald-300' },
    { label: 'Đang bị khóa', value: stats.lockedUsers, icon: Ban, color: 'text-[#ba1a1a] dark:text-red-300' },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {entries.map(({ label, value, icon: Icon, color }) => (
        <div key={label} className="rounded-xl bg-white dark:bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[#5c4039] dark:text-muted-foreground">{label}</h2>
            <span className={'grid size-9 place-items-center rounded-lg bg-[#f1f3ff] dark:bg-muted ' + color}><Icon className="size-4" /></span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <strong className={'text-2xl tabular-nums ' + color}>{numbers.format(value)}</strong>
            {label === 'Tổng người dùng' && previousTotal > 0 && (
              <span className="text-xs font-semibold text-[#006b2f] dark:text-emerald-300" title="Tăng trưởng tổng tài khoản trong 30 ngày gần nhất">
                +{percents.format(stats.registeredLast30Days / previousTotal)}
              </span>
            )}
            {label === 'Đang hoạt động' && stats.totalUsers > 0 && (
              <span className="rounded-full bg-[#e9edff] dark:bg-secondary px-2 py-1 text-xs text-[#006b2f] dark:text-emerald-300">
                {percents.format(stats.activeUsers / stats.totalUsers)}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
