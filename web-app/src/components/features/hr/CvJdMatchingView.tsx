'use client';

import React, { useState } from 'react';
import { SessionHistoryItem } from '@/services/historyService';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  FileText,
  Briefcase,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Award,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-react';

interface CvJdMatchingViewProps {
  session: SessionHistoryItem | null;
}

export const CvJdMatchingView: React.FC<CvJdMatchingViewProps> = ({ session }) => {
  const [cvExpanded, setCvExpanded] = useState(true);
  const [jdExpanded, setJdExpanded] = useState(true);

  if (!session) {
    return (
      <Card className="border-slate-200 bg-white p-8 text-center">
        <CardContent className="space-y-2">
          <FileText className="mx-auto size-8 text-slate-400" />
          <h4 className="font-semibold text-slate-700">Chưa có thông tin So khớp CV & JD</h4>
          <p className="text-xs text-slate-500">
            Dữ liệu phân tích so khớp CV-JD cho phiên này chưa sẵn sàng.
          </p>
        </CardContent>
      </Card>
    );
  }

  const strongAreas = Array.isArray(session.strongAreas) ? session.strongAreas : [];
  const gapAreas = Array.isArray(session.gapAreas) ? session.gapAreas : [];
  const missingSkills = Array.isArray(session.criticalMissingSkills) ? session.criticalMissingSkills : [];

  return (
    <div className="space-y-6">
      {/* 1. TOP SECTION: CV & JD Original Text (Full view by default) */}
      <div className="grid gap-6 md:grid-cols-2 min-w-0 w-full overflow-hidden">
        {/* CV Text Card */}
        <Card className="border-slate-200 shadow-sm bg-white min-w-0 w-full overflow-hidden flex flex-col justify-between">
          <div>
            <CardHeader className="border-b border-slate-100 bg-slate-50/80 pb-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <FileText className="size-4 text-blue-600" />
                  Thông Tin Hồ Sơ Ứng Viên (CV)
                </CardTitle>
                {session.cvFileUrl && (
                  <a
                    href={session.cvFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200"
                  >
                    <span>Mở PDF Cloudinary</span>
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
              <CardDescription className="text-xs text-slate-500 truncate mt-1">
                Tệp CV: {session.cvFilename || 'Không có thông tin tệp'}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-3 text-sm min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="size-3.5 text-blue-600" /> Nội Dung Văn Bản CV:
                </span>
                <button
                  type="button"
                  onClick={() => setCvExpanded(!cvExpanded)}
                  className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-semibold cursor-pointer"
                >
                  {cvExpanded ? <><ChevronUp className="size-3" /> Thu gọn</> : <><ChevronDown className="size-3" /> Xem toàn bộ</>}
                </button>
              </div>
              <div className={`text-xs text-slate-700 bg-slate-50/90 p-4 rounded-xl border border-slate-200 overflow-y-auto font-mono whitespace-pre-wrap break-words leading-relaxed transition-all duration-300 shadow-inner ${cvExpanded ? 'max-h-[32rem]' : 'max-h-44'}`}>
                {session.cvExtractedText || 'Chưa có nội dung văn bản CV được trích xuất cho phiên này.'}
              </div>
            </CardContent>
          </div>
        </Card>

        {/* JD Text Card */}
        <Card className="border-slate-200 shadow-sm bg-white min-w-0 w-full overflow-hidden flex flex-col justify-between">
          <div>
            <CardHeader className="border-b border-slate-100 bg-slate-50/80 pb-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Briefcase className="size-4 text-indigo-600" />
                  Yêu Cầu Mô Tả Công Việc (JD)
                </CardTitle>
                {session.jdFileUrl && (
                  <a
                    href={session.jdFileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline bg-indigo-50 px-2.5 py-1 rounded-md border border-indigo-200"
                  >
                    <span>Mở PDF Cloudinary</span>
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
              <CardDescription className="text-xs text-slate-500 truncate mt-1">
                Tệp JD: {session.jdFilename || 'Không có thông tin tệp'}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-3 text-sm min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Briefcase className="size-3.5 text-indigo-600" /> Nội Dung Văn Bản JD:
                </span>
                <button
                  type="button"
                  onClick={() => setJdExpanded(!jdExpanded)}
                  className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer"
                >
                  {jdExpanded ? <><ChevronUp className="size-3" /> Thu gọn</> : <><ChevronDown className="size-3" /> Xem toàn bộ</>}
                </button>
              </div>
              <div className={`text-xs text-slate-700 bg-slate-50/90 p-4 rounded-xl border border-slate-200 overflow-y-auto font-mono whitespace-pre-wrap break-words leading-relaxed transition-all duration-300 shadow-inner ${jdExpanded ? 'max-h-[32rem]' : 'max-h-44'}`}>
                {session.jdExtractedText || 'Chưa có nội dung văn bản JD được trích xuất cho phiên này.'}
              </div>
            </CardContent>
          </div>
        </Card>
      </div>

      {/* 2. BOTTOM SECTION: Matching & Evaluation Results */}
      {/* 2.1 Match Result Header Banner */}
      <Card className="border-blue-200 bg-gradient-to-r from-blue-50/90 via-indigo-50/50 to-slate-50 p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <Sparkles className="size-5 text-blue-600" />
              <h3 className="text-lg font-bold text-slate-900">
                Kết Quả Phân Tích & So Khớp CV-JD
              </h3>
            </div>
            <p className="text-xs text-slate-600">
              Vị trí tuyển dụng: <strong>{session.roleTitle || 'Chưa xác định'}</strong> | Cấp độ: <strong>{session.candidateLevel || 'N/A'}</strong>
            </p>
            {/* Competency Fit Score — progress bar */}
            {session.competencyFitScore !== undefined && (
              <div className="mt-3 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700">Điểm Phù Hợp Năng Lực Cốt Lõi</span>
                  <span className="font-bold text-blue-700">{session.competencyFitScore}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      session.competencyFitScore >= 80 ? 'bg-emerald-500' :
                      session.competencyFitScore >= 60 ? 'bg-sky-500' : 'bg-rose-500'
                    }`}
                    style={{ width: `${Math.min(100, session.competencyFitScore)}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-3">
            {session.matchLevel && (
              <div className="text-right">
                <span className="text-xs text-slate-500 font-medium block">Mức Độ Phù Hợp</span>
                <Badge
                  className={`px-3 py-1 text-xs font-bold ${
                    session.matchLevel.toLowerCase().includes('cao') || session.matchLevel.toLowerCase().includes('high') || session.matchLevel.toLowerCase().includes('eligible')
                      ? 'bg-emerald-600 text-white'
                      : session.matchLevel.toLowerCase().includes('vừa') || session.matchLevel.toLowerCase().includes('medium') || session.matchLevel.toLowerCase().includes('moderate') || session.matchLevel.toLowerCase().includes('khớp')
                      ? 'bg-sky-600 text-white'
                      : 'bg-rose-500 text-white'
                  }`}
                >
                  {session.matchLevel}
                </Badge>
              </div>
            )}

            {session.overallScore !== undefined && session.overallScore !== null && (
              <div className="flex flex-col items-center justify-center rounded-xl bg-white px-4 py-2 border border-slate-200 shadow-xs">
                <span className="text-[10px] font-semibold text-slate-500 uppercase">Match Score</span>
                <span className="text-2xl font-black text-blue-600">{session.overallScore}%</span>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 2.2 Matching Breakdown Details */}
      <div className="grid gap-6 md:grid-cols-2 min-w-0 w-full overflow-hidden">
        {/* Strong Areas & Competency Fit Score */}
        <Card className="border-slate-200 shadow-sm bg-white p-5 space-y-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase block mb-2">
              Kỹ Năng Mạnh Khớp Tuyển Dụng ({strongAreas.length})
            </span>
            {strongAreas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 min-w-0">
                {strongAreas.map((skill, idx) => (
                  <Badge key={idx} variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-300 gap-1 text-xs whitespace-normal break-words max-w-full inline-flex items-start text-left py-1 px-2.5 h-auto font-medium leading-tight">
                    <CheckCircle2 className="size-3 text-emerald-600 shrink-0 mt-0.5" />
                    <span className="break-words min-w-0">{skill}</span>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Chưa ghi nhận kỹ năng mạnh vượt trội.</p>
            )}
          </div>

          {session.competencyFitScore !== undefined && (
            <div className="pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
              <span className="text-slate-600 font-medium">Điểm Phù Hợp Năng Lực Cốt Lõi:</span>
              <span className="font-bold text-slate-900">{session.competencyFitScore}%</span>
            </div>
          )}
        </Card>


        {/* Gap Areas & Critical Missing Skills */}
        <Card className="border-slate-200 shadow-sm bg-white p-5 space-y-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase block mb-2">
              Kỹ Năng Còn Thiếu / Cần Bổ Sung ({gapAreas.length})
            </span>
            {gapAreas.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 min-w-0">
                {gapAreas.map((skill, idx) => (
                  <Badge key={idx} variant="outline" className="bg-rose-50 text-rose-800 border-rose-300 gap-1 text-xs whitespace-normal break-words max-w-full inline-flex items-start text-left py-1 px-2.5 h-auto font-medium leading-tight">
                    <AlertTriangle className="size-3 text-rose-500 shrink-0 mt-0.5" />
                    <span className="break-words min-w-0">{skill}</span>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Không có khoảng trống kỹ năng đáng kể.</p>
            )}
          </div>

          {missingSkills.length > 0 && (
            <div className="pt-3 border-t border-slate-100">
              <span className="text-xs font-semibold text-amber-700 uppercase block mb-2">
                Kỹ Năng Quan Trọng Thiếu Bắt Buộc (Critical Gaps)
              </span>
              <div className="flex flex-wrap gap-1.5 min-w-0">
                {missingSkills.map((skill, idx) => (
                  <Badge key={idx} variant="outline" className="bg-amber-50 text-amber-900 border-amber-300 text-xs whitespace-normal break-words max-w-full inline-flex items-start text-left py-1 px-2.5 h-auto font-medium leading-tight">
                    <span className="shrink-0 mr-1">⚠️</span>
                    <span className="break-words min-w-0">{skill}</span>
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* 2.3 Hiring Recommendation */}
      {session.hiringRecommendation && (
        <Card className="border-slate-200 bg-slate-50/80 p-5">
          <div className="flex items-start space-x-3">
            <Award className="size-5 text-indigo-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="text-xs font-bold uppercase text-slate-700 tracking-wider">
                Khuyến Nghị Tuyển Dụng Từ Hệ Thống (Hiring Recommendation)
              </h4>
              <p className="text-sm text-slate-800 leading-relaxed font-medium">
                {session.hiringRecommendation}
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};
