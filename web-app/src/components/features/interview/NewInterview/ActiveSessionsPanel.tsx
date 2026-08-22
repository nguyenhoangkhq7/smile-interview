'use client';

import { useState } from 'react';
import Link from 'next/link';
import { FileText, X, MessageCircle, Briefcase, Play, Clock, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export type SessionStage = 'UPLOADED' | 'ASSESSED' | 'INTERVIEWING';

export interface ActiveSession {
  sessionId: string;
  roleTitle: string;
  cvFilename: string;
  jdFilename: string;
  status: string;
  date: string;
  hasAssessment?: boolean;
  hasQuestions?: boolean;
  competencyFitScore?: number;
  stage?: SessionStage;
  answeredCount?: number;
  totalQuestions?: number;
}

interface ActiveSessionsPanelProps {
  sessions: ActiveSession[];
  onResume: (sessionId: string) => void;
  onViewAssessment: (sessionId: string) => void;
}

function StageBadge({ session }: { session: ActiveSession }) {
  if (session.stage === 'UPLOADED') {
    return (
      <Badge variant="outline" className="text-[10px] gap-1 font-bold bg-blue-500/10 text-blue-600 border-blue-200">
        <FileText size={10} />
        Chờ đánh giá
      </Badge>
    );
  }

  if (session.stage === 'ASSESSED') {
    return (
      <Badge variant="outline" className="text-[10px] gap-1 font-bold bg-amber-500/10 text-amber-700 border-amber-200">
        <Sparkles size={10} />
        Đã đánh giá {session.competencyFitScore !== undefined ? `(${session.competencyFitScore}%)` : ''}
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="text-[10px] gap-1 font-bold bg-emerald-500/10 text-emerald-700 border-emerald-200">
      <Play size={10} />
      {session.totalQuestions
        ? `Đang phỏng vấn (${session.answeredCount || 0}/${session.totalQuestions})`
        : 'Đang phỏng vấn'}
    </Badge>
  );
}

interface SessionCardProps {
  session: ActiveSession;
  onResume: (id: string) => void;
  onViewAssessment: (id: string) => void;
}

function SessionCard({ session, onResume, onViewAssessment }: SessionCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm hover:border-brand-orange/30 transition-all">
      <div className="flex items-center justify-between gap-2">
        <strong className="text-sm font-bold text-foreground truncate max-w-[200px]" title={session.roleTitle}>
          {session.roleTitle}
        </strong>
        <StageBadge session={session} />
      </div>

      <div className="my-3 space-y-1.5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <FileText size={13} className="text-brand-orange shrink-0" />
          <span className="truncate max-w-[280px]" title={session.cvFilename}>{session.cvFilename}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Briefcase size={13} className="text-blue-500 shrink-0" />
          <span className="truncate max-w-[280px]" title={session.jdFilename}>{session.jdFilename}</span>
        </div>
      </div>

      <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-4">
        <Clock size={11} />
        Cập nhật: {new Date(session.date).toLocaleString('vi-VN')}
      </div>

      <div>
        {/* Stage 1: Uploaded only */}
        {session.stage === 'UPLOADED' && (
          <Button
            size="sm"
            onClick={() => onResume(session.sessionId)}
            className="w-full bg-brand-orange text-white hover:bg-brand-orange-hover text-xs h-9 shadow-sm"
          >
            <Sparkles size={13} className="mr-1.5" />
            Tiến hành Đánh giá
          </Button>
        )}

        {/* Stage 2: Assessed */}
        {session.stage === 'ASSESSED' && (
          <Button
            size="sm"
            onClick={() => onViewAssessment(session.sessionId)}
            className="w-full bg-brand-orange text-white hover:bg-brand-orange-hover text-xs h-9 shadow-sm"
          >
            <Sparkles size={13} className="mr-1.5" />
            Xem đánh giá & Bắt đầu phỏng vấn
          </Button>
        )}

        {/* Stage 3: In Interview */}
        {session.stage === 'INTERVIEWING' && (
          <div className={`grid gap-2 ${session.hasAssessment ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {session.hasAssessment && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onViewAssessment(session.sessionId)}
                className="text-xs h-9 border-brand-orange/20 text-brand-orange hover:bg-brand-orange/5"
              >
                <Sparkles size={13} className="mr-1" />
                Xem đánh giá
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => onResume(session.sessionId)}
              className="bg-emerald-600 text-white hover:bg-emerald-700 text-xs h-9 shadow-sm"
            >
              <Play size={13} fill="currentColor" className="mr-1.5" />
              Tiếp tục Phỏng vấn
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export function ActiveSessionsPanel({
  sessions,
  onResume,
  onViewAssessment,
}: ActiveSessionsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAllModal, setShowAllModal] = useState(false);
  const [timeFilter, setTimeFilter] = useState('all');

  const displayedSessions = sessions.slice(0, 5);

  const filteredSessions = sessions.filter((s) => {
    if (timeFilter === 'all') return true;
    const now = new Date();
    const sDate = new Date(s.date);
    const diffDays = Math.ceil(Math.abs(now.getTime() - sDate.getTime()) / (1000 * 60 * 60 * 24));

    if (timeFilter === 'today') return sDate.toDateString() === now.toDateString();
    if (timeFilter === 'week') return diffDays <= 7;
    if (timeFilter === 'month') return diffDays <= 30;
    return true;
  });

  return (
    <>
      {}
      {!isExpanded ? (
        <button
          onClick={() => setIsExpanded(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-brand-orange px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-orange/25 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-brand-orange/35 transition-all"
        >
          <MessageCircle size={18} />
          <span>Phiên đang thực hiện ({sessions.length})</span>
        </button>
      ) : (
                <div className="fixed bottom-24 right-6 z-40 flex w-[380px] max-h-[500px] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl animate-fade-up">
          {}
          <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
            <div className="flex items-center gap-2">
              <MessageCircle size={18} className="text-brand-orange" />
              <span className="text-sm font-bold text-foreground">Phiên đang thực hiện</span>
              <Badge variant="secondary" className="px-1.5 py-0 bg-brand-orange/10 text-brand-orange">{sessions.length}</Badge>
            </div>
            <Button size="icon" variant="ghost" onClick={() => setIsExpanded(false)} className="size-7 rounded-full text-muted-foreground">
              <X size={16} />
            </Button>
          </div>

          {}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {sessions.length === 0 ? (
              <p className="py-8 text-center text-xs text-muted-foreground">Không có phiên nào đang thực hiện</p>
            ) : (
              <>
                {displayedSessions.map((session) => (
                  <SessionCard
                    key={session.sessionId}
                    session={session}
                    onResume={onResume}
                    onViewAssessment={onViewAssessment}
                  />
                ))}

                {sessions.length > 5 && (
                  <Button variant="outline" size="sm" onClick={() => setShowAllModal(true)} className="w-full text-xs">
                    Xem thêm {sessions.length - 5} phiên khác
                  </Button>
                )}

                <Link href="/history" className="block text-center text-xs font-semibold text-brand-orange hover:underline pt-1">
                  Mở toàn bộ lịch sử →
                </Link>
              </>
            )}
          </div>
        </div>
      )}

      {/* Full Modal for all active sessions */}
      <Dialog open={showAllModal} onOpenChange={setShowAllModal}>
        <DialogContent className="max-w-[700px] max-h-[85vh] flex flex-col p-0">
          <DialogHeader className="px-6 py-4 border-b border-border flex flex-row items-center justify-between gap-4">
            <div className="space-y-0.5">
              <DialogTitle className="text-lg font-extrabold text-foreground">Danh sách tất cả phiên đang thực hiện ({sessions.length})</DialogTitle>
              <p className="text-xs text-muted-foreground">Các phiên chưa hoàn thành được liệt kê chi tiết dưới đây</p>
            </div>
            <div className="mr-8">
              <Select value={timeFilter} onValueChange={(val) => setTimeFilter(val ?? 'all')}>
                <SelectTrigger className="w-40 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả thời gian</SelectItem>
                  <SelectItem value="today">Hôm nay</SelectItem>
                  <SelectItem value="week">7 ngày qua</SelectItem>
                  <SelectItem value="month">30 ngày qua</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {filteredSessions.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">Không tìm thấy phiên nào phù hợp với bộ lọc.</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {filteredSessions.map((session) => (
                  <SessionCard
                    key={session.sessionId}
                    session={session}
                    onResume={(id) => { onResume(id); setShowAllModal(false); }}
                    onViewAssessment={(id) => { onViewAssessment(id); setShowAllModal(false); }}
                  />
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
