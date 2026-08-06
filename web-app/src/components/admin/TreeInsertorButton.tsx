'use client';

import React from 'react';
import { Plus } from 'lucide-react';

interface TreeInsertorButtonProps {
  onClick: (e: React.MouseEvent) => void;
  title?: string;
}

export function TreeInsertorButton({ onClick, title = "Thêm danh mục cùng cấp" }: TreeInsertorButtonProps) {
  return (
    <div 
      className="
        absolute left-1/2 -bottom-5 -translate-x-1/2 w-[84px] h-[26px] z-50
        flex items-center justify-center cursor-pointer group/tab
        /* 1. Slide from top down + scale reveal animation */
        opacity-0 -translate-y-2 scale-90 pointer-events-none
        group-hover/node:opacity-100 group-hover/node:translate-y-0 group-hover/node:scale-100 group-hover/node:pointer-events-auto
        transition-all duration-300 ease-out
      "
      onClick={(e) => {
        e.stopPropagation();
        onClick(e);
      }}
      title={title}
    >
      {/* Ambient orange glow backdrop on tab hover */}
      <div className="absolute inset-0 rounded-b-full bg-orange-500/25 blur-md opacity-0 group-hover/tab:opacity-100 transition-opacity duration-300" />

      {/* Seamless Bézier Curve Tab SVG */}
      <svg 
        viewBox="0 0 84 26" 
        className="absolute inset-0 w-full h-full text-slate-900 drop-shadow-[0_4px_10px_rgba(0,0,0,0.6)]" 
      >
        <defs>
          {/* Glowing gradient for light effect along the curve */}
          <linearGradient id="tabGlowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#f97316" stopOpacity="0.2" />
            <stop offset="50%" stopColor="#fb923c" stopOpacity="1" />
            <stop offset="100%" stopColor="#f97316" stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* Tab Background Fill (matches row bg) */}
        <path 
          d="M0,0 C16,0 21,26 42,26 C63,26 68,0 84,0 Z" 
          fill="currentColor" 
        />

        {/* Glowing stroke outline along the Bézier curve */}
        <path 
          d="M0,0 C16,0 21,26 42,26 C63,26 68,0 84,0" 
          fill="none" 
          stroke="url(#tabGlowGradient)" 
          strokeWidth="1.5" 
          className="opacity-30 group-hover/node:opacity-70 group-hover/tab:opacity-100 transition-opacity duration-300"
        />
      </svg>

      {/* Plus Icon with rotation 90deg + scale + glow micro-interaction */}
      <div className="relative z-10 flex items-center justify-center text-slate-400 group-hover/tab:text-orange-400 transition-all duration-300 group-hover/tab:rotate-90 group-hover/tab:scale-125">
        <Plus className="w-4 h-4" strokeWidth={3} />
      </div>

      {/* Tooltip badge on hover */}
      <span className="absolute -bottom-7 px-2 py-0.5 rounded-md bg-slate-950/95 border border-orange-500/40 text-[10px] font-semibold text-orange-300 whitespace-nowrap opacity-0 group-hover/tab:opacity-100 translate-y-1 group-hover/tab:translate-y-0 transition-all duration-200 pointer-events-none shadow-2xl">
        + Danh mục cùng cấp
      </span>
    </div>
  );
}

export default TreeInsertorButton;
