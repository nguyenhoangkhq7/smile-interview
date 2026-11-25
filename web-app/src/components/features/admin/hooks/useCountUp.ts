'use client';

import { useEffect, useRef, useState } from 'react';

interface UseCountUpOptions {
  durationMs?: number;
  decimals?: number;
}

/**
 * Smooth data-driven count-up animation hook using easeOutCubic.
 * Re-animates smoothly whenever `targetValue` changes.
 */
export function useCountUp(
  targetValue: number,
  options: UseCountUpOptions = {}
): string {
  const { durationMs = 750, decimals = 0 } = options;
  const [displayValue, setDisplayValue] = useState<number>(targetValue);
  const previousValueRef = useRef<number>(0);

  useEffect(() => {
    const startValue = previousValueRef.current;
    const delta = targetValue - startValue;

    if (Math.abs(delta) < 0.001) {
      previousValueRef.current = targetValue;
      return;
    }

    let animationFrameId: number;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValue + delta * eased;

      setDisplayValue(current);

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        setDisplayValue(targetValue);
        previousValueRef.current = targetValue;
      }
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [targetValue, durationMs]);

  return displayValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
