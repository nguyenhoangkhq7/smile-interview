'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

const FENCE_SPLIT = /(```[\s\S]*?```|~~~[\s\S]*?~~~)/g;
const PROSE_TOKEN = /(`[^`\n]+`\s*|\S+\s*)/g;
const MAX_REVEAL_MS = 750;
const MIN_TICK_MS = 16;
const MAX_TICK_MS = 34;

function tokenizeForReveal(text: string): string[] {
  if (!text) return [];
  const tokens: string[] = [];
  for (const part of text.split(FENCE_SPLIT)) {
    if (!part) continue;
    if (part.startsWith('```') || part.startsWith('~~~')) {
      tokens.push(part);
      continue;
    }
    const matches = part.match(PROSE_TOKEN);
    if (matches) tokens.push(...matches);
    else tokens.push(part);
  }
  return tokens;
}

/**
 * Progressively reveals AI text on word/code-block boundaries within a capped
 * time budget so reading stays natural without eating into interview time.
 */
export function useProgressiveText(text: string, enabled: boolean) {
  const tokens = useMemo(() => tokenizeForReveal(text), [text]);
  const [state, setState] = useState<{ text: string; count: number }>({ text: '', count: 0 });

  const total = tokens.length;
  const shouldAnimate = enabled && total > 1;
  const visibleCount = !shouldAnimate
    ? total
    : state.text === text
      ? Math.min(total, state.count)
      : 1;
  const isRevealing = shouldAnimate && visibleCount < total;

  const complete = useCallback(() => {
    setState({ text, count: total });
  }, [text, total]);

  useEffect(() => {
    if (!shouldAnimate) return;
    if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      const immediate = setTimeout(() => setState({ text, count: total }), 0);
      return () => clearTimeout(immediate);
    }
    const tickMs = Math.max(MIN_TICK_MS, Math.min(MAX_TICK_MS, Math.floor(MAX_REVEAL_MS / total)));
    const timer = setInterval(() => {
      setState(prev => {
        const current = prev.text === text ? prev.count : 1;
        const next = Math.min(total, current + 1);
        if (next >= total) clearInterval(timer);
        return { text, count: next };
      });
    }, tickMs);
    return () => clearInterval(timer);
  }, [shouldAnimate, text, total]);

  const displayedText = !shouldAnimate
    ? text
    : visibleCount >= total
      ? text
      : tokens.slice(0, visibleCount).join('');

  return { displayedText, isRevealing, complete };
}
