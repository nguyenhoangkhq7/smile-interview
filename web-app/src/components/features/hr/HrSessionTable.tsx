'use client';

import React from 'react';
import Link from 'next/link';
import { SessionHistoryItem } from '@/services/historyService';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Search, Calendar, FileText, Briefcase, ChevronRight, Award, AlertTriangle } from 'lucide-react';

interface HrSessionTableProps {
  sessions: SessionHistoryItem[];
}

export const HrSessionTable: React.FC<HrSessionTableProps> = ({ sessions }) => {
  if (!sessions || sessions.length === 0) {
    return (
      <Card className="border-dashed py-12 text-center shadow-none">
        <CardContent className="flex flex-col items-center justify-center space-y-3">
          <div className="rounded-full bg-slate-100 p-4 text-slate-400">
            <FileText className="size-8" />
          </div>
          <CardTitle className="text-lg font-semibold text-slate-700">Chưa có phiên phỏng vấn nào</CardTitle>
          <p className="max-w-md text-sm text-slate-500">
            Chưa có phiên phỏng vấn được khởi tạo trong hệ thống. Hãy tạo phiên phỏng vấn mới để bắt đầu đánh giá AI.
          </p>
        </CardContent>
      </Card>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Completed':
        return <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-emerald-200">Hoàn thành</Badge>;
      case 'In progress':
        return <Badge variant="secondary" className="bg-amber-100 text-amber-700 hover:bg-amber-100 border-amber-200">Đang thực hiện</Badge>;
      default:
        return <Badge variant="outline" className="text-slate-600">Chưa bắt đầu</Badge>;
    }
  };

  const getMatchBadge = (matchLevel?: string) => {
    if (!matchLevel) return null;
    if (matchLevel.toLowerCase().includes('high') || matchLevel.toLowerCase().includes('rất tốt')) {
      return <Badge className="bg-emerald-600 text-white font-medium">Khớp cao</Badge>;
    }
    if (matchLevel.toLowerCase().includes('moderate') || matchLevel.toLowerCase().includes('khớp')) {
      return <Badge className="bg-blue-600 text-white font-medium">Khớp vừa</Badge>;
    }
    return <Badge variant="destructive">Khớp thấp</Badge>;
  };

  return (
    <Card className="overflow-hidden border-slate-200 shadow-sm">
      <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle className="text-xl font-bold text-slate-900">Danh Sách Phiên Phỏng Vấn</CardTitle>
            <p className="mt-1 text-sm text-slate-500">
              Chọn phiên phỏng vấn để kiểm tra ngân hàng câu hỏi AI và thực hiện đánh giá chất lượng (HR Evaluation).
            </p>
          </div>
          <Badge variant="outline" className="px-3 py-1 text-xs font-semibold text-slate-600">
            Tổng cộng: {sessions.length} phiên
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-100/60 text-xs uppercase font-semibold text-slate-600">
              <tr>
                <th className="px-6 py-3.5">Mã Phiên / Ngày tạo</th>
                <th className="px-6 py-3.5">Vị Trí Recruitment</th>
                <th className="px-6 py-3.5">Tài Liệu CV / JD</th>
                <th className="px-6 py-3.5">Level & Phù Hợp</th>
                <th className="px-6 py-3.5">Trạng Thái</th>
                <th className="px-6 py-3.5 text-right">Thao Tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70 bg-white">
              {sessions.map((session) => (
                <tr key={session.id} className="transition-colors hover:bg-slate-50/80">
                  {/* ID / Date */}
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="font-mono font-bold text-slate-800 text-xs">
                        {session.id.length > 18 ? `${session.id.substring(0, 18)}...` : session.id}
                      </span>
                      <span className="mt-1 flex items-center text-xs text-slate-500">
                        <Calendar className="mr-1 size-3.5" />
                        {new Date(session.date).toLocaleDateString('vi-VN', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </td>

                  {/* Role Title */}
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <Briefcase className="size-4 text-brand-orange shrink-0" />
                      <span className="font-semibold text-slate-900">
                        {session.roleTitle || session.roleTypeDetected || 'Developer'}
                      </span>
                    </div>
                  </td>

                  {/* CV / JD Files */}
                  <td className="px-6 py-4">
                    <div className="flex flex-col space-y-1 text-xs text-slate-600">
                      <span className="truncate max-w-[180px] font-medium" title={session.cvFilename}>
                        📄 CV: {session.cvFilename || 'CV_Upload.pdf'}
                      </span>
                      <span className="truncate max-w-[180px] text-slate-500" title={session.jdFilename}>
                        📋 JD: {session.jdFilename || 'JD_Requirement.pdf'}
                      </span>
                    </div>
                  </td>

                  {/* Candidate Level & Match */}
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {session.candidateLevel && (
                        <Badge variant="outline" className="border-slate-300 text-xs">
                          {session.candidateLevel}
                        </Badge>
                      )}
                      {getMatchBadge(session.matchLevel)}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-6 py-4">
                    {getStatusBadge(session.status)}
                  </td>

                  {/* Action */}
                  <td className="px-6 py-4 text-right">
                    <Button
                      size="sm"
                      className="bg-brand-orange text-white hover:bg-brand-orange-hover font-semibold shadow-sm gap-1.5"
                    >
                      <Link href={`/hr-dashboard/${session.id}`} className="inline-flex items-center gap-1.5">
                        <Search className="size-3.5" />
                        <span>Chấm điểm AI</span>
                        <ChevronRight className="size-3.5 ml-0.5 opacity-70" />
                      </Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
