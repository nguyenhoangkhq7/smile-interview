'use client';

import { useState, type FormEvent, type RefObject } from 'react';
import { BookOpen, Download, ExternalLink, FileUp, Paperclip, Pencil, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getStudyReferenceUrl, type StudyResource } from './studyPlan';

export interface StudyTaskResourceActions {
  add: (title: string, url: string) => Promise<boolean>;
  update: (resource: StudyResource, title: string, url: string) => Promise<boolean>;
  upload: (file: File) => Promise<boolean>;
  download: (resource: StudyResource) => Promise<Blob>;
  remove: (resource: StudyResource) => void;
}

export function StudyTaskResources({ items, actions, disabled, detailsRef }: {
  items: readonly StudyResource[];
  actions: StudyTaskResourceActions;
  disabled: boolean;
  detailsRef?: RefObject<HTMLDetailsElement | null>;
}) {
  const [error, setError] = useState<string>();
  const [downloading, setDownloading] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  async function saveLink(event: FormEvent<HTMLFormElement>, item?: StudyResource) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const url = getStudyReferenceUrl(String(data.get('url') ?? '').trim());
    if (!url) {
      setError('Hãy nhập đường dẫn HTTP hoặc HTTPS hợp lệ.');
      return;
    }
    setError(undefined);
    const title = String(data.get('title') ?? '').trim() || 'Tài liệu tham khảo';
    const saved = item ? await actions.update(item, title, url) : await actions.add(title, url);
    if (saved) {
      if (item) setEditingId(null);
      else form.reset();
    } else setError('Không lưu được đường dẫn.');
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = new FormData(form).get('file');
    if (!(file instanceof File) || !file.size) {
      setError('Hãy chọn một tệp có nội dung.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Tệp đính kèm tối đa 10 MiB.');
      return;
    }
    setError(undefined);
    if (await actions.upload(file)) form.reset();
    else setError('Không tải lên được tệp.');
  }

  async function download(item: StudyResource) {
    setError(undefined);
    setDownloading(item.id);
    try {
      const url = URL.createObjectURL(await actions.download(item));
      const link = document.createElement('a');
      link.href = url;
      link.download = item.fileName ?? item.title;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError('Không tải xuống được tài liệu.');
    } finally {
      setDownloading(null);
    }
  }

  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
        <Paperclip size={17} className="text-(--practice-muted)" aria-hidden="true" />
        Tài liệu tham khảo &amp; Liên kết
      </h3>

      {items.length > 0 && (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {items.map((item) => {
            const reference = item.url && getStudyReferenceUrl(item.url);
            if (editingId === item.id) {
              return (
                <li key={item.id} className="rounded-xl border border-slate-200 bg-(--practice-pale) p-3 sm:col-span-2">
                  <form onSubmit={(event) => void saveLink(event, item)} className="space-y-2">
                    <fieldset disabled={disabled} className="space-y-2">
                      <Input name="title" aria-label="Sửa tên tài liệu" maxLength={255} defaultValue={item.title} />
                      <Input name="url" aria-label="Sửa đường dẫn tài liệu" type="url" maxLength={2048} defaultValue={item.url ?? ''} required />
                      <div className="flex justify-end gap-2">
                        <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>Hủy</Button>
                        <Button type="submit" size="sm" className="bg-(--practice-primary) hover:bg-(--practice-primary-hover)">Lưu đường dẫn</Button>
                      </div>
                    </fieldset>
                  </form>
                </li>
              );
            }
            return (
              <li
                key={item.id}
                className="group flex items-center justify-between gap-2 rounded-xl border border-slate-200/70 bg-(--practice-pale)/60 p-2.5 text-xs transition-colors hover:bg-(--practice-pale)"
              >
                {reference ? (
                  <a
                    href={reference}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex min-w-0 flex-1 items-center gap-2.5"
                  >
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-200/70 text-(--practice-primary)">
                      <BookOpen size={15} aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-foreground group-hover:text-(--practice-primary)">
                        {item.title}
                      </span>
                      <span className="block truncate text-[11px] text-(--practice-muted)">{reference}</span>
                    </span>
                    <ExternalLink size={14} className="shrink-0 text-(--practice-muted) group-hover:text-(--practice-primary)" aria-hidden="true" />
                  </a>
                ) : item.fileName ? (
                  <button
                    type="button"
                    disabled={downloading !== null}
                    onClick={() => void download(item)}
                    className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                  >
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-200/70 text-(--practice-primary)">
                      <Download size={15} aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-foreground">{item.title}</span>
                      <span className="block truncate text-[11px] text-(--practice-muted)">{item.fileName}</span>
                    </span>
                  </button>
                ) : (
                  <span className="min-w-0 flex-1 truncate font-medium">{item.title}</span>
                )}
                <div className="flex shrink-0 gap-0.5">
                  {reference && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      disabled={disabled}
                      aria-label={`Sửa tài liệu ${item.title}`}
                      onClick={() => setEditingId(item.id)}
                    >
                      <Pencil aria-hidden="true" />
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    disabled={disabled}
                    aria-label={`Xóa tài liệu ${item.title}`}
                    onClick={() => actions.remove(item)}
                    className="hover:text-destructive"
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <details ref={detailsRef} className="rounded-xl border border-(--practice-blue-strong) bg-card p-3">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-semibold text-foreground select-none">
          <Plus size={14} className="text-(--practice-primary)" aria-hidden="true" />
          Thêm tài liệu hoặc tệp đính kèm
        </summary>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <form onSubmit={(event) => void saveLink(event)} className="space-y-2 rounded-lg bg-slate-50 p-2.5">
            <fieldset disabled={disabled} className="space-y-2">
              <p className="text-[11px] font-bold tracking-wide text-(--practice-muted) uppercase">Liên kết ngoài</p>
              <Input name="title" aria-label="Tên tài liệu" maxLength={255} placeholder="Tên tài liệu (tùy chọn)" className="h-8 text-xs" />
              <Input name="url" aria-label="Đường dẫn tài liệu" type="url" maxLength={2048} placeholder="https://…" required className="h-8 text-xs" />
              <Button type="submit" size="sm" variant="outline" className="w-full text-xs">Thêm đường dẫn</Button>
            </fieldset>
          </form>
          <form onSubmit={uploadFile} className="space-y-2 rounded-lg bg-slate-50 p-2.5">
            <fieldset disabled={disabled} className="space-y-2">
              <p className="flex items-center gap-1 text-[11px] font-bold tracking-wide text-(--practice-muted) uppercase">
                <FileUp size={12} aria-hidden="true" /> Tệp đính kèm (≤ 10MB)
              </p>
              <Input name="file" aria-label="Tệp ôn tập" type="file" required className="h-8 text-xs" />
              <Button type="submit" size="sm" variant="outline" className="w-full text-xs">Tải tệp lên</Button>
            </fieldset>
          </form>
        </div>
      </details>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </section>
  );
}
