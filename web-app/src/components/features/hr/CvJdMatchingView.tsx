'use client';

import React from 'react';
import { SessionHistoryItem } from '@/services/historyService';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileText, Briefcase, CheckCircle2, AlertTriangle, XCircle, Sparkles, ExternalLink } from 'lucide-react';

interface CvJdMatchingViewProps {
  session: SessionHistoryItem | null;
}

const ALIGNMENT_STYLE: Record<string, { label: string; className: string }> = {
  MATCH: { label: 'Đạt yêu cầu', className: 'bg-emerald-50 text-emerald-800 border-emerald-300' },
  PARTIAL: { label: 'Khoảng trống', className: 'bg-amber-50 text-amber-800 border-amber-300' },
  MISSING: { label: 'Thiếu', className: 'bg-rose-50 text-rose-800 border-rose-300' },
};

export const CvJdMatchingView: React.FC<CvJdMatchingViewProps> = ({ session }) => {
  const skills = session?.skillGapResults ?? [];
  const report = session?.skillGapReport ?? null;

  if (!session || (skills.length === 0 && !report)) {
    return (
      <Card className="border-slate-200 bg-white p-8 text-center">
        <CardContent className="space-y-2">
          <FileText className="mx-auto size-8 text-slate-400" />
          <h4 className="font-semibold text-slate-700">Chưa có kết quả phân tích Skill-Gap</h4>
          <p className="text-xs text-slate-500">Phiên này chưa chạy pipeline phân tích CV – JD.</p>
        </CardContent>
      </Card>
    );
  }

  const matched = skills.filter((s) => s.semantic_alignment === 'MATCH');
  const partial = skills.filter((s) => s.semantic_alignment === 'PARTIAL');
  const missing = skills.filter((s) => s.semantic_alignment === 'MISSING');

  const renderSkill = (s: (typeof skills)[number]) => {
    const style = ALIGNMENT_STYLE[s.semantic_alignment] ?? ALIGNMENT_STYLE.MISSING;
    return (
      <div key={s.jd_skill_id} className="rounded-lg border border-slate-200 bg-white p-3 text-xs space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-slate-900">{s.jd_skill_id}</span>
          <Badge variant="outline" className={style.className}>{style.label}</Badge>
        </div>
        <div className="text-slate-600">
          Yêu cầu: <strong>{s.required_proficiency.toFixed(2)}</strong> · Ứng viên:{' '}
          <strong>{s.candidate_proficiency.toFixed(2)}</strong> · Gap: <strong>{s.gap_magnitude.toFixed(2)}</strong>
        </div>
        {s.matched_cv_skill_id && (
          <div className="text-slate-500">
            Khớp với kỹ năng CV: {s.matched_cv_skill_id}
            {s.is_substituted ? ' (thay thế)' : ''}
          </div>
        )}
        {s.cv_evidence_spans.length > 0 && (
          <div className="text-slate-500 italic">“{s.cv_evidence_spans[0]}”</div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-slate-200 bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="size-4 text-blue-600" /> CV
            </CardTitle>
            <CardDescription className="truncate">{session.cvFilename || 'Không có thông tin tệp'}</CardDescription>
          </CardHeader>
          {session.cvFileUrl && (
            <CardContent>
              <a href={session.cvFileUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
                Mở tệp <ExternalLink className="size-3" />
              </a>
            </CardContent>
          )}
        </Card>
        <Card className="border-slate-200 bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Briefcase className="size-4 text-indigo-600" /> JD
            </CardTitle>
            <CardDescription className="truncate">{session.jdFilename || 'Không có thông tin tệp'}</CardDescription>
          </CardHeader>
          {session.jdFileUrl && (
            <CardContent>
              <a href={session.jdFileUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                Mở tệp <ExternalLink className="size-3" />
              </a>
            </CardContent>
          )}
        </Card>
      </div>

      <Card className="border-blue-200 bg-blue-50/50 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 font-bold text-slate-900">
            <Sparkles className="size-5 text-blue-600" /> Phân tích khoảng trống năng lực
          </h3>
          <div className="flex gap-2 text-xs font-semibold">
            <span className="rounded bg-emerald-100 px-2 py-1 text-emerald-800">Khớp {report?.matched_count ?? matched.length}</span>
            <span className="rounded bg-amber-100 px-2 py-1 text-amber-800">Một phần {report?.partial_count ?? partial.length}</span>
            <span className="rounded bg-rose-100 px-2 py-1 text-rose-800">Thiếu {report?.missing_count ?? missing.length}</span>
          </div>
        </div>
        {report?.markdown_summary && (
          <pre className="mt-3 whitespace-pre-wrap text-xs text-slate-700 font-sans">{report.markdown_summary}</pre>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase text-slate-500">
            <CheckCircle2 className="size-4 text-emerald-600" /> Đạt ({matched.length})
          </h4>
          {matched.map(renderSkill)}
        </div>
        <div className="space-y-2">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase text-slate-500">
            <AlertTriangle className="size-4 text-amber-600" /> Khoảng trống ({partial.length})
          </h4>
          {partial.map(renderSkill)}
        </div>
        <div className="space-y-2">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase text-slate-500">
            <XCircle className="size-4 text-rose-600" /> Thiếu ({missing.length})
          </h4>
          {missing.map(renderSkill)}
        </div>
      </div>
    </div>
  );
};
