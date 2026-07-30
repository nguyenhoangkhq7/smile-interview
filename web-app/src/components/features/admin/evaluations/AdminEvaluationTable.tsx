'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { HrEvaluationAdminItem } from './types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Star, Calendar, User, ExternalLink, MessageSquare, Search, FileText } from 'lucide-react';

interface AdminEvaluationTableProps {
  evaluations: HrEvaluationAdminItem[];
}

export const AdminEvaluationTable: React.FC<AdminEvaluationTableProps> = ({ evaluations = [] }) => {
  const [selectedNotes, setSelectedNotes] = useState<{
    evaluator: string;
    notes: string;
    sessionId: string;
  } | null>(null);

  const renderStarRating = (rating?: number | null) => {
    if (rating === undefined || rating === null) {
      return <span className="text-xs text-slate-500 italic">Chưa đánh giá</span>;
    }

    return (
      <div className="flex items-center space-x-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`size-3.5 ${
              star <= rating
                ? 'fill-amber-400 text-amber-400'
                : 'fill-slate-800 text-slate-700'
            }`}
          />
        ))}
        <span className="ml-1 text-xs font-mono font-bold text-slate-300">
          {rating}/5
        </span>
      </div>
    );
  };

  if (!evaluations || evaluations.length === 0) {
    return (
      <Card className="border border-white/10 bg-slate-900/90 py-12 text-center shadow-lg backdrop-blur-md">
        <CardContent className="flex flex-col items-center justify-center space-y-3">
          <div className="rounded-full bg-slate-800 p-4 text-slate-400">
            <FileText className="size-8" />
          </div>
          <CardTitle className="text-lg font-semibold text-white">
            Chưa Có Đánh Giá Nào Từ HR
          </CardTitle>
          <p className="max-w-md text-sm text-slate-400">
            Hệ thống chưa ghi nhận lượt đánh giá thực nghiệm nào từ các chuyên viên HR. Dữ liệu sẽ tự động xuất hiện tại đây khi có đánh giá mới.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="overflow-hidden border border-white/10 bg-slate-900/90 text-white shadow-xl backdrop-blur-md">
        <CardHeader className="border-b border-white/10 bg-slate-950/60 pb-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="text-xl font-bold text-white flex items-center gap-2">
                <Search className="size-5 text-orange-400" />
                Kết Quả Đánh Giá Chi Tiết Từ HR (Validation Log)
              </CardTitle>
              <p className="mt-1 text-xs text-slate-400">
                Bảng ghi chú và chấm điểm định lượng/định tính đối với ngân hàng câu hỏi AI và độ chính xác so khớp CV-JD.
              </p>
            </div>
            <Badge variant="outline" className="border-orange-500/30 bg-orange-500/10 text-orange-400 font-semibold px-3 py-1">
              {evaluations.length} bản ghi
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-slate-950/80 text-xs uppercase font-semibold text-slate-400">
                <tr>
                  <th className="px-5 py-3.5">Mã Phiên (Session ID)</th>
                  <th className="px-5 py-3.5">Người Đánh Giá (HR)</th>
                  <th className="px-5 py-3.5">Độ Chính Xác So Khớp</th>
                  <th className="px-5 py-3.5">Đánh Giá Lập Luận AI</th>
                  <th className="px-5 py-3.5">Chất Lượng Câu Hỏi</th>
                  <th className="px-5 py-3.5">Thời Gian</th>
                  <th className="px-5 py-3.5 text-right">Ghi Chú Feedback</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 bg-slate-900/60">
                {evaluations.map((item) => (
                  <tr key={item.id} className="transition-colors hover:bg-white/[0.02]">
                    {/* Session ID */}
                    <td className="px-5 py-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-bold text-slate-200">
                          {item.session_id.length > 14
                            ? `${item.session_id.substring(0, 14)}...`
                            : item.session_id}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          className="text-slate-400 hover:text-orange-400"
                          title="Xem chi tiết phiên HR"
                        >
                          <Link href={`/hr-dashboard/${item.session_id}`} target="_blank">
                            <ExternalLink className="size-3.5" />
                          </Link>
                        </Button>
                      </div>
                    </td>

                    {/* Evaluator Name */}
                    <td className="px-5 py-4">
                      <div className="flex items-center space-x-2">
                        <User className="size-4 text-slate-400" />
                        <span className="font-medium text-slate-200">
                          {item.evaluator_name || 'HR Anonymous'}
                        </span>
                      </div>
                    </td>

                    {/* CV-JD Matching Rating */}
                    <td className="px-5 py-4">
                      {renderStarRating(item.rating_matching_accuracy)}
                    </td>

                    {/* AI Rationale Rating */}
                    <td className="px-5 py-4">
                      {renderStarRating(item.rating_ai_rationale)}
                    </td>

                    {/* Question Quality Rating */}
                    <td className="px-5 py-4">
                      {renderStarRating(item.rating_question_quality)}
                    </td>

                    {/* Created At */}
                    <td className="px-5 py-4">
                      <span className="flex items-center text-xs text-slate-400">
                        <Calendar className="mr-1.5 size-3.5 text-slate-500" />
                        {new Date(item.created_at).toLocaleDateString('vi-VN', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </td>

                    {/* Feedback Notes */}
                    <td className="px-5 py-4 text-right">
                      {item.feedback_notes ? (
                        <div className="flex items-center justify-end space-x-2">
                          <span className="max-w-[140px] truncate text-xs text-slate-300 italic" title={item.feedback_notes}>
                            &quot;{item.feedback_notes}&quot;
                          </span>
                          <Button
                            variant="outline"
                            size="xs"
                            className="border-white/10 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                            onClick={() =>
                              setSelectedNotes({
                                evaluator: item.evaluator_name || 'HR Anonymous',
                                notes: item.feedback_notes || '',
                                sessionId: item.session_id,
                              })
                            }
                          >
                            <MessageSquare className="mr-1 size-3" /> Xem đầy đủ
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500 italic">Không có ghi chú</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Expandable Feedback Dialog */}
      <Dialog open={!!selectedNotes} onOpenChange={() => setSelectedNotes(null)}>
        <DialogContent className="border-white/10 bg-slate-900 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-bold text-white">
              <MessageSquare className="size-5 text-orange-400" />
              Chi Tiết Ghi Chú Đánh Giá HR
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400">
              Đánh giá từ chuyên viên: <strong>{selectedNotes?.evaluator}</strong>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div className="rounded-lg border border-white/10 bg-slate-950 p-4">
              <p className="text-xs font-semibold uppercase text-slate-400 mb-1">Mã phiên:</p>
              <p className="font-mono text-xs font-bold text-orange-400">{selectedNotes?.sessionId}</p>
            </div>

            <div className="rounded-lg border border-white/10 bg-slate-950 p-4">
              <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Nội dung phản hồi (Feedback Notes):</p>
              <p className="text-sm leading-relaxed text-slate-200 whitespace-pre-line">
                {selectedNotes?.notes}
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
