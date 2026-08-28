'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Star, Award } from 'lucide-react';

interface HrEvaluationFormProps {
  /** Which rating widget to show (determined by the active tab) */
  activeTab?: 'matching' | 'questions' | 'transcript';
  /** Controlled values passed down from shared parent state */
  ratingMatchingAccuracy: number;
  ratingAiRationale: number;
  ratingQuestionQuality: number;
  onRatingMatchingAccuracyChange: (val: number) => void;
  onRatingAiRationaleChange: (val: number) => void;
  onRatingQuestionQualityChange: (val: number) => void;
  /** Set true after the parent has successfully submitted */
  isSubmitted?: boolean;
}

export const HrEvaluationForm: React.FC<HrEvaluationFormProps> = ({
  activeTab = 'matching',
  ratingMatchingAccuracy,
  ratingAiRationale,
  ratingQuestionQuality,
  onRatingMatchingAccuracyChange,
  onRatingAiRationaleChange,
  onRatingQuestionQualityChange,
  isSubmitted = false,
}) => {
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
              disabled={isSubmitted}
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

      <CardContent className="p-6 space-y-6">
        {/* Rating 1: CV-JD Matching Accuracy — shown on matching tab */}
        {activeTab === 'matching' && renderStarRating(
          '1. Đánh giá độ chính xác So khớp CV & JD (CV-JD Matching Accuracy)',
          'Độ chính xác của AI khi phân tích điểm mạnh, khoảng trống kỹ năng và mức độ phù hợp CV-JD (1: Rất kém → 5: Rất chính xác)',
          ratingMatchingAccuracy,
          onRatingMatchingAccuracyChange
        )}

        {/* Ratings 2+3: AI Rationale + Question Quality — shown on questions tab */}
        {activeTab === 'questions' && renderStarRating(
          '2. Đánh giá chất lượng lập luận AI (AI Rationale Rating)',
          'Mức độ hợp lý của lý do AI chọn câu hỏi dựa trên hồ sơ ứng viên (1: Rất kém → 5: Rất tốt)',
          ratingAiRationale,
          onRatingAiRationaleChange
        )}
        {activeTab === 'questions' && renderStarRating(
          '3. Đánh giá chất lượng câu hỏi (Question Quality Rating)',
          'Độ chính xác, độ phân loại và tính thực tế của câu hỏi (1: Không phù hợp → 5: Rất thực tế)',
          ratingQuestionQuality,
          onRatingQuestionQualityChange
        )}
      </CardContent>
    </Card>
  );
};
