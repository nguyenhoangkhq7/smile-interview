'use client';

import type { DragEvent, ChangeEvent, RefObject } from 'react';
import { Briefcase, FileText, FolderOpen, AlertTriangle, Eye, X as XIcon } from 'lucide-react';
import { Button, buttonVariants } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import Link from 'next/link';
import type { CvSource, JdSource } from '@/hooks/useNewInterview';
import { cn } from '@/lib/utils';

interface ComboboxOption { id: number; label: string; date: string; }

interface DatabaseResume {
  id: number;
  file_name: string;
  created_at: string;
  file_url?: string;
}

interface DatabaseJd {
  id: number;
  title: string;
  created_at: string;
}


import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';

interface ComboboxProps {
  options: ComboboxOption[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  placeholder: string;
  searchPlaceholder: string;
  icon: React.ReactNode;
}

function Combobox({ options, selectedId, onSelect, placeholder, searchPlaceholder, icon }: ComboboxProps) {
  const [open, setOpen]   = useState(false);
  const [q,    setQ]      = useState('');
  const wrapRef           = useRef<HTMLDivElement>(null);
  const selected          = options.find((o) => o.id === selectedId);
  const filtered          = options.filter((o) => o.label.toLowerCase().includes(q.toLowerCase()));

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={wrapRef} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-sm transition-all ${open ? 'border-brand-orange shadow-[0_0_0_3px_rgba(234,88,12,0.12)]' : 'border-border'} bg-card`}
      >
        <span className="flex min-w-0 items-center gap-2">
          {icon}
          <span className={`truncate ${selected ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
            {selected ? selected.label : placeholder}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1">
          {selected && (
            <span onClick={(e) => { e.stopPropagation(); onSelect(null); }} className="rounded-full p-0.5 text-muted-foreground hover:text-destructive">
              <X size={12} />
            </span>
          )}
          <ChevronDown size={14} className={`text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 rounded-lg border border-border bg-card p-2 shadow-lg">
          <div className="mb-2 flex items-center gap-2 rounded-md border border-border bg-muted/50 px-2 py-1.5">
            <Search size={13} className="text-muted-foreground" />
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent text-xs outline-none text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <div className="max-h-52 overflow-y-auto flex flex-col gap-0.5">
            {filtered.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">Không tìm thấy kết quả</p>
            ) : filtered.map((opt) => {
              const isSelected = opt.id === selectedId;
              return (
                <button key={opt.id} type="button"
                  onClick={() => { onSelect(opt.id); setOpen(false); setQ(''); }}
                  className={`flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-xs transition-colors ${isSelected ? 'bg-accent text-brand-orange font-semibold' : 'text-foreground hover:bg-muted'}`}
                >
                  <span className="truncate max-w-[75%]" title={opt.label}>{opt.label}</span>
                  <span className="text-muted-foreground">{opt.date}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── File Drop Zone ─────────────────────────────────────────────────────────────
interface DropZoneProps {
  zone: 'cv' | 'jd';
  file: File | null;
  dragActive: boolean;
  error: string | null;
  accept: string;
  hint: string;
  icon: React.ReactNode;
  inputRef: RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => void;
  onDragLeave: (zone: 'cv' | 'jd') => void;
  onDrop: (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => void;
  onFileChange: (e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => void;
  onClear: () => void;
  onTrigger: () => void;
}

function DropZone({ zone, file, dragActive, error: _error, accept, hint, icon, inputRef, onDragOver, onDragLeave, onDrop, onFileChange, onClear, onTrigger }: DropZoneProps) {
  if (file) {
    return (
      <div className="flex items-center justify-between rounded-xl border border-brand-orange/30 bg-brand-orange/5 p-3.5">
        <div className="flex items-center gap-3">
          <FileText size={22} className="text-brand-orange shrink-0" />
          <div>
            <p className="text-sm font-medium text-foreground">{file.name}</p>
            <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        </div>
        <button onClick={onClear} className="rounded-full p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors">
          <XIcon size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${dragActive ? 'border-brand-orange bg-brand-orange/8' : 'border-border hover:border-brand-orange/50 hover:bg-accent/50'}`}
      onDragOver={(e) => onDragOver(e, zone)}
      onDragLeave={() => onDragLeave(zone)}
      onDrop={(e) => onDrop(e, zone)}
      onClick={onTrigger}
    >
      <span className="text-muted-foreground/50">{icon}</span>
      <p className="text-sm text-muted-foreground">
        Kéo thả hoặc <span className="font-semibold text-brand-orange">chọn tệp</span>
      </p>
      <p className="text-xs text-muted-foreground/70">{hint}</p>
      <input ref={inputRef} type="file" className="hidden" accept={accept} onChange={(e) => onFileChange(e, zone)} />
    </div>
  );
}

// ── Props ──────────────────────────────────────────────────────────────────────
interface UploadStepProps {
  cvSource: CvSource; setCvSource: (v: CvSource) => void;
  jdSource: JdSource; setJdSource: (v: JdSource) => void;
  cvFile: File | null; jdFile: File | null;
  jdText: string; setJdText: (v: string) => void;
  dragOverCv: boolean; dragOverJd: boolean;
  cvError: string | null; jdError: string | null;
  savedResumes: DatabaseResume[]; savedJds: DatabaseJd[];
  selectedResumeId: number | null; setSelectedResumeId: (id: number | null) => void;
  selectedJdId: number | null; setSelectedJdId: (id: number | null) => void;
  fileInputCvRef: RefObject<HTMLInputElement | null>;
  fileInputJdRef: RefObject<HTMLInputElement | null>;

