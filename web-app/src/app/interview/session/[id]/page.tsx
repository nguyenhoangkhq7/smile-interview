'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { io, Socket } from 'socket.io-client';
import { DittoAvatarModule } from '@/components/DittoAvatarModule';
import { historyService, SessionHistoryItem, QuestionFeedback } from '@/services/historyService';
import { questionService } from '@/services/questionService';
import styles from './session.module.css';

type SessionState = 'INITIALIZING' | 'AI_SPEAKING' | 'LISTENING' | 'CONFIRM_ANSWER' | 'AI_THINKING' | 'FINISHED';

export default function InterviewSessionPage() {
  const params = useParams();
  const router = useRouter();
  const id = (params?.id as string) || '';

  // Session Data & Navigation
  const [session, setSession] = useState<SessionHistoryItem | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>('INITIALIZING');
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [questionCount, setQuestionCount] = useState(0);
  const [topicTag, setTopicTag] = useState('');
  const [isDeepDive, setIsDeepDive] = useState(false);
  const [showExitModal, setShowExitModal] = useState(false);

  // Chat Transcript Board
  const [chatLog, setChatLog] = useState<{ sender: 'AI' | 'User'; text: string; time: string; isDeepDive?: boolean }[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Audio / Socket / Engine Service Status
  const [socketConnected, setSocketConnected] = useState(false);
  const [ttsMode, setTtsMode] = useState<'online' | 'mock'>('mock');
  const [sttMode, setSttMode] = useState<'online' | 'mock'>('mock');
  const socketRef = useRef<Socket | null>(null);

  // 3D Avatar Controlled Props
  const [avatarConnected, setAvatarConnected] = useState(false);
  const [avatarPlaying, setAvatarPlaying] = useState(false);
  const [avatarAnalyser, setAvatarAnalyser] = useState<any>(null);

  // Local Media Capture & Toggles
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [micEnabled, setMicEnabled] = useState(true);
  const [permissionError, setPermissionError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Timer Limits
  const [timeLeft, setTimeLeft] = useState(900); // 15 mins countdown
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Recording & STT Audio buffers
  const [recording, setRecording] = useState(false);
  const [userAnswerDraft, setUserAnswerDraft] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const speechRecognitionRef = useRef<any>(null);
  const finalTranscriptRef = useRef<string>('');

  // Audio playing singletons for TTS Mock Mode
  const mockAnalyserIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Scroll to bottom of chat transcript
  const scrollToBottom = useCallback(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [chatLog, scrollToBottom]);

  // ── 1. Init Session Data & Media Permissions ──
  useEffect(() => {
    async function initSession() {
      if (!id) return;
      const data = await historyService.getSessionById(id);
      if (data) {
        setSession(data);
      } else {
        // Fallback create
        const newSession = await historyService.createSession(id, 'React Frontend Engineer', 'CV_Preview.pdf', 'JD_Preview.pdf');
        setSession(newSession);
      }
    }
    initSession();
    startMediaCapture();

    return () => {
      stopMediaCapture();
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (socketRef.current) socketRef.current.disconnect();
      if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);
    };
  }, [id]);

  // Starts the countdown clock
  const startTimer = () => {
    if (timerIntervalRef.current) return;
    timerIntervalRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current!);
          handleInterviewFinish(true); // Auto-finish on timeout
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const startMediaCapture = async () => {
    try {
      setPermissionError(false);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 360 },
        audio: true
      });
      setMediaStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error('Quyền truy cập Camera/Mic bị từ chối:', err);
      setPermissionError(true);
    }
  };

  const stopMediaCapture = () => {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
    }
  };

  const toggleCamera = () => {
    if (mediaStream) {
      const videoTrack = mediaStream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !cameraEnabled;
        setCameraEnabled(videoTrack.enabled);
      }
    }
  };

  const toggleMic = () => {
    if (mediaStream) {
      const audioTrack = mediaStream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !micEnabled;
        setMicEnabled(audioTrack.enabled);
      }
    }
  };

  // ── 2. Socket Connection & TTS/STT Engine Health Checks ──
  useEffect(() => {
    const streamingUrl = process.env.NEXT_PUBLIC_STREAMING_SERVICE_URL || 'http://localhost:8001';
    console.log(`[Session] Connecting to streaming-service: ${streamingUrl}`);

    const socket = io(streamingUrl, {
      transports: ['websocket'],
      reconnectionAttempts: 2,
      timeout: 2500
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[Session] Streaming Service connected!');
      setSocketConnected(true);
      setAvatarConnected(true);
      setTtsMode('online');
      setSttMode('online');
      
      // Join interview room
      socket.emit('join-interview', { interviewId: id, userId: 'candidate-user' });
    });

    socket.on('connect_error', () => {
      console.warn('[Session] Connection to streaming service failed. Falling back to native browser Speech APIs.');
      setSocketConnected(false);
      setAvatarConnected(true); // Keep 3D avatar scene alive in visual fallback mode
      setTtsMode('mock');
      setSttMode('mock');
    });

    // Handle incoming audio transcriptions from server-side STT
    socket.on('stt-result', (data: any) => {
      if (data.status === 'success') {
        setUserAnswerDraft(data.text);
        setSessionState('CONFIRM_ANSWER');
      } else {
        setUserAnswerDraft('[Không nhận diện được giọng nói. Vui lòng ghi âm lại hoặc nhập tay.]');
        setSessionState('CONFIRM_ANSWER');
      }
      setRecording(false);
    });

    socket.on('stt-error', (err: any) => {
      console.error('[Session] STT Socket Error:', err);
      setUserAnswerDraft('[Lỗi xử lý âm thanh. Vui lòng tự nhập câu trả lời của bạn.]');
      setSessionState('CONFIRM_ANSWER');
      setRecording(false);
    });

    // Wire up TTS audio lip-sync from backend streams
    // (Note: useAudioLipSync listens directly inside DittoAvatarModule when not controlled,
    // but here we are in controlled mode, so we handle it at the page level)
    let audioContext: AudioContext | null = null;
    let analyserNode: AnalyserNode | null = null;
    let audioEl: HTMLAudioElement | null = null;
    let sourceNode: MediaElementAudioSourceNode | null = null;

    socket.on('tts-result', async (bufferData: any) => {
      try {
        let buffer;
        if (bufferData instanceof ArrayBuffer) {
          buffer = bufferData;
        } else if (bufferData?.buffer instanceof ArrayBuffer) {
          buffer = bufferData.buffer;
        } else {
          buffer = new Uint8Array(bufferData).buffer;
        }

        const blob = new Blob([buffer], { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);

        if (!audioContext) {
          audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
          analyserNode = audioContext.createAnalyser();
          analyserNode.fftSize = 256;
          analyserNode.smoothingTimeConstant = 0.6;
          analyserNode.connect(audioContext.destination);
          setAvatarAnalyser(analyserNode);

          audioEl = new Audio();
          audioEl.crossOrigin = 'anonymous';
          sourceNode = audioContext.createMediaElementSource(audioEl);
          sourceNode.connect(analyserNode);

          audioEl.addEventListener('play', () => setAvatarPlaying(true));
          audioEl.addEventListener('pause', () => setAvatarPlaying(false));
          audioEl.addEventListener('ended', () => {
            setAvatarPlaying(false);
            URL.revokeObjectURL(url);
            // Transition to LISTENING when speech ends
            setSessionState('LISTENING');
          });
        }

        if (audioContext.state === 'suspended') {
          await audioContext.resume();
        }

        if (audioEl) {
          audioEl.src = url;
          await audioEl.play();
        }
      } catch (err) {
        console.error('[Session] Audio playback error:', err);
        // Fail-safe transition to listening if audio breaks
        setSessionState('LISTENING');
      }
    });

    return () => {
      socket.disconnect();
      if (audioContext) {
        audioContext.close();
      }
    };
  }, [id]);

  // ── 3. Start First Question ──
  const handleStartInterview = async () => {
    await questionService.resetSession(id);
    setSessionState('AI_THINKING');
    startTimer();

    setTimeout(async () => {
      const nextQ = await questionService.getNextQuestion(id);
      setCurrentQuestion(nextQ.questionText);
      setTopicTag(nextQ.topicTag);
      setIsDeepDive(nextQ.isDeepDive);
      setQuestionCount(1);

      // Save question to transcript chat board
      setChatLog([{ sender: 'AI', text: nextQ.questionText, time: formatCurrentTime(), isDeepDive: nextQ.isDeepDive }]);

      setSessionState('AI_SPEAKING');
      speakQuestion(nextQ.questionText);
    }, 1200);
  };

  const formatCurrentTime = () => {
    const d = new Date();
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  };

  // ── 4. Speak Question (TTS Interface & Fallback) ──
  const speakQuestion = (text: string) => {
    if (ttsMode === 'online' && socketRef.current?.connected) {
      console.log('[Session] Sending TTS to server:', text);
      socketRef.current.emit('process-tts', text);
    } else {
      // Mock Mode Fallback (Web Speech API speechSynthesis)
      console.log('[Session] Synthesizing speech via native SpeechSynthesis:', text);
      
      // Cancel current playbacks
      window.speechSynthesis.cancel();
      if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'vi-VN';

      // Find a Vietnamese voice if available
      const voices = window.speechSynthesis.getVoices();
      const viVoice = voices.find(v => v.lang.includes('VI') || v.lang.includes('vi'));
      if (viVoice) utterance.voice = viVoice;

      // Mock Analyser to drive lip-sync mouth movements in offline mode
      const mockAnalyserNode = {
        frequencyBinCount: 128,
        getByteFrequencyData: (array: Uint8Array) => {
          for (let i = 0; i < array.length; i++) {
            // Generate fluctuating wave-energy to make lips open/close naturally
            array[i] = Math.random() * 160 + 20;
          }
        }
      };

      utterance.onstart = () => {
        setAvatarPlaying(true);
        setAvatarAnalyser(mockAnalyserNode);
        
        // Frequently trigger small variations
        mockAnalyserIntervalRef.current = setInterval(() => {
          // Simply triggers useFrame cycles
        }, 100);
      };

      utterance.onend = () => {
        setAvatarPlaying(false);
        setAvatarAnalyser(null);
        if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);
        // Switch to user speaking state
        setSessionState('LISTENING');
      };

      utterance.onerror = (e) => {
        console.error('SpeechSynthesis error:', e);
        setAvatarPlaying(false);
        setAvatarAnalyser(null);
        setSessionState('LISTENING');
      };

      window.speechSynthesis.speak(utterance);
    }
  };

  // ── 5. User Recording & Transcribing (STT Interface & Fallback) ──
  const handleStartRecording = async () => {
    setUserAnswerDraft('');
    audioChunksRef.current = [];
    setRecording(true);

    if (sttMode === 'online' && mediaStream) {
      // Online mode: record chunks
      try {
        // Isolate audio tracks to prevent Chrome from throwing NotSupportedError
        // when using an audio-only mimeType with a video-containing stream.
        const audioTracks = mediaStream.getAudioTracks();
        if (audioTracks.length === 0) {
          throw new Error('Không tìm thấy thiết bị Microphone.');
        }
        const audioStream = new MediaStream(audioTracks);

        let options = {};
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          options = { mimeType: 'audio/webm;codecs=opus' };
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          options = { mimeType: 'audio/webm' };
        }

        const recorder = new MediaRecorder(audioStream, options);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.onstop = async () => {
          setSessionState('AI_THINKING');
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          
          // Send raw array buffer to Socket.IO transcription endpoint
          const buffer = await audioBlob.arrayBuffer();
          if (socketRef.current?.connected) {
            console.log('[Session] Sending audio buffer to STT socket...');
            socketRef.current.emit('process-stt', buffer);
          } else {
            // Socket disconnected mid-recording, fallback to fetch
            uploadAudioBlob(audioBlob);
          }
        };

        recorder.start();
      } catch (err) {
        console.error('Failed to start MediaRecorder:', err);
        setRecording(false);
      }
    } else {
      // Offline mode: Web Speech API webkitSpeechRecognition
      console.log('[Session] Starting webkitSpeechRecognition in mock mode...');
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const rec = new SpeechRecognition();
        rec.lang = 'vi-VN';
        rec.interimResults = true;
        rec.continuous = true;
        finalTranscriptRef.current = '';
        setUserAnswerDraft('');

        rec.onresult = (event: any) => {
          let interimTranscript = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscriptRef.current += event.results[i][0].transcript;
            } else {
              interimTranscript += event.results[i][0].transcript;
            }
          }
          // Fulfill live draft text view
          setUserAnswerDraft(finalTranscriptRef.current + interimTranscript);
        };

        rec.onerror = (e: any) => {
          console.error('Speech recognition error:', e);
        };

        rec.onend = () => {
          setRecording(false);
          setSessionState('CONFIRM_ANSWER');
        };

        speechRecognitionRef.current = rec;
        rec.start();
      } else {
        // Fallback if browser does not support SpeechRecognition
        console.warn('SpeechRecognition not supported in this browser. Simulating typing answer.');
        // Typing simulation of a technical mock answer
        let i = 0;
        const targetText = 'Tôi nghĩ useMemo và useCallback dùng để tối ưu hóa hiệu năng render trong React. useMemo giúp lưu giữ giá trị của phép tính phức tạp, còn useCallback giúp lưu giữ tham chiếu của callback function nhằm tránh re-render.';
        const typingInterval = setInterval(() => {
          setUserAnswerDraft((prev) => prev + targetText.charAt(i));
          i++;
          if (i >= targetText.length) {
            clearInterval(typingInterval);
            setRecording(false);
            setSessionState('CONFIRM_ANSWER');
          }
        }, 30);
      }
    }
  };

  const handleStopRecording = () => {
    if (sttMode === 'online') {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    } else {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
      }
    }
  };

  // POST fallback if socket STT drops
  const uploadAudioBlob = async (blob: Blob) => {
    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
      const streamingUrl = process.env.NEXT_PUBLIC_STREAMING_SERVICE_URL || 'http://localhost:8001';

      const res = await fetch(`${streamingUrl}/api/v1/audio/transcribe`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error('API transcribe failed');
      const data = await res.json();
      setUserAnswerDraft(data.text || '');
      setSessionState('CONFIRM_ANSWER');
    } catch (err) {
      console.error('[Session] Ingestion fallback failed:', err);
      setUserAnswerDraft('[Lỗi kết nối. Không thể nhận diện. Vui lòng điền câu trả lời.]');
      setSessionState('CONFIRM_ANSWER');
    }
  };

  // ── 6. Submit Answer (Confirm Draft & Advance State) ──
  const handleSubmitAnswer = async () => {
    if (!userAnswerDraft.trim()) return;

    // Push User answer to Chat transcript
    const answer = userAnswerDraft.trim();
    setChatLog((prev) => [...prev, { sender: 'User', text: answer, time: formatCurrentTime() }]);
    setSessionState('AI_THINKING');

    // Call questionService state machine with answer evaluation
    setTimeout(async () => {
      try {
        const nextQ = await questionService.getNextQuestion(id, answer);

        // Save evaluated QA pair to history database
        const currentSession = await historyService.getSessionById(id);
        if (currentSession && session) {
          const evalItem: QuestionFeedback = {
            question: currentQuestion,
            answer,
            score: nextQ.score,
            strengths: nextQ.strengths,
            improvements: nextQ.improvements,
            suggestedAnswer: nextQ.suggestedAnswer,
            topicTag: topicTag,
            isDeepDive: isDeepDive
          };
          currentSession.questions.push(evalItem);
          await historyService.saveSession(currentSession);
        }

        if (nextQ.isFinished) {
          handleInterviewFinish(false);
        } else {
          // Switch back to speaking the next question
          setCurrentQuestion(nextQ.questionText);
          setTopicTag(nextQ.topicTag);
          setIsDeepDive(nextQ.isDeepDive);
          setQuestionCount((prev) => prev + 1);

          setChatLog((prev) => [
            ...prev,
            { sender: 'AI', text: nextQ.questionText, time: formatCurrentTime(), isDeepDive: nextQ.isDeepDive }
          ]);

          setSessionState('AI_SPEAKING');
          speakQuestion(nextQ.questionText);
        }
      } catch (err) {
        console.error('Error transitioning question state:', err);
        // Fail-safe end interview
        handleInterviewFinish(false);
      }
    }, 1500); // 1.5s thinking delay
  };

  // ── 7. End Interview Execution ──
  const handleInterviewFinish = async (isTimeout = false) => {
    setSessionState('FINISHED');
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    
    try {
      const currentSession = await historyService.getSessionById(id);
      if (currentSession) {
        currentSession.status = 'Completed';
        
        // Calculate average overallScore
        if (currentSession.questions.length > 0) {
          const totalScores = currentSession.questions.reduce((sum, q) => sum + q.score, 0);
          currentSession.overallScore = Math.round(totalScores / currentSession.questions.length);
        } else {
          currentSession.overallScore = 60; // baseline if empty
        }

        await historyService.saveSession(currentSession);
      }
      
      router.push(`/interview/session/${id}/result`);
    } catch (err) {
      console.error('Error completing session:', err);
      router.push(`/history`);
    }
  };

  const handleEndEarlyConfirm = () => {
    setShowExitModal(false);
    handleInterviewFinish(false);
  };

  // Timer format (mm:ss)
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  };

  const isTimerUrgent = timeLeft < 120; // 2 minutes

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1>Phỏng vấn Kỹ thuật Mock</h1>
          <p>
            {session ? `Vị trí: ${session.roleTitle}` : 'Đang thiết lập...'}
          </p>
        </div>

        <div className={styles.headerRight}>
          <span className={styles.progressLabel}>Câu hỏi {questionCount} / 5</span>
          
          <div className={`${styles.timerBox} ${isTimerUrgent ? styles.timerWarning : ''}`}>
            <span>⏱</span>
            <span>{formatTime(timeLeft)}</span>
          </div>

          <button className={styles.endButton} onClick={() => setShowExitModal(true)}>
            Kết thúc phỏng vấn
          </button>
        </div>
      </header>

      {/* Service Connection Status Board */}
      <div className={styles.dashboard}>
        <span className={styles.engineStatus}>
          Tổng kết nối:
          <span className={`${styles.statusPill} ${socketConnected ? styles.pillOnline : styles.pillOffline}`}>
            {socketConnected ? 'Kết nối' : 'Ngoại tuyến'}
          </span>
        </span>
        <span className={styles.engineStatus}>
          Giọng nói (TTS):
          <span className={`${styles.statusPill} ${ttsMode === 'online' ? styles.pillOnline : styles.pillOffline}`}>
            {ttsMode === 'online' ? 'Trực tuyến' : 'Giả lập'}
          </span>
        </span>
        <span className={styles.engineStatus}>
          Nhận diện (STT):
          <span className={`${styles.statusPill} ${sttMode === 'online' ? styles.pillOnline : styles.pillOffline}`}>
            {sttMode === 'online' ? 'Trực tuyến' : 'Giả lập'}
          </span>
        </span>
      </div>

      {/* Main Grid: User Feed vs Avatar Feed */}
      <main className={styles.mainGrid}>
        {/* Left Column: User Webcam */}
        <section className={styles.sessionCard}>
          <div className={styles.cardTitle}>
            <span>ỨNG VIÊN (BẠN)</span>
            <span style={{ fontSize: '0.75rem', color: '#10b981' }}>● LIVE</span>
          </div>
          
          <div className={styles.webcamBox}>
            {permissionError ? (
              <div className={styles.webcamError}>
                <span>🚫</span>
                <h4>Quyền truy cập Camera/Mic bị từ chối</h4>
                <p>
                  Ditto cần quyền truy cập webcam và microphone của bạn để tiến hành buổi phỏng vấn trực tiếp. 
                  Hãy cho phép trong cài đặt trình duyệt của bạn và thử lại.
                </p>
                <button className={styles.webcamErrorBtn} onClick={startMediaCapture}>
                  Cho phép lại
                </button>
              </div>
            ) : (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={styles.videoElement}
                  style={{ display: cameraEnabled ? 'block' : 'none' }}
                />
                {!cameraEnabled && (
                  <div className={styles.webcamFallback}>
                    <span>📷 CAMERA OFF</span>
                  </div>
                )}
                
                {/* Audio Waves Recording HUD */}
                {recording && (
                  <div className={styles.recordingDot}>
                    <div className={styles.pulseRed} />
                    <span>ĐANG GHI ÂM</span>
                  </div>
                )}

                {/* Media Capture Toggle Toggles */}
                <div className={styles.overlayControls}>
                  <button
                    className={`${styles.controlBtn} ${!cameraEnabled ? styles.controlBtnMuted : styles.controlBtnActive}`}
                    onClick={toggleCamera}
                    title={cameraEnabled ? 'Tắt Camera' : 'Bật Camera'}
                  >
                    {cameraEnabled ? '📹' : '❌'}
                  </button>
                  <button
                    className={`${styles.controlBtn} ${!micEnabled ? styles.controlBtnMuted : styles.controlBtnActive}`}
                    onClick={toggleMic}
                    title={micEnabled ? 'Tắt Mic' : 'Bật Mic'}
                  >
                    {micEnabled ? '🎙️' : '🔇'}
                  </button>
                </div>
              </>
            )}
          </div>
        </section>

        {/* Right Column: AI Avatar Stage */}
        <section className={styles.sessionCard}>
          <div className={styles.cardTitle}>
            <span>NGƯỜI PHỎNG VẤN (AI)</span>
            {avatarPlaying && <span style={{ fontSize: '0.75rem', color: '#8b5cf6' }}>🔊 Đang nói</span>}
            {sessionState === 'LISTENING' && <span style={{ fontSize: '0.75rem', color: '#06b6d4' }}>👂 Đang lắng nghe</span>}
            {sessionState === 'AI_THINKING' && <span style={{ fontSize: '0.75rem', color: '#eab308' }}>⌛ Đang xử lý</span>}
          </div>

          <div
            className={`${styles.avatarBox} ${
              sessionState === 'LISTENING' ? styles.avatarBoxListening :
              sessionState === 'AI_THINKING' ? styles.avatarBoxThinking : ''
            }`}
          >
            {avatarConnected ? (
              <DittoAvatarModule
                controlled={true}
                analyser={avatarAnalyser}
                isConnected={socketConnected || ttsMode === 'mock'}
                isPlaying={avatarPlaying}
                isListening={sessionState === 'LISTENING'}
                isThinking={sessionState === 'AI_THINKING'}
              />
            ) : (
              <div className={styles.webcamFallback} style={{ color: '#cbd5e1' }}>
                <span>🤖 Đang kết nối mô hình 3D...</span>
              </div>
            )}
          </div>
        </section>

        {/* Dynamic Chat Transcript Board */}
        <section className={styles.transcriptCard}>
          <div className={styles.cardTitle}>
            <span>BẢN GHI HỘI THOẠI TRỰC TIẾP</span>
          </div>
          
          <div className={styles.transcriptScroll}>
            {chatLog.length === 0 ? (
              <div className={styles.transcriptEmpty}>
                <span>💬</span>
                <p>Nội dung phỏng vấn sẽ xuất hiện tại đây.</p>
              </div>
            ) : (
              chatLog.map((log, index) => (
                <div key={index} className={`${styles.messageRow} ${log.sender === 'AI' ? styles.messageRowAi : styles.messageRowUser}`}>
                  <div className={`${styles.bubble} ${log.sender === 'AI' ? styles.bubbleAi : styles.bubbleUser}`}>
                    {log.isDeepDive && (
                      <span className={styles.bubbleDeepDiveBadge}>Hỏi sâu (Deep dive)</span>
                    )}
                    <p style={{ margin: 0 }}>{log.text}</p>
                    <span className={styles.bubbleTime}>{log.time}</span>
                  </div>
                </div>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </section>

        {/* State Controls Actions Area */}
        <section className={styles.controlsPanel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              {sessionState === 'INITIALIZING' && (
                <>
                  <div className={styles.indicatorPulse} />
                  <span>Sẵn sàng bắt đầu buổi phỏng vấn?</span>
                </>
              )}
              {sessionState === 'AI_SPEAKING' && (
                <>
                  <div className={`${styles.indicatorPulse} ${styles.pulsePurple}`} />
                  <span>AI đang hỏi câu hỏi...</span>
                </>
              )}
              {sessionState === 'LISTENING' && (
                <>
                  <div className={`${styles.indicatorPulse} ${styles.pulseCyan}`} />
                  <span>Hãy trả lời bằng giọng nói qua Mic của bạn:</span>
                </>
              )}
              {sessionState === 'CONFIRM_ANSWER' && (
                <>
                  <div className={styles.indicatorPulse} style={{ backgroundColor: '#10b981' }} />
                  <span>Xác nhận/Chỉnh sửa câu trả lời của bạn:</span>
                </>
              )}
              {sessionState === 'AI_THINKING' && (
                <>
                  <div className={`${styles.indicatorPulse} ${styles.pulsePurple}`} style={{ animationDuration: '0.8s' }} />
                  <span>AI đang xử lý và đánh giá câu trả lời...</span>
                </>
              )}
            </div>
            
            {recording && (
              <div className={styles.waveform}>
                <div className={styles.waveBar} />
                <div className={styles.waveBar} />
                <div className={styles.waveBar} />
                <div className={styles.waveBar} />
                <div className={styles.waveBar} />
              </div>
            )}
          </div>

          {/* Caption Overlay / Edit Areas */}
          {sessionState === 'INITIALIZING' && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem 0' }}>
              <button className={styles.primaryBtn} style={{ padding: '0.8rem 2.5rem', fontSize: '1rem' }} onClick={handleStartInterview}>
                Bắt đầu ngay ➔
              </button>
            </div>
          )}

          {sessionState === 'AI_SPEAKING' && (
            <div className={styles.captionArea}>
              <p style={{ margin: 0 }}><strong>Ditto:</strong> &ldquo;{currentQuestion}&rdquo;</p>
            </div>
          )}

          {sessionState === 'LISTENING' && (
            <div className={styles.confirmBox}>
              <div className={styles.captionArea} style={{ minHeight: '100px', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
                {recording ? (
                  <>
                    <p style={{ margin: 0, color: '#0284c7', fontWeight: 600 }}>[Mic đang ghi âm. Nói rõ ràng...]</p>
                    <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.95rem', color: '#1e293b' }}>
                      {userAnswerDraft || <span className={styles.captionHint}>Chưa có âm thanh được thu nhận...</span>}
                    </p>
                  </>
                ) : (
                  <span className={styles.captionHint}>Click &ldquo;Ghi âm câu trả lời&rdquo; để bắt đầu phát biểu.</span>
                )}
              </div>
              <div className={styles.confirmActions}>
                {recording ? (
                  <button className={styles.dangerBtn} onClick={handleStopRecording}>
                    Tôi đã nói xong 🛑
                  </button>
                ) : (
                  <button className={styles.primaryBtn} onClick={handleStartRecording} disabled={permissionError}>
                    🎙️ Ghi âm câu trả lời
                  </button>
                )}
              </div>
            </div>
          )}

          {sessionState === 'CONFIRM_ANSWER' && (
            <div className={styles.confirmBox}>
              <textarea
                className={styles.confirmTextArea}
                value={userAnswerDraft}
                onChange={(e) => setUserAnswerDraft(e.target.value)}
                placeholder="Nhập hoặc sửa lại câu trả lời tại đây..."
              />
              <div className={styles.confirmActions}>
                <button className={styles.secondaryBtn} onClick={handleStartRecording}>
                  🎙️ Thu âm lại
                </button>
                <button className={styles.primaryBtn} onClick={handleSubmitAnswer} disabled={!userAnswerDraft.trim()}>
                  Gửi câu trả lời ➔
                </button>
              </div>
            </div>
          )}

          {sessionState === 'AI_THINKING' && (
            <div className={styles.captionArea} style={{ justifyContent: 'center', backgroundColor: '#faf5ff' }}>
              <span className={styles.captionHint} style={{ color: '#7c3aed' }}>Ditto đang cân nhắc câu hỏi tiếp theo dựa trên câu trả lời của bạn...</span>
            </div>
          )}
        </section>
      </main>

      {/* Exit confirmation modal dialog */}
      {showExitModal && (
        <div className={styles.modalOverlay}>
          <div className={styles.modal}>
            <h3>Kết thúc phỏng vấn sớm?</h3>
            <p>
              Bạn đang ở trong buổi phỏng vấn trực tiếp. Nếu kết thúc sớm, 
              kết quả sẽ chỉ được tính cho các câu hỏi bạn đã hoàn thành. 
              Bạn có chắc chắn muốn thoát?
            </p>
            <div className={styles.modalActions}>
              <button className={styles.secondaryBtn} onClick={() => setShowExitModal(false)}>
                Hủy bỏ
              </button>
              <button className={styles.dangerBtn} onClick={handleEndEarlyConfirm}>
                Đồng ý thoát
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
