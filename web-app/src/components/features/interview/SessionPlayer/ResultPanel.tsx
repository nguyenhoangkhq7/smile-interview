'use client';

import { CheckCircle, Download, Info, X, ArrowRight, FileSpreadsheet } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Image from 'next/image';
import { exportQuestionBankToCSV } from '@/lib/exportUtils';

interface ResultPanelProps {
  recordedBlob: Blob | null;
  showInfoBanner: boolean;
  setShowInfoBanner: (v: boolean) => void;
  handleDownloadVideo: () => void;
  handleGoToResults: () => void;
  questions?: any[];
  sessionId?: string;
}

export function ResultPanel({
  recordedBlob,
  showInfoBanner,
  setShowInfoBanner,
  handleDownloadVideo,
  handleGoToResults,
  questions,
  sessionId,
}: ResultPanelProps) {
  return (
    <div className="min-h-screen w-screen bg-background text-foreground flex flex-col font-sans animate-fade-up">
      { }
      <header className="border-b border-border bg-card px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Image src="/logo.png" alt="Smile Interview Logo" width={150} height={36} className="h-9 w-auto" unoptimized />
          <div className="h-4 w-[1px] bg-border" />
          <h1 className="text-sm font-semibold tracking-wide text-foreground">Phỏng vấn Kỹ thuật</h1>
        </div>
      </header>

      { }
      <main className="flex-grow flex flex-col items-center justify-center p-6 md:p-12 bg-muted/20">
        <div className="max-w-xl w-full bg-card border border-border rounded-2xl p-8 shadow-xl flex flex-col items-center text-center gap-6 animate-fade-up">
          <span className="flex size-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 shadow-inner">
            <CheckCircle size={36} />
          </span>

          <div className="space-y-2">
            <h2 className="text-2xl font-extrabold text-foreground">Buổi phỏng vấn đã hoàn thành!</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Cảm ơn bạn đã tham gia buổi phỏng vấn giả lập trực tuyến. Bạn có thể tải video ghi hình buổi phỏng vấn (bao gồm webcam và mic của bạn) dưới đây để phục vụ tự đánh giá.
            </p>
          </div>

          <div className="w-full space-y-4">
            {recordedBlob && (
              <div className="w-full space-y-3">
                <Button onClick={handleDownloadVideo} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-11 rounded-xl shadow-md flex items-center justify-center gap-2">
                  <Download size={16} />
                  Tải video cuộc phỏng vấn
                </Button>

                {showInfoBanner && (
                  <div className="bg-muted border border-border text-[10px] text-muted-foreground p-3.5 rounded-xl text-left leading-relaxed flex items-start gap-2 relative">
                    <Info size={14} className="text-muted-foreground/70 shrink-0 mt-0.5" />
                    <span>
                      Video chỉ chứa hình ảnh và giọng nói của bạn. Cuộc trò chuyện với AI không được ghi lại trong file video.
                    </span>
                    <button className="text-muted-foreground hover:text-foreground absolute top-2.5 right-2.5 p-0.5 rounded-full hover:bg-muted-foreground/10" onClick={() => setShowInfoBanner(false)}>
                      <X size={12} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {questions && questions.length > 0 && (
              <Button
                onClick={() => exportQuestionBankToCSV(questions, sessionId || '')}
                variant="outline"
                className="w-full border-emerald-600/30 text-emerald-700 hover:bg-emerald-50 font-bold h-11 rounded-xl shadow-sm flex items-center justify-center gap-2"
              >
                <FileSpreadsheet size={16} />
                <span>Xuất chi tiết câu hỏi &amp; trả lời (CSV)</span>
              </Button>
            )}

            <Button onClick={handleGoToResults} className="w-full bg-brand-orange hover:bg-brand-orange-hover text-white font-extrabold h-11 rounded-xl shadow-lg shadow-brand-orange/20 flex items-center justify-center gap-1.5 border-none">
              <span>Xem báo cáo kết quả đánh giá</span>
              <ArrowRight size={16} />
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
