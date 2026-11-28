'use client';

import { useId, useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight, ClipboardList, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ApplicationProfile } from '@/services/applicationProfiles';
import { ApplicationDocumentViewer } from './ApplicationDocumentViewer';
import { CandidateCvJdSummary } from './CandidateCvJdSummary';

export function ApplicationDocumentsPanel({ profile }: { profile: ApplicationProfile }) {
  const [viewer, setViewer] = useState<'idle' | 'open' | 'closed'>('idle');
  const viewerId = useId();
  const isOpen = viewer === 'open';
  const documents = [
    { label: 'CV', name: profile.cvFilename || 'CV của hồ sơ', Icon: FileText },
    { label: 'Mô tả công việc', name: profile.jdFilename || profile.jdTitle || 'JD của hồ sơ', Icon: ClipboardList },
  ];

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border bg-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight">Tài liệu đã dùng</h2>
        <p className="mt-1 text-sm text-muted-foreground">CV và JD dùng cho các lượt phỏng vấn của hồ sơ này.</p>
        <div className="mt-4 flex flex-col gap-3 rounded-xl bg-muted/35 p-3 sm:p-4 lg:flex-row lg:items-center">
          <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
            {documents.map(({ label, name, Icon }) => (
              <div key={label} className="flex min-w-0 items-center gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-orange/10 text-brand-orange">
                  <Icon size={17} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="mt-0.5 text-sm font-medium wrap-anywhere">{name}</p>
                </div>
              </div>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            className="h-11 self-start px-3 sm:h-9 lg:self-auto"
            aria-controls={viewerId}
            aria-expanded={isOpen}
            onClick={() => setViewer(isOpen ? 'closed' : 'open')}
          >
            {isOpen ? 'Thu gọn tài liệu' : 'Xem tài liệu'}
            <ChevronDown aria-hidden="true" className="transition-transform group-aria-expanded/button:rotate-180" />
          </Button>
        </div>
        <div id={viewerId} hidden={!isOpen}>
          {viewer !== 'idle' && (
            <div className="mt-4 space-y-3">
              <ApplicationDocumentViewer profileId={profile.id} key={profile.id} compact />
              <Link
                href="/interview/new"
                className="inline-flex min-h-10 items-center gap-1 rounded-sm text-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange"
              >
                Tạo hồ sơ với tài liệu mới <ChevronRight size={14} aria-hidden="true" />
              </Link>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border bg-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight">Kết quả đối chiếu CV và JD</h2>
        <p className="mt-1 text-sm text-muted-foreground">Các trạng thái mô tả thông tin tìm được trong CV.</p>
        <div className="mt-4">
          <CandidateCvJdSummary skills={profile.skills} report={profile.analysis} view="profile" />
        </div>
      </section>
    </div>
  );
}
