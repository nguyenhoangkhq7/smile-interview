'use client';

import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useRef, useSyncExternalStore } from 'react';
import type { MouseEvent, PointerEvent } from 'react';
import { usePixelOffice } from '@/hooks/usePixelOffice';
import type { ColorTheme } from './animate-pixel-office';
import styles from './theme-picker.module.css';

type Drag = { pointerId: number; startX: number; start: number; travel: number; moved: boolean };

const dragThreshold = 6;

const subscribe = () => () => undefined;
const clientSnapshot = () => true;
const serverSnapshot = () => false;

export default function ThemePicker() {
  const hydrated = useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
  const { resolvedTheme, setTheme } = useTheme();
  const value: ColorTheme = hydrated && resolvedTheme === 'dark' ? 'dark' : 'light';
  const { art, renderer } = usePixelOffice(value);
  const drag = useRef<Drag | null>(null);
  const ignorePointerClick = useRef(false);
  const isDark = value === 'dark';

  function startDrag(event: PointerEvent<HTMLButtonElement>) {
    if (!event.isPrimary || event.button !== 0) return;
    ignorePointerClick.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointerId: event.pointerId, startX: event.clientX, start: Number(isDark),
      travel: event.currentTarget.clientWidth * 0.48, moved: false };
  }

  function moveDrag(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const distance = event.clientX - current.startX;
    if (!current.moved && Math.abs(distance) < dragThreshold) return;
    current.moved = true;
    renderer.current?.scrub(current.start + distance / current.travel);
  }

  function endDrag(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    drag.current = null;
    if (!current.moved) return;
    ignorePointerClick.current = true;
    const next = current.start + (event.clientX - current.startX) / current.travel >= 0.5 ? 'dark' : 'light';
    if (next === value) renderer.current?.setTheme(value);
    else setTheme(next);
  }

  function cancelDrag(event: PointerEvent<HTMLButtonElement>) {
    if (drag.current?.pointerId !== event.pointerId) return;
    drag.current = null;
    renderer.current?.setTheme(value);
  }

  function click(event: MouseEvent<HTMLButtonElement>) {
    if (event.detail > 0 && ignorePointerClick.current) return;
    setTheme(isDark ? 'light' : 'dark');
  }

  return (
    <button type="button" role="switch" aria-label="Chế độ tối" aria-checked={isDark} title={isDark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
      className={styles.switch} onClick={click} onPointerDown={startDrag} onPointerMove={moveDrag}
      onPointerUp={endDrag} onPointerCancel={cancelDrag} onLostPointerCapture={cancelDrag}>
      <span aria-hidden="true" className={styles.fallback}>
        <span className={styles.lens}>
          <Sun size={12} className={styles.dayIcon} />
          <Moon size={12} className={styles.nightIcon} />
        </span>
      </span>
      <span ref={art} aria-hidden="true" className={styles.scene} />
    </button>
  );
}

export function SystemThemeButton({ className }: { className?: string }) {
  const hydrated = useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
  const { theme, setTheme } = useTheme();

  return (
    <button type="button" className={className} aria-label="Giao diện theo hệ thống"
      aria-pressed={hydrated && theme === 'system'} onClick={() => setTheme('system')}>
      <Monitor size={14} aria-hidden="true" /> Theo hệ thống
    </button>
  );
}
