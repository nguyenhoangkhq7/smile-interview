'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';

/**
 * useAudioLipSync
 *
 * Connects to the streaming-service via Socket.IO, listens for 'tts-result'
 * events (raw ArrayBuffer audio), feeds the audio through the Web Audio API
 * AnalyserNode, and exposes the analyser for real-time lip-sync in the 3D
 * canvas.
 */
export function useAudioLipSync(serverUrl: string = 'http://localhost:8001') {
  const [analyser, setAnalyser]       = useState<AnalyserNode | null>(null);
  const [audioUrl, setAudioUrl]       = useState<string | null>(null);
  const [isPlaying, setIsPlaying]     = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  // Refs — mutated without triggering re-renders
  const socketRef        = useRef<any>(null);
  const audioContextRef  = useRef<AudioContext | null>(null);
  const analyserRef      = useRef<AnalyserNode | null>(null);
  const audioRef         = useRef<HTMLAudioElement | null>(null);       // singleton <audio> element
  const sourceNodeRef    = useRef<MediaElementAudioSourceNode | null>(null);       // singleton MediaElementSourceNode
  const currentUrlRef    = useRef<string | null>(null);       // last Object URL (for revocation)
  const isInitializedRef = useRef<boolean>(false);

  // ── initAudio ─────────────────────────────────────────────────────────────
  // Must be called from a user-gesture handler so the browser permits
  // AudioContext creation. Safe to call multiple times (no-ops after first).
  // ──────────────────────────────────────────────────────────────────────────
  const initAudio = useCallback(() => {
    if (isInitializedRef.current) return;
    isInitializedRef.current = true;

    // 1. AudioContext (singleton)
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioContextClass();
    audioContextRef.current = ctx;

    // 2. AnalyserNode (singleton), connected straight to speakers
    const analyserNode = ctx.createAnalyser();
    analyserNode.fftSize             = 256;  // 128 frequency bins — low latency
    analyserNode.smoothingTimeConstant = 0.6; // less smoothing = snappier lip-sync
    analyserNode.connect(ctx.destination);
    analyserRef.current = analyserNode;
    setAnalyser(analyserNode);

    // 3. HTML Audio element (singleton)
    const audio = new Audio();
    audio.crossOrigin = 'anonymous';
    audioRef.current  = audio;

    // 4. MediaElementSourceNode (singleton) — created ONCE, wired permanently.
    //    Creating it again on the same element throws InvalidStateError.
    const source = ctx.createMediaElementSource(audio);
    source.connect(analyserNode);
    sourceNodeRef.current = source;

    // Playback state tracking
    audio.addEventListener('play',  () => setIsPlaying(true));
    audio.addEventListener('pause', () => setIsPlaying(false));
    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      // Revoke the finished Object URL to free memory
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
        currentUrlRef.current = null;
      }
    });

    console.log('[useAudioLipSync] AudioContext + MediaElementSourceNode initialised once.');
  }, []);

  // ── handleTTSResult ────────────────────────────────────────────────────────
  // Called each time the server streams back a TTS audio buffer.
  // ──────────────────────────────────────────────────────────────────────────
  const handleTTSResult = useCallback(async (data: any) => {
    // Normalise incoming data to ArrayBuffer (Socket.IO may deliver Buffer)
    let buffer: ArrayBuffer;
    if (data instanceof ArrayBuffer) {
      buffer = data;
    } else if (data?.buffer instanceof ArrayBuffer) {
      buffer = data.buffer;
    } else {
      buffer = new Uint8Array(data).buffer;
    }

    const blob = new Blob([buffer], { type: 'audio/mpeg' });
    const url  = URL.createObjectURL(blob);

    // Revoke previous Object URL (memory hygiene)
    if (currentUrlRef.current) {
      URL.revokeObjectURL(currentUrlRef.current);
    }
    currentUrlRef.current = url;
    setAudioUrl(url);

    const ctx         = audioContextRef.current;
    const audio       = audioRef.current;
    const sourceNode  = sourceNodeRef.current;

    if (!ctx || !audio || !sourceNode) {
      console.warn(
        '[useAudioLipSync] AudioContext not initialised yet. ' +
        'Call initAudio() from a user gesture first.'
      );
      return;
    }

    // Resume context if the browser auto-suspended it (common in Chrome)
    if (ctx.state === 'suspended') {
      try {
        await ctx.resume();
      } catch (err) {
        console.error('[useAudioLipSync] ctx.resume() failed:', err);
      }
    }

    // ⚠️  DO NOT call audio.load() — that invalidates the already-wired
    //     MediaElementSourceNode and causes silence on every request after
    //     the first. Simply reassign .src; the browser will fetch the new
    //     blob URL automatically when play() is called.
    audio.src = url;

    try {
      await audio.play();
    } catch (err) {
      console.error('[useAudioLipSync] audio.play() failed:', err);
    }
  }, []);

  // ── Socket.IO lifecycle ────────────────────────────────────────────────────
  useEffect(() => {
    const socket = io(serverUrl, {
      transports:         ['websocket'],
      reconnection:       true,
      reconnectionAttempts: Infinity,
      reconnectionDelay:  1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[useAudioLipSync] Socket connected:', socket.id);
      setIsConnected(true);
    });

    socket.on('disconnect', (reason) => {
      console.warn('[useAudioLipSync] Socket disconnected:', reason);
      setIsConnected(false);
    });

    socket.on('tts-result', handleTTSResult);

    return () => {
      socket.off('tts-result', handleTTSResult);
      socket.disconnect();

      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
        currentUrlRef.current = null;
      }
      isInitializedRef.current = false;
    };
  }, [serverUrl, handleTTSResult]);

  // ── sendTTS ────────────────────────────────────────────────────────────────
  const sendTTS = useCallback((text: string) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('process-tts', text);
    } else {
      console.warn('[useAudioLipSync] Cannot send TTS: Socket not connected');
    }
  }, []);

  return {
    analyser,
    audioUrl,
    isPlaying,
    isConnected,
    /** Call from a user-gesture handler to initialise AudioContext */
    initAudio,
    /** Trigger TTS synthesis and playback for the given text */
    sendTTS,
  };
}
