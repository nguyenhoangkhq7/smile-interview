'use client';

import { useId, useState } from 'react';
import { Check, ChevronDown, CircleHelp, ClipboardList, Info, X } from 'lucide-react';
import type { EligibilityReport } from '@/services/eligibility';

const priorities = { required: 'Bắt buộc', preferred: 'Ưu tiên', unspecified: 'JD chưa nêu mức độ' };
const decisions = {
  met: { label: 'Đạt', icon: Check, tone: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200' },
  not_met: { label: 'Không đạt', icon: X, tone: 'bg-rose-50 text-rose-800 dark:bg-rose-950 dark:text-rose-200' },
  insufficient_evidence: { label: 'Chưa đủ thông tin', icon: CircleHelp, tone: 'bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200' },
};
const previewSize = 4;

export function EligibilityPanel({ report }: { report: EligibilityReport }) {
  const [showAll, setShowAll] = useState(false);
  const group = useId();
  const rows = showAll ? report.results : report.results.slice(0, previewSize);
  const remaining = report.results.length - previewSize;
  return <section aria-label="Điều kiện ứng tuyển" className="overflow-hidden rounded-xl border bg-card">
    <header className="flex items-center gap-2.5 border-b bg-muted/25 px-4 py-3">
      <ClipboardList aria-hidden="true" size={17} className="text-brand-orange" />
      <h3 className="text-sm font-semibold">Điều kiện ứng tuyển</h3>
      {report.results.length > 0 && <span className="rounded-full bg-muted px-2 text-xs tabular-nums text-muted-foreground">{report.results.length}</span>}
    </header>
    {report.state === 'unavailable' && <p className="p-4 text-sm text-muted-foreground">Chưa thể kiểm tra điều kiện ứng tuyển cho lần phân tích này.</p>}
    {report.state === 'partial' && <p className="flex items-start gap-2 bg-amber-50/70 px-4 py-2 text-xs leading-5 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
      <Info aria-hidden="true" size={14} className="mt-0.5 shrink-0" />Một phần điều kiện hoặc bằng chứng chưa được xác minh.
    </p>}
    {report.state === 'complete' && !rows.length && <p className="p-4 text-sm text-muted-foreground">Chưa tìm thấy điều kiện ứng tuyển riêng trong JD.</p>}
    <ul id={group} className="divide-y">
      {rows.map(row => {
        const { label, icon: Icon, tone } = decisions[row.status];
        return <li key={row.condition_id}>
          <details name={group} className="group/condition">
            <summary className="grid min-h-12 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-4 py-2.5 hover:bg-muted/30 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange sm:grid-cols-[minmax(0,1fr)_auto_auto] [&::-webkit-details-marker]:hidden">
              <span className="min-w-0 text-sm leading-5 font-medium wrap-anywhere">
                <span className="mr-2 inline-block rounded bg-muted/65 px-1.5 align-middle text-[11px] font-medium text-muted-foreground">{priorities[row.priority]}</span>
                {row.jd_quote}
              </span>
              <span className={`col-start-1 row-start-2 inline-flex items-center gap-1 justify-self-start rounded-md px-2 py-0.5 text-xs font-medium sm:col-start-2 sm:row-start-1 ${tone}`}>
                <Icon aria-hidden="true" size={13} />{label}
              </span>
              <ChevronDown aria-hidden="true" size={15} className="col-start-2 row-span-2 row-start-1 text-muted-foreground transition-transform group-open/condition:rotate-180 sm:col-start-3 sm:row-span-1" />
            </summary>
            <div className="mx-3 mb-3 space-y-2 rounded-lg bg-muted/40 px-3 py-2.5 text-sm leading-6">
              <p className="wrap-anywhere">{row.reason}</p>
              {row.cv_quotes.length > 0 && <div>
                <p className="mb-1 text-xs font-semibold text-muted-foreground">Bằng chứng từ CV</p>
                <ul className="space-y-1 border-l-2 border-brand-orange/30 pl-3">
                  {row.cv_quotes.map(quote => <li key={quote}><blockquote className="whitespace-pre-wrap wrap-anywhere">{quote}</blockquote></li>)}
                </ul>
              </div>}
            </div>
          </details>
        </li>;
      })}
    </ul>
    {remaining > 0 && <button type="button" aria-controls={group} aria-expanded={showAll} onClick={() => setShowAll(value => !value)}
      className="flex min-h-10 w-full items-center justify-center gap-1.5 border-t bg-muted/20 text-xs font-semibold hover:bg-muted/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-orange">
      {showAll ? 'Thu gọn danh sách' : `Xem thêm ${remaining} điều kiện`}
      <ChevronDown aria-hidden="true" size={14} className={showAll ? 'rotate-180' : ''} />
    </button>}
  </section>;
}
