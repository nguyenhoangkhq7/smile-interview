'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Star, Send, CheckCircle2, Lock, MessageSquare, Award } from 'lucide-react';

interface HrEvaluationFormProps {
  sessionId: string;
}

export const HrEvaluationForm: React.FC<HrEvaluationFormProps> = ({ sessionId }) => {
  const [evaluatorName, setEvaluatorName] = useState('');
  const [ratingMatchingAccuracy, setRatingMatchingAccuracy] = useState<number>(5);
  const [ratingAiRationale, setRatingAiRationale] = useState<number>(5);
  const [ratingQuestionQuality, setRatingQuestionQuality] = useState<number>(5);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!sessionId) {
      toast.error('Lỗi: Không tìm thấy mã phiên phỏng vấn (Session ID).');
      return;
    }

    setIsSubmitting(true);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const payload = {
        session_id: sessionId,
        evaluator_name: evaluatorName.trim() || undefined,
        rating_matching_accuracy: ratingMatchingAccuracy,
        rating_ai_rationale: ratingAiRationale,
        rating_question_quality: ratingQuestionQuality,
        feedback_notes: feedbackNotes.trim() || undefined,
      };

      const res = await fetch('/api/hr-evaluations', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.message || 'Gửi đánh giá thất bại');
      }

      setIsSubmitted(true);
      toast.success('Đã gửi đánh giá HR thành công!');
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Đã có lỗi xảy ra khi gửi đánh giá');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStarRating = (
    label: string,
    description: string,
    value: number,
    onChange: (val: number) => void
  ) => {
    return (
      <div className="space-y-2">
        <div>
          <Label className="text-sm font-semibold text-slate-800">{label}</Label>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <div className="flex items-center space-x-1.5">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              disabled={isSubmitting || isSubmitted}
              onClick={() => onChange(star)}
              className={`p-1.5 transition-transform hover:scale-110 focus:outline-none ${
                isSubmitted ? 'cursor-not-allowed opacity-80' : 'cursor-pointer'
              }`}
            >
              <Star
                className={`size-6 ${
                  star <= value
                    ? 'fill-amber-400 text-amber-400'
                    : 'fill-slate-100 text-slate-300 hover:text-amber-300'
                }`}
              />
            </button>
          ))}
          <span className="ml-2 font-mono text-sm font-bold text-slate-700">
            {value} / 5
          </span>
        </div>
      </div>
    );
  };

  if (isSubmitted) {
    return (
      <Card className="border-emerald-200 bg-emerald-50/50 shadow-sm">
        <CardContent className="flex flex-col items-center justify-center p-8 text-center space-y-3">
          <div className="rounded-full bg-emerald-100 p-3 text-emerald-600">
            <CheckCircle2 className="size-8" />
          </div>
          <CardTitle className="text-xl font-bold text-emerald-900">
            Đánh Giá HR Đã Được Lưu Thành Công!
          </CardTitle>
          <CardDescription className="max-w-md text-sm text-emerald-700">
            Cảm ơn bạn đã đóng góp đánh giá về chất lượng câu hỏi AI. Thông tin này sẽ giúp hệ thống liên tục tối ưu hóa mô hình AI.
          </CardDescription>
          <div className="mt-2 inline-flex items-center space-x-1 text-xs font-semibold text-emerald-800 bg-emerald-100/80 px-3 py-1.5 rounded-md">
            <Lock className="size-3.5 mr-1" /> Form đánh giá đã được khóa
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-200 shadow-md">
      <CardHeader className="border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center space-x-2">
          <Award className="size-5 text-brand-orange" />
          <CardTitle className="text-lg font-bold text-slate-900">
            Biểu Mẫu Chấm Điểm AI (HR Evaluation)
          </CardTitle>
        </div>
        <CardDescription className="text-xs text-slate-500">
          Đánh giá chất lượng lập luận AI & mức độ phù hợp của ngân hàng câu hỏi đối với vị trí tuyển dụng.
        </CardDescription>
      </CardHeader>

      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Evaluator Name */}
          <div className="space-y-2">
            <Label htmlFor="evaluatorName" className="text-sm font-semibold text-slate-800">
              Tên Chuyên Viên HR (Evaluator Name)
            </Label>
            <Input
              id="evaluatorName"
              type="text"
              placeholder="Nhập tên của bạn (Ví dụ: Nguyễn Văn A)"
              value={evaluatorName}
              onChange={(e) => setEvaluatorName(e.target.value)}
              disabled={isSubmitting}
              className="bg-white"
            />
          </div>

          {/* Rating 1: CV-JD Matching Accuracy */}
          {renderStarRating(
            '1. Đánh giá độ chính xác So khớp CV & JD (CV-JD Matching Accuracy)',
            'Độ chính xác của AI khi phân tích điểm mạnh, khoảng trống kỹ năng và mức độ phù hợp CV-JD (1: Rất kém -> 5: Rất chính xác)',
            ratingMatchingAccuracy,
            setRatingMatchingAccuracy
          )}

          {/* Rating 2: AI Rationale */}
          {renderStarRating(
            '2. Đánh giá chất lượng lập luận AI (AI Rationale Rating)',
            'Mức độ hợp lý của lý do AI chọn câu hỏi dựa trên hồ sơ ứng viên (1: Rất kém -> 5: Rất tốt)',
            ratingAiRationale,
            setRatingAiRationale
          )}

          {/* Rating 3: Question Quality */}
          {renderStarRating(
            '3. Đánh giá chất lượng câu hỏi (Question Quality Rating)',
            'Độ chính xác, độ phân loại và tính thực tế của câu hỏi (1: Không phù hợp -> 5: Rất thực tế)',
            ratingQuestionQuality,
            setRatingQuestionQuality
          )}

          {/* Feedback Notes */}
          <div className="space-y-2">
            <Label htmlFor="feedbackNotes" className="text-sm font-semibold text-slate-800">
              Ghi Chú & Nhận Xét Bổ Sung (Feedback Notes)
            </Label>
            <Textarea
              id="feedbackNotes"
              rows={4}
              placeholder="Nhập góp ý hoặc ghi chú bổ sung về ngân hàng câu hỏi..."
              value={feedbackNotes}
              onChange={(e) => setFeedbackNotes(e.target.value)}
              disabled={isSubmitting}
              className="bg-white"
            />
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-brand-orange text-white hover:bg-brand-orange-hover font-bold py-2.5 shadow-sm gap-2"
          >
            {isSubmitting ? (
              <>
                <span className="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Đang gửi đánh giá...</span>
              </>
            ) : (
              <>
                <Send className="size-4" />
                <span>Gửi Đánh Giá HR</span>
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};
