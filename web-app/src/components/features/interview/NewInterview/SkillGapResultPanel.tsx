'use client';

import type { AnalyzeWithReportResponse } from '@/services/cvJdMatching';
import { Button } from '@/components/ui/button';
import { CandidateCvJdSummary } from '@/components/features/applications/CandidateCvJdSummary';
import { RefreshCw, RotateCcw, Save, Sparkles } from 'lucide-react';

interface SkillGapResultPanelProps {
  analysis: AnalyzeWithReportResponse;
  roleTitle: string;
  analyzing: boolean;
  startingInterview: boolean;
  onRefresh: () => void;
  onReset: () => void;
  onStartInterview: () => void;
}

export function SkillGapResultPanel({ analysis, roleTitle, analyzing, startingInterview, onRefresh, onReset, onStartInterview }: SkillGapResultPanelProps) {
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-5">
      <div className="space-y-2">
        <p className="flex items-center gap-2 text-xs font-semibold text-brand-orange"><Sparkles size={14} />Phân tích CV và mô tả công việc</p>
        <h2 className="text-2xl font-bold">{roleTitle || 'Kết quả đối chiếu kỹ năng'}</h2>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={analyzing || startingInterview}><RefreshCw size={14} className={analyzing ? 'animate-spin' : ''} />Phân tích lại</Button>
        <Button variant="ghost" size="sm" onClick={onReset} disabled={analyzing || startingInterview}><RotateCcw size={14} />Đổi CV/JD</Button>
      </div>
    </div>
    <CandidateCvJdSummary skills={analysis.skills ?? []} report={analysis.report} />
    <div className="flex flex-col items-start justify-between gap-4 border-t pt-5 sm:flex-row sm:items-center">
      <p className="text-sm text-muted-foreground">Lưu hồ sơ để bắt đầu phỏng vấn và theo dõi kết quả luyện tập.</p>
      <Button size="lg" onClick={onStartInterview} disabled={startingInterview || analyzing} className="w-full sm:w-auto"><Save size={16} />{startingInterview ? 'Đang lưu hồ sơ…' : 'Lưu hồ sơ ứng tuyển'}</Button>
    </div>
  </div>;
}
