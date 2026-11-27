'use client';

import { ChevronDown, ScanSearch } from 'lucide-react';
import type { useAiQualityReview } from '@/hooks/useAiQualityReview';
import type { AiQualityFinding, AiQualitySection } from './types';

function FindingRow({ finding }: { finding: AiQualityFinding }) {
  const needsReview = finding.status === 'REVIEW';
  const location = [finding.turn == null ? null : 'Lượt ' + finding.turn, finding.skill].filter(Boolean).join(' · ');
  return <li className="space-y-2 rounded-lg border border-[#edf0ff] p-3 dark:border-border">
    <div className="flex flex-wrap items-center gap-2">
      <span className={needsReview
        ? 'rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-200'
        : 'rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground'}>
        {needsReview ? 'Cần xem lại' : 'Thiếu dữ liệu'}
      </span>
      {location && <span className="break-words text-xs font-semibold">{location}</span>}
    </div>
    <p className="text-sm">{finding.detail}</p>
    {finding.excerpt && <blockquote className="whitespace-pre-wrap [overflow-wrap:anywhere] border-l-2 border-border pl-3 text-sm text-muted-foreground">
      {finding.excerpt}
    </blockquote>}
  </li>;
}

function ReviewSection({ title, unit, section }: { title: string; unit: string; section: AiQualitySection }) {
  return <section className="min-w-0 space-y-3 rounded-xl bg-white p-4 shadow-xs dark:bg-card">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="font-semibold">{title}</h3>
      <p className="text-xs text-muted-foreground">{section.total} {unit} đã rà soát</p>
    </div>
    {section.findings.length > 0 ? <ul className="space-y-2">
      {section.findings.map((finding, index) => <FindingRow key={index} finding={finding} />)}
    </ul> : <p className="text-sm text-muted-foreground">
      {section.total > 0 ? 'Chưa phát hiện vấn đề qua các quy tắc hiện có.' : 'Phiên chưa có dữ liệu cho phần này.'}
    </p>}
  </section>;
}

export default function InterviewAiQuality({ review, running, failed, run }: ReturnType<typeof useAiQualityReview>) {
  return <section aria-busy={running} className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl bg-white p-5 shadow-xs dark:bg-card">
      <div className="max-w-xl space-y-1">
        <h2 className="text-lg font-semibold">Chất lượng AI</h2>
        <p className="text-sm text-muted-foreground">
          Kiểm tra theo quy tắc trên dữ liệu đã lưu của phiên.
        </p>
      </div>
      <button type="button" onClick={() => void run()} disabled={running}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-3.5 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
        <ScanSearch aria-hidden="true" className="size-4" />
        {running ? 'Đang kiểm tra…' : review ? 'Kiểm tra lại' : 'Chạy kiểm tra'}
      </button>
    </div>
    <QualityMethod />
    {failed && <p role="alert" className="text-sm text-red-700 dark:text-red-300">
      {review ? 'Lần kiểm tra mới thất bại. Đang hiển thị kết quả trước đó.' : 'Không thể chạy kiểm tra chất lượng AI. Vui lòng thử lại.'}
    </p>}
    {review && <div aria-live="polite" className="grid items-start gap-3 lg:grid-cols-2">
      <ReviewSection title="Đối sánh CV–JD" unit="kỹ năng" section={review.matching} />
      <ReviewSection title="Câu hỏi phỏng vấn" unit="câu hỏi" section={review.questions} />
    </div>}
  </section>;
}

function QualityMethod() {
  return <details className="group rounded-xl bg-white px-4 py-3 text-sm shadow-xs dark:bg-card">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-semibold [&::-webkit-details-marker]:hidden">
      Phương pháp kiểm tra
      <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground group-open:rotate-180" />
    </summary>
    <dl className="mt-3 grid gap-3 text-muted-foreground md:grid-cols-2">
      <div><dt className="font-medium text-foreground">Đối sánh CV–JD</dt>
        <dd>So từng trích dẫn đã lưu với văn bản CV/JD sau khi chuẩn hóa Unicode và khoảng trắng. Báo thiếu nguồn, thiếu trích dẫn, trích dẫn lệch nguồn hoặc phân tích có cờ suy giảm.</dd>
      </div>
      <div><dt className="font-medium text-foreground">Câu hỏi phỏng vấn</dt>
        <dd>Dùng quy tắc phát hiện câu lặp, nhiều yêu cầu độc lập, đoạn mã bị thiếu, yêu cầu dùng ChatGPT và câu thoại quá dài. Trích dẫn trực tiếp được đối chiếu với CV/JD.</dd>
      </div>
    </dl>
    <p className="mt-3 border-t pt-3 text-muted-foreground">Kiểm tra chạy trong FastAPI. Đánh giá độ đúng kỹ thuật và các suy diễn cần hiểu ngữ nghĩa nằm ngoài phạm vi của bộ quy tắc này.</p>
  </details>;
}
