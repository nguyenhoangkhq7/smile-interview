import React from 'react';

export const LEVEL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  INTERN: { bg: 'bg-slate-800/80', text: 'text-slate-300', border: 'border-slate-700/60' },
  FRESHER: { bg: 'bg-sky-950/60', text: 'text-sky-300', border: 'border-sky-800/50' },
  JUNIOR: { bg: 'bg-teal-950/60', text: 'text-teal-300', border: 'border-teal-800/50' },
  MID: { bg: 'bg-violet-950/60', text: 'text-violet-300', border: 'border-violet-800/50' },
  SENIOR: { bg: 'bg-amber-950/60', text: 'text-amber-300', border: 'border-amber-800/50' },
  LEAD: { bg: 'bg-rose-950/60', text: 'text-rose-300', border: 'border-rose-800/50' },
  ALL: { bg: 'bg-orange-950/60', text: 'text-orange-300', border: 'border-orange-800/50' },
};

export const LEVEL_ORDER = ['INTERN', 'FRESHER', 'JUNIOR', 'MID', 'SENIOR', 'LEAD', 'ALL'];

export function LevelBadge({ level }: { level: string }) {
  const style = LEVEL_STYLES[level.toUpperCase()] ?? {
    bg: 'bg-slate-800/60',
    text: 'text-slate-400',
    border: 'border-slate-700/40',
  };
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-wide ${style.bg} ${style.text} ${style.border}`}
    >
      {level}
    </span>
  );
}

export function MappedLevelsBadges({ levels }: { levels?: string[] }) {
  if (!levels || levels.length === 0) {
    return <span className="text-[11px] italic text-slate-500">Chưa áp dụng</span>;
  }
  const sorted = [...levels].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.toUpperCase()) - LEVEL_ORDER.indexOf(b.toUpperCase())
  );
  return (
    <div className="flex flex-wrap gap-1">
      {sorted.map((lvl) => (
        <LevelBadge key={lvl} level={lvl} />
      ))}
    </div>
  );
}

export function formatCategoryLabel(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .replace(/_/g, ' ')
    .toLowerCase()
    .split(' ')
    .filter(Boolean)
    .map((word) => {
      if (word === 'qa') return 'QA';
      if (word === 'js') return 'JS';
      if (word === 'id') return 'ID';
      if (word === 'cv') return 'CV';
      if (word === 'jd') return 'JD';
      if (word === 'nestjs') return 'NestJS';
      if (word === 'mongodb') return 'MongoDB';
      if (word === 'mysql') return 'MySQL';
      if (word === 'postgresql') return 'PostgreSQL';
      if (word === 'api') return 'API';
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

export function generateCategoryCode(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toUpperCase()
    .replace(/[^A-Z0-9\s_]/g, '')
    .trim()
    .replace(/\s+/g, '_');
}

export function CurvedTreeConnector({ isLast }: { isLast: boolean }) {
  return (
    <div className="absolute -left-6 top-0 bottom-0 w-6 pointer-events-none select-none">
      {!isLast && (
        <div className="absolute left-[3px] top-0 bottom-0 w-[1.5px] bg-slate-700/60 group-hover/node:bg-orange-500/40 transition-colors" />
      )}
      <svg
        className="absolute left-[3px] top-0 w-6 h-7 text-slate-700/70 group-hover/row:text-orange-400 group-hover/crit:text-teal-400 transition-colors"
        fill="none"
        viewBox="0 0 24 28"
      >
        <path
          d="M 0 0 V 14 C 0 21, 6 27, 24 27"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
