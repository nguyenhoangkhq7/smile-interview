'use client';

/**
 * HighlightedText.tsx
 *
 * Jobscan-style inline text highlighter.
 * Uses colored underline + bold styling (not background fill) to match
 * the visual style of Jobscan's "Highlighted Skills" view.
 *
 * - Green underline + bold: skill present in both JD and CV (match)
 * - Red underline + bold: skill in JD but absent in CV (missing)
 * - Safe: handles null/empty inputs, escapes regex special characters.
 */

import React, { useMemo } from 'react';

export interface HighlightedTextProps {
  text: string;
  matches: string[];
  missing: string[];
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function buildPattern(keywords: string[]): RegExp | null {
  const nonEmpty = keywords.filter((k) => k && k.trim().length > 0);
  if (nonEmpty.length === 0) return null;
  // Sort longest-first so "Full Stack" matches before "Stack"
  const alts = nonEmpty.map(escapeRegex).sort((a, b) => b.length - a.length);
  return new RegExp(`(${alts.join('|')})`, 'gi');
}

export default function HighlightedText({ text, matches, missing }: HighlightedTextProps) {
  const segments = useMemo(() => {
    if (!text) return [];
    const matchSet = new Set(matches.map((k) => k.toLowerCase()));
    const missingSet = new Set(missing.map((k) => k.toLowerCase()));
    const allKeywords = [...matches, ...missing];
    const pattern = buildPattern(allKeywords);
    if (!pattern) return [{ type: 'plain' as const, value: text }];

    return text.split(pattern).map((part, idx) => {
      const lower = part.toLowerCase();
      if (matchSet.has(lower)) return { type: 'match' as const, value: part, key: idx };
      if (missingSet.has(lower)) return { type: 'missing' as const, value: part, key: idx };
      return { type: 'plain' as const, value: part, key: idx };
    });
  }, [text, matches, missing]);

  if (!text) {
    return (
      <p style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.85rem', margin: 0 }}>
        Không có nội dung để hiển thị.
      </p>
    );
  }

  return (
    <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: '0.875rem', color: '#1e293b' }}>
      {segments.map((seg, idx) => {
        if (seg.type === 'match') {
          return (
            <span
              key={idx}
              title="✅ Kỹ năng phù hợp"
              style={{
                color: '#15803d',
                fontWeight: 700,
                textDecoration: 'underline',
                textDecorationColor: '#16a34a',
                textUnderlineOffset: '3px',
                cursor: 'default',
              }}
            >
              {seg.value}
            </span>
          );
        }
        if (seg.type === 'missing') {
          return (
            <span
              key={idx}
              title="❌ Kỹ năng còn thiếu trong CV"
              style={{
                color: '#dc2626',
                fontWeight: 700,
                textDecoration: 'underline',
                textDecorationColor: '#ef4444',
                textUnderlineOffset: '3px',
                cursor: 'default',
              }}
            >
              {seg.value}
            </span>
          );
        }
        return <span key={idx}>{seg.value}</span>;
      })}
    </span>
  );
}
