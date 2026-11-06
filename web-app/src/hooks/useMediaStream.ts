import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Hook to manage user media devices (Camera and Microphone) for interview sessions.
 */
export function useMediaStream() {
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [micEnabled, setMicEnabled] = useState(true);
  const [permissionError, setPermissionError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const startMediaCapture = useCallback(async () => {
    try {
      setPermissionError(false);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 360 },
        audio: true,
      });
      setMediaStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      return stream;
    } catch (err) {
      console.error('Quyền truy cập Camera/Mic bị từ chối:', err);
      setPermissionError(true);
      return null;
    }
  }, []);

  const toggleCamera = useCallback(() => {
    if (mediaStream) {
      const videoTrack = mediaStream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !cameraEnabled;
        setCameraEnabled(videoTrack.enabled);
      }
    }
  }, [mediaStream, cameraEnabled]);

  const toggleMic = useCallback(() => {
    if (mediaStream) {
      const audioTrack = mediaStream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !micEnabled;
        setMicEnabled(audioTrack.enabled);
      }
    }
  }, [mediaStream, micEnabled]);

  const stopMediaStream = useCallback(() => {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      setMediaStream(null);
    }
  }, [mediaStream]);

  useEffect(() => {
    return () => {
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [mediaStream]);

  return {
    mediaStream,
    setMediaStream,
    cameraEnabled,
    micEnabled,
    permissionError,
    videoRef,
    startMediaCapture,
    toggleCamera,
    toggleMic,
    stopMediaStream,
  };
}
