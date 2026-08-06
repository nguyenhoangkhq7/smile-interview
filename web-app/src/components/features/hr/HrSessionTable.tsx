'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  Search, Calendar, FileText, Briefcase, ChevronRight,
  Sparkles, CheckCircle2, HelpCircle, MessageSquare, Radio,
  ArrowUpDown, Filter, RefreshCw,
} from 'lucide-react';

type SortOrder = 'newest' | 'oldest';
type StageFilter = 'ALL' | 'CV_JD_MATCHED' | 'QUESTION_BANK_READY' | 'INTERVIEW_IN_PROGRESS' | 'COMPLETED';

interface HrSessionTableProps {
  sessions: SessionHistoryItem[];
}

export const HrSessionTable: React.FC<HrSessionTableProps> = ({ sessions: initialSessions }) => {
  const [sessionList, setSessionList] = useState<SessionHistoryItem[]>(initialSessions);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest');
  const [stageFilter, setStageFilter] = useState<StageFilter>('ALL');
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    historyService.getHistory().then((data) => {
      if (data && data.length > 0) setSessionList(data);
    });
  }, []);

  useEffect(() => {
    if (initialSessions && initialSessions.length > 0) setSessionList(initialSessions);
  }, [initialSessions]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    const data = await historyService.getHistory();
    if (data && data.length > 0) setSessionList(data);
    setIsRefreshing(false);
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const es = new EventSource('/api/hr-realtime');
    es.addEventListener('SESSION_STAGE_UPDATED', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const { sessionId, stage } = data;
        if (sessionId && stage) {
          setSessionList((prev) => {
            const idx = prev.findIndex((s) => s.id === sessionId);
            if (idx !== -1) {
              const updated = [...prev];
              updated[idx] = { ...updated[idx], currentStage: stage };
              return updated;
            }
            historyService.getHistory().then((fresh) => {
              if (fresh && fresh.length > 0) setSessionList(fresh);
            });
            return prev;
          });
          const labels: Record<string, string> = {
            CV_JD_MATCHED: 'CV-JD Hoàn Tất',
            QUESTION_BANK_READY: 'Bộ Câu Hỏi Đã Sinh',
            INTERVIEW_IN_PROGRESS: 'Đang Phỏng Vấn',
            COMPLETED: 'Phỏng Vấn Hoàn Tất',
          };
          toast.info(`🔔 ${sessionId.substring(0, 8)}... → ${labels[stage] || stage}`, { duration: 4000 });
        }
      } catch (_) { /* ignore */ }
    });
    es.onerror = () => { /* auto-reconnect */ };
    return () => { es.close(); };
  }, []);

  const filteredList = useMemo(() => {
    let list = [...sessionList];
    if (stageFilter !== 'ALL') {
      list = list.filter((s) => {
        const stage = s.currentStage || (s.status === 'Completed' ? 'COMPLETED' : s.status === 'In progress' ? 'INTERVIEW_IN_PROGRESS' : 'CV_JD_MATCHED');
        return stage === stageFilter;
      });
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((s) =>
        s.id.toLowerCase().includes(q) ||
        (s.roleTitle || '').toLowerCase().includes(q) ||
        (s.roleTypeDetected || '').toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      const da = new Date(a.date).getTime();
      const db = new Date(b.date).getTime();
      return sortOrder === 'newest' ? db - da : da - db;
    });
    return list;
  }, [sessionList, searchQuery, sortOrder, stageFilter]);

  const getStageBadge = (stage?: string, status?: string) => {
    const s = stage || (status === 'Completed' ? 'COMPLETED' : status === 'In progress' ? 'INTERVIEW_IN_PROGRESS' : 'CV_JD_MATCHED');
    switch (s) {
      case 'CV_JD_MATCHED':
        return <Badge className="bg-sky-100 text-sky-800 border-sky-300 gap-1 font-semibold text-[11px]"><Sparkles className="size-3 text-sky-600" /> CV-JD Matched</Badge>;
      case 'QUESTION_BANK_READY':
        return <Badge className="bg-amber-100 text-amber-900 border-amber-300 gap-1 font-semibold text-[11px]"><HelpCircle className="size-3 text-amber-600" /> Bank Ready</Badge>;
      case 'INTERVIEW_IN_PROGRESS':
        return <Badge className="bg-purple-100 text-purple-900 border-purple-300 gap-1 font-semibold text-[11px] animate-pulse"><Radio className="size-3 text-purple-600" /> Live...</Badge>;
      default:
        return <Badge className="bg-emerald-100 text-emerald-900 border-emerald-300 gap-1 font-semibold text-[11px]"><CheckCircle2 className="size-3 text-emerald-600" /> Hoàn tất</Badge>;
    }
  };

  const getMatchBadge = (matchLevel?: string) => {
    if (!matchLevel) return null;
    const m = matchLevel.toLowerCase();
    if (m.includes('high') || m.includes('cao') || m.includes('rất tốt'))
      return <Badge className="bg-emerald-600 text-white font-medium text-[10px]">Cao</Badge>;
    if (m.includes('moderate') || m.includes('khớp') || m.includes('vừa'))
      return <Badge className="bg-blue-600 text-white font-medium text-[10px]">Vừa</Badge>;
    return <Badge variant="destructive" className="text-[10px]">Thấp</Badge>;
  };

  const stageOptions: { value: StageFilter; label: string }[] = [
    { value: 'ALL', label: 'Tất cả giai đoạn' },
    { value: 'CV_JD_MATCHED', label: 'CV-JD Matched' },
    { value: 'QUESTION_BANK_READY', label: 'Bank Ready' },
    { value: 'INTERVIEW_IN_PROGRESS', label: 'Đang phỏng vấn' },
    { value: 'COMPLETED', label: 'Hoàn tất' },
  ];

  return (
    <Card className="overflow-hidden border-slate-200 shadow-sm">
      <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <CardTitle className="text-xl font-bold text-slate-900">Danh Sách Phiên Phỏng Vấn</CardTitle>
            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-ping" /> Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="px-2.5 py-1 text-xs font-semibold text-slate-600">
              {filteredList.length} / {sessionList.length} phiên
            </Badge>
            <button
              onClick={handleRefresh}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <RefreshCw className={`size-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Làm mới
            </button>
          </div>
        </div>

        {/* Filter/Sort Controls */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-400" />
            <Input
              placeholder="Tìm theo ID hoặc vị trí..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-white border-slate-200"
            />
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5">
            <ArrowUpDown className="size-3.5 text-slate-400" />
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              className="text-xs font-medium text-slate-700 bg-transparent focus:outline-none cursor-pointer"
            >
              <option value="newest">Mới nhất trước</option>
              <option value="oldest">Cũ nhất trước</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5">
            <Filter className="size-3.5 text-slate-400" />
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value as StageFilter)}
              className="text-xs font-medium text-slate-700 bg-transparent focus:outline-none cursor-pointer"
            >
              {stageOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {filteredList.length === 0 ? (
          <div className="flex flex-col items-center justify-center space-y-3 py-14 text-center">
            <div className="rounded-full bg-slate-100 p-4 text-slate-400">
              <FileText className="size-8" />
            </div>
            <p className="font-semibold text-slate-700">
              {sessionList.length === 0 ? 'Chưa có phiên phỏng vấn nào' : 'Không tìm thấy phiên khớp bộ lọc'}
            </p>
            <p className="text-sm text-slate-500 max-w-xs">
              {sessionList.length === 0 ? 'Tạo phiên phỏng vấn mới để bắt đầu.' : 'Thử thay đổi bộ lọc hoặc từ khóa tìm kiếm.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-100/60 text-xs uppercase font-semibold text-slate-600">
                <tr>
                  <th className="px-5 py-3">Mã Phiên / Ngày tạo</th>
                  <th className="px-5 py-3">Vị Trí</th>
                  <th className="px-5 py-3">CV / JD</th>
                  <th className="px-5 py-3">Cấp độ & Phù hợp</th>
                  <th className="px-5 py-3">Giai Đoạn</th>
                  <th className="px-5 py-3 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70 bg-white">
                {filteredList.map((session) => (
                  <tr key={session.id} className="transition-colors hover:bg-slate-50/80">
                    <td className="px-5 py-4">
                      <div className="flex flex-col">
                        <span className="font-mono font-bold text-slate-800 text-[11px]">
                          {session.id.length > 16 ? `${session.id.substring(0, 16)}...` : session.id}
                        </span>
                        <span className="mt-1 flex items-center text-[11px] text-slate-500">
                          <Calendar className="mr-1 size-3" />
                          {new Date(session.date).toLocaleDateString('vi-VN', {
                            day: '2-digit', month: '2-digit', year: 'numeric',
                            hour: '2-digit', minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center space-x-2">
                        <Briefcase className="size-3.5 text-brand-orange shrink-0" />
                        <span className="font-semibold text-slate-900 text-xs max-w-[130px] truncate">
                          {session.roleTitle || session.roleTypeDetected || 'Developer'}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-col space-y-0.5 text-[11px] text-slate-600">
                        <span className="truncate max-w-[150px] font-medium" title={session.cvFilename}>
                          📄 {session.cvFilename || 'CV_Upload.pdf'}
                        </span>
                        <span className="truncate max-w-[150px] text-slate-400" title={session.jdFilename}>
                          📋 {session.jdFilename || 'JD_Requirement.pdf'}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap items-center gap-1">
                        {session.candidateLevel && (
                          <Badge variant="outline" className="border-slate-300 text-[10px] px-1.5 py-0">
                            {session.candidateLevel}
                          </Badge>
                        )}
                        {getMatchBadge(session.matchLevel)}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      {getStageBadge(session.currentStage, session.status)}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link href={`/hr-dashboard/${session.id}`}>
                        <Button
                          size="sm"
                          className="bg-brand-orange text-white hover:bg-brand-orange-hover font-semibold shadow-sm gap-1.5 text-xs px-3 inline-flex items-center"
                        >
                          <MessageSquare className="size-3.5" />
                          <span>Chấm điểm AI</span>
                          <ChevronRight className="size-3 opacity-70" />
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
