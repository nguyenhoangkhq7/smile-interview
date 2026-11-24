'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ChartNoAxesCombined, ClipboardList, Crosshair, ListChecks, NotebookPen, Printer } from 'lucide-react';
import { cn } from '@/lib/utils';

const sections = [
  { id: 'overview', label: 'Tổng quan', Icon: ChartNoAxesCombined },
  { id: 'skills', label: 'Kỹ năng', Icon: Crosshair },
  { id: 'questions', label: 'Câu hỏi', Icon: ClipboardList },
  { id: 'study', label: 'Ôn tập', Icon: ListChecks },
] as const;

const control = 'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1.5 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 xl:px-3';

export function ResultNavigation({ studyHref, hasNavbar = false }: { studyHref: string; hasNavbar?: boolean }) {
  const nav = useRef<HTMLElement>(null);
  const [active, setActive] = useState<(typeof sections)[number]['id']>('overview');
  const [stickyTop, setStickyTop] = useState(hasNavbar ? 69 : 0);

  useEffect(() => {
    const navbar = document.querySelector<HTMLElement>('[data-site-navbar]');

    const syncStickyOffsets = () => {
      const top = navbar ? Math.ceil(navbar.getBoundingClientRect().height) : 0;
      setStickyTop(top);
      const navHeight = nav.current ? Math.ceil(nav.current.getBoundingClientRect().height) : 45;
      nav.current?.parentElement?.style.setProperty('--result-scroll-mt', `${top + navHeight + 16}px`);
    };

    const update = () => {
      const threshold = Math.max(48, (nav.current?.getBoundingClientRect().bottom ?? 0) + 12);
      const current = sections.findLast(({ id }) => {
        const section = document.getElementById(id);
        return section && section.getBoundingClientRect().top <= threshold;
      });
      setActive(current?.id ?? 'overview');
    };

    const onLayoutChange = () => {
      syncStickyOffsets();
      update();
    };

    onLayoutChange();

    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(onLayoutChange)
      : null;
    if (navbar) observer?.observe(navbar);
    if (nav.current) observer?.observe(nav.current);

    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', onLayoutChange);
    return () => {
      observer?.disconnect();
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', onLayoutChange);
    };
  }, []);

  return (
    <nav
      ref={nav}
      aria-label="Các phần của báo cáo"
      style={{ top: stickyTop }}
      className="sticky z-20 border-b border-slate-200 bg-[#f9f8f6]/95 backdrop-blur print:hidden"
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-3 py-2 sm:px-6">
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
            <Printer size={14} aria-hidden="true" /> <span className="sr-only sm:not-sr-only">In</span>
          </button>
          <Link href={studyHref} title="Lập kế hoạch" className={cn(control, 'bg-[#b02700] text-white hover:bg-[#8c2100]')}>
            <NotebookPen size={14} aria-hidden="true" /> <span className="sr-only sm:not-sr-only">Kế hoạch ôn tập</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
