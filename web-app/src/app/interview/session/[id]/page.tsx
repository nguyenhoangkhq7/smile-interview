'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { useInterviewSession } from '@/hooks/useInterviewSession';
import { InterviewerAvatar } from '@/components/interview/InterviewerAvatar/InterviewerAvatar';
import { ChatPanel } from '@/components/features/interview/SessionPlayer/ChatPanel';
import { ControlsBar } from '@/components/features/interview/SessionPlayer/ControlsBar';
import { ResultPanel } from '@/components/features/interview/SessionPlayer/ResultPanel';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { CameraOff, Info, Timer, Radio, Volume2, Circle } from 'lucide-react';

export default function InterviewSessionPage() {
  const {
    id,
    session,
    sessionState,
    chatLog,
    socketConnected,
    ttsMode,
    avatarConnected,
    avatarAnalyser,
    cameraEnabled,
    micEnabled,
    permissionError,
    videoRef,
    timeLeft,
    recording,
    userAnswerDraft,
    inputType,
    setInputType,
    keyboardAnswer,
    setKeyboardAnswer,
    isRevealing,
    isRecording,
    recordedBlob,
    recordingDurationMs,
    showInfoBanner,
    setShowInfoBanner,
    showExitModal,
    setShowExitModal,
    submitFinalAnswer,
    handleStartRecording,
    handleStopRecording,
    startMediaCapture,
    toggleCamera,
    toggleMic,
    handleStartInterview,
    handleEndEarlyConfirm,
    handleToggleSessionRecording,
    handleDownloadVideo,
    handleGoToResults,
    formatTime,
    formatDuration,
  } = useInterviewSession();

  const getAiStatusChip = () => {
    if (sessionState === 'AI_SPEAKING') {
      return (
        <div className="flex items-center gap-1.5 bg-purple-50 border border-purple-200 px-3 py-1 rounded-full text-[10px] font-semibold text-purple-700 shadow-sm animate-pulse">
          <Volume2 size={12} className="text-purple-500" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang nói</span>
        </div>
      );
    }
    if (sessionState === 'LISTENING') {
      return (
        <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full text-[10px] font-semibold text-emerald-700 shadow-sm animate-pulse">
          <Radio size={12} className="text-emerald-500" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang lắng nghe</span>
        </div>
      );
    }
    if (sessionState === 'AI_THINKING') {
      return (
        <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-3 py-1 rounded-full text-[10px] font-semibold text-slate-600 shadow-sm">
          <Timer size={12} className="text-slate-400 animate-spin" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang suy nghĩ</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-3 py-1 rounded-full text-[10px] font-semibold text-slate-500 shadow-sm">
        <Circle size={12} className="text-slate-400" />
        <span>NGƯỜI PHỎNG VẤN (AI)</span>
      </div>
    );
  };

  
  if (sessionState === 'FINISHED') {
    return (
      <ProtectedRoute>
        <ResultPanel
          recordedBlob={recordedBlob}
          showInfoBanner={showInfoBanner}
          setShowInfoBanner={setShowInfoBanner}
          handleDownloadVideo={handleDownloadVideo}
          handleGoToResults={handleGoToResults}
          questions={session?.questions}
          sessionId={id}
        />
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="flex flex-col h-screen bg-slate-50 overflow-hidden font-sans">
        
        <header className="border-b border-border bg-card px-6 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <Link href="/history">
              <Image src="/logo.png" alt="Smile Interview Logo" width={150} height={36} className="h-9 w-auto" unoptimized />
            </Link>
            <div className="h-4 w-[1px] bg-border" />
            <h1 className="text-sm font-semibold tracking-wide text-foreground">Phỏng vấn Kỹ thuật</h1>
          </div>

          {}
          <div className="flex items-center gap-2">
            <Timer size={16} className={timeLeft <= 60 ? 'text-red-600 animate-pulse' : timeLeft <= 180 ? 'text-amber-500' : 'text-slate-800'} />
            <span className={`font-mono text-sm font-bold tracking-wide ${timeLeft <= 60 ? 'text-red-600 animate-pulse' : timeLeft <= 180 ? 'text-amber-600' : 'text-slate-800'}`}>
              {formatTime(timeLeft)}
            </span>
          </div>
        </header>

        {}
        <main className="flex-1 w-full overflow-hidden flex flex-col items-center py-6 min-h-0">
          <div className="w-full max-w-5xl flex flex-col h-full gap-4 px-4 min-h-0">
            
            {}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 shrink-0 w-full">
              {}
              <div className="relative aspect-video rounded-2xl overflow-hidden border border-border bg-slate-950 shadow-sm w-full">
                {}
                <div className="absolute top-2.5 left-2.5 bg-black/60 backdrop-blur-sm text-slate-100 text-[10px] font-bold tracking-wider px-2 py-1 rounded z-10 flex items-center gap-1.5">
                  {isRecording && <span className="size-1.5 rounded-full bg-red-500 animate-pulse shrink-0" />}
                  <span>ỨNG VIÊN (BẠN)</span>
                </div>

                <div className="w-full h-full relative">
                  {permissionError ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-red-950/20">
                      <Info size={24} className="text-red-500 mb-2" />
                      <h4 className="text-xs font-bold text-red-600 uppercase tracking-wider mb-1">Camera/Mic bị từ chối</h4>
                      <p className="text-[10px] text-slate-400 max-w-[240px] leading-relaxed mb-3">
                        Vui lòng cho phép quyền truy cập webcam/microphone trong trình duyệt để phỏng vấn.
                      </p>
                      <Button size="sm" onClick={startMediaCapture} className="bg-red-600 hover:bg-red-500 text-white font-semibold text-[10px]">
                        Cho phép lại
                      </Button>
                    </div>
                  ) : (
                    <>
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        disablePictureInPicture
                        className="w-full h-full object-cover scale-x-[-1]"
                        style={{ display: cameraEnabled ? 'block' : 'none' }}
                      />
                      {!cameraEnabled && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900">
                          <CameraOff size={32} className="text-slate-500 mb-1.5" />
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">CAMERA OFF</span>
                        </div>
                      )}

                      <ControlsBar
                        cameraEnabled={cameraEnabled}
                        micEnabled={micEnabled}
                        isRecording={isRecording}
                        recordingDurationMs={recordingDurationMs}
                        toggleCamera={toggleCamera}
                        toggleMic={toggleMic}
                        onExit={() => setShowExitModal(true)}
                        onToggleSessionRecording={handleToggleSessionRecording}
                        formatDuration={formatDuration}
                      />
                    </>
                  )}
                </div>
              </div>

              {}
              <div className="relative aspect-video rounded-2xl overflow-hidden border border-border bg-slate-950 shadow-sm w-full">
                {}
                <div className="absolute top-2.5 left-2.5 z-10 flex items-center gap-1.5">
                  {getAiStatusChip()}
                </div>

                <div className="w-full h-full relative">
                  {avatarConnected ? (
                    <div className="absolute inset-0 w-full h-full">
                      <InterviewerAvatar
                        controlled={true}
                        analyser={avatarAnalyser}
                        isConnected={socketConnected || ttsMode === 'mock'}
                      />
                    </div>
                  ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 animate-fade-in">
                      <div className="size-6 border-2 border-t-brand-orange border-muted rounded-full animate-spin mb-2" />
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Đang tải Avatar 3D...</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {}
            <ChatPanel
              chatLog={chatLog}
              userAnswerDraft={userAnswerDraft}
              sessionState={sessionState}
              inputType={inputType}
              setInputType={setInputType}
              keyboardAnswer={keyboardAnswer}
              setKeyboardAnswer={setKeyboardAnswer}
              recording={recording}
              isRevealing={isRevealing}
              permissionError={permissionError}
              micEnabled={micEnabled}
              handleStartRecording={handleStartRecording}
              handleStopRecording={handleStopRecording}
              submitFinalAnswer={submitFinalAnswer}
              handleStartInterview={handleStartInterview}
              toggleMic={toggleMic}
            />
          </div>
        </main>

        {}
        <Dialog open={showExitModal} onOpenChange={setShowExitModal}>
          <DialogContent className="max-w-[420px]">
            <DialogHeader className="space-y-2">
              <DialogTitle className="text-base font-bold text-foreground">Kết thúc phỏng vấn sớm?</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
                Bạn đang ở trong buổi phỏng vấn trực tiếp. Nếu kết thúc sớm, kết quả sẽ chỉ được tính cho các câu hỏi bạn đã hoàn thành. Bạn có chắc chắn muốn thoát?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex gap-2 justify-end pt-3">
              <Button size="sm" variant="outline" onClick={() => setShowExitModal(false)}>
                Hủy bỏ
              </Button>
              <Button size="sm" onClick={handleEndEarlyConfirm} className="bg-red-600 hover:bg-red-500 text-white font-semibold">
                Đồng ý thoát
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ProtectedRoute>
  );
}
