'use client';

interface StatCard {
  label: string;
  value: number | string;
  tone?: 'orange' | 'blue' | 'violet' | 'emerald';
}

interface StatCardsProps {
  items: StatCard[];
}

export default function StatCards({ items }: StatCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      {items.map((item) => {
        return (
          <div
            key={item.label}
            className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-5 shadow-sm"
          >
            <p className="text-sm text-slate-400 uppercase tracking-wider">{item.label}</p>
            <p className="mt-2 text-4xl font-bold leading-none tabular-nums text-white">{item.value}</p>
          </div>
        );
      })}
    </div>
  );
}
