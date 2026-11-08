'use client';

import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { EvidenceSession, interviewError } from '@/services/evidenceInterview';
import { interviewVoice, VoiceTurn } from '@/services/interviewVoice';
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
}
const initial: VoiceState = { enabled: false, paused: false, listening: false, speaking: false,
  loadingSpeech: false, transcribing: false, countdown: false, retryAvailable: false, error: '', avatarReady: false };
type Recording = { audio: string; turn: VoiceTurn; generation: number };

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
  private silence = 1200;

  constructor(private current: () => Options, private update: (state: Partial<VoiceState>) => void) {}
  get stopped() { return this.closed; }
  private emit(state: Partial<VoiceState>) { if (!this.closed) this.update(state); }

  async start() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Micro cần HTTPS hoặc localhost và trình duyệt hỗ trợ ghi âm.');
    this.context = new AudioContext();
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
      this.turn = next;
      this.announcedTurn = '';
      this.emit({ retryAvailable: false, error: '', listening: false });
    }
    if (options.suspended || options.busy) {
      this.cancelTimer(); this.detector.reset(); this.emit({ listening: false });
      if (options.suspended) this.cancelSpeech();
    } else if (!this.paused && this.announcedTurn !== next.turn_id && !this.detector.active) {
      void this.speak();
    }
  }

  setAuto(auto: boolean) { this.auto = auto; if (!auto) this.cancelTimer(); }
  setSilence(ms: number) { this.silence = ms; }
  pause(value: boolean) {
    this.paused = value; this.cancelTimer(); this.detector.reset();
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
    this.cancelTimer(); this.cancelSpeech(); this.detector.reset();
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
    if (result.frames) {
      const recording = { audio: encodeWav(result.frames, this.context!.sampleRate), turn: this.turn, generation: this.generation };
      this.queue.push(recording);
      if (this.failed || this.queue.length >= 3) {
        this.pause(true);
        this.emit({ error: 'Nhận diện chưa theo kịp. Hãy xử lý bản ghi đang chờ trước khi tiếp tục.' });
      }
      void this.drain();
    } else if (result.ended && !this.processing && !this.queue.length && !this.failed) this.scheduleSubmit();
  }

  private async drain() {
    if (this.processing || this.closed || this.failed) return;
    this.processing = true; this.emit({ transcribing: true });
    try {
      while (this.queue.length && !this.closed && !this.failed) {
        const recording = this.queue.shift()!;
        if (recording.generation !== this.generation) continue;
        const abort = new AbortController(); this.recognitionAbort = abort;
        try {
          const text = await interviewVoice.transcribe(this.current().id, recording.turn, recording.audio, abort.signal);
          if (this.closed || abort.signal.aborted || recording.generation !== this.generation) continue;
          this.draft = [this.draft.trim(), text.trim()].filter(Boolean).join(' ');
          this.current().setAnswer(this.draft);
        } catch (error) {
          if (!abort.signal.aborted && recording.generation === this.generation) {
            this.failed = recording; this.cancelTimer();
            this.emit({ retryAvailable: true, error: interviewError(error) });
          }
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
  discard() { this.failed = null; this.emit({ retryAvailable: false, error: '' }); void this.drain(); }

  private scheduleSubmit() {
    this.cancelTimer();
    const options = this.current();
    if (!this.auto || this.paused || options.suspended || options.busy || this.submitting || this.detector.active
      || this.failed || this.processing || this.queue.length || this.playing || this.speechAbort || !this.draft.trim()) return;
    const generation = this.generation;
    this.emit({ countdown: true });
    this.timer = setTimeout(async () => {
      this.timer = null; this.emit({ countdown: false });
      const latest = this.current();
      if (this.closed || this.paused || latest.suspended || latest.busy || this.detector.active
        || this.failed || this.processing || this.queue.length || generation !== this.generation) return;
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
    engine.current?.beforeSubmit();
    try { return await latest.current.submit(response ?? latest.current.answer); }
    finally { engine.current?.afterSubmit(); }
  };
  return { ...state, starting, automatic, silenceMs, enable, disable, submit,
    pause: () => engine.current?.pause(!state.paused),
    replay: () => engine.current?.speak(), interrupt: () => engine.current?.cancelSpeech(),
    retry: () => engine.current?.retry(), discard: () => engine.current?.discard(),
    cancelAuto: () => engine.current?.cancelTimer(),
    setAutomatic: (value: boolean) => { setAutomatic(value); engine.current?.setAuto(value); },
    setSilenceMs: (value: number) => { setSilenceMs(value); engine.current?.setSilence(value); },
  };
}
