import { useEffect, useRef } from 'react';
import type { ColorTheme, mountPixelOffice } from '@/components/layout/ThemePicker/animate-pixel-office';

type PixelOffice = ReturnType<typeof mountPixelOffice>;

export function usePixelOffice(theme: ColorTheme) {
  const art = useRef<HTMLSpanElement>(null);
  const renderer = useRef<PixelOffice | null>(null);
  const latestTheme = useRef(theme);

  useEffect(() => {
    latestTheme.current = theme;
    renderer.current?.setTheme(theme);
  }, [theme]);

  useEffect(() => {
    const container = art.current;
    if (!container) return;
    let active = true;
    void import('@/components/layout/ThemePicker/animate-pixel-office').then(({ mountPixelOffice }) => {
      if (active) renderer.current = mountPixelOffice(container, latestTheme.current);
    }).catch(() => {
      // Keep the CSS switch visible if the renderer cannot be loaded.
      if (active) container.replaceChildren();
    });

    return () => {
      active = false;
      renderer.current?.dispose();
      renderer.current = null;
    };
  }, []);

  return { art, renderer };
}
