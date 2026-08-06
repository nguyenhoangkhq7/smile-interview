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
      case 'cao':
      case 'eligible':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'low':
      case 'thấp':
      case 'ineligible':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      default:
        return 'bg-sky-100 text-sky-800 border-sky-300';
    }
  };

  return (
    <Card className="overflow-hidden border border-slate-200 bg-white text-slate-900 shadow-sm">
      <CardContent className="p-6 space-y-5">
        {/* Header Badges */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-orange-50 text-brand-orange ring-1 ring-orange-200">
              <Bot className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                Bối Cảnh Đánh Giá Phỏng Vấn AI
                <Sparkles className="size-4 text-amber-500" />
              </h2>
              <p className="text-xs text-slate-500">Tóm tắt phân tích CV/JD & Ngữ cảnh sinh câu hỏi tự động</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-700 gap-1 px-3 py-1 font-medium">
              <Layers className="size-3.5 text-blue-600" />
              <span>Vị trí: <strong>{role_type}</strong></span>
            </Badge>

            <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-700 gap-1 px-3 py-1 font-medium">
              <UserCheck className="size-3.5 text-emerald-600" />
              <span>Cấp độ: <strong>{candidate_level}</strong></span>
            </Badge>

            <Badge className={`border gap-1 px-3 py-1 font-semibold ${getMatchColor(overall_match)}`}>
              <span>Khớp CV-JD: <strong>{overall_match.toUpperCase()}</strong></span>
            </Badge>
          </div>
        </div>

        {/* Strong Areas & Gap Areas */}
        <div className="grid gap-4 md:grid-cols-2 min-w-0 w-full overflow-hidden">
          {/* Strong Areas */}
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 min-w-0 w-full overflow-hidden">
            <div className="mb-2 flex items-center space-x-2 text-emerald-700 font-semibold text-xs uppercase tracking-wide">
              <CheckCircle2 className="size-4 shrink-0" />
              <span>Điểm Mạnh / Kỹ Năng Tương Thích ({strong_areas.length})</span>
            </div>
            {strong_areas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 min-w-0">
                {strong_areas.map((area, idx) => (
                  <Badge
                    key={idx}
                    variant="outline"
                    className="bg-emerald-100/90 text-emerald-900 border-emerald-300/80 text-xs whitespace-normal break-words max-w-full inline-flex items-start text-left py-1 px-2.5 h-auto font-medium leading-tight"
                  >
                    <span className="break-words min-w-0">{area}</span>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Không tìm thấy điểm mạnh nổi bật.</p>
            )}
          </div>

          {/* Gap Areas */}
          <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4 min-w-0 w-full overflow-hidden">
            <div className="mb-2 flex items-center space-x-2 text-rose-700 font-semibold text-xs uppercase tracking-wide">
              <AlertCircle className="size-4 shrink-0" />
              <span>Hạn Chế / Kỹ Năng Cần Kiểm Tra ({gap_areas.length})</span>
            </div>
            {gap_areas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 min-w-0">
                {gap_areas.map((area, idx) => (
                  <Badge
                    key={idx}
                    variant="outline"
                    className="bg-rose-100/90 text-rose-900 border-rose-300/80 text-xs whitespace-normal break-words max-w-full inline-flex items-start text-left py-1 px-2.5 h-auto font-medium leading-tight"
                  >
                    <span className="break-words min-w-0">{area}</span>
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
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 min-w-0 w-full overflow-hidden">
            <p className="mb-1 text-xs font-semibold text-amber-800 uppercase tracking-wide flex items-center gap-1.5">
              <Sparkles className="size-3.5" /> Lý Do AI Đề Xuất Cấu Trúc Câu Hỏi (Rationale):
            </p>
            <p className="text-sm leading-relaxed text-slate-800 font-normal italic">
              &quot;{generation_rationale}&quot;
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
