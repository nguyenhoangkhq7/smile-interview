'use client';

import React, { useState } from 'react';
import { QuestionFeedback } from '@/services/historyService';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import {
  MessageSquare,
  User,
  Bot,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Search,
  Star,
  Send,
} from 'lucide-react';

interface InterviewTranscriptViewProps {
  questions: QuestionFeedback[];
  sessionId?: string;
}

const TurnCardItem: React.FC<{
  q: QuestionFeedback;
  idx: number;
  sessionId?: string;
}> = ({ q, idx, sessionId }) => {
  const [rating, setRating] = useState<number>(q.hrRating || 5);
  const [feedback, setFeedback] = useState<string>(q.hrFeedback || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSaved, setIsSaved] = useState<boolean>(Boolean(q.hrRating || q.hrFeedback));

  const handleSaveTurnEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId) {
      toast.error('Lỗi: Không tìm thấy mã phiên phỏng vấn.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/turn-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          turnId: q.id,
          turnIndex: idx,
          hrRating: rating,
          hrFeedback: feedback.trim() || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Lỗi khi lưu đánh giá lượt');
      }

      setIsSaved(true);
      toast.success(`Đã lưu đánh giá & nhận xét cho lượt câu hỏi #${idx + 1}!`);
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Lỗi khi kết nối server');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card
      className={`border-slate-200 shadow-sm transition-all overflow-hidden min-w-0 w-full ${
        q.isDeepDive ? 'border-l-4 border-l-purple-500 bg-purple-50/20' : 'bg-white'
      }`}
    >
      {/* Turn Header */}
      <CardHeader className="bg-slate-50/70 border-b border-slate-100 py-3 px-5 flex flex-wrap items-center justify-between gap-2 min-w-0">
        <div className="flex items-center space-x-2 flex-wrap gap-1 min-w-0">
          <span className="flex size-6 items-center justify-center rounded-md bg-slate-900 text-xs font-bold text-white font-mono shrink-0">
            #{idx + 1}
          </span>
          {q.topicTag && (
            <Badge variant="outline" className="bg-white text-slate-700 border-slate-300 text-xs whitespace-normal break-words max-w-full">
              {q.topicTag}
            </Badge>
          )}
          {q.isDeepDive && (
            <Badge className="bg-purple-100 text-purple-800 border-purple-200 text-xs gap-1 shrink-0">
              <Search className="size-3 text-purple-600" /> Hỏi Sâu (Deep Dive)
            </Badge>
          )}
        </div>

        {(() => {
          if (q.score === undefined || q.score === null) return null;
          const displayScore = q.score > 0 && q.score <= 10 ? Math.round(q.score * 10) : q.score;
          return (
            <div className="flex items-center space-x-1.5 bg-white px-3 py-1 rounded-lg border border-slate-200 shrink-0">
              <span className="text-[11px] font-semibold text-slate-500">Điểm lượt:</span>
              <span
                className={`text-xs font-bold ${
                  displayScore >= 80 ? 'text-emerald-600' : displayScore >= 60 ? 'text-amber-600' : 'text-rose-600'
                }`}
              >
                {displayScore}/100
              </span>
            </div>
          );
        })()}
      </CardHeader>

      <CardContent className="p-5 space-y-4 min-w-0">
        {/* AI Question */}
        <div className="flex items-start space-x-3 bg-indigo-50/50 p-3.5 rounded-xl border border-indigo-100 min-w-0">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white mt-0.5">
            <Bot className="size-4" />
          </div>
          <div className="space-y-0.5 min-w-0 flex-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 block">
              Câu hỏi từ AI Interviewer
            </span>
            <p className="text-sm font-semibold text-slate-900 leading-relaxed break-words whitespace-pre-wrap">
              {q.question}
            </p>
          </div>
        </div>

        {/* Candidate Answer */}
        <div className="flex items-start space-x-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200 min-w-0">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-white mt-0.5">
            <User className="size-4" />
          </div>
          <div className="space-y-0.5 min-w-0 flex-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
              Câu trả lời của Ứng viên (Speech-to-Text)
            </span>
            <p className="text-sm text-slate-800 leading-relaxed font-mono whitespace-pre-wrap break-words">
              {q.answer || '(Ứng viên chưa nhập / ghi âm câu trả lời)'}
            </p>
          </div>
        </div>

        {/* AI Analysis & Feedback */}
        {(q.strengths || q.improvements || q.suggestedAnswer) && (
          <div className="grid gap-3 pt-2 sm:grid-cols-2 min-w-0">
            {q.strengths && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 text-xs text-emerald-950 space-y-1 min-w-0">
                <span className="font-bold flex items-center gap-1 text-emerald-800">
                  <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" /> Điểm Mạnh Trong Lời Đáp:
                </span>
                <p className="leading-relaxed break-words">{q.strengths}</p>
              </div>
            )}

            {q.improvements && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-xs text-amber-950 space-y-1 min-w-0">
                <span className="font-bold flex items-center gap-1 text-amber-800">
                  <AlertCircle className="size-3.5 text-amber-600 shrink-0" /> Điểm Cần Cải Thiện:
                </span>
                <p className="leading-relaxed break-words">{q.improvements}</p>
              </div>
            )}

            {q.suggestedAnswer && (
              <div className="sm:col-span-2 rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-950 space-y-1 min-w-0">
                <span className="font-bold flex items-center gap-1 text-blue-800">
                  <Lightbulb className="size-3.5 text-blue-600 shrink-0" /> Gợi Ý Câu Trả Lời Chuẩn Mẫu (Best Practice):
                </span>
                <p className="leading-relaxed font-mono break-words whitespace-pre-wrap">{q.suggestedAnswer}</p>
              </div>
            )}
          </div>
        )}

        {/* HR Evaluation for this specific Q&A turn */}
        <div className="mt-4 pt-4 border-t border-slate-200 bg-slate-50/70 p-4 rounded-xl space-y-3 min-w-0">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
              <Star className="size-4 text-amber-500 fill-amber-400" />
              Đánh Giá & Nhận Xét Lượt #{idx + 1} (HR Turn Review)
            </span>
            {isSaved && (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-md border border-emerald-200">
                <CheckCircle2 className="size-3 text-emerald-600" /> Đã lưu nhận xét
              </span>
            )}
          </div>

          <form onSubmit={handleSaveTurnEvaluation} className="space-y-3">
            <div className="flex items-center space-x-2">
              <span className="text-xs text-slate-600 font-medium">Chấm điểm lượt:</span>
              <div className="flex items-center space-x-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    className="p-1 hover:scale-110 transition-transform focus:outline-none cursor-pointer"
                  >
                    <Star
                      className={`size-5 ${
                        star <= rating
                          ? 'fill-amber-400 text-amber-400'
                          : 'fill-slate-100 text-slate-300 hover:text-amber-300'
                      }`}
                    />
                  </button>
                ))}
              </div>
              <span className="font-mono text-xs font-bold text-slate-700">{rating} / 5 điểm</span>
            </div>

            <Textarea
              rows={2}
              placeholder={`Nhập nhận xét / ghi chú của HR riêng cho cặp câu hỏi - đáp án #${idx + 1}...`}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              className="bg-white text-xs border-slate-200 focus:border-indigo-400 resize-y"
            />

            <div className="flex justify-end">
              <Button
                type="submit"
                size="sm"
                disabled={isSubmitting}
                className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold gap-1.5 h-8 px-3"
              >
                {isSubmitting ? (
                  <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <Send className="size-3.5" />
                )}
                <span>Lưu Nhận Xét Lượt #{idx + 1}</span>
              </Button>
            </div>
          </form>
        </div>
      </CardContent>
    </Card>
  );
};

