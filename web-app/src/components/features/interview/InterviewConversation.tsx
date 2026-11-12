'use client';

import { MarkdownContent } from '@/components/common/MarkdownContent';
import type { InterviewController } from './EvidenceTextInterview';

export function IntroductionHistory({ interview }: { interview: InterviewController }) {
  const conversation = interview.session?.conversation;
  if (!conversation) return null;
  return <details className="rounded-xl border p-4"><summary className="text-sm font-semibold">Mở đầu và giới thiệu bản thân</summary>
    <div className="mt-3 space-y-3 text-sm"><MarkdownContent content={conversation.opening_text} />
      <p className="whitespace-pre-wrap">{conversation.introduction || 'Đã bỏ qua phần giới thiệu.'}</p>
    </div>
  </details>;
}
