import React from 'react';
import { QuestionItem } from './types';
import { QuestionCard } from './QuestionCard';
import { Badge } from '@/components/ui/badge';
import { HelpCircle } from 'lucide-react';

interface QuestionCardListProps {
  questions?: QuestionItem[];
}

export const QuestionCardList: React.FC<QuestionCardListProps> = ({ questions = [] }) => {
  if (!questions || questions.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
        <HelpCircle className="mx-auto size-8 text-slate-400 mb-2" />
        <p className="font-semibold">Chưa có câu hỏi nào trong ngân hàng này.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Section Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center space-x-2">
          <h3 className="text-lg font-bold text-slate-900">
            Ngân Hàng Câu Hỏi AI Tạo Tự Động
          </h3>
          <Badge className="bg-brand-orange text-white font-semibold">
            {questions.length} câu
          </Badge>
        </div>
        <span className="text-xs text-slate-500 font-medium">
          Dựa trên ma trận thiếu hụt kỹ năng CV-JD
        </span>
      </div>

      {/* Cards List */}
      <div className="space-y-4">
        {questions.map((q, idx) => (
          <QuestionCard key={q.id || idx} question={q} index={idx} />
        ))}
      </div>
    </div>
  );
};
