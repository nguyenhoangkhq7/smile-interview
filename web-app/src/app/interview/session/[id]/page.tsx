'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { io, Socket } from 'socket.io-client';
import { InterviewerAvatar } from '@/components/interview/InterviewerAvatar/InterviewerAvatar';
import { historyService, SessionHistoryItem, QuestionFeedback } from '@/services/historyService';
// Removed questionService
import { useSessionRecorder } from '@/hooks/useSessionRecorder';
import { useAuthStore } from '@/store/authStore';
import styles from './session.module.css';
import {
  Camera,
  CameraOff,
  Mic,
  MicOff,
  Timer,
  Info,
  Download,
  PhoneOff,
  ListOrdered,
  MessageSquare,
  Radio,
  Circle,
  Video,
  VideoOff,
  Volume2,
  Play,
  X,
  CornerDownRight,
  Copy,
  CheckCircle,
  ArrowRight,
  Send
} from 'lucide-react';

type SessionState = 'INITIALIZING' | 'AI_SPEAKING' | 'LISTENING' | 'AI_THINKING' | 'FINISHED';

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
  const transcriptScrollRef = useRef<HTMLDivElement>(null);

  // Audio / Socket / Engine Service Status
  const [socketConnected, setSocketConnected] = useState(false);
  const [ttsMode, setTtsMode] = useState<'online' | 'mock'>('online');
  const [sttMode, setSttMode] = useState<'online' | 'mock'>('online');
  const socketRef = useRef<Socket | null>(null);

  // Persistent Audio Pipeline Refs (Prevents browser autoplay blockages)
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);

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
  const [inputType, setInputType] = useState<'voice' | 'keyboard'>('voice');
  const [keyboardAnswer, setKeyboardAnswer] = useState('');
  const [baseQuestionIndex, setBaseQuestionIndex] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const speechRecognitionRef = useRef<any>(null);
  const isExitingRef = useRef(false);
  const finalTranscriptRef = useRef<string>('');
  const latestTranscriptRef = useRef<string>('');

  // Audio playing singletons for TTS Mock Mode
  const mockAnalyserIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Video recording hook & Finished screen states
  const { startRecording, stopRecording, isRecording, recordedBlob, recordingDurationMs } = useSessionRecorder(mediaStream);
  const [showInfoBanner, setShowInfoBanner] = useState(true);
  const currentQuestionRef = useRef<string>('');

  // Simulated streaming STT state
  const [isRevealing, setIsRevealing] = useState(false);
  const autoStartMicRef = useRef(false);

  const formatCurrentTime = () => {
    const d = new Date();
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  };

  // ── Auto-scroll container to bottom when turns or draft results update ──
  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [chatLog, userAnswerDraft]);

  // ── Initialize Audio context synchronously on User click gesture ──
  const initAudioOnUserGesture = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (!audioContextRef.current) {
      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
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
          // Transition to LISTENING when speech ends
          autoStartMicRef.current = true;
          setSessionState('LISTENING');
        });

        console.log('[Session] Audio pipeline initialized on user gesture');
      } catch (err) {
        console.error('[Session] Failed to initialize audio pipeline:', err);
      }
    } else if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume().catch((err) => {
        console.error('[Session] Failed to resume AudioContext:', err);
      });
    }
  }, []);

  // ── End Interview Execution ──
  const handleInterviewFinish = useCallback(async (isTimeout = false) => {
    isExitingRef.current = true;
    setSessionState('FINISHED');
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    
    // Stop recording first
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
    if (speechRecognitionRef.current) {
      try { speechRecognitionRef.current.stop(); } catch {}
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
    }

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

        await historyService.saveSession({
          ...currentSession,
          replaceQuestions: true
        });

        // Trigger background evaluation on the backend immediately!
        console.log(`[Session Finish] Triggering background evaluation for session: ${id}`);
        const token = useAuthStore.getState().token;
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        fetch(`/api/sessions/${id}/evaluate`, { 
          method: 'POST',
          headers: headers
        }).catch((evalErr) => {
          console.error('[Session Finish] Background evaluation trigger failed:', evalErr);
        });
      }
    } catch (err) {
      console.error('Error completing session:', err);
    }
  }, [id, mediaStream]);

  // ── Speak Question (TTS Interface & Fallback) ──
  const speakQuestion = useCallback((text: string, forceOffline: boolean = false) => {
    if (!forceOffline && ttsMode === 'online' && socketRef.current?.connected) {
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

      const voices = window.speechSynthesis.getVoices();
      const viVoice = voices.find(v => v.lang.includes('VI') || v.lang.includes('vi'));
      if (viVoice) utterance.voice = viVoice;

      const mockAnalyserNode = {
        frequencyBinCount: 128,
        getByteFrequencyData: (array: Uint8Array) => {
          for (let i = 0; i < array.length; i++) {
            array[i] = Math.random() * 160 + 20;
          }
        }
      };

      utterance.onstart = () => {
        setAvatarPlaying(true);
        setAvatarAnalyser(mockAnalyserNode);

        mockAnalyserIntervalRef.current = setInterval(() => {
          // Simply triggers useFrame cycles
        }, 100);
      };

      utterance.onend = () => {
        setAvatarPlaying(false);
        setAvatarAnalyser(null);
        if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);
        autoStartMicRef.current = true;
        setSessionState('LISTENING');
      };

      utterance.onerror = (e) => {
        console.error('SpeechSynthesis error:', e);
        setAvatarPlaying(false);
        setAvatarAnalyser(null);
        autoStartMicRef.current = false;
        setSessionState('LISTENING');
      };

      window.speechSynthesis.speak(utterance);
    }
  }, [ttsMode]);

  // ── Submit Answer (Auto-submit finalized transcript and evaluation) ──
  const submitFinalAnswer = useCallback(async (answer: string) => {
    if (!answer.trim()) return;

    // Push User answer to Chat transcript
    setChatLog((prev) => [...prev, { sender: 'User', text: answer, time: formatCurrentTime() }]);
    setUserAnswerDraft('');
    setSessionState('AI_THINKING');

    if (socketRef.current?.connected) {
      socketRef.current.emit('orchestration-event', {
        type: 'CANDIDATE_TEXT_SUBMIT',
        payload: { text: answer }
      });

      // Save user answer to session history
      if (id) {
        historyService.getSessionById(id).then(session => {
          if (session) {
            const updatedQuestions = session.questions ? [...session.questions] : [];
            if (updatedQuestions.length === 0) {
              // Self-heal: if empty, push the current question being answered
              updatedQuestions.push({
                question: currentQuestionRef.current || 'Câu hỏi',
                answer: answer,
                score: 0,
                strengths: '',
                improvements: '',
                suggestedAnswer: '',
                topicTag: topicTag || '',
                isDeepDive: isDeepDive
              });
            } else {
              const lastIndex = updatedQuestions.length - 1;
              updatedQuestions[lastIndex] = {
                ...updatedQuestions[lastIndex],
                answer: answer
              };
            }
            historyService.saveSession({
              ...session,
              questions: updatedQuestions,
              replaceQuestions: true
            });
          }
        });
      }
    } else {
      console.error('Socket not connected to send answer');
      setSessionState('LISTENING');
    }
  }, []);

  // ── Server-Sent Events (SSE) streaming reveal for online STT ──
  const streamTranscript = useCallback((fullText: string) => {
    setRecording(false);
    autoStartMicRef.current = false;
    setIsRevealing(true);
    setUserAnswerDraft('');
    setSessionState('LISTENING');

    const streamingUrl = process.env.NEXT_PUBLIC_STREAMING_SERVICE_URL || 'http://localhost:8001';
    const sseUrl = `${streamingUrl}/api/v1/audio/stream-transcribe?text=${encodeURIComponent(fullText)}`;

    let eventSource: EventSource | null = null;
    let fallbackInterval: NodeJS.Timeout | null = null;

    const runFallback = () => {
      if (fallbackInterval) return;
      console.warn('[SSE] EventSource failed or unsupported. Falling back to client-side streaming reveal.');
      const words = fullText.split(' ');
      let currentWordIndex = 0;
      let currentText = '';
      fallbackInterval = setInterval(() => {
        if (currentWordIndex < words.length) {
          currentText += (currentWordIndex === 0 ? '' : ' ') + words[currentWordIndex];
          setUserAnswerDraft(currentText);
          currentWordIndex++;
        } else {
          if (fallbackInterval) clearInterval(fallbackInterval);
          setIsRevealing(false);
          submitFinalAnswer(fullText);
        }
      }, 80);
    };

    try {
      eventSource = new EventSource(sseUrl);
      let currentText = '';

      eventSource.onmessage = (event) => {
        const data = event.data;
        if (data === '[START]') {
          setUserAnswerDraft('');
        } else if (data === '[END]') {
          if (eventSource) eventSource.close();
          setIsRevealing(false);
          submitFinalAnswer(fullText);
        } else {
          currentText += (currentText === '' ? '' : ' ') + data;
          setUserAnswerDraft(currentText);
        }
      };

      eventSource.onerror = () => {
        if (eventSource) eventSource.close();
        runFallback();
      };
    } catch (e) {
      runFallback();
    }
  }, [submitFinalAnswer]);

  // POST fallback if socket STT drops
  const uploadAudioBlob = useCallback(async (blob: Blob) => {
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
      streamTranscript(data.text || '');
    } catch (err) {
      console.error('[Session] Ingestion fallback failed:', err);
      setUserAnswerDraft('[Lỗi kết nối. Không thể nhận diện. Vui lòng ghi âm lại.]');
      setRecording(false);
      autoStartMicRef.current = false;
      setSessionState('LISTENING');
    }
  }, [streamTranscript]);

  // ── 5. User Recording & Transcribing (STT Interface & Fallback) ──
  const handleStartRecording = useCallback(async () => {
    setUserAnswerDraft('');
    audioChunksRef.current = [];

    if (sttMode === 'online') {
      if (!mediaStream) {
        console.error('No media stream available for online STT.');
        alert('Thiết bị ghi âm không sẵn sàng hoặc quyền truy cập Microphone bị từ chối.');
        return;
      }
      setRecording(true);
      try {
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
          if (isExitingRef.current) {
            console.log('[Session] Exiting. Ignoring onstop event.');
            return;
          }
          
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });

          // Prevent sending empty/silent audio to avoid STT hallucinations on silence
          if (audioBlob.size < 1000) {
            console.warn('[Session] Audio recording was empty or too short, ignoring. Size:', audioBlob.size);
            setRecording(false);
            setSessionState('LISTENING');
            return;
          }

          setSessionState('AI_THINKING');
          autoStartMicRef.current = false;

          const buffer = await audioBlob.arrayBuffer();
          if (socketRef.current?.connected) {
            console.log('[Session] Sending audio buffer to STT socket...');
            socketRef.current.emit('process-stt', buffer);
          } else {
            uploadAudioBlob(audioBlob);
          }
        };

        recorder.start();
      } catch (err) {
        console.error('Failed to start MediaRecorder:', err);
        setRecording(false);
      }
    } else {
      setRecording(true);
      console.log('[Session] Starting webkitSpeechRecognition...');
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const rec = new SpeechRecognition();
        rec.lang = 'vi-VN';
        rec.interimResults = true;
        rec.continuous = true;
        
        finalTranscriptRef.current = '';
        latestTranscriptRef.current = '';
        setUserAnswerDraft('');

        rec.onresult = (event: any) => {
          console.log('[STT] onresult event received:', event);
          let interimTranscript = '';
          let finalTranscript = '';
          
          for (let i = 0; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript;
            } else {
              interimTranscript += transcript;
            }
          }
          
          finalTranscriptRef.current = finalTranscript;
          const fullText = finalTranscript + interimTranscript;
          latestTranscriptRef.current = fullText;
          
          console.log('[STT] Current accumulated text:', fullText);
          setUserAnswerDraft(fullText);
        };

        rec.onerror = (e: any) => {
          console.error('[STT] Speech recognition error:', e);
        };

        rec.onend = () => {
          console.log('[STT] Speech recognition ended.');
          setRecording(false);
          autoStartMicRef.current = false;
          
          if (isExitingRef.current) {
            console.log('[Session] Exiting. Ignoring SpeechRecognition onend event.');
            return;
          }
          
          const finalizedAnswer = latestTranscriptRef.current.trim() || finalTranscriptRef.current.trim();
          console.log('[STT] Finalized text to submit:', finalizedAnswer);
          
          if (finalizedAnswer) {
            submitFinalAnswer(finalizedAnswer);
          } else {
            setSessionState('LISTENING');
          }
        };

        speechRecognitionRef.current = rec;
        rec.start();
      } else {
        console.warn('SpeechRecognition not supported in this browser. Switching to keyboard input.');
        alert('Trình duyệt của bạn không hỗ trợ Nhận diện Giọng nói. Vui lòng nhập câu trả lời bằng bàn phím.');
        setInputType('keyboard');
        setRecording(false);
      }
    }
  }, [sttMode, mediaStream, uploadAudioBlob, submitFinalAnswer]);

  const handleStopRecording = useCallback(() => {
    setRecording(false);
    autoStartMicRef.current = false;
    if (sttMode === 'online') {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    } else {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
      }
    }
  }, [sttMode]);

  // Space Bar keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        const activeEl = document.activeElement;
        if (activeEl) {
          const tag = activeEl.tagName.toUpperCase();
          if (tag === 'INPUT' || tag === 'TEXTAREA' || activeEl.hasAttribute('contenteditable')) {
            return;
          }
        }

        e.preventDefault(); // Prevent page scrolling

        if (sessionState === 'LISTENING' && !isRevealing) {
          if (recording) {
            handleStopRecording();
          } else {
            handleStartRecording();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [sessionState, recording, isRevealing, handleStartRecording, handleStopRecording]);

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

  useEffect(() => {
    async function initSession() {
      if (!id) return;
      console.log('[Session] Fetching session detail for ID:', id);
      const data = await historyService.getSessionById(id);
      console.log('[Session] Fetched session data:', data);
      if (data) {
        setSession(data);
        
        // Resume state from history
        if (data.questions && data.questions.length > 0) {
          const initialChatLog: any[] = [];
          let baseAnsweredCount = 0;
          data.questions.forEach((q: any) => {
            if (q.question) {
               const questionText = typeof q.question === 'object' && q.question !== null
                 ? q.question.question
                 : q.question;
               initialChatLog.push({ sender: 'AI', text: questionText, time: formatCurrentTime(), isDeepDive: q.isDeepDive });
            }
            if (q.answer) {
               initialChatLog.push({ sender: 'User', text: q.answer, time: formatCurrentTime() });
               if (!q.isDeepDive) {
                 baseAnsweredCount++;
               }
            }
          });
          console.log('[Session] Reconstructed chatLog:', initialChatLog, 'baseAnsweredCount:', baseAnsweredCount);
          if (initialChatLog.length > 0) {
             setChatLog(initialChatLog);
             setQuestionCount(initialChatLog.filter(log => log.sender === 'AI').length);
             setBaseQuestionIndex(baseAnsweredCount);
          }
        }
      }
    }
    initSession();
    startMediaCapture();

    return () => {
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
      }
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (socketRef.current) socketRef.current.disconnect();
      if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);
      
      // Clean up audio
      if (audioElRef.current) {
        audioElRef.current.pause();
        audioElRef.current.src = '';
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, [id]);

  // Starts the countdown clock
  const startTimer = useCallback(() => {
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
  }, [handleInterviewFinish]);

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

  // Keep Callback Refs for WebSocket Event Listeners (Avoid stale closures & socket recreation)
  const streamTranscriptRef = useRef(streamTranscript);
  const initAudioOnUserGestureRef = useRef(initAudioOnUserGesture);

  useEffect(() => {
    streamTranscriptRef.current = streamTranscript;
  }, [streamTranscript]);

  useEffect(() => {
    initAudioOnUserGestureRef.current = initAudioOnUserGesture;
  }, [initAudioOnUserGesture]);

  const handleInterviewFinishRef = useRef(handleInterviewFinish);
  const speakQuestionRef = useRef(speakQuestion);

  useEffect(() => {
    handleInterviewFinishRef.current = handleInterviewFinish;
  }, [handleInterviewFinish]);

  useEffect(() => {
    speakQuestionRef.current = speakQuestion;
  }, [speakQuestion]);

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

      // We will join-interview manually via handleStartInterview to ensure user gesture
    });

    socket.on('orchestration-event', (data: any) => {
      console.log('[Session] Received orchestration event:', data);
      if (data.type === 'INTERVIEWER_ACTION') {
        const { actionType, text, score, evaluation } = data.payload;
        if (actionType === 'CONCLUDING') {
          handleInterviewFinishRef.current(false);
          return;
        }

        // Save evaluation for the previous question if available
        if (evaluation && score !== undefined) {
          historyService.getSessionById(id).then(session => {
             if (session && session.questions) {
                // Find the first question that doesn't have a score yet or update the latest one
                // Actually, the answer is just pushed to chatLog, but the question was already there.
                // Let's just find the last question and update it.
                const updatedQuestions = [...session.questions];
                if (updatedQuestions.length > 0) {
                   const lastIndex = updatedQuestions.length - 1;
                   updatedQuestions[lastIndex] = {
                      ...updatedQuestions[lastIndex],
                      score: score,
                      strengths: evaluation, // Mapping evaluation string to strengths or a combined field
                      improvements: actionType === 'FOLLOW_UP' ? 'Needs more detail' : '',
                   };
                   
                   // If it's a transition to a NEW topic, we might want to add the new question to the list.
                   // If it's FOLLOW_UP, we also add the new follow-up question.
                   updatedQuestions.push({
                      question: text,
                      answer: '',
                      score: 0,
                      strengths: '',
                      improvements: '',
                      suggestedAnswer: '',
                      topicTag: '',
                      isDeepDive: actionType === 'FOLLOW_UP'
                   });

                   historyService.saveSession({
                      ...session,
                      questions: updatedQuestions,
                      replaceQuestions: true
                   });
                }
             }
          });
        }

        setCurrentQuestion(text);
        currentQuestionRef.current = text;
        setQuestionCount((prev) => prev + 1);
        setIsDeepDive(actionType === 'FOLLOW_UP');

        setChatLog((prev) => [
          ...prev,
          { sender: 'AI', text, time: formatCurrentTime(), isDeepDive: actionType === 'FOLLOW_UP' }
        ]);

        setSessionState('AI_SPEAKING');
        speakQuestionRef.current(text);
      } else if (data.type === 'STATE_UPDATE') {
        if (data.payload.status === 'COMPLETED') {
          handleInterviewFinishRef.current(false);
        } else if (data.payload.status === 'INIT') {
           setSessionState('INITIALIZING');
        } else if (data.payload.status === 'IN_PROGRESS') {
           // User rejoined an in-progress session, let them continue speaking
           setSessionState('LISTENING');
        }
      }
    });

    socket.on('connect_error', () => {
      console.warn('[Session] Connection to streaming service failed.');
      setSocketConnected(false);
      setAvatarConnected(true);
    });

    // Handle incoming audio transcriptions from server-side STT
    socket.on('stt-result', (data: any) => {
      if (data.status === 'success') {
        streamTranscriptRef.current(data.text);
      } else {
        setUserAnswerDraft('[Không nhận diện được giọng nói. Vui lòng ghi âm lại.]');
        setRecording(false);
        setSessionState('LISTENING');
      }
    });

    socket.on('stt-error', (err: any) => {
      console.error('[Session] STT Socket Error:', err);
      setUserAnswerDraft('[Lỗi xử lý âm thanh. Vui lòng ghi âm lại.]');
      setRecording(false);
      setSessionState('LISTENING');
    });

    socket.on('tts-error', (err: any) => {
      console.error('[Session] TTS Socket Error:', err);
      // Fallback to offline TTS
      setTtsMode('mock');
      if (currentQuestionRef.current && speakQuestionRef.current) {
        speakQuestionRef.current(currentQuestionRef.current, true);
      } else {
        setSessionState('LISTENING');
      }
    });

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

        // Ensure audio pipeline is initialized/resumed
        initAudioOnUserGestureRef.current();

        const ctx = audioContextRef.current;
        const audio = audioElRef.current;

        if (ctx && ctx.state === 'suspended') {
          await ctx.resume();
        }

        if (audio) {
          audio.src = url;
          audio.addEventListener('ended', () => {
            URL.revokeObjectURL(url);
            setAvatarPlaying(false);
            autoStartMicRef.current = true;
            setSessionState('LISTENING');
          }, { once: true });
          setAvatarPlaying(true);
          await audio.play();
        }
      } catch (err) {
        console.error('[Session] Audio playback error:', err);
        setSessionState('LISTENING');
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [id]);

  // ── 3. Start First Question ──
  const handleStartInterview = async () => {
    console.log('[Session] handleStartInterview clicked. sessionState:', sessionState, 'socket connected:', socketRef.current?.connected);
    initAudioOnUserGesture();
    setSessionState('AI_THINKING');
    startTimer();

    if (socketRef.current?.connected) {
      let initialQuestions = [];
      try {
        if (session?.actionableSuggestions) {
          initialQuestions = typeof session.actionableSuggestions === 'string' 
            ? JSON.parse(session.actionableSuggestions) 
            : session.actionableSuggestions;
        }
      } catch (e) {
        console.error('Failed to parse initialQuestions from actionableSuggestions', e);
      }
      
      console.log('[Session] Emitting join-interview with initialQuestions:', initialQuestions, 'baseQuestionIndex:', baseQuestionIndex);
      socketRef.current.emit('join-interview', { 
        interviewId: id, 
        userId: 'candidate-user', 
        initialQuestions,
        baseQuestionIndex
      });
    } else {
      console.warn('[Session] Cannot emit join-interview, socket is disconnected!');
    }
  };

  useEffect(() => {
    if (sessionState !== 'LISTENING') return;
    if (!autoStartMicRef.current) return;
    if (recording || isRevealing || permissionError || !micEnabled) return;

    autoStartMicRef.current = false;
    const timerId = window.setTimeout(() => {
      handleStartRecording();
    }, 150);

    return () => window.clearTimeout(timerId);
  }, [sessionState, recording, isRevealing, permissionError, micEnabled, handleStartRecording]);

  const handleEndEarlyConfirm = () => {
    setShowExitModal(false);
    handleInterviewFinish(false);
  };

  // Auto-stop video recording if page transitions to FINISHED
  useEffect(() => {
    if (sessionState === 'FINISHED' && isRecording) {
      stopRecording();
    }
  }, [sessionState, isRecording, stopRecording]);

  const handleToggleSessionRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleDownloadVideo = () => {
    if (!recordedBlob) return;
    const url = URL.createObjectURL(recordedBlob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `smile-interview-${id}-${new Date().toISOString().slice(0, 10)}.webm`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  };

  const handleGoToResults = () => {
    router.push(`/interview/session/${id}/result`);
  };

  // Timer format (mm:ss)
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  };

  const formatDuration = (ms: number) => {
    const totalSecs = Math.floor(ms / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getAiStatusChip = () => {
    if (sessionState === 'AI_SPEAKING') {
      return (
        <div className="flex items-center gap-2 bg-violet-50 border border-violet-200 backdrop-blur-md px-3 py-1.5 rounded-full text-[11px] font-semibold text-violet-700 shadow-sm animate-fade-in">
          <Volume2 size={12} className="text-violet-500 animate-pulse" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang nói</span>
        </div>
      );
    }
    if (sessionState === 'LISTENING') {
      return (
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 backdrop-blur-md px-3 py-1.5 rounded-full text-[11px] font-semibold text-emerald-700 shadow-sm animate-fade-in">
          <Radio size={12} className="text-emerald-300 animate-pulse" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang lắng nghe</span>
        </div>
      );
    }
    if (sessionState === 'AI_THINKING') {
      return (
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 backdrop-blur-md px-3 py-1.5 rounded-full text-[11px] font-semibold text-slate-600 shadow-sm animate-fade-in">
          <Timer size={12} className="text-slate-500 animate-spin" />
          <span>NGƯỜI PHỎNG VẤN (AI) — Đang suy nghĩ</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 backdrop-blur-md px-3 py-1.5 rounded-full text-[11px] font-semibold text-slate-500 shadow-sm animate-fade-in">
        <Circle size={12} className="text-slate-400" />
        <span>NGƯỜI PHỎNG VẤN (AI)</span>
      </div>
    );
  };

  // ── Render FINISHED Screen ──
  if (sessionState === 'FINISHED') {
    return (
      <div className="min-h-screen w-screen bg-slate-50 text-slate-800 flex flex-col font-sans animate-fade-in">
        {/* Header */}
        <header className={styles.header}>
          <div className="flex items-center gap-4">
            <Link href="/history">
              <img src="/logo.png" alt="Smile Interview Logo" className="h-9 w-auto" />
            </Link>
            <div className="h-4 w-[1px] bg-slate-200" />
            <div>
              <h1 className="text-sm font-semibold tracking-wide text-slate-900">Phỏng vấn Kỹ thuật</h1>
              <p className="text-xs text-slate-500">
                {session ? `Vị trí: ${session.roleTitle}` : 'Đang thiết lập...'}
              </p>
            </div>
          </div>
        </header>

        <main className="flex-grow flex flex-col items-center justify-center min-h-[80vh] gap-6 p-12 bg-slate-50">
          <div className={styles.finishedCard}>
            <div className="w-16 h-16 bg-emerald-50 border border-emerald-100 rounded-full flex items-center justify-center mb-2 shadow-inner">
              <CheckCircle size={48} className="text-emerald-500" />
            </div>
            
            <h2 className={styles.finishedTitle}>Buổi phỏng vấn đã hoàn thành!</h2>
            <p className={styles.finishedDesc}>
              Cảm ơn bạn đã tham gia buổi phỏng vấn giả lập trực tuyến. Bạn có thể tải video ghi hình buổi phỏng vấn (bao gồm webcam và mic của bạn) dưới đây để phục vụ tự đánh giá.
            </p>

            <div className="w-full flex flex-col gap-4 items-center">
              {recordedBlob && (
                <div className="w-full flex flex-col gap-4 items-center">
                  <button className={styles.downloadBtn} onClick={handleDownloadVideo}>
                    <Download size={16} />
                    <span>Tải video cuộc phỏng vấn</span>
                  </button>

                  {showInfoBanner && (
                    <div className="bg-slate-50 border border-slate-200 text-[10px] text-slate-500 p-3.5 rounded-xl text-left leading-relaxed flex items-start gap-2 relative animate-fade-in w-full">
                      <Info size={14} className="text-slate-400 shrink-0 mt-0.5" />
                      <span>
                        Video chỉ chứa hình ảnh và giọng nói của bạn. Cuộc trò chuyện với AI không được ghi lại trong file video.
                      </span>
                      <button className="text-slate-400 hover:text-slate-600 absolute top-2 right-2" onClick={() => setShowInfoBanner(false)}>
                        <X size={12} />
                      </button>
                    </div>
                  )}
                </div>
              )}

              <button
                className={styles.viewResultsBtn}
                onClick={handleGoToResults}
              >
                <span className="flex items-center justify-center gap-1.5">
                  <span>Xem báo cáo kết quả đánh giá</span>
                  <ArrowRight size={16} />
                </span>
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50 overflow-hidden">
      
      {/* Header */}
      <header className={styles.header}>
        <div className="flex items-center gap-4">
          <Link href="/history">
            <img src="/logo.png" alt="Smile Interview Logo" className="h-9 w-auto" />
          </Link>
          <div className="h-4 w-[1px] bg-slate-200" />
          <div>
            <h1 className="text-sm font-semibold tracking-wide text-slate-900">Phỏng vấn Kỹ thuật</h1>
            <p className="text-xs text-slate-500">
              {session ? `Vị trí: ${session.roleTitle}` : 'Đang thiết lập...'}
            </p>
          </div>
        </div>

        {/* Timer countdown placed in header top-right */}
        <div className="flex items-center gap-2">
          <Timer size={18} className={timeLeft <= 60 ? 'text-red-600 animate-pulse' : timeLeft <= 180 ? 'text-amber-500' : 'text-slate-800'} />
          <span className={`font-mono text-base font-semibold tracking-wide ${timeLeft <= 60 ? 'text-red-600 animate-pulse' : timeLeft <= 180 ? 'text-amber-600' : 'text-slate-800'}`}>
            {formatTime(timeLeft)}
          </span>
        </div>
      </header>

      {/* MAIN CONTENT WRAPPER - Centered horizontally */}
      <main className="flex-1 w-full overflow-hidden flex flex-col items-center py-6 min-h-0">
        {/* CENTERED CONTAINER - Holds videos and transcript */}
        <div className="w-full max-w-6xl flex flex-col h-full gap-6 px-4 lg:px-8 min-h-0">
          {/* 1. TOP VIDEO GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 shrink-0 w-full">
          {/* Left panel: Candidate Webcam */}
          <div className="relative aspect-video rounded-2xl overflow-hidden border border-slate-200 bg-[#0f172a] shadow-sm w-full">
            {/* Webcam video overlay label */}
            <div className="absolute top-[10px] left-[10px] bg-black/50 backdrop-blur-[4px] text-[#f1f5f9] text-[0.65rem] font-semibold tracking-wider px-2 py-1 rounded-[4px] z-10 flex items-center gap-1.5">
              {isRecording && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse shrink-0" />}
              {!cameraEnabled && <CameraOff size={11} className="text-slate-300 shrink-0" />}
              <span>ỨNG VIÊN (BẠN)</span>
            </div>

            <div className="w-full h-full relative">
              {permissionError ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-rose-950/20">
                  <Info size={28} className="text-rose-500 mb-2" />
                  <h4 className="text-xs font-bold text-rose-600 uppercase tracking-wider mb-1">Quyền truy cập Camera/Mic bị từ chối</h4>
                  <p className="text-[11px] text-slate-400 max-w-[280px] leading-relaxed mb-3">
                    Cho phép quyền truy cập webcam/mic trong trình duyệt để AI có thể đánh giá.
                  </p>
                  <button className="bg-rose-600 hover:bg-rose-500 active:scale-95 text-white text-[11px] font-bold px-3 py-1.5 rounded-lg transition" onClick={startMediaCapture}>
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
                    disablePictureInPicture
                    className={styles.webcamVideo}
                    style={{ display: cameraEnabled ? 'block' : 'none' }}
                  />
                  {!cameraEnabled && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0f172a]">
                      <CameraOff size={32} className="text-slate-500 mb-2" />
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">CAMERA OFF</span>
                    </div>
                  )}

                  {/* Overlaid Record Pill centered bottom of candidate panel */}
                  <button
                    className={`${styles.recordBtn} ${isRecording ? styles.recording : ''}`}
                    onClick={handleToggleSessionRecording}
                  >
                    {isRecording ? (
                      <>
                        <span className={styles.recordPulse} />
                        <span>Đang ghi {formatDuration(recordingDurationMs)}</span>
                      </>
                    ) : (
                      <>
                        <Video size={14} />
                        <span>Ghi lại</span>
                      </>
                    )}
                  </button>

                  {/* Bottom-right Overlay Group: Mic/Camera toggles + End Session */}
                  <div className={styles.controlsOverlay}>
                    <button
                      className={`${styles.controlBtn} ${micEnabled ? styles.active : styles.muted}`}
                      onClick={toggleMic}
                      title={micEnabled ? 'Tắt Mic' : 'Bật Mic'}
                    >
                      {micEnabled ? <Mic size={16} /> : <MicOff size={16} />}
                    </button>

                    <button
                      className={`${styles.controlBtn} ${cameraEnabled ? styles.active : styles.muted}`}
                      onClick={toggleCamera}
                      title={cameraEnabled ? 'Tắt Camera' : 'Bật Camera'}
                    >
                      {cameraEnabled ? <Camera size={16} /> : <CameraOff size={16} />}
                    </button>

                    <button
                      className={styles.endBtn}
                      onClick={() => setShowExitModal(true)}
                    >
                      <PhoneOff size={14} />
                      <span>Kết thúc</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Right panel: AI Avatar */}
          <div className="relative aspect-video rounded-2xl overflow-hidden border border-slate-200 bg-[#0f172a] shadow-sm w-full">
            {/* AI Status tag overlay */}
            <div className="absolute top-[10px] left-[10px] bg-black/50 backdrop-blur-[4px] text-[#f1f5f9] text-[0.65rem] font-semibold tracking-wider px-2 py-1 rounded-[4px] z-10 flex items-center gap-1.5">
              <span>NGƯỜI PHỎNG VẤN (AI)</span>
            </div>

            <div className={styles.avatarBox}>
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
                  <Info size={32} className="text-slate-500 animate-spin mb-2" />
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Đang tải Avatar 3D...</span>
                </div>
              )}
            </div>
          </div>
        </div>

      {/* 2. BOTTOM TRANSCRIPT */}
      <div className="flex-grow flex-1 min-h-0 bg-white border border-slate-200 rounded-2xl shadow-sm flex flex-col overflow-hidden relative w-full mt-6">
        
        {/* Section Header */}
        <div className={styles.transcriptHeader}>
          <div className="flex items-center gap-2">
            <MessageSquare size={14} className="text-indigo-600" />
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Bản ghi hội thoại trực tiếp</span>
          </div>
          
          <button disabled className="text-slate-400 opacity-50 text-xs flex items-center gap-1 cursor-not-allowed">
            <Copy size={12} />
            <span>Sao chép</span>
          </button>
        </div>

        {/* Transcript Scroll Container */}
        <div ref={transcriptScrollRef} className={`${styles.transcriptScroll} px-6 py-4`}>
          {chatLog.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center gap-4 py-12 bg-white min-h-[200px] animate-fade-in">
              <MessageSquare size={36} className="text-[#cbd5e1]" />
              <p className="text-sm text-[#94a3b8]">Nội dung phỏng vấn sẽ xuất hiện tại đây.</p>
              {sessionState === 'INITIALIZING' && (
                <button 
                  className={styles.startBtn} 
                  onClick={handleStartInterview}
                >
                  <Play size={14} className="fill-current" />
                  <span>Bắt đầu phỏng vấn</span>
                </button>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4 w-full">
              {chatLog.map((log, index) => {
                const isAi = log.sender === 'AI';
                return (
                  <div key={index} className={`flex flex-col max-w-[75%] ${isAi ? 'self-start items-start' : 'self-end items-end'}`}>
                    <span className="text-[10px] text-slate-400 font-bold mb-1 ml-1">
                      {isAi ? 'NGƯỜI PHỎNG VẤN (AI)' : 'BẠN'}
                    </span>
                    <div className={isAi ? styles.aiBubble : styles.userBubble}>
                      {isAi && log.isDeepDive && (
                        <div className="flex items-center gap-1 text-[10px] font-bold text-violet-600 mb-1">
                          <CornerDownRight size={10} />
                          <span>HỎI SÂU</span>
                        </div>
                      )}
                      <p className="whitespace-pre-line">{log.text}</p>
                      <span className="block text-[9px] text-slate-400 mt-1.5 text-right">{log.time}</span>
                    </div>
                  </div>
                );
              })}

              {/* Real-time speech streaming draft bubble */}
              {sessionState === 'LISTENING' && userAnswerDraft && (
                <div className="flex flex-col max-w-[75%] self-end items-end">
                  <span className="text-[10px] text-emerald-600 font-bold mb-1 mr-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                    <span>ĐANG NÓI...</span>
                  </span>
                  <div className={`${styles.userBubble} bg-emerald-50/40 border border-dashed border-emerald-300 text-emerald-950`}>
                    <p className="inline">
                      {userAnswerDraft}
                      <span className="inline-block w-1.5 h-4 ml-0.5 bg-emerald-500 animate-pulse align-middle" />
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
          <div ref={transcriptEndRef} />
        </div>

        {/* Inline notification warning when mic is turned off inside LISTENING state */}
        {sessionState === 'LISTENING' && !micEnabled && (
          <div className="absolute bottom-16 inset-x-4 bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-center justify-between text-xs text-rose-800 backdrop-blur-sm z-10 shadow-lg animate-fade-in">
            <div className="flex items-center gap-2">
              <MicOff size={14} className="text-rose-600 animate-pulse" />
              <span>Microphone của bạn đang tắt. Hãy bật mic để trả lời câu hỏi.</span>
            </div>
            <button className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3 py-1.5 rounded-lg text-[10px] uppercase transition active:scale-95" onClick={toggleMic}>
              Bật mic
            </button>
          </div>
        )}

        {/* Action trigger bar for speech or keyboard input in LISTENING mode */}
        {sessionState === 'LISTENING' && (
          <div className="p-3 border-t border-slate-200 bg-slate-50/30 flex justify-center shrink-0 w-full">
            {inputType === 'keyboard' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%' }}>
                <div style={{ display: 'flex', gap: '0.5rem', width: '100%', alignItems: 'flex-end' }}>
                  <textarea
                    value={keyboardAnswer}
                    onChange={(e) => setKeyboardAnswer(e.target.value)}
                    placeholder="Nhập câu trả lời của bạn tại đây..."
                    style={{
                      flex: 1,
                      minHeight: '80px',
                      padding: '0.75rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.85rem',
                      outline: 'none',
                      resize: 'none',
                      fontFamily: 'inherit',
                      color: '#0f172a',
                      backgroundColor: '#ffffff'
                    }}
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
                  <button
                    onClick={() => {
                      if (keyboardAnswer.trim()) {
                        submitFinalAnswer(keyboardAnswer);
                        setKeyboardAnswer('');
                      }
                    }}
                    disabled={!keyboardAnswer.trim()}
                    style={{
                      backgroundColor: keyboardAnswer.trim() ? '#ea580c' : '#cbd5e1',
                      color: '#ffffff',
                      border: 'none',
                      width: '40px',
                      height: '40px',
                      borderRadius: '0.5rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: keyboardAnswer.trim() ? 'pointer' : 'default',
                      transition: 'all 0.2s',
                      flexShrink: 0
                    }}
                  >
                    <Send size={16} />
                  </button>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Nhấn Enter để gửi, Shift + Enter để xuống dòng</span>
                  <button
                    onClick={() => setInputType('voice')}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#ea580c',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem'
                    }}
                  >
                    <Mic size={12} />
                    <span>Trả lời bằng giọng nói</span>
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
                {recording ? (
                  <button className={styles.stopRecordingBtn} onClick={handleStopRecording} style={{ width: '100%', maxWidth: '400px' }}>
                    <MicOff size={16} />
                    <span>Tôi đã trả lời xong (Dừng ghi)</span>
                  </button>
                ) : (
                  <button className={styles.startSpeakingBtn} onClick={handleStartRecording} disabled={permissionError || isRevealing} style={{ width: '100%', maxWidth: '400px' }}>
                    <Mic size={16} />
                    <span>Bắt đầu nói (Bật ghi âm)</span>
                  </button>
                )}
                {!recording && (
                  <button
                    onClick={() => setInputType('keyboard')}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#64748b',
                      fontSize: '0.78rem',
                      fontWeight: 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      marginTop: '0.25rem'
                    }}
                  >
                    <MessageSquare size={12} />
                    <span>Nhập câu trả lời bằng bàn phím</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Thinking overlay message */}
        {sessionState === 'AI_THINKING' && (
          <div className="p-3 border-t border-slate-200 bg-slate-50/50 flex justify-center shrink-0 text-xs text-indigo-600 font-semibold items-center gap-2 shadow-inner">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
            <span>AI đang lắng nghe và phân tích câu trả lời của bạn...</span>
          </div>
        )}
      </div>
    </div>
  </main>

      {/* Exit confirmation modal dialog */}
      {showExitModal && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalIcon}>
              <PhoneOff size={22} />
            </div>
            <h3 className={styles.modalTitle}>Kết thúc phỏng vấn sớm?</h3>
            <p className={styles.modalDesc}>
              Bạn đang ở trong buổi phỏng vấn trực tiếp. Nếu kết thúc sớm, kết quả sẽ chỉ được tính cho các câu hỏi bạn đã hoàn thành. Bạn có chắc chắn muốn thoát?
            </p>
            <div className={styles.modalActions}>
              <button className={styles.modalCancelBtn} onClick={() => setShowExitModal(false)}>
                Hủy bỏ
              </button>
              <button className={styles.modalConfirmBtn} onClick={handleEndEarlyConfirm}>
                Đồng ý thoát
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
