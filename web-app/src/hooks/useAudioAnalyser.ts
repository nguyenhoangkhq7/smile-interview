import { useState, useRef, useCallback, useEffect } from 'react';

export interface AudioAnalyserLike {
  frequencyBinCount: number;
  getByteFrequencyData(array: Uint8Array): void;
}

interface ExtendedWindow extends Window {
  webkitAudioContext?: typeof AudioContext;
}

/**
 * Hook to manage Web Audio API context and frequency analyser for avatar lip-sync animation.
 */
export function useAudioAnalyser(onAudioEnded?: () => void) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);

  const [avatarConnected, setAvatarConnected] = useState(false);
  const [avatarPlaying, setAvatarPlaying] = useState(false);
  const [avatarAnalyser, setAvatarAnalyser] = useState<AudioAnalyserLike | null>(null);

  const initAudioOnUserGesture = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (!audioContextRef.current) {
      try {
        const AudioCtx = window.AudioContext || (window as unknown as ExtendedWindow).webkitAudioContext;
        if (!AudioCtx) return;

        const ctx = new AudioCtx();
        audioContextRef.current = ctx;

        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.6;
        analyser.connect(ctx.destination);
        analyserNodeRef.current = analyser;
        setAvatarAnalyser(analyser);

        const audio = new Audio();
        audio.crossOrigin = 'anonymous';
        audioElRef.current = audio;

        const source = ctx.createMediaElementSource(audio);
        source.connect(analyser);
        sourceNodeRef.current = source;

        audio.addEventListener('play', () => setAvatarPlaying(true));
        audio.addEventListener('pause', () => setAvatarPlaying(false));
        audio.addEventListener('ended', () => {
          setAvatarPlaying(false);
          onAudioEnded?.();
        });

        setAvatarConnected(true);
        console.log('[useAudioAnalyser] Audio pipeline initialized on user gesture');
      } catch (err) {
        console.error('[useAudioAnalyser] Failed to initialize audio pipeline:', err);
      }
    } else if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume().catch((err) => {
        console.error('[useAudioAnalyser] Failed to resume AudioContext:', err);
      });
    }
  }, [onAudioEnded]);

  useEffect(() => {
    return () => {
      if (audioElRef.current) {
        audioElRef.current.pause();
        audioElRef.current.src = '';
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  return {
    audioContextRef,
    analyserNodeRef,
    audioElRef,
    avatarConnected,
    setAvatarConnected,
    avatarPlaying,
    setAvatarPlaying,
    avatarAnalyser,
    setAvatarAnalyser,
    initAudioOnUserGesture,
  };
}
