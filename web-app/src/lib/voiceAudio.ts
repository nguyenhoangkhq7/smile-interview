/** WAV input is independent of browser MediaRecorder codecs (Qwen ASR accepts WAV). */
export function encodeWav(frames: Float32Array[], sourceRate: number): string {
  const length = frames.reduce((sum, frame) => sum + frame.length, 0);
  const input = new Float32Array(length);
  let offset = 0;
  for (const frame of frames) { input.set(frame, offset); offset += frame.length; }
  const rate = 16000;
  const ratio = sourceRate / rate;
  const count = Math.floor(length / ratio);
  const bytes = new ArrayBuffer(44 + count * 2);
  const view = new DataView(bytes);
  const ascii = (at: number, text: string) => { for (let i = 0; i < text.length; i++) view.setUint8(at + i, text.charCodeAt(i)); };
  ascii(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); ascii(8, 'WAVE'); ascii(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); ascii(36, 'data'); view.setUint32(40, count * 2, true);
  // Average source samples rather than dropping them when downsampling.
  for (let i = 0; i < count; i++) {
    const start = Math.floor(i * ratio), end = Math.min(length, Math.floor((i + 1) * ratio));
    let sample = 0;
    for (let j = start; j < end; j++) sample += input[j];
    sample = Math.max(-1, Math.min(1, sample / Math.max(1, end - start)));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  const data = new Uint8Array(bytes);
  let binary = '';
  for (let i = 0; i < data.length; i += 8192) binary += String.fromCharCode(...data.subarray(i, i + 8192));
  return btoa(binary);
}

/** Local acoustic VAD: requires sustained voice and retains pre-roll to avoid clipped words. */
export class VoiceDetector {
  private preRoll: Float32Array[] = [];
  private frames: Float32Array[] = [];
  private speechMs = 0;
  private silenceMs = 0;
  private durationMs = 0;
  private segmentHasSpeech = false;
  active = false;

  constructor(private segmentMs = 25000) {}

  reset() {
    this.preRoll = []; this.frames = []; this.speechMs = 0;
    this.silenceMs = 0; this.durationMs = 0; this.active = false; this.segmentHasSpeech = false;
  }

  feed(frame: Float32Array, rate: number, threshold: number, silenceLimit: number) {
    const ms = frame.length / rate * 1000;
    let sum = 0;
    for (const value of frame) sum += value * value;
    const voiced = Math.sqrt(sum / frame.length) >= threshold;
    let started = false;
    if (!this.active) {
      this.preRoll.push(frame);
      while (this.preRoll.length * ms > 350) this.preRoll.shift();
      this.speechMs = voiced ? this.speechMs + ms : 0;
      if (this.speechMs >= 180) {
        this.active = true; started = true; this.segmentHasSpeech = true; this.frames = this.preRoll;
        this.preRoll = []; this.durationMs = this.frames.length * ms;
      }
    } else {
      this.frames.push(frame); this.durationMs += ms;
      this.segmentHasSpeech ||= voiced;
      this.silenceMs = voiced ? 0 : this.silenceMs + ms;
      if (this.silenceMs >= silenceLimit || (this.durationMs >= this.segmentMs && voiced)) {
        const frames = this.segmentHasSpeech ? this.frames : null;
        const continued = this.silenceMs < silenceLimit;
        if (continued) {
          // Caption chunks do not end the user's turn or repeat/drop audio frames.
          this.frames = []; this.durationMs = 0; this.segmentHasSpeech = false;
        } else this.reset();
        return { started, frames, continued, ended: !continued };
      }
    }
    return { started, frames: null, continued: false, ended: false };
  }
}
