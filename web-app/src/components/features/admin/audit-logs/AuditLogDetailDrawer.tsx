'use client';

import { ArrowRight, Copy, X } from 'lucide-react';
import { useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { displayAuditRow } from './auditDisplay';
import type { AuditDetail } from './types';

interface Props {
  open: boolean;
  detail?: AuditDetail;
  failed?: boolean;
  onRetry: () => void;
  onClose: () => void;
  onCopyJson: (json: string) => Promise<boolean>;
}

export default function AuditLogDetailDrawer({ open, detail, failed, onRetry, onClose, onCopyJson }: Props) {
  const [copyFeedback, setCopyFeedback] = useState('');
  const event = detail?.event;
  const display = event && displayAuditRow(event);
  const json = detail ? JSON.stringify(detail, null, 2) : '';

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent showCloseButton={false} overlayClassName="bg-[#293041]/30"
        className="top-0 right-0 bottom-0 left-auto flex h-dvh max-w-lg translate-x-0 translate-y-0 flex-col gap-0 rounded-none bg-white dark:bg-card p-0 sm:max-w-lg">
        <header className="flex items-start justify-between gap-4 bg-[#f1f3ff] dark:bg-muted p-6">
          <div className="min-w-0 space-y-2">
            <DialogTitle className="text-lg">Chi tiết nhật ký thao tác</DialogTitle>
            {event && <p className="break-all font-mono text-xs text-[#186392] dark:text-sky-300">
              #{event.id} · {event.action} · {event.targetCode}
            </p>}
          </div>
          <button type="button" aria-label="Đóng chi tiết" onClick={onClose}
            className="rounded-lg p-2 text-[#5c4039] dark:text-muted-foreground hover:bg-[#e9edff] dark:hover:bg-secondary">
            <X className="size-5" />
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
          {failed ? <p role="alert" className="text-red-700">
            Không thể tải chi tiết.
            <button type="button" className="ml-2 underline" onClick={onRetry}>Thử lại</button>
          </p> : detail && event && display ? (
            <>
              <dl className="grid grid-cols-2 gap-3 rounded-xl bg-[#f1f3ff] dark:bg-muted p-4 text-xs">
                <div><dt className="text-[#5c4039] dark:text-muted-foreground">Quản trị viên</dt><dd>{event.actorName}</dd></div>
                <div><dt className="text-[#5c4039] dark:text-muted-foreground">Thời gian</dt><dd>{display.time} · {display.date}</dd></div>
                <div><dt className="text-[#5c4039] dark:text-muted-foreground">Địa chỉ kết nối đến backend</dt><dd>{detail.peerAddress ?? '—'}</dd></div>
                <div><dt className="text-[#5c4039] dark:text-muted-foreground">Đối tượng</dt><dd>{display.target}</dd></div>
                <div className="col-span-2"><dt className="text-[#5c4039] dark:text-muted-foreground">Tóm tắt</dt><dd>{event.summary}</dd></div>
                {typeof detail.details.reason === 'string' && <div className="col-span-2">
                  <dt className="text-[#5c4039] dark:text-muted-foreground">Lý do</dt><dd className="break-words">{detail.details.reason}</dd>
                </div>}
              </dl>

              {detail.changes.length > 0 && <section className="space-y-2">
                <h3 className="font-semibold">Giá trị thay đổi</h3>
                <ul className="space-y-2 rounded-xl bg-[#f1f3ff] dark:bg-muted p-3">
                  {detail.changes.map((change) => <li key={change.field} className="space-y-1 rounded-lg bg-white dark:bg-card p-3">
                    <p className="break-all font-mono text-xs font-semibold">{change.field}</p>
                    <div className="flex flex-wrap items-center gap-2 break-all text-xs">
                      <span className="rounded bg-[#ffdad6] dark:bg-red-950 px-2 py-1 text-[#ba1a1a] dark:text-red-300">{change.oldValue || '—'}</span>
                      <ArrowRight className="size-4 text-[#5c4039] dark:text-muted-foreground" aria-hidden />
                      <span className="rounded bg-[#1f8642]/15 px-2 py-1 text-[#006b2f] dark:text-emerald-300">{change.newValue || '—'}</span>
                    </div>
                  </li>)}
                </ul>
              </section>}

              <section className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">Dữ liệu bản ghi</h3>
                  <button type="button" onClick={async () => {
                    const copied = await onCopyJson(json);
                    setCopyFeedback(copied ? 'Đã sao chép JSON.' : 'Không thể sao chép vào clipboard.');
                  }}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-[#186392] dark:text-sky-300">
                    <Copy className="size-3.5" /> Sao chép JSON
                  </button>
                </div>
                {copyFeedback && <p role="status" className="text-xs">{copyFeedback}</p>}
                <pre className="overflow-x-auto rounded-xl bg-[#293041] p-4 text-xs text-[#edf0ff]">{json}</pre>
              </section>
            </>
          ) : <p role="status">Đang tải chi tiết…</p>}
        </div>
      </DialogContent>
    </Dialog>
  );
}
