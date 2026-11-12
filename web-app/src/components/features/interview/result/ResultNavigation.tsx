'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ChartNoAxesCombined, ClipboardList, Crosshair, ListChecks, NotebookPen, Printer, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

const sections = [
  { id: 'overview', label: 'Tổng quan', Icon: ChartNoAxesCombined },
  { id: 'skills', label: 'Kỹ năng', Icon: Crosshair },
  { id: 'feedback', label: 'Nhận xét AI', Icon: Sparkles },
  { id: 'questions', label: 'Chi tiết câu hỏi', Icon: ClipboardList },
  { id: 'study', label: 'Gợi ý ôn tập', Icon: ListChecks },
] as const;

const control = 'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1.5 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 xl:px-3';

export function ResultNavigation({ studyHref }: { studyHref: string }) {
  const nav = useRef<HTMLElement>(null);
  const [active, setActive] = useState<(typeof sections)[number]['id']>('overview');

  useEffect(() => {
    const update = () => {
      const threshold = Math.max(148, (nav.current?.getBoundingClientRect().bottom ?? 0) + 8);
      const current = sections.findLast(({ id }) => {
        const section = document.getElementById(id);
        return section && section.getBoundingClientRect().top <= threshold;
      });
      setActive(current?.id ?? 'overview');
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  return (
    <nav ref={nav} aria-label="Các phần của báo cáo" className="sticky top-16 z-20 border-b border-slate-200 bg-[#f9f8f6]/95 backdrop-blur print:hidden">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-3 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-1 overflow-x-auto px-0.5 py-0.5">
          {sections.map(({ id, label, Icon }) => (
            <a key={id} href={`#${id}`} aria-current={active === id ? 'location' : undefined} onClick={() => setActive(id)}
              className={cn(control, active === id ? 'bg-[#e4edf8] text-slate-900' : 'text-[#63504a] hover:bg-[#eee9e5]')}>
              <Icon size={14} aria-hidden="true" className={active === id ? 'text-[#b02700]' : undefined} />
              {label}
            </a>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <button type="button" onClick={() => window.print()} title="In kết quả"
            className={cn(control, 'cursor-pointer bg-[#e4edf8] text-slate-800 hover:bg-[#d7e4f4]')}>
            <Printer size={14} aria-hidden="true" /> <span className="sr-only sm:not-sr-only">In kết quả</span>
          </button>
          <Link href={studyHref} title="Lập kế hoạch" className={cn(control, 'bg-[#b02700] text-white hover:bg-[#8c2100]')}>
            <NotebookPen size={14} aria-hidden="true" /> <span className="sr-only sm:not-sr-only">Lập kế hoạch</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
