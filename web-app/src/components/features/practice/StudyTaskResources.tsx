'use client';

import { useState, type FormEvent } from 'react';
import { Download, ExternalLink, Pencil, Trash2 } from 'lucide-react';
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

export function StudyTaskResources({ items, actions, disabled }: {
  items: readonly StudyResource[];
  actions: StudyTaskResourceActions;
  disabled: boolean;
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
    <div className="space-y-2">
      <h4 className="font-semibold">Tài liệu tham khảo</h4>
      <ul className="space-y-1.5">
        {items.map((item) => {
          const reference = item.url && getStudyReferenceUrl(item.url);
          if (editingId === item.id) {
            return (
              <li key={item.id} className="rounded-lg bg-(--practice-pale) p-2.5">
                <form onSubmit={(event) => void saveLink(event, item)} className="space-y-2">
                  <fieldset disabled={disabled} className="space-y-2">
                    <Input name="title" aria-label="Sửa tên tài liệu" maxLength={255} defaultValue={item.title} />
                    <Input name="url" aria-label="Sửa đường dẫn tài liệu" type="url" maxLength={2048} defaultValue={item.url ?? ''} required />
                    <div className="flex justify-end gap-2">
                      <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>Hủy</Button>
                      <Button type="submit" size="sm">Lưu đường dẫn</Button>
                    </div>
                  </fieldset>
                </form>
              </li>
            );
          }
          return (
            <li key={item.id} className="flex items-center justify-between gap-2 rounded-lg bg-(--practice-pale) px-2.5 py-1 text-xs">
              {reference ? (
                <a href={reference} target="_blank" rel="noopener noreferrer" className="flex min-w-0 items-center gap-1.5 font-medium text-(--practice-primary) hover:underline">
                  <ExternalLink size={14} className="shrink-0" aria-hidden="true" /><span className="wrap-anywhere">{item.title}</span>
                </a>
              ) : item.fileName ? (
                <Button type="button" variant="ghost" size="sm" disabled={downloading !== null}
                  onClick={() => void download(item)} className="h-auto min-w-0 justify-start whitespace-normal text-left">
                  <Download aria-hidden="true" /><span className="wrap-anywhere">{item.title}</span>
                </Button>
              ) : <span>{item.title}</span>}
              <div className="flex shrink-0 gap-1">
                {reference && <Button type="button" variant="ghost" size="icon-xs" disabled={disabled}
                  aria-label={`Sửa tài liệu ${item.title}`} onClick={() => setEditingId(item.id)}><Pencil aria-hidden="true" /></Button>}
                <Button type="button" variant="ghost" size="icon-xs" disabled={disabled} aria-label={`Xóa tài liệu ${item.title}`}
                  onClick={() => actions.remove(item)}>
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      <details className="rounded-lg border border-(--practice-blue-strong) p-2.5">
        <summary className="cursor-pointer text-xs font-semibold">Thêm tài liệu</summary>
        <form onSubmit={(event) => void saveLink(event)} className="mt-2 space-y-2">
          <fieldset disabled={disabled} className="space-y-2">
            <Input name="title" aria-label="Tên tài liệu" maxLength={255} placeholder="Tên tài liệu (tùy chọn)" />
            <Input name="url" aria-label="Đường dẫn tài liệu" type="url" maxLength={2048} placeholder="https://…" required />
            <Button type="submit" size="sm" variant="outline">Thêm đường dẫn</Button>
          </fieldset>
        </form>
        <form onSubmit={uploadFile} className="mt-2 border-t pt-2">
          <fieldset disabled={disabled} className="space-y-2">
            <Input name="file" aria-label="Tệp ôn tập" type="file" required />
            <Button type="submit" size="sm" variant="outline">Tải tệp lên</Button>
          </fieldset>
        </form>
      </details>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