export const InterviewTranscriptView: React.FC<InterviewTranscriptViewProps> = ({
  questions = [],
  sessionId,
}) => {
  if (!questions || questions.length === 0) {
    return (
      <Card className="border-slate-200 bg-white p-8 text-center min-w-0 w-full">
        <CardContent className="space-y-3">
          <MessageSquare className="mx-auto size-10 text-slate-400" />
          <h4 className="text-base font-bold text-slate-800">Chưa Có Dữ Liệu Đối Thoại Phỏng Vấn</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Phiên phỏng vấn này chưa có dữ liệu ghi âm / đối thoại lượt trả lời trực tiếp của ứng viên với AI.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 min-w-0 w-full">
      {/* Banner */}
      <Card className="border-indigo-200 bg-gradient-to-r from-indigo-50/80 via-slate-50 to-purple-50/40 p-5 shadow-sm min-w-0">
        <div className="flex items-center space-x-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shrink-0">
            <MessageSquare className="size-5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-bold text-slate-900">
              Nhật Ký Quá Trình Phỏng Vấn & Đánh Giá Từng Câu Trả Lời
            </h3>
            <p className="text-xs text-slate-600">
              Tổng số lượt hỏi đáp: <strong>{questions.length} câu hỏi</strong> | Cho phép HR chấm điểm & ghi chú trực tiếp cho mỗi cặp câu hỏi - đáp án.
            </p>
          </div>
        </div>
      </Card>

      {/* Questions & Responses List */}
      <div className="space-y-5 min-w-0">
        {questions.map((q, idx) => (
          <TurnCardItem key={q.id || idx} q={q} idx={idx} sessionId={sessionId} />
        ))}
      </div>
    </div>
  );
};

