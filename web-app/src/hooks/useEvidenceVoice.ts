'use client';

import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { EvidenceSession, interviewError } from '@/services/evidenceInterview';
import { interviewVoice, VoiceTurn, type RecognitionResult } from '@/services/interviewVoice';
import { encodeWav, VoiceDetector } from '@/lib/voiceAudio';
import { SimliAvatar } from '@/lib/simliAvatar';

interface Options {
  id: string; session: EvidenceSession | null; answer: string; busy: boolean; suspended: boolean;
  setAnswer: (text: string) => void;
  videoRef: RefObject<HTMLVideoElement | null>; audioRef: RefObject<HTMLAudioElement | null>;
  submit: (text: string) => Promise<EvidenceSession | null | undefined>;
}
interface VoiceState {
  enabled: boolean; paused: boolean; listening: boolean; speaking: boolean;
  loadingSpeech: boolean; transcribing: boolean; countdown: boolean; retryAvailable: boolean;
  error: string; avatarReady: boolean;
  captions: string; review: Review | null;
}
interface Review { segment: number; audio: string; text: string; alternative?: string; unavailable: boolean }
const initial: VoiceState = { enabled: false, paused: false, listening: false, speaking: false,
  loadingSpeech: false, transcribing: false, countdown: false, retryAvailable: false, error: '', avatarReady: false,
  captions: '', review: null };
type Recording = { audio: string; turn: VoiceTurn; generation: number; segment: number; phase: 'preview' | 'final' };
type Segment = { preview: string; text: string; resolved: boolean; review: Review | null };

/** One lifecycle for capture, recognition, playback and turn cancellation. No independent LLM state. */
class VoiceConversation {
  private closed = false;
  private paused = false;
  private context: AudioContext | null = null;
  private microphone: MediaStream | null = null;
  private capture: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private silent: GainNode | null = null;
  private player: SimliAvatar | null = null;
  private ready = false;
  private startupAbort = new AbortController();
  private detector = new VoiceDetector(4000);
  private speechAbort: AbortController | null = null;
  private recognitionAbort: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;
  private turn: VoiceTurn | null = null;
  private announcedTurn = '';
  private queue: Recording[] = [];
  private failed: Recording | null = null;
  private processing = false;
  private playing = false;
  private auto = true;
  private submitting = false;
  private draft = '';
  private baseDraft = '';
  private segments: Segment[] = [];
  private contextFrames: Float32Array[] = [];
  private contextMs = 0;
  private segment = 0;
  private silence = 1200;

  constructor(private current: () => Options, private update: (state: Partial<VoiceState>) => void) {}
  get stopped() { return this.closed; }
  private emit(state: Partial<VoiceState>) { if (!this.closed) this.update(state); }

