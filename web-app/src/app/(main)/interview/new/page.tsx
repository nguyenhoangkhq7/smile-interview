'use client';

import dynamic from 'next/dynamic';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { useNewInterview } from '@/hooks/useNewInterview';
import { UploadStep } from '@/components/features/interview/NewInterview/UploadStep';
import { ActiveSessionsPanel } from '@/components/features/interview/NewInterview/ActiveSessionsPanel';
import { SkillGapResultPanel } from '@/components/features/interview/NewInterview/SkillGapResultPanel';
import {
  InterviewProgressStepper,
  InterviewFlowStep,
} from '@/components/features/interview/NewInterview/InterviewProgressStepper';
import { Button } from '@/components/ui/button';
import { CheckCircle, AlertTriangle } from 'lucide-react';

const PdfViewerModal = dynamic(() => import('@/components/common/PdfViewerModal'), { ssr: false });

export default function NewInterviewPage() {
  const {
    user,
    cvFile,
    setCvFile,
    jdFile,
    setJdFile,
    jdText,
    setJdText,
    cvSource,
    setCvSource,
    jdSource,
    setJdSource,
    savedResumes,
    savedJds,
    selectedResumeId,
    setSelectedResumeId,
    selectedJdId,
    setSelectedJdId,
    dragOverCv,
    dragOverJd,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileChange,
    triggerFileSelect,
    fileInputCvRef,
    fileInputJdRef,
    cvError,
    jdError,
    uploading,
    analyzing,
    generating,
    apiError,
    roleTitle,
    ingested,
    analysis,
    activeSessions,
    viewerOpen,
    setViewerOpen,
    viewerUrl,
    setViewerUrl,
    viewerTitle,
    setViewerTitle,
    handleUploadAndIngest,
    handleRunAssessment,
    handleResumeSession,
    handleViewAssessment,
    handleReset,
    handleStartInterview,
  } = useNewInterview();

  const currentStep: InterviewFlowStep = generating
    ? 'interview'
    : analysis || analyzing || ingested
    ? 'assessment'
    : 'upload';

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gradient-to-br from-brand-orange/5 via-background to-brand-green/5 text-foreground flex flex-col font-sans">
        <main className="max-w-5xl w-full mx-auto px-4 py-12 flex-1 flex flex-col justify-center">
          {/* Header */}
          <div className="mb-8 text-center space-y-2">
            <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-foreground">
              Khởi tạo phỏng vấn NCKH
            </h1>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto">
              Chọn CV và mô tả công việc để phân tích kỹ năng và bắt đầu phỏng vấn.
            </p>
          </div>

          <InterviewProgressStepper
            currentStep={currentStep}
            uploading={uploading}
            analyzing={analyzing}
            generating={generating}
            hasAssessment={!!analysis}
            onSelectStep={(step) => {
              if (step === 'upload' && (analysis || ingested)) {
                handleReset();
              }
            }}
          />

          {!analysis && !uploading && !analyzing && (
            <ActiveSessionsPanel
              sessions={activeSessions}
              onResume={handleResumeSession}
              onViewAssessment={handleViewAssessment}
            />
          )}

          {apiError && (
            <div className="mb-6 flex items-center justify-between gap-4 p-4 rounded-xl border border-destructive/20 bg-destructive/10 text-destructive text-sm animate-fade-up">
              <span className="flex items-center gap-2 font-medium">
                <AlertTriangle size={16} />
                {apiError}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleReset}
                className="hover:bg-destructive/20 text-destructive"
              >
                Thử lại
              </Button>
            </div>
          )}

          {!uploading && !analyzing && !analysis && !ingested && (
            <div className="bg-card border border-border rounded-2xl p-6 md:p-8 shadow-xl animate-fade-up">
              <UploadStep
                cvSource={cvSource}
                setCvSource={setCvSource}
                jdSource={jdSource}
                setJdSource={setJdSource}
                cvFile={cvFile}
                jdFile={jdFile}
                jdText={jdText}
                setJdText={setJdText}
                dragOverCv={dragOverCv}
                dragOverJd={dragOverJd}
                cvError={cvError}
                jdError={jdError}
                savedResumes={savedResumes}
                savedJds={savedJds}
                selectedResumeId={selectedResumeId}
                setSelectedResumeId={setSelectedResumeId}
                selectedJdId={selectedJdId}
                setSelectedJdId={setSelectedJdId}
                fileInputCvRef={fileInputCvRef}
                fileInputJdRef={fileInputJdRef}
                defaultResumeId={user?.defaultResumeId || null}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onFileChange={handleFileChange}
                onTrigger={triggerFileSelect}
                onClearCv={() => setCvFile(null)}
                onClearJd={() => setJdFile(null)}
                onViewPdf={(url, title) => {
                  setViewerUrl(url);
                  setViewerTitle(title);
                  setViewerOpen(true);
                }}
                onSubmit={handleUploadAndIngest}
                disabled={
                  (cvSource === 'upload' && !cvFile) ||
                  ((cvSource === 'saved' || cvSource === 'default') && !selectedResumeId) ||
                  (jdSource === 'upload' && !jdFile) ||
                  (jdSource === 'text' && !jdText.trim()) ||
                  (jdSource === 'saved' && !selectedJdId)
                }
              />
            </div>
          )}

          {uploading && (
            <div className="bg-card border border-border rounded-2xl p-12 shadow-xl flex flex-col items-center justify-center gap-6 text-center animate-fade-up">
              <div className="size-10 rounded-full border-4 border-t-brand-orange border-muted animate-spin" />
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">Đang tải tài liệu lên...</h3>
                <p className="text-xs text-muted-foreground">Hồ sơ của bạn đang được truyền tải an toàn</p>
              </div>
            </div>
          )}

          {analyzing && (
            <div className="bg-card border border-border rounded-2xl p-12 shadow-xl flex flex-col items-center justify-center gap-6 text-center animate-fade-up">
              <div className="size-10 rounded-full border-4 border-t-purple-500 border-muted animate-spin" />
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">
                  Đang phân tích CV và yêu cầu công việc...
                </h3>
                <p className="text-xs text-muted-foreground">
                  Quá trình này có thể mất vài phút. Vui lòng chờ trong giây lát.
                </p>
              </div>
            </div>
          )}

          {ingested && !analyzing && !analysis && (
            <div className="bg-card border border-border rounded-2xl p-10 shadow-xl text-center space-y-6 animate-fade-up">
              <span className="flex size-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mx-auto">
                <CheckCircle size={32} />
              </span>
              <div className="space-y-1">
                <h2 className="text-xl font-bold text-foreground">Tải lên thành công!</h2>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  Hồ sơ CV và JD đã sẵn sàng. Bấm nút bên dưới để chạy phân tích khoảng trống năng lực (Skill-Gap).
                </p>
              </div>
              <div className="flex justify-center gap-3 pt-2">
                <Button variant="outline" onClick={handleReset}>
                  Tải lại tài liệu khác
                </Button>
                <Button
                  onClick={() => handleRunAssessment(false)}
                  className="bg-brand-orange text-white hover:bg-brand-orange-hover"
                >
                  Phân tích kỹ năng
                </Button>
              </div>
            </div>
          )}

          {analysis && (
            <div className="bg-card border border-border rounded-2xl p-6 md:p-8 shadow-xl animate-fade-up">
              <SkillGapResultPanel
                analysis={analysis}
                roleTitle={roleTitle}
                analyzing={analyzing}
                startingInterview={generating}
                onRefresh={() => handleRunAssessment(true)}
                onReset={handleReset}
                onStartInterview={handleStartInterview}
              />
            </div>
          )}

          {generating && (
            <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-card border border-border rounded-2xl p-8 max-w-sm w-full text-center space-y-4 shadow-2xl">
                <div className="size-10 rounded-full border-4 border-t-amber-500 border-muted animate-spin mx-auto" />
                <h3 className="text-lg font-bold text-foreground">
                  Đang chuẩn bị phỏng vấn...
                </h3>
                <p className="text-xs text-muted-foreground">
                  Khởi tạo phân phối niềm tin Prior Belief và sinh câu hỏi Abductive CoT mở đầu
                </p>
              </div>
            </div>
          )}
        </main>
      </div>

      {viewerOpen && (
        <PdfViewerModal
          isOpen={viewerOpen}
          onClose={() => setViewerOpen(false)}
          pdfUrl={viewerUrl}
          title={viewerTitle}
        />
      )}
    </ProtectedRoute>
  );
}
