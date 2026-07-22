'use client';

import { Camera, CameraOff, Mic, MicOff, PhoneOff, Video } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ControlsBarProps {
  cameraEnabled: boolean;
  micEnabled: boolean;
  isRecording: boolean;
  recordingDurationMs: number;
  toggleCamera: () => void;
  toggleMic: () => void;
  onExit: () => void;
  onToggleSessionRecording: () => void;
  formatDuration: (ms: number) => string;
}

export function ControlsBar({
  cameraEnabled,
  micEnabled,
  isRecording,
  recordingDurationMs,
  toggleCamera,
  toggleMic,
  onExit,
  onToggleSessionRecording,
  formatDuration,
}: ControlsBarProps) {
  return (
    <>
      {}
      <button
        onClick={onToggleSessionRecording}
        className={`absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold transition-all shadow-md z-15 ${
          isRecording
            ? 'bg-red-600 text-white animate-pulse shadow-red-500/20'
            : 'bg-black/60 text-white hover:bg-black/80'
        }`}
      >
        {isRecording ? (
          <>
            <span className="size-2 rounded-full bg-white animate-ping" />
            <span>Đang ghi {formatDuration(recordingDurationMs)}</span>
          </>
        ) : (
          <>
            <Video size={13} />
            <span>Ghi lại</span>
          </>
        )}
      </button>

      {}
      <div className="absolute bottom-3 right-3 flex items-center gap-2 z-15">
        <Button
          size="icon"
          variant="outline"
          onClick={toggleMic}
          className={`size-8 rounded-full border border-white/20 shadow-md ${
            micEnabled
              ? 'bg-black/50 hover:bg-black/70 text-white'
              : 'bg-red-600/80 hover:bg-red-600 text-white'
          }`}
          title={micEnabled ? 'Tắt Mic' : 'Bật Mic'}
        >
          {micEnabled ? <Mic size={14} /> : <MicOff size={14} />}
        </Button>

        <Button
          size="icon"
          variant="outline"
          onClick={toggleCamera}
          className={`size-8 rounded-full border border-white/20 shadow-md ${
            cameraEnabled
              ? 'bg-black/50 hover:bg-black/70 text-white'
              : 'bg-red-600/80 hover:bg-red-600 text-white'
          }`}
          title={cameraEnabled ? 'Tắt Camera' : 'Bật Camera'}
        >
          {cameraEnabled ? <Camera size={14} /> : <CameraOff size={14} />}
        </Button>

        <Button
          size="sm"
          onClick={onExit}
          className="h-8 rounded-full bg-red-600 hover:bg-red-700 text-white font-bold text-xs gap-1.5 px-3.5 shadow-md shadow-red-600/25 border-none"
        >
          <PhoneOff size={12} />
          <span>Kết thúc</span>
        </Button>
      </div>
    </>
  );
}