  async start() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Micro cần HTTPS hoặc localhost và trình duyệt hỗ trợ ghi âm.');
    // Let the browser resample the microphone with its native audio converter.
    // This avoids relying on the simple WAV fallback downsampler for 48 kHz input.
    this.context = new AudioContext({ sampleRate: 16000 });
    await this.context.resume();
    const cfg = await interviewVoice.config(this.current().id);
    if (this.closed) return;
    if (!cfg.enabled) throw new Error('Máy chủ chưa bật giọng nói. Hãy cấu hình OpenRouter.');
    if (!cfg.avatar?.configured) throw new Error('Dịch vụ avatar Simli chưa được cấu hình trên máy chủ.');
    if (cfg.format !== 'pcm') throw new Error('Simli cần giọng đọc định dạng PCM trên máy chủ.');
    const microphone = await navigator.mediaDevices.getUserMedia({ audio: {
      echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1,
    } });
    if (this.closed) { microphone.getTracks().forEach(track => track.stop()); return; }
    this.microphone = microphone;
    const context = this.context!;
    const { videoRef, audioRef, session } = this.current();
    if (!videoRef.current || !audioRef.current || !session?.pending_turn) throw new Error('Phòng phỏng vấn chưa sẵn sàng. Hãy tải lại trang.');
    this.player = new SimliAvatar(videoRef.current, audioRef.current, playing => {
      this.playing = playing; this.emit({ speaking: playing });
    }, () => {
      if (this.closed) return;
      this.stop();
      this.update({ ...initial, error: 'Mất kết nối avatar Simli. Hãy kết nối lại; phần trả lời đã nhận diện vẫn được giữ.' });
    });
    const token = await interviewVoice.avatarSession(this.current().id,
      { turn_id: session.pending_turn.turn_id, expected_state_version: session.state_version }, this.startupAbort.signal);
    if (this.closed) return;
    await this.player.start(token, this.startupAbort.signal);
    if (this.closed) return;
    await context.audioWorklet.addModule('/audio/voice-capture.worklet.js');
    if (this.closed) return;
    this.source = context.createMediaStreamSource(microphone);
    this.capture = new AudioWorkletNode(context, 'voice-capture');
    this.silent = context.createGain(); this.silent.gain.value = 0;
    this.source.connect(this.capture); this.capture.connect(this.silent); this.silent.connect(context.destination);
    this.capture.port.onmessage = event => this.frame(event.data as Float32Array);
    microphone.getAudioTracks()[0].onended = () => {
      this.pause(true); this.emit({ error: 'Micro đã ngắt. Hãy tắt rồi bật lại giọng nói.' });
    };
    if (microphone.getAudioTracks().some(track => track.readyState === 'ended')) throw new Error('Micro đã ngắt trong lúc kết nối. Hãy thử lại.');
    this.ready = true;
    this.emit({ enabled: true, avatarReady: true, error: '' });
    this.sync();
  }

  sync() {
    // React may rerender while start() is waiting for config/microphone permission.
    // Do not consume the first turn before the audio player is ready.
    if (this.closed || !this.player || !this.ready) return;
    const options = this.current(), session = options.session;
    this.draft = options.answer;
    if (!session?.pending_turn || session.is_finished || session.session_id !== options.id) {
      this.stop(); this.update(initial); return;
    }
    const next = { turn_id: session.pending_turn.turn_id, expected_state_version: session.state_version };
    if (this.turn?.turn_id !== next.turn_id || this.turn.expected_state_version !== next.expected_state_version) {
      this.generation++; this.cancelTimer(); this.cancelSpeech(); this.recognitionAbort?.abort();
      this.queue = []; this.failed = null; this.detector.reset(); this.submitting = false;
      this.segments = []; this.contextFrames = []; this.contextMs = 0; this.segment = 0; this.baseDraft = options.answer;
      this.turn = next;
      this.announcedTurn = '';
      this.emit({ retryAvailable: false, error: '', listening: false, captions: '', review: null });
    }
    if (options.suspended || options.busy) {
      this.cancelTimer(); this.flushRecording(); this.emit({ listening: false });
      if (options.suspended) this.cancelSpeech();
    } else if (!this.paused && this.announcedTurn !== next.turn_id && !this.detector.active) {
      void this.speak();
    }
  }

  setAuto(auto: boolean) { this.auto = auto; if (!auto) this.cancelTimer(); }
  setSilence(ms: number) { this.silence = ms; }
  pause(value: boolean) {
    this.paused = value; this.cancelTimer(); this.flushRecording();
    this.microphone?.getAudioTracks().forEach(track => { track.enabled = !value; });
    if (value) this.cancelSpeech();
    this.emit({ paused: value, listening: false });
    if (!value) this.sync();
  }
  cancelTimer() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null; this.emit({ countdown: false });
  }
  cancelSpeech() {
    this.speechAbort?.abort(); this.speechAbort = null; this.player?.stop();
    this.emit({ speaking: false, loadingSpeech: false });
  }
  beforeSubmit() {
    this.cancelTimer(); this.cancelSpeech(); this.detector.reset();
    // Manual send is only available once all transcription is complete.
    this.submitting = true;
  }
  afterSubmit() { this.submitting = false; }

  async speak() {
    if (!this.player || !this.ready || !this.turn || this.closed || this.paused || this.current().suspended || this.current().busy) return;
    this.announcedTurn = this.turn.turn_id;
    this.cancelTimer(); this.cancelSpeech(); this.flushRecording();
    const abort = new AbortController(); this.speechAbort = abort;
    this.emit({ loadingSpeech: true, error: '' });
    try {
      await this.context!.resume();
      const response = await interviewVoice.speech(this.current().id, this.turn, abort.signal);
      if (abort.signal.aborted || this.closed) return;
      this.emit({ loadingSpeech: false });
      await this.player.play(response, abort.signal);
    } catch (error) {
      if (!abort.signal.aborted) this.emit({ error: error instanceof Error ? error.message : 'Không thể đọc câu hỏi.' });
    } finally {
      if (this.speechAbort === abort) { this.speechAbort = null; this.emit({ loadingSpeech: false }); }
    }
  }

  private frame(samples: Float32Array) {
    const options = this.current();
    if (this.closed || this.paused || this.submitting || options.busy || options.suspended || !this.turn) return;
    const result = this.detector.feed(samples, this.context!.sampleRate, this.playing ? 0.028 : 0.015, this.silence);
    if (result.started) {
      this.cancelTimer(); this.cancelSpeech(); this.emit({ listening: true });
    }
    if (result.ended) this.emit({ listening: false });
    if (result.frames) this.collect(result.frames, result.ended);
    else if (result.ended) { this.finishContext(); void this.drain(); }
    if (!this.paused && (this.failed || this.queue.filter(item => item.phase === 'final').length >= 4)) {
      this.pause(true);
      this.emit({ error: 'Nhận diện chưa theo kịp. Bản ghi đã được giữ; hãy chờ xử lý rồi tiếp tục nghe.' });
    }
  }

  private collect(frames: Float32Array[], ended: boolean) {
    if (!this.turn || !this.context) return;
    if (!this.segments[this.segment]) this.segments[this.segment] = { preview: '', text: '', resolved: false, review: null };
    this.contextFrames.push(...frames);
    this.contextMs += frames.reduce((sum, frame) => sum + frame.length, 0) / this.context.sampleRate * 1000;
    if (ended || this.contextMs >= 24000) this.finishContext();
    else {
      const audio = encodeWav(frames, this.context.sampleRate);
      // Final recognition later replaces these isolated caption chunks.
      this.queue.push({ audio, segment: this.segment, phase: 'preview', turn: this.turn, generation: this.generation });
    }
    void this.drain();
  }

  private finishContext() {
    if (!this.contextFrames.length || !this.context || !this.turn) return;
    const segment = this.segment;
    // Full contextual audio supersedes all previews that have not started.
    this.queue = this.queue.filter(item => item.segment !== segment || item.phase !== 'preview');
    this.queue.push({ audio: encodeWav(this.contextFrames, this.context.sampleRate), segment,
      phase: 'final', turn: this.turn, generation: this.generation });
    this.contextFrames = []; this.contextMs = 0; this.segment++;
  }

  private flushRecording() {
    const frames = this.detector.flush();
    if (frames) this.collect(frames, true);
    else this.finishContext();
    if (this.queue.length) void this.drain();
  }

  private publishRecognition() {
    this.draft = [this.baseDraft, ...this.segments.map(segment => segment.text)].filter(Boolean).join(' ').trim();
    this.current().setAnswer(this.draft);
    this.emit({ captions: [this.baseDraft, ...this.segments.map(segment => segment.text || segment.preview)].filter(Boolean).join(' ').trim(),
      review: this.segments.find(segment => segment.review)?.review ?? null });
  }

  confirmReview(segment: number, alternative: boolean) {
    const item = this.segments[segment], review = item?.review;
    if (!review || (alternative && !review.alternative)) return;
    item.text = alternative ? review.alternative! : review.text;
    item.review = null;
    this.publishRecognition(); this.scheduleSubmit();
  }

  rejectReview(segment: number) {
    if (!this.segments[segment]?.review) return;
    this.segments[segment] = { preview: '', text: '', resolved: true, review: null };
    this.cancelTimer(); this.publishRecognition();
    // Repeating the audio is explicit; do not auto-submit the remaining draft.
    this.setAuto(false);
  }

  private get unsettled() {
    return Boolean(this.contextFrames.length || this.segments.some(segment => !segment.resolved || segment.review));
  }

  canSubmit() { return !this.detector.active && !this.processing && !this.queue.length && !this.failed && !this.unsettled; }

  private async drain() {
    if (this.processing || this.closed || this.failed) return;
    this.processing = true; this.emit({ transcribing: true });
    try {
      while (this.queue.length && !this.closed && !this.failed) {
        const recording = this.queue.shift()!;
        if (recording.generation !== this.generation) continue;
        const abort = new AbortController(); this.recognitionAbort = abort;
        try {
          const result: RecognitionResult = await interviewVoice.transcribe(this.current().id, recording.turn, recording.audio, abort.signal, recording.phase);
          if (this.closed || abort.signal.aborted || recording.generation !== this.generation) continue;
          const segment = this.segments[recording.segment];
          if (recording.phase === 'preview') {
            if (!segment.text) segment.preview = [segment.preview, result.text].filter(Boolean).join(' ');
          } else {
            segment.text = result.text;
            segment.resolved = true;
            segment.review = result.review_required ? { segment: recording.segment, audio: recording.audio,
              text: result.text, alternative: result.alternative_text, unavailable: result.verification === 'unavailable' } : null;
          }
          this.publishRecognition();
        } catch (error) {
          if (recording.phase === 'final' && !abort.signal.aborted && recording.generation === this.generation) {
            this.failed = recording; this.cancelTimer();
            this.emit({ retryAvailable: true, error: interviewError(error) });
          }
          // Preview failures do not discard audio: the contextual final request still owns it.
        }
      }
    } finally {
      this.processing = false; this.emit({ transcribing: false });
      if (!this.closed && !this.failed && !this.queue.length) this.scheduleSubmit();
    }
  }

  retry() {
    if (!this.failed || this.failed.generation !== this.generation) return;
    this.queue.unshift(this.failed); this.failed = null;
    this.emit({ retryAvailable: false, error: '' }); void this.drain();
  }
  discard() {
    if (this.failed) {
      // An explicit discard removes the failed segment; a preview can never stand in for it.
      this.segments[this.failed.segment] = { preview: '', text: '', resolved: true, review: null };
    }
    this.failed = null; this.publishRecognition(); this.emit({ retryAvailable: false, error: '' }); void this.drain();
  }

  private scheduleSubmit() {
    this.cancelTimer();
    const options = this.current();
    if (!this.auto || this.paused || options.suspended || options.busy || this.submitting || this.detector.active
      || !this.canSubmit() || this.playing || this.speechAbort || !this.draft.trim()) return;
    const generation = this.generation;
    this.emit({ countdown: true });
    this.timer = setTimeout(async () => {
      this.timer = null; this.emit({ countdown: false });
      const latest = this.current();
      if (this.closed || this.paused || latest.suspended || latest.busy || this.detector.active
        || !this.canSubmit() || generation !== this.generation) return;
      this.beforeSubmit();
      const next = await latest.submit(this.draft);
      this.submitting = false;
      // No automatic retry of paid grading; leave the exact draft/request ID for a manual retry.
      if (!next) this.emit({ error: 'Chưa gửi được câu trả lời. Nội dung vẫn được giữ; hãy bấm Gửi để thử lại.' });
    }, 1000);
  }

  stop() {
    this.ready = false;
    this.startupAbort.abort();
    this.cancelTimer(); this.cancelSpeech(); this.recognitionAbort?.abort();
    this.closed = true; this.generation++; this.queue = []; this.failed = null;
    this.contextFrames = []; this.segments = [];
    this.player?.close();
    if (this.capture) { this.capture.port.onmessage = null; this.capture.disconnect(); }
    this.source?.disconnect(); this.silent?.disconnect();
    this.microphone?.getTracks().forEach(track => { track.onended = null; track.stop(); });
    void this.context?.close().catch(() => {});
  }
}

