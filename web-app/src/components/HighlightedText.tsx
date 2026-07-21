'use client';

/**
 * HighlightedText.tsx
 *
 * Jobscan-style inline text highlighter with non-clipping hover tooltips.
 * Uses colored underline + bold styling (not background fill) to match
 * the visual style of Jobscan's "Highlighted Skills" view.
 *
 * - Green underline + bold: Matching Skill
 * - Amber underline + bold: Skill Variation (formerly Weak)
 * - Red underline + bold: Missing Skill
 *
 * Tooltip Popover is shown automatically on hover.
 * The tooltip is rendered at the container level (absolute positioning with boundary protection)
 * so it scrolls naturally and NEVER gets clipped by column borders or overflow containers.
 */

import React, { useMemo, useState, useRef } from 'react';
import { Info, AlertCircle, XCircle } from 'lucide-react';

export interface HighlightedTextProps {
  text: string;
  matches: string[];
  variations?: string[]; // Skill Variation (formerly weak)
  missing: string[];
  keywordDetails?: Record<string, { criteriaName: string; reasoning: string }>;
}

const STOP_WORDS = new Set([
  'at', 'in', 'on', 'the', 'and', 'of', 'to', 'a', 'an', 'by', 'for', 'with', 'about', 'from',
  'tại', 'ở', 'và', 'cho', 'của', 'để', 'với', 'về', 'từ', 'bởi'
]);

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function buildPattern(keywords: string[]): RegExp | null {
  const nonEmpty = [...new Set(
    keywords
      .filter((k) => k && k.trim().length > 0)
      .filter((k) => !STOP_WORDS.has(k.trim().toLowerCase()))
  )];
  if (nonEmpty.length === 0) return null;

  const alts = nonEmpty
    .map(escapeRegex)
    .sort((a, b) => b.length - a.length);

  return new RegExp(`\\b(${alts.join('|')})\\b`, 'gi');
}

interface TooltipState {
  type: 'variation' | 'missing';
  value: string;
  top: number;
  left: number;
  reasoning?: string;
}

