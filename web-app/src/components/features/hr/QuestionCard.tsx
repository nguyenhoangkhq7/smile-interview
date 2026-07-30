import React from 'react';
import { QuestionItem } from './types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { HelpCircle, Lightbulb, Code2, Server, MessageSquare, Tag, CheckSquare } from 'lucide-react';

interface QuestionCardProps {
  question: QuestionItem;
  index: number;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({ question, index }) => {
  const getTypeBadge = (type?: string) => {
    switch (type?.toLowerCase()) {
      case 'behavioural':
      case 'behavioral':
        return (
          <Badge className="bg-purple-100 text-purple-800 border-purple-200 hover:bg-purple-100 gap-1">
            <MessageSquare className="size-3" /> Hành vi (Behavioral)
          </Badge>
        );
      case 'coding':
        return (
          <Badge className="bg-blue-100 text-blue-800 border-blue-200 hover:bg-blue-100 gap-1">
            <Code2 className="size-3" /> Lập trình (Coding)
          </Badge>
        );
      case 'system_design':
        return (
          <Badge className="bg-indigo-100 text-indigo-800 border-indigo-200 hover:bg-indigo-100 gap-1">
            <Server className="size-3" /> Thiết kế hệ thống (System Design)
          </Badge>
        );
      default:
        return (
          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 hover:bg-emerald-100 gap-1">
            <HelpCircle className="size-3" /> Kỹ thuật (Technical)
          </Badge>
        );
    }
  };

  const getDifficultyBadge = (difficulty?: string) => {
    switch (difficulty?.toLowerCase()) {
      case 'hard':
        return <Badge variant="destructive">Khó (Hard)</Badge>;
      case 'medium':
        return <Badge variant="secondary" className="bg-amber-100 text-amber-800 border-amber-300">Trung bình (Medium)</Badge>;
      default:
        return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 border-emerald-300">Dễ (Easy)</Badge>;
    }
  };

  return (
    <Card className="overflow-hidden border-slate-200 shadow-sm transition-all hover:shadow-md">
      <CardHeader className="bg-slate-50/60 border-b border-slate-100 py-3.5 px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2.5">
            <span className="flex size-7 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white font-mono">
              {question.id || `Q${String(index + 1).padStart(3, '0')}`}
            </span>
            {question.topic && (
              <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">
                <Tag className="size-3 text-slate-400" />
                {question.topic}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {getTypeBadge(question.type)}
            {getDifficultyBadge(question.difficulty)}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-4">
        {/* Main Question Text */}
        <div>
          <p className="text-base font-semibold leading-relaxed text-slate-900 whitespace-pre-line">
            {question.question}
          </p>
        </div>

        {/* Behavioural STAR Prompt */}
        {question.star_prompt && (
          <div className="rounded-lg border border-purple-200 bg-purple-50/60 p-3.5 text-xs text-purple-900 space-y-1">
            <p className="font-bold flex items-center gap-1 text-purple-800">
              <MessageSquare className="size-3.5 text-purple-600" /> Khung Đánh Giá S.T.A.R:
            </p>
            <p className="leading-relaxed">{question.star_prompt}</p>
          </div>
        )}

        {/* Coding / Technical Hints */}
        {question.hints && question.hints.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3.5 text-xs text-amber-900 space-y-1.5">
            <p className="font-bold flex items-center gap-1 text-amber-800">
              <Lightbulb className="size-3.5 text-amber-600" /> Gợi Ý / Thuật Toán Đánh Giá (Hints):
            </p>
            <ul className="list-disc list-inside space-y-1 text-amber-950">
              {question.hints.map((hint, hIdx) => (
                <li key={hIdx}>{hint}</li>
              ))}
            </ul>
          </div>
        )}

        {/* System Design Components to Cover */}
        {question.components_to_cover && question.components_to_cover.length > 0 && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-3.5 text-xs text-indigo-900 space-y-2">
            <p className="font-bold flex items-center gap-1 text-indigo-800">
              <CheckSquare className="size-3.5 text-indigo-600" /> Thành Phần Cần Yêu Cầu Trả Lời (Components):
            </p>
            <div className="flex flex-wrap gap-1.5">
              {question.components_to_cover.map((comp, cIdx) => (
                <Badge key={cIdx} variant="outline" className="bg-white border-indigo-300 text-indigo-700 text-xs">
                  {comp}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