export function useEvidenceVoice(options: Options) {
  const [state, setState] = useState<VoiceState>(initial);
  const [starting, setStarting] = useState(false);
  const [automatic, setAutomatic] = useState(true);
  const [silenceMs, setSilenceMs] = useState(1200);
  const latest = useRef(options);
  const engine = useRef<VoiceConversation | null>(null);
  useEffect(() => { latest.current = options; engine.current?.sync(); }, [options]);
  useEffect(() => () => engine.current?.stop(), []);
  const disable = useCallback(() => { engine.current?.stop(); engine.current = null; setState(initial); setStarting(false); }, []);
  const enable = async () => {
    if (engine.current && !engine.current.stopped) return;
    setStarting(true);
    const conversation = new VoiceConversation(() => latest.current, patch => setState(previous =>
      Object.entries(patch).every(([key, value]) => previous[key as keyof VoiceState] === value)
        ? previous : { ...previous, ...patch }));
    engine.current = conversation; conversation.setAuto(automatic); conversation.setSilence(silenceMs);
    try { await conversation.start(); }
    catch (error) {
      conversation.stop(); engine.current = null;
      setState({ ...initial, error: interviewError(error) });
    } finally { setStarting(false); }
  };
  const submit = async (response?: string) => {
    if (engine.current && !engine.current.canSubmit()) return;
    engine.current?.beforeSubmit();
    try { return await latest.current.submit(response ?? latest.current.answer); }
    finally { engine.current?.afterSubmit(); }
  };
  return { ...state, starting, automatic, silenceMs, enable, disable, submit,
    pause: () => engine.current?.pause(!state.paused),
    replay: () => engine.current?.speak(), interrupt: () => engine.current?.cancelSpeech(),
    retry: () => engine.current?.retry(), discard: () => engine.current?.discard(),
    confirmReview: (segment: number, alternative: boolean) => engine.current?.confirmReview(segment, alternative),
    rejectReview: (segment: number) => { setAutomatic(false); engine.current?.rejectReview(segment); },
    cancelAuto: () => engine.current?.cancelTimer(),
    setAutomatic: (value: boolean) => { setAutomatic(value); engine.current?.setAuto(value); },
    setSilenceMs: (value: number) => { setSilenceMs(value); engine.current?.setSilence(value); },
  };
}