  defaultResumeId: string | null;
  onDragOver: (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => void;
  onDragLeave: (zone: 'cv' | 'jd') => void;
  onDrop: (e: DragEvent<HTMLDivElement>, zone: 'cv' | 'jd') => void;
  onFileChange: (e: ChangeEvent<HTMLInputElement>, zone: 'cv' | 'jd') => void;
  onTrigger: (zone: 'cv' | 'jd') => void;
  onClearCv: () => void;
  onClearJd: () => void;
  onViewPdf: (url: string, title: string) => void;
  onSubmit: () => void;
  disabled: boolean;
}

// ── Main Export ────────────────────────────────────────────────────────────────
export function UploadStep({
  cvSource, setCvSource, jdSource, setJdSource,
  cvFile, jdFile, jdText, setJdText,
  dragOverCv, dragOverJd, cvError, jdError,
  savedResumes, savedJds,
  selectedResumeId, setSelectedResumeId,
  selectedJdId, setSelectedJdId,
  fileInputCvRef, fileInputJdRef,
  defaultResumeId,
  onDragOver, onDragLeave, onDrop, onFileChange, onTrigger,
  onClearCv, onClearJd, onViewPdf,
  onSubmit, disabled,
}: UploadStepProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {/* ── CV Column ── */}
        <div className="space-y-3">
          <label className="text-sm font-semibold text-foreground">Hồ sơ cá nhân (CV)</label>
          <div className="flex gap-1.5">
            {(['upload', 'saved', ...(defaultResumeId ? ['default'] : [])] as CvSource[]).map((src) => (
              <button key={src} type="button"
                onClick={() => setCvSource(src)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${cvSource === src ? 'bg-brand-orange text-white' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
              >
                {src === 'upload' ? 'Tải CV mới' : src === 'saved' ? 'CV đã lưu' : 'CV mặc định'}
              </button>
            ))}
          </div>

          {cvSource === 'upload' && (
            <DropZone zone="cv" file={cvFile} dragActive={dragOverCv} error={cvError}
              accept=".pdf" hint="PDF • Tối đa 10MB"
              icon={<FolderOpen size={36} />}
              inputRef={fileInputCvRef}
              onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
              onFileChange={onFileChange} onClear={onClearCv} onTrigger={() => onTrigger('cv')}
            />
          )}

          {cvSource === 'saved' && (
            <Combobox
              options={savedResumes.map((r) => ({ id: r.id, label: r.file_name, date: new Date(r.created_at).toLocaleDateString('vi-VN') }))}
              selectedId={selectedResumeId} onSelect={setSelectedResumeId}
              placeholder="-- Chọn CV trong danh sách --"
              searchPlaceholder="Tìm kiếm CV theo tên..."
              icon={<FileText size={15} className="text-brand-orange shrink-0" />}
            />
          )}

          {cvSource === 'default' && (() => {
            const def = savedResumes.find((r) => String(r.id) === String(defaultResumeId));
            return (
              <div className="space-y-2">
                <div className="flex items-center gap-3 rounded-xl border border-brand-orange/30 bg-brand-orange/5 p-3.5">
                  <FileText size={22} className="text-brand-orange shrink-0" />
                  <p className="text-sm font-medium text-foreground">{def?.file_name || 'Đang tải CV mặc định...'}</p>
                </div>
                {def?.file_url && (
                  <Button size="sm" variant="outline" onClick={() => onViewPdf(def.file_url!, `CV mặc định: ${def.file_name}`)}>
                    <Eye size={13} className="mr-1.5" /> Xem CV mặc định
                  </Button>
                )}
              </div>
            );
          })()}

          {cvError && <p className="flex items-center gap-1 text-xs text-destructive"><AlertTriangle size={12} /> {cvError}</p>}
        </div>

        {/* ── JD Column ── */}
        <div className="space-y-3">
          <label className="text-sm font-semibold text-foreground">Mô tả công việc (JD)</label>
          <div className="flex gap-1.5">
            {(['upload', 'text', 'saved'] as JdSource[]).map((src) => (
              <button key={src} type="button"
                onClick={() => setJdSource(src)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${jdSource === src ? 'bg-brand-orange text-white' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
              >
                {src === 'upload' ? 'Tải tệp JD' : src === 'text' ? 'Dán văn bản' : 'JD đã lưu'}
              </button>
            ))}
          </div>

          {jdSource === 'upload' && (
            <DropZone zone="jd" file={jdFile} dragActive={dragOverJd} error={jdError}
              accept=".pdf,.docx,.doc" hint="PDF, DOCX, DOC • Tối đa 10MB"
              icon={<Briefcase size={36} />}
              inputRef={fileInputJdRef}
              onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
              onFileChange={onFileChange} onClear={onClearJd} onTrigger={() => onTrigger('jd')}
            />
          )}

          {jdSource === 'text' && (
            <Textarea
              value={jdText} onChange={(e) => setJdText(e.target.value)}
              placeholder="Dán toàn bộ nội dung bản mô tả công việc (JD) vào đây..."
              className="min-h-[180px] resize-none"
            />
          )}

          {jdSource === 'saved' && (
            <Combobox
              options={savedJds.map((j) => ({ id: j.id, label: j.title, date: new Date(j.created_at).toLocaleDateString('vi-VN') }))}
              selectedId={selectedJdId} onSelect={setSelectedJdId}
              placeholder="-- Chọn JD trong danh sách --"
              searchPlaceholder="Tìm kiếm JD theo tên..."
              icon={<Briefcase size={15} className="text-blue-500 shrink-0" />}
            />
          )}

          {jdError && <p className="flex items-center gap-1 text-xs text-destructive"><AlertTriangle size={12} /> {jdError}</p>}
        </div>
      </div>

      {}
      <div className="flex items-center justify-end gap-3 pt-2">
        <Link href="/" className={cn(buttonVariants({ variant: 'outline' }))}>
          Hủy bỏ
        </Link>
        <Button onClick={onSubmit} disabled={disabled} className="bg-brand-orange text-white hover:bg-brand-orange-hover">
          Tải lên CV &amp; JD
        </Button>
      </div>
    </div>
  );
}
