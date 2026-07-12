'use client';

interface StatCard {
  label: string;
  value: number | string;
  tone?: 'orange' | 'blue' | 'violet' | 'emerald';
}

interface StatCardsProps {
  items: StatCard[];
}

const toneStyles: Record<NonNullable<StatCard['tone']>, string> = {
  orange: 'from-orange-500/20 to-orange-500/5 text-orange-300 ring-orange-500/20',
  blue: 'from-sky-500/20 to-sky-500/5 text-sky-300 ring-sky-500/20',
  violet: 'from-violet-500/20 to-violet-500/5 text-violet-300 ring-violet-500/20',
  emerald: 'from-emerald-500/20 to-emerald-500/5 text-emerald-300 ring-emerald-500/20',
};

export default function StatCards({ items }: StatCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      {items.map((item, index) => {
        const tone = item.tone ?? ['orange', 'blue', 'violet', 'emerald'][index % 4] as NonNullable<StatCard['tone']>;

        return (
          <div
            key={item.label}
            className={`rounded-3xl border border-white/6 bg-gradient-to-br ${toneStyles[tone]} px-5 py-5 shadow-[0_14px_42px_rgba(2,6,23,0.26)] ring-1 backdrop-blur-sm`}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">{item.label}</p>
            <p className="mt-2 text-[2.15rem] font-semibold leading-none tabular-nums text-white">{item.value}</p>
          </div>
        );
      })}
    </div>
  );
}
