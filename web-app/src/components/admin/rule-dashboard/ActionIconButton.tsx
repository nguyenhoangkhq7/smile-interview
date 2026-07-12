'use client';

import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ActionVariant = 'neutral' | 'danger' | 'accent';

interface ActionIconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon: ReactNode;
  variant?: ActionVariant;
}

const variantStyles: Record<ActionVariant, string> = {
  neutral: 'border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white hover:bg-white/[0.08]',
  danger: 'border-slate-700 text-slate-300 hover:border-rose-500/50 hover:text-rose-200 hover:bg-rose-500/15',
  accent: 'border-amber-400/40 text-amber-300 hover:border-amber-400/60 hover:text-amber-200 hover:bg-amber-400/15',
};

export default function ActionIconButton({ label, icon, variant = 'neutral', className = '', ...props }: ActionIconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border bg-slate-900/60 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500/40 ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {icon}
    </button>
  );
}