export default function HighlightedText({ text, matches, variations = [], missing, keywordDetails = {} }: HighlightedTextProps) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const segments = useMemo(() => {
    if (!text) return [];

    const matchSet = new Set(matches.map((k) => k.toLowerCase()));
    const variationSet = new Set(variations.map((k) => k.toLowerCase()));
    const missingSet = new Set(missing.map((k) => k.toLowerCase()));

    const allKeywords = [...matches, ...variations, ...missing];
    const pattern = buildPattern(allKeywords);
    if (!pattern) return [{ type: 'plain' as const, value: text }];

    return text.split(pattern).map((part, idx) => {
      const lower = part.toLowerCase();
      if (matchSet.has(lower)) return { type: 'match' as const, value: part, key: idx };
      if (variationSet.has(lower)) return { type: 'variation' as const, value: part, key: idx };
      if (missingSet.has(lower)) return { type: 'missing' as const, value: part, key: idx };
      return { type: 'plain' as const, value: part, key: idx };
    });
  }, [text, matches, variations, missing]);

  const handleMouseEnter = (
    e: React.MouseEvent<HTMLSpanElement>,
    type: 'variation' | 'missing',
    value: string
  ) => {
    if (!containerRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const parentRect = containerRef.current.getBoundingClientRect();
    const parentWidth = parentRect.width;

    // Calculate position relative to container's canvas
    const scrollTop = containerRef.current.scrollTop || 0;
    const scrollLeft = containerRef.current.scrollLeft || 0;

    const targetTop = rect.top - parentRect.top + scrollTop;
    let targetLeft = rect.left - parentRect.left + scrollLeft + rect.width / 2;

    // Boundary protection: prevent popover (280px wide) from clipping left/right
    const minLeft = 150; // padding to keep center offset safe
    const maxLeft = parentWidth - 150;
    targetLeft = Math.max(minLeft, Math.min(maxLeft, targetLeft));

    const details = keywordDetails[value.toLowerCase()];

    setTooltip({
      type,
      value,
      top: targetTop,
      left: targetLeft,
      reasoning: details?.reasoning,
    });
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  if (!text) {
    return (
      <p style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.85rem', margin: 0 }}>
        Không có nội dung để hiển thị.
      </p>
    );
  }

  const isMissing = tooltip?.type === 'missing';

  return (
    <span
      ref={containerRef}
      style={{ position: 'relative', display: 'block', height: '100%', width: '100%' }}
    >
      <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: '0.875rem', color: '#1e293b' }}>
        {segments.map((seg, idx) => {
          if (seg.type === 'match') {
            return (
              <span
                key={idx}
                title="Kỹ năng phù hợp"
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
          if (seg.type === 'variation') {
            return (
              <span
                key={idx}
                onMouseEnter={(e) => handleMouseEnter(e, 'variation', seg.value)}
                onMouseLeave={handleMouseLeave}
                style={{
                  color: '#d97706',
                  fontWeight: 700,
                  textDecoration: 'underline',
                  textDecorationColor: '#f59e0b',
                  textUnderlineOffset: '3px',
                  cursor: 'help',
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
                onMouseEnter={(e) => handleMouseEnter(e, 'missing', seg.value)}
                onMouseLeave={handleMouseLeave}
                style={{
                  color: '#dc2626',
                  fontWeight: 700,
                  textDecoration: 'underline',
                  textDecorationColor: '#ef4444',
                  textUnderlineOffset: '3px',
                  cursor: 'help',
                }}
              >
                {seg.value}
              </span>
            );
          }
          return <span key={idx}>{seg.value}</span>;
        })}
      </span>

      {/* Shared Absolute Tooltip with Boundary Protection */}
      {tooltip && (
        <span
          style={{
            position: 'absolute',
            top: `${tooltip.top}px`,
            left: `${tooltip.left}px`,
            transform: 'translate(-50%, -100%) translateY(-8px)',
            width: '280px',
            backgroundColor: isMissing ? '#fef2f2' : '#fffbeb',
            border: `1px solid ${isMissing ? '#fca5a5' : '#fcd34d'}`,
            borderRadius: '12px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05)',
            padding: '0.85rem',
            zIndex: 200,
            color: '#1e293b',
            fontSize: '0.8rem',
            fontWeight: 'normal',
            lineHeight: '1.4',
            textAlign: 'left',
            cursor: 'default',
            whiteSpace: 'normal',
            display: 'block',
            pointerEvents: 'none', // Allow cursor to pass through cleanly
          }}
        >
          {/* Header */}
          <span style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontWeight: 800,
              color: isMissing ? '#991b1b' : '#92400e',
              fontSize: '0.82rem'
            }}>
              {isMissing ? <XCircle size={14} /> : <AlertCircle size={14} />}
              {isMissing ? 'Kỹ năng còn thiếu' : 'Biến thể kỹ năng'}
            </span>
          </span>

          {/* Pill Tag */}
          <span style={{ display: 'block', marginBottom: '0.5rem' }}>
            <span style={{
              display: 'inline-block',
              backgroundColor: isMissing ? '#dc2626' : '#d97706',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '0.68rem',
              padding: '0.15rem 0.45rem',
              borderRadius: '4px',
            }}>
              {tooltip.value}
            </span>
          </span>

          {/* Reasoning Content */}
          <span style={{ display: 'block', margin: '0 0 0.5rem 0', color: '#334155', fontSize: '0.78rem' }}>
            {tooltip.reasoning ? tooltip.reasoning : (
              isMissing
                ? `Kỹ năng "${tooltip.value}" không được tìm thấy trong bản CV của bạn.`
                : `Kỹ năng "${tooltip.value}" khớp một phần hoặc ở dạng từ khóa biến thể trong CV.`
            )}
          </span>

          {/* Recommendation */}
          <span style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.35rem',
            borderTop: `1px solid ${isMissing ? '#fee2e2' : '#fef3c7'}`,
            paddingTop: '0.5rem',
            marginTop: '0.5rem',
            color: '#475569',
            fontSize: '0.72rem'
          }}>
            <Info size={12} style={{ marginTop: '2px', flexShrink: 0 }} />
            <span>
              {isMissing
                ? 'Khuyến nghị: Bạn nên bổ sung kỹ năng này vào CV để tăng độ tương thích với mô tả công việc.'
                : 'Khuyến nghị: Bạn nên làm rõ thế mạnh của mình bằng việc bổ sung biến thể từ khóa này vào CV.'}
            </span>
          </span>

          {/* Arrow */}
          <span
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              borderTop: `6px solid ${isMissing ? '#fca5a5' : '#fcd34d'}`,
            }}
          />
        </span>
      )}
    </span>
  );
}
