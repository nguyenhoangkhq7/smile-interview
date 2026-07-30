import React from 'react';
import { QuestionBankMetadata } from './types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Bot, CheckCircle2, AlertCircle, Sparkles, Layers, UserCheck } from 'lucide-react';

interface AiContextBannerProps {
  metadata?: QuestionBankMetadata;
}

export const AiContextBanner: React.FC<AiContextBannerProps> = ({ metadata }) => {
  if (!metadata) {
    return (
      <Card className="border-amber-200 bg-amber-50/50 p-4">
        <p className="text-sm text-amber-800">Không tìm thấy thông tin bối cảnh AI (Metadata).</p>
      </Card>
    );
  }

  const {
    role_type = 'FULLSTACK',
    candidate_level = 'JUNIOR',
    overall_match = 'medium',
    strong_areas = [],
    gap_areas = [],
    total_questions = 0,
    generation_rationale = '',
  } = metadata;

  const getMatchColor = (match?: string) => {
    switch (match?.toLowerCase()) {
      case 'high':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'low':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      default:
        return 'bg-amber-100 text-amber-800 border-amber-300';
    }
  };

  return (
    <Card className="overflow-hidden border-slate-200 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white shadow-md">
      <CardContent className="p-6 space-y-5">
        {/* Header Badges */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/60 pb-4">
          <div className="flex items-center space-x-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-brand-orange/20 text-brand-orange ring-1 ring-brand-orange/30">
              <Bot className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Bối Cảnh Đánh Giá Phỏng Vấn AI
                <Sparkles className="size-4 text-amber-400" />
              </h2>
              <p className="text-xs text-slate-400">Tóm tắt phân tích CV/JD & Ngữ cảnh sinh câu hỏi tự động</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-slate-700 bg-slate-800/80 text-slate-200 gap-1 px-3 py-1">
              <Layers className="size-3.5 text-blue-400" />
              <span>Vị trí: <strong>{role_type}</strong></span>
            </Badge>

            <Badge variant="outline" className="border-slate-700 bg-slate-800/80 text-slate-200 gap-1 px-3 py-1">
              <UserCheck className="size-3.5 text-emerald-400" />
              <span>Cấp độ: <strong>{candidate_level}</strong></span>
            </Badge>

            <Badge className={`border gap-1 px-3 py-1 font-semibold ${getMatchColor(overall_match)}`}>
              <span>Khớp CV-JD: <strong>{overall_match.toUpperCase()}</strong></span>
            </Badge>
          </div>
        </div>

        {/* Strong Areas & Gap Areas */}
        <div className="grid gap-4 md:grid-cols-2">
          {/* Strong Areas */}
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4">
            <div className="mb-2 flex items-center space-x-2 text-emerald-400 font-semibold text-xs uppercase tracking-wide">
              <CheckCircle2 className="size-4" />
              <span>Điểm Mạnh / Kỹ Năng Tương Thích ({strong_areas.length})</span>
            </div>
            {strong_areas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {strong_areas.map((area, idx) => (
                  <Badge key={idx} variant="secondary" className="bg-emerald-900/60 text-emerald-200 border-emerald-700/50 text-xs">
                    {area}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Không tìm thấy điểm mạnh nổi bật.</p>
            )}
          </div>

          {/* Gap Areas */}
          <div className="rounded-xl border border-rose-500/20 bg-rose-950/20 p-4">
            <div className="mb-2 flex items-center space-x-2 text-rose-400 font-semibold text-xs uppercase tracking-wide">
              <AlertCircle className="size-4" />
              <span>Hạn Chế / Kỹ Năng Cần Kiểm Tra ({gap_areas.length})</span>
            </div>
            {gap_areas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {gap_areas.map((area, idx) => (
                  <Badge key={idx} variant="secondary" className="bg-rose-900/60 text-rose-200 border-rose-700/50 text-xs">
                    {area}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Không có thiếu sót kỹ năng lớn.</p>
            )}
          </div>
        </div>

        {/* Generation Rationale Callout */}
        {generation_rationale && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
            <p className="mb-1 text-xs font-semibold text-amber-400 uppercase tracking-wide flex items-center gap-1.5">
              <Sparkles className="size-3.5" /> Lý Do AI Đề Xuất Cấu Trúc Câu Hỏi (Rationale):
            </p>
            <p className="text-sm leading-relaxed text-slate-200 font-normal italic">
              &quot;{generation_rationale}&quot;
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
