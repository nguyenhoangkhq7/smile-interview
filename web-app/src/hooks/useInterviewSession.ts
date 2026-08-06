'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { io, Socket } from 'socket.io-client';
import { historyService, SessionHistoryItem } from '@/services/historyService';
import { useSessionRecorder } from '@/hooks/useSessionRecorder';
import { useAuthStore } from '@/store/authStore';

interface SpeechRecognitionInstance {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((ev: any) => any) | null; // eslint-disable-line @typescript-eslint/no-explicit-any
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

interface ExtendedWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionInstance;
  webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  webkitAudioContext?: typeof AudioContext;
  webkitHighlight?: unknown;
}

export interface AudioAnalyserLike {
  frequencyBinCount: number;
  getByteFrequencyData(array: Uint8Array): void;
}

export type SessionState = 'INITIALIZING' | 'AI_SPEAKING' | 'LISTENING' | 'AI_THINKING' | 'FINISHED';

export function useInterviewSession() {
  const params = useParams();
  const router = useRouter();
  const id = (params?.id as string) || '';

  // Session Data & Navigation
  const [session, setSession] = useState<SessionHistoryItem | null>(null);
  const sessionRef = useRef<SessionHistoryItem | null>(null);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const [sessionState, setSessionState] = useState<SessionState>('INITIALIZING');
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [questionCount, setQuestionCount] = useState(0);
  const [topicTag] = useState('');
  const [isDeepDive, setIsDeepDive] = useState(false);
  const [showExitModal, setShowExitModal] = useState(false);

  // Chat Transcript Board
  const [chatLog, setChatLog] = useState<{ sender: 'AI' | 'User'; text: string; time: string; isDeepDive?: boolean }[]>([]);

  
  const [socketConnected, setSocketConnected] = useState(false);
  const [ttsMode, setTtsMode] = useState<'online' | 'mock'>('online');
  const [sttMode, setSttMode] = useState<'online' | 'mock'>('online');
  const socketRef = useRef<Socket | null>(null);

  
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);

  
  const [avatarConnected, setAvatarConnected] = useState(false);
  const [avatarPlaying, setAvatarPlaying] = useState(false);
  const [avatarAnalyser, setAvatarAnalyser] = useState<AudioAnalyserLike | null>(null);

  
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [micEnabled, setMicEnabled] = useState(true);
  const [permissionError, setPermissionError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  
  const [timeLeft, setTimeLeft] = useState(900); 
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  
  const [recording, setRecording] = useState(false);
  const [userAnswerDraft, setUserAnswerDraft] = useState('');
  const [inputType, setInputType] = useState<'voice' | 'keyboard'>('voice');
  const [keyboardAnswer, setKeyboardAnswer] = useState('');
  const [baseQuestionIndex, setBaseQuestionIndex] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const speechRecognitionRef = useRef<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
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

  
  const initAudioOnUserGesture = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (!audioContextRef.current) {
      try {
        const AudioCtx = window.AudioContext || (window as ExtendedWindow).webkitAudioContext;
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

  
  const handleInterviewFinish = useCallback(async (_isTimeout = false) => {
    isExitingRef.current = true;
    setSessionState('FINISHED');
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    
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

        if (currentSession.questions.length > 0) {
          const scoredQuestions = currentSession.questions.filter((q) => (q.score || 0) > 0);
          if (scoredQuestions.length > 0) {
            const totalScores = scoredQuestions.reduce((sum, q) => sum + (q.score || 0), 0);
            currentSession.overallScore = Math.round(totalScores / scoredQuestions.length);
          }
        } else {
          currentSession.overallScore = 60;
        }

        await historyService.saveSession({
          ...currentSession,
          replaceQuestions: true
        });

        const token = useAuthStore.getState().token;
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        fetch(`/api/sessions/${id}/evaluate`, { 
          method: 'POST',
          headers
        }).catch((evalErr) => {
          console.error('[Session Finish] Background evaluation trigger failed:', evalErr);
        });
        fetch('/api/hr-realtime', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId: id, stage: 'COMPLETED' }),
        }).catch(() => {});
      }
    } catch (err) {
      console.error('Error completing session:', err);
    }
  }, [id, mediaStream]);

  
  const speakQuestion = useCallback((text: string, forceOffline = false) => {
    if (!forceOffline && ttsMode === 'online' && socketRef.current?.connected) {
      socketRef.current.emit('process-tts', text);
    } else {
      window.speechSynthesis.cancel();
      if (mockAnalyserIntervalRef.current) clearInterval(mockAnalyserIntervalRef.current);

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'vi-VN';

      const viVoice = window.speechSynthesis.getVoices().find(v => v.lang.includes('VI') || v.lang.includes('vi'));
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
        mockAnalyserIntervalRef.current = setInterval(() => {}, 100);
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

  
  const submitFinalAnswer = useCallback(async (answer: string) => {
    if (!answer.trim()) return;

    setChatLog((prev) => [...prev, { sender: 'User', text: answer, time: formatCurrentTime() }]);
    setUserAnswerDraft('');
    setSessionState('AI_THINKING');

    if (socketRef.current?.connected) {
      socketRef.current.emit('orchestration-event', {
        type: 'CANDIDATE_TEXT_SUBMIT',
        payload: { text: answer }
      });

      if (id) {
        historyService.getSessionById(id).then(session => {
          if (session) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const updatedQuestions: any[] = session.questions ? [...session.questions] : [];
            const activeQText = currentQuestionRef.current;

            let targetIdx = updatedQuestions.findIndex((q: any) => {
              const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
              return qStr && activeQText && qStr.trim() === activeQText.trim();
            });

            if (targetIdx === -1) {
              targetIdx = updatedQuestions.findIndex((q: any) => !q.answer);
            }

            if (targetIdx !== -1) {
              updatedQuestions[targetIdx] = { ...updatedQuestions[targetIdx], answer: answer };
            } else {
              updatedQuestions.push({
                question: activeQText || 'Câu hỏi',
                answer: answer,
                score: 0,
                strengths: '',
                improvements: '',
                suggestedAnswer: '',
                topicTag: topicTag || '',
                isDeepDive
              });
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
  }, [id, topicTag, isDeepDive]);

  
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
    } catch {
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

  
  const handleStartRecording = useCallback(async () => {
    setUserAnswerDraft('');
    audioChunksRef.current = [];

    if (sttMode === 'online') {
      if (!mediaStream) {
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
          if (isExitingRef.current) return;
          
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });

          if (audioBlob.size < 1000) {
            setRecording(false);
            setSessionState('LISTENING');
            return;
          }

          setSessionState('AI_THINKING');
          autoStartMicRef.current = false;

          const buffer = await audioBlob.arrayBuffer();
          if (socketRef.current?.connected) {
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
      const SpeechRecognition = (window as ExtendedWindow).SpeechRecognition || (window as ExtendedWindow).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const rec = new SpeechRecognition();
        rec.lang = 'vi-VN';
        rec.interimResults = true;
        rec.continuous = true;
        
        finalTranscriptRef.current = '';
        latestTranscriptRef.current = '';
        setUserAnswerDraft('');

        rec.onresult = (event: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
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
          setUserAnswerDraft(fullText);
        };

        rec.onend = () => {
          setRecording(false);
          autoStartMicRef.current = false;
          
          if (isExitingRef.current) return;
          
          const finalizedAnswer = latestTranscriptRef.current.trim() || finalTranscriptRef.current.trim();
          if (finalizedAnswer) {
            submitFinalAnswer(finalizedAnswer);
          } else {
            setSessionState('LISTENING');
          }
        };

        speechRecognitionRef.current = rec;
        rec.start();
      } else {
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
        e.preventDefault();
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
      const data = await historyService.getSessionById(id);
      if (data) {
        setSession(data);
        if (data.questions && data.questions.length > 0) {
          const initialChatLog: { sender: 'AI' | 'User'; text: string; time: string; isDeepDive?: boolean }[] = [];
          let baseAnsweredCount = 0;
          data.questions.forEach((q: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
            if (q.answer) {
              if (q.question) {
                 const questionText = typeof q.question === 'object' && q.question !== null
                   ? (q.question as unknown as { question: string }).question
                   : q.question;
                 initialChatLog.push({ sender: 'AI', text: questionText, time: formatCurrentTime(), isDeepDive: q.isDeepDive });
              }
              initialChatLog.push({ sender: 'User', text: q.answer, time: formatCurrentTime() });
              if (!q.isDeepDive) {
                baseAnsweredCount++;
              }
            }
          });
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
      
      if (audioElRef.current) {
        audioElRef.current.pause();
        audioElRef.current.src = '';
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, [id]);

  const startTimer = useCallback(() => {
    if (timerIntervalRef.current) return;
    timerIntervalRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current!);
          handleInterviewFinish(true);
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

  const streamTranscriptRef = useRef(streamTranscript);
  const initAudioOnUserGestureRef = useRef(initAudioOnUserGesture);
  const handleInterviewFinishRef = useRef(handleInterviewFinish);
  const speakQuestionRef = useRef(speakQuestion);

  useEffect(() => { streamTranscriptRef.current = streamTranscript; }, [streamTranscript]);
  useEffect(() => { initAudioOnUserGestureRef.current = initAudioOnUserGesture; }, [initAudioOnUserGesture]);
  useEffect(() => { handleInterviewFinishRef.current = handleInterviewFinish; }, [handleInterviewFinish]);
  useEffect(() => { speakQuestionRef.current = speakQuestion; }, [speakQuestion]);

  // Socket logic
  useEffect(() => {
    const streamingUrl = process.env.NEXT_PUBLIC_STREAMING_SERVICE_URL || 'http://localhost:8001';
    const socket = io(streamingUrl, {
      transports: ['websocket'],
      reconnectionAttempts: 2,
      timeout: 2500
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setSocketConnected(true);
      setAvatarConnected(true);
      setTtsMode('online');
      setSttMode('online');
    });

    socket.on('orchestration-event', (data: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      if (data.type === 'INTERVIEWER_ACTION') {
        const { actionType, text, score, evaluation } = data.payload;
        if (actionType === 'CONCLUDING') {
          handleInterviewFinishRef.current(false);
          return;
        }

        if (evaluation && score !== undefined) {
          historyService.getSessionById(id).then(session => {
             if (session && session.questions) {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const updatedQuestions: any[] = [...session.questions];
                const answeredQText = currentQuestionRef.current;

                let answeredIdx = updatedQuestions.findIndex((q: any) => {
                  const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
                  return qStr && answeredQText && qStr.trim() === answeredQText.trim();
                });

                if (answeredIdx === -1) {
                  for (let i = updatedQuestions.length - 1; i >= 0; i--) {
                    if (updatedQuestions[i].answer && !updatedQuestions[i].score) {
                      answeredIdx = i;
                      break;
                    }
                  }
                }

                if (answeredIdx !== -1) {
                  updatedQuestions[answeredIdx] = {
                    ...updatedQuestions[answeredIdx],
                    score: score ?? 0,
                    strengths: evaluation,
                    improvements: actionType === 'FOLLOW_UP' ? 'Cần bổ sung chi tiết' : '',
                  };
                }

                const newQExists = updatedQuestions.some((q: any) => {
                  const qStr = typeof q.question === 'object' && q.question !== null ? q.question.question : q.question;
                  return qStr && text && qStr.trim() === text.trim();
                });

                if (!newQExists && text) {
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
                }

                historyService.saveSession({
                   ...session,
                   questions: updatedQuestions,
                   replaceQuestions: true
                });
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
           setSessionState('LISTENING');
           const activeSess = sessionRef.current;
           if (!currentQuestionRef.current && activeSess && activeSess.questions && activeSess.questions.length > 0) {
              const qState = data.payload.questionState;
              const idx = qState?.baseQuestionIndex ?? 0;
              const currentQ = activeSess.questions[idx];
              if (currentQ) {
                  const qText = currentQ.question;
                  setCurrentQuestion(qText);
                  currentQuestionRef.current = qText;
                  
                  setChatLog((prev) => {
                     const exists = prev.some(log => log.sender === 'AI' && log.text === qText);
                     if (!exists) {
                        return [...prev, { sender: 'AI', text: qText, time: formatCurrentTime(), isDeepDive: currentQ.isDeepDive }];
                     }
                     return prev;
                  });
              }
           }
        }
      }
    });

    socket.on('connect_error', () => {
      setSocketConnected(false);
      setAvatarConnected(true);
    });

    socket.on('stt-result', (data: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      if (data.status === 'success') {
        streamTranscriptRef.current(data.text);
      } else {
        setUserAnswerDraft('[Không nhận diện được giọng nói. Vui lòng ghi âm lại.]');
        setRecording(false);
        setSessionState('LISTENING');
      }
    });

    socket.on('stt-error', () => {
      setUserAnswerDraft('[Lỗi xử lý âm thanh. Vui lòng ghi âm lại.]');
      setRecording(false);
      setSessionState('LISTENING');
    });

    socket.on('tts-error', () => {
      setTtsMode('mock');
      if (currentQuestionRef.current && speakQuestionRef.current) {
        speakQuestionRef.current(currentQuestionRef.current, true);
      } else {
        setSessionState('LISTENING');
      }
    });

    socket.on('tts-result', async (bufferData: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
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

  const handleStartInterview = async () => {
    initAudioOnUserGesture();
    setSessionState('AI_THINKING');
    startTimer();

    if (socketRef.current?.connected) {
      let initialQuestions = [];
      try {
        if (session?.questions && session.questions.length > 0) {
          initialQuestions = session.questions.map((q: any) => ({ // eslint-disable-line @typescript-eslint/no-explicit-any
            question: q.question || '',
            good_answer_signals: q.goodAnswerSignals || [],
            topic: q.topicTag || ''
          }));
        } else if (session?.actionableSuggestions) {
          initialQuestions = typeof session.actionableSuggestions === 'string' 
            ? JSON.parse(session.actionableSuggestions) 
            : session.actionableSuggestions;
        }
      } catch (e) {
        console.error('Failed to parse initialQuestions', e);
      }
      
      socketRef.current.emit('join-interview', { 
        interviewId: id, 
        userId: 'candidate-user', 
        initialQuestions,
        baseQuestionIndex
      });
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

  const handleToggleSessionRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

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

  const handleGoToResults = useCallback(() => {
    router.push(`/interview/session/${id}/result`);
  }, [id, router]);

  const formatTime = useCallback((secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  }, []);

  const formatDuration = useCallback((ms: number) => {
    const totalSecs = Math.floor(ms / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return {
    id,
    session,
    sessionState,
    currentQuestion,
    questionCount,
    topicTag,
    isDeepDive,
    chatLog,
    socketConnected,
    ttsMode,
    sttMode,
    avatarConnected,
    avatarPlaying,
    avatarAnalyser,
    mediaStream,
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
    initAudioOnUserGesture,
    handleInterviewFinish,
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
    formatCurrentTime,
  };
}
