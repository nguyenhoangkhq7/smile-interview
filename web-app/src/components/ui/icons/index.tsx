/**
 * Central SVG icon registry — all inline icons used across the app.
 * Named exports so tree-shaking works perfectly.
 */

import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

const base = (size: number): SVGProps<SVGSVGElement> => ({
  width: size,
  height: size,
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  viewBox: '0 0 24 24',
});

export function IconUpload({ size = 20, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </svg>
  );
}

export function IconBriefcase({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    </svg>
  );
}

export function IconMic({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

export function IconBarChart({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

export function IconCheck({ size = 16, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function IconArrow({ size = 16, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function IconFile({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

export function IconUsers({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

export function IconTrend({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  );
}

export function IconStar({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export function IconClock({ size = 22, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function IconSearch({ size = 16, ...p }: IconProps) {
  return (
    <svg {...base(size)} {...p}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function IconChevronDown({ size = 11, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

export function IconRefresh({ size = 14, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 21h5v-5" />
    </svg>
  );
}

export function IconChevronLeft({ size = 16, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

export function IconX({ size = 14, ...p }: IconProps) {
  return (
    <svg {...base(size)} strokeWidth={2.5} {...p}>
      <path d="m15 9-6 6M9 9l6 6" />
    </svg>
  );
}
