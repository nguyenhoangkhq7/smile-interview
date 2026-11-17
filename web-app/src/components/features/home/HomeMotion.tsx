'use client';

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`home-reveal ${visible ? 'home-reveal-visible' : ''} ${className ?? ''}`}
      style={{ '--reveal-delay': `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}

export function CountUp({ value, suffix = '' }: { value: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [count, setCount] = useState(0);
  const precision = Number.isInteger(value) ? 0 : 1;

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      const startedAt = performance.now();
      const duration = 1400;
      const precisionFactor = 10 ** precision;
      let frame = 0;
      const update = (now: number) => {
        const progress = Math.min((now - startedAt) / duration, 1);
        const eased = 1 - (1 - progress) ** 4;
        setCount(Math.round(value * precisionFactor * eased) / precisionFactor);
        if (progress < 1) frame = requestAnimationFrame(update);
      };
      frame = requestAnimationFrame(update);
      observer.disconnect();
      return () => cancelAnimationFrame(frame);
    }, { threshold: 0.5 });
    observer.observe(element);
    return () => observer.disconnect();
  }, [value, precision]);

  return <span ref={ref}>{count.toLocaleString('vi-VN', { minimumFractionDigits: precision, maximumFractionDigits: precision })}{suffix}</span>;
}

export function Parallax({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const bounds = element.getBoundingClientRect();
        const centerOffset = bounds.top + bounds.height / 2 - window.innerHeight / 2;
        element.style.setProperty('--parallax-y', `${Math.max(-14, Math.min(14, centerOffset * -0.025))}px`);
      });
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  return <div ref={ref} className="home-parallax">{children}</div>;
}
