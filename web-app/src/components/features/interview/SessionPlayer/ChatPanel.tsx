'use client';

import { useRef, useEffect } from 'react';
import { MessageSquare, Copy, CornerDownRight, Play, Mic, MicOff, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import type { SessionState } from '@/hooks/useInterviewSession';

interface ChatLogItem {
  sender: 'AI' | 'User';
  text: string;
  time: string;
  isDeepDive?: boolean;
}

interface ChatPanelProps {
  chatLog: ChatLogItem[];
  userAnswerDraft: string;
  sessionState: SessionState;
  inputType: 'voice' | 'keyboard';
  setInputType: (v: 'voice' | 'keyboard') => void;
  keyboardAnswer: string;
  setKeyboardAnswer: (v: string) => void;
  recording: boolean;
  isRevealing: boolean;
  permissionError: boolean;
  micEnabled: boolean;
  handleStartRecording: () => void;
  handleStopRecording: () => void;
  submitFinalAnswer: (answer: string) => void;
  handleStartInterview: () => void;
  toggleMic: () => void;
}

export function ChatPanel({
  chatLog,
  userAnswerDraft,
  sessionState,
  inputType,
  setInputType,
  keyboardAnswer,
  setKeyboardAnswer,
  recording,
  isRevealing,
  permissionError,
  micEnabled,
  handleStartRecording,
  handleStopRecording,
  submitFinalAnswer,
  handleStartInterview,
  toggleMic,
}: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatLog, userAnswerDraft]);

  return (
    <div className="flex-1 flex flex-col bg-card border border-border rounded-2xl shadow-sm overflow-hidden relative min-h-[300px]">
      {}
      <div className="flex items-center justify-between border-b border-border bg-muted/20 px-4 py-3 shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-brand-orange" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Bản ghi hội thoại trực tiếp</span>
        </div>
        <button disabled className="text-slate-400 opacity-40 text-xs flex items-center gap-1 cursor-not-allowed font-medium">
          <Copy size={13} />
          <span>Sao chép</span>
        </button>
      </div>

      {}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {chatLog.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center gap-3 py-16 animate-fade-up">
            <MessageSquare size={36} className="text-muted-foreground/35" />
            <p className="text-sm text-muted-foreground font-medium">Nội dung phỏng vấn sẽ xuất hiện tại đây.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4 w-full">
            {chatLog.map((log, index) => {
              const isAi = log.sender === 'AI';
              return (
                <div key={index} className={`flex flex-col max-w-[80%] ${isAi ? 'self-start items-start animate-slide-in' : 'self-end items-end'}`}>
                  <span className="text-[10px] text-muted-foreground font-bold mb-1 px-1">
                    {isAi ? 'NGƯỜI PHỎNG VẤN (AI)' : 'BẠN'}
                  </span>
                  <div className={`rounded-2xl px-4 py-2.5 text-sm shadow-sm relative ${
                    isAi
                      ? 'bg-slate-100 text-slate-900 rounded-tl-none border border-slate-200'
                      : 'bg-brand-orange text-white rounded-tr-none'
                  }`}>
                    {isAi && log.isDeepDive && (
                      <div className="flex items-center gap-1 text-[10px] font-bold text-purple-600 mb-1">
                        <CornerDownRight size={10} />
                        <span>HỎI SÂU</span>
                      </div>
                    )}
                    <p className="whitespace-pre-line leading-relaxed">{log.text}</p>
                    <span className={`block text-[9px] mt-1 text-right ${isAi ? 'text-slate-400' : 'text-white/70'}`}>
                      {log.time}
                    </span>
                  </div>
                </div>
              );
            })}

            {}
            {sessionState === 'LISTENING' && userAnswerDraft && (
              <div className="flex flex-col max-w-[80%] self-end items-end">
                <span className="text-[10px] text-emerald-600 font-bold mb-1 px-1 flex items-center gap-1">
                  <span className="size-1.5 rounded-full bg-emerald-500 animate-ping" />
                  <span>ĐANG NÓI...</span>
                </span>
                <div className="rounded-2xl rounded-tr-none px-4 py-2.5 text-sm bg-emerald-50/40 border border-dashed border-emerald-300 text-emerald-950">
                  <p className="inline leading-relaxed">
                    {userAnswerDraft}
                    <span className="inline-block w-1.5 h-4 ml-0.5 bg-emerald-500 animate-pulse align-middle" />
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {}
      {sessionState === 'INITIALIZING' && (
        <div className="p-4 border-t border-border bg-muted/10 flex flex-col items-center justify-center shrink-0 w-full gap-3">
          <p className="text-xs text-muted-foreground text-center">
            {chatLog.length > 0
              ? 'Nhấp vào nút dưới đây để tiếp tục buổi phỏng vấn của bạn.'
              : 'Nhấp vào nút dưới đây để bắt đầu buổi phỏng vấn giả lập.'}
          </p>
          <Button onClick={handleStartInterview} className="bg-brand-orange hover:bg-brand-orange-hover text-white text-xs font-semibold px-6 h-10">
            <Play size={13} fill="currentColor" className="mr-1.5" />
            {chatLog.length > 0 ? 'Tiếp tục phỏng vấn' : 'Bắt đầu phỏng vấn'}
          </Button>
        </div>
      )}

      {}
      {sessionState === 'LISTENING' && !micEnabled && (
        <div className="absolute bottom-16 inset-x-4 bg-red-50 border border-red-200 rounded-xl p-3 flex items-center justify-between text-xs text-red-800 backdrop-blur-sm z-10 shadow-lg animate-fade-in">
          <div className="flex items-center gap-2">
            <MicOff size={14} className="text-red-500 animate-pulse" />
            <span>Microphone của bạn đang tắt. Hãy bật mic để trả lời câu hỏi.</span>
          </div>
          <Button size="sm" onClick={toggleMic} className="bg-red-600 hover:bg-red-500 text-white text-[10px] uppercase font-bold tracking-wider h-8">
            Bật mic
          </Button>
        </div>
      )}

      {}
      {sessionState === 'LISTENING' && (
        <div className="p-3 border-t border-border bg-muted/10 flex justify-center shrink-0 w-full">
          {inputType === 'keyboard' ? (
            <div className="flex flex-col gap-2 w-full">
              <div className="flex gap-2 w-full items-end">
                <Textarea
                  value={keyboardAnswer}
                  onChange={(e) => setKeyboardAnswer(e.target.value)}
                  placeholder="Nhập câu trả lời của bạn tại đây..."
                  className="flex-1 min-h-[70px] max-h-[140px] resize-none text-xs bg-white"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      if (keyboardAnswer.trim()) {
                        submitFinalAnswer(keyboardAnswer);
                        setKeyboardAnswer('');
                      }
                    }
                  }}
                />
                <Button
                  onClick={() => {
                    if (keyboardAnswer.trim()) {
                      submitFinalAnswer(keyboardAnswer);
                      setKeyboardAnswer('');
                    }
                  }}
                  disabled={!keyboardAnswer.trim()}
                  className={`size-10 rounded-lg p-0 shrink-0 ${keyboardAnswer.trim() ? 'bg-brand-orange text-white hover:bg-brand-orange-hover' : 'bg-muted text-muted-foreground'}`}
                >
                  <Send size={15} />
                </Button>
              </div>
              <div className="flex justify-between items-center text-[10px]">
                <span className="text-muted-foreground">Nhấn Enter để gửi, Shift + Enter để xuống dòng</span>
                <button onClick={() => setInputType('voice')} className="font-semibold text-brand-orange hover:underline flex items-center gap-1">
                  <Mic size={11} />
                  <span>Trả lời bằng giọng nói</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 w-full">
              {recording ? (
                <Button onClick={handleStopRecording} className="w-full max-w-[320px] bg-red-600 hover:bg-red-700 text-white text-xs h-10 font-bold rounded-xl shadow-md">
                  <MicOff size={14} className="mr-1.5" />
                  <span>Tôi đã trả lời xong (Dừng ghi)</span>
                </Button>
              ) : (
                <Button onClick={handleStartRecording} disabled={permissionError || isRevealing} className="w-full max-w-[320px] bg-brand-orange hover:bg-brand-orange-hover text-white text-xs h-10 font-bold rounded-xl shadow-md">
                  <Mic size={14} className="mr-1.5" />
                  <span>Bắt đầu nói (Bật ghi âm)</span>
                </Button>
              )}
              {!recording && (
                <button onClick={() => setInputType('keyboard')} className="text-xs text-muted-foreground hover:underline flex items-center gap-1 mt-1 font-semibold">
                  <MessageSquare size={11} />
                  <span>Nhập câu trả lời bằng bàn phím</span>
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {}
      {sessionState === 'AI_THINKING' && (
        <div className="p-3 border-t border-border bg-muted/20 flex justify-center shrink-0 text-xs text-indigo-600 font-semibold items-center gap-2 shadow-inner">
          <span className="size-1.5 rounded-full bg-indigo-500 animate-ping" />
          <span>AI đang lắng nghe và phân tích câu trả lời của bạn...</span>
        </div>
      )}
    </div>
  );
}
