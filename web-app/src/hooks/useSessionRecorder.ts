'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * useSessionRecorder Hook
 * 
 * Captures and records a given local MediaStream (webcam + mic).
 * Note: Recording captures candidate webcam + mic only. AI avatar audio is not included in the recording output.
 * 
 * @param stream The existing MediaStream containing candidate video and audio tracks.
 */
export function useSessionRecorder(stream: MediaStream | null) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordingDurationMs, setRecordingDurationMs] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const durationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {
        console.error('[useSessionRecorder] Error stopping MediaRecorder:', e);
      }
    }
    setIsRecording(false);
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((track) => track.stop());
      screenStreamRef.current = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (isRecording) {
      console.warn('[useSessionRecorder] Cannot start: Already recording.');
      return;
    }

    chunksRef.current = [];
    setRecordedBlob(null);
    setRecordingDurationMs(0);

    try {
      // Prompt user to select screen/window/tab to share/record
      console.log('[useSessionRecorder] Prompting for screen capture...');
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: true
      });
      screenStreamRef.current = screenStream;

      // Extract screen video track
      const screenVideoTrack = screenStream.getVideoTracks()[0];
      if (!screenVideoTrack) {
        throw new Error('No video track found in screen capture.');
      }

      // Handle user manually clicking native "Stop sharing" button in browser bar
      screenVideoTrack.onended = () => {
        console.log('[useSessionRecorder] Screen capture ended by user natively.');
        stopRecording();
      };

      // Extract microphone track from camera/mic stream
      const audioTrack = stream ? stream.getAudioTracks()[0] : null;

      // Combine tracks: Screen Video + Mic Audio
      const combinedTracks = [screenVideoTrack];
      if (audioTrack) {
        combinedTracks.push(audioTrack);
      }

      const combinedStream = new MediaStream(combinedTracks);

      // Determine the best supported mimeType in the current browser
      const types = [
        'video/webm;codecs=vp9,opus',
        'video/webm;codecs=vp8,opus',
        'video/webm',
        'video/mp4'
      ];

      let selectedType = '';
      for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
          selectedType = type;
          break;
        }
      }

      const options = selectedType ? { mimeType: selectedType } : undefined;
      console.log('[useSessionRecorder] Starting MediaRecorder on screen share with mimeType:', selectedType || 'default');

      const recorder = new MediaRecorder(combinedStream, options);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const mimeType = mediaRecorderRef.current?.mimeType || 'video/webm';
        console.log('[useSessionRecorder] MediaRecorder stopped. Assembling chunks count:', chunksRef.current.length);
        const finalBlob = new Blob(chunksRef.current, { type: mimeType });
        setRecordedBlob(finalBlob);

        // Stop duration timer
        if (durationIntervalRef.current) {
          clearInterval(durationIntervalRef.current);
          durationIntervalRef.current = null;
        }

        // Release screen tracks
        if (screenStreamRef.current) {
          screenStreamRef.current.getTracks().forEach((track) => track.stop());
          screenStreamRef.current = null;
        }
      };

      startTimeRef.current = Date.now();
      
      // Start recording in 1-second timeslices
      recorder.start(1000);
      setIsRecording(true);

      // Start duration counter
      durationIntervalRef.current = setInterval(() => {
        setRecordingDurationMs(Date.now() - startTimeRef.current);
      }, 200);

    } catch (err) {
      console.error('[useSessionRecorder] Failed to initialize screen recording:', err);
      // Clean up in case of failure
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((track) => track.stop());
        screenStreamRef.current = null;
      }
    }
  }, [stream, isRecording, stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop();
        } catch {
          // ignore
        }
      }
      if (screenStreamRef.current) {
        try {
          screenStreamRef.current.getTracks().forEach((track) => track.stop());
        } catch {
          // ignore
        }
      }
    };
  }, []);

  return {
    startRecording,
    stopRecording,
    isRecording,
    recordedBlob,
    recordingDurationMs
  };
}
