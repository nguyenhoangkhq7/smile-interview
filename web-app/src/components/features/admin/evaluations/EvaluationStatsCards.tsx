import React from 'react';
import { HrEvaluationAdminItem } from './types';
import { Card, CardContent } from '@/components/ui/card';
import { Star, ClipboardCheck, Bot, Award, TrendingUp, Target } from 'lucide-react';

interface EvaluationStatsCardsProps {
  evaluations: HrEvaluationAdminItem[];
}

export const EvaluationStatsCards: React.FC<EvaluationStatsCardsProps> = ({ evaluations = [] }) => {
  const totalCount = evaluations.length;

  const matchingScores = evaluations
    .map((e) => e.rating_matching_accuracy)
    .filter((s): s is number => typeof s === 'number' && s > 0);
  const avgMatching =
    matchingScores.length > 0
      ? (matchingScores.reduce((acc, curr) => acc + curr, 0) / matchingScores.length).toFixed(1)
      : '0.0';

  const rationaleScores = evaluations
    .map((e) => e.rating_ai_rationale)
    .filter((s): s is number => typeof s === 'number' && s > 0);
  const avgRationale =
    rationaleScores.length > 0
      ? (rationaleScores.reduce((acc, curr) => acc + curr, 0) / rationaleScores.length).toFixed(1)
      : '0.0';

  const qualityScores = evaluations
    .map((e) => e.rating_question_quality)
    .filter((s): s is number => typeof s === 'number' && s > 0);
  const avgQuality =
    qualityScores.length > 0
      ? (qualityScores.reduce((acc, curr) => acc + curr, 0) / qualityScores.length).toFixed(1)
      : '0.0';

  const renderStars = (scoreStr: string) => {
    const scoreNum = parseFloat(scoreStr);
    return (
      <div className="flex items-center space-x-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`size-4 ${
              star <= Math.round(scoreNum)
                ? 'fill-amber-400 text-amber-400'
                : 'fill-slate-800 text-slate-700'
            }`}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* Card 1: Total Evaluations */}
      <Card className="overflow-hidden border border-white/10 bg-slate-900/90 text-white shadow-lg backdrop-blur-md">
        <CardContent className="p-5 flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Tổng Số Đánh Giá HR
            </p>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white">{totalCount}</span>
              <span className="text-xs text-slate-400">lượt chấm điểm</span>
            </div>
            <p className="text-[11px] text-emerald-400 flex items-center gap-1 font-medium">
              <TrendingUp className="size-3" /> Thu thập từ HR Validation
            </p>
          </div>
          <div className="flex size-12 items-center justify-center rounded-2xl bg-orange-500/10 text-orange-400 border border-orange-500/20 shadow-inner">
            <ClipboardCheck className="size-6" />
          </div>
        </CardContent>
      </Card>

      {/* Card 2: Avg Matching Accuracy Score */}
      <Card className="overflow-hidden border border-white/10 bg-slate-900/90 text-white shadow-lg backdrop-blur-md">
        <CardContent className="p-5 flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Điểm So Khớp CV-JD
            </p>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-blue-400">{avgMatching}</span>
              <span className="text-xs text-slate-400">/ 5.0 sao</span>
            </div>
            {renderStars(avgMatching)}
          </div>
          <div className="flex size-12 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-inner">
            <Target className="size-6" />
          </div>
        </CardContent>
      </Card>

      {/* Card 3: Avg AI Rationale Score */}
      <Card className="overflow-hidden border border-white/10 bg-slate-900/90 text-white shadow-lg backdrop-blur-md">
        <CardContent className="p-5 flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Điểm Lập Luận AI
            </p>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-amber-400">{avgRationale}</span>
              <span className="text-xs text-slate-400">/ 5.0 sao</span>
            </div>
            {renderStars(avgRationale)}
          </div>
          <div className="flex size-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-inner">
            <Bot className="size-6" />
          </div>
        </CardContent>
      </Card>

      {/* Card 4: Avg Question Quality Score */}
      <Card className="overflow-hidden border border-white/10 bg-slate-900/90 text-white shadow-lg backdrop-blur-md">
        <CardContent className="p-5 flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Chất Lượng Câu Hỏi AI
            </p>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-emerald-400">{avgQuality}</span>
              <span className="text-xs text-slate-400">/ 5.0 sao</span>
            </div>
            {renderStars(avgQuality)}
          </div>
          <div className="flex size-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-inner">
            <Award className="size-6" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
