import type { SimliClient } from 'simli-client';
import { SimliPcmResampler } from './simliAudio';

export interface SimliConnection {
  start(): Promise<void>; stop(): Promise<void>;
  sendAudioData(bytes: Uint8Array): void; ClearBuffer(): void;
  on(event: string, callback: (...args: string[]) => void): void;
}
type Factory = (token: string, video: HTMLVideoElement, audio: HTMLAudioElement) => Promise<SimliConnection>;
const factory: Factory = async (token, video, audio) => {
  const { SimliClient, LogLevel } = await import('simli-client');
  const client = new SimliClient(token, video, audio, null, LogLevel.CRITICAL);
  const stop = client.stop.bind(client);
  let disposed = false;
  client.stop = async () => {
    if (disposed) return;
    disposed = true;
    try { await stop(); }
    finally {
      // SDK 3.2.0 allocates this context even for raw PCM and does not close it in stop().
      const context: AudioContext | undefined = Reflect.get(client, 'audioContext');
      if (context && context.state !== 'closed') await context.close().catch(() => {});
    }
  };
  return client as SimliClient;
};

/** Simli owns playback; never play a second copy of the TTS audio locally. */
export class SimliAvatar {
  private client: SimliConnection | null = null;
  private closed = false;
  private connected = false;
  private epoch = 0;
  private speakingNow = false;
  private speechStarts = 0;
  private lastSilentAt = 0;
  constructor(private video: HTMLVideoElement, private audio: HTMLAudioElement,
    private playing: (value: boolean) => void, private disconnected: () => void,
    private create: Factory = factory) {}

  async start(token: string, signal: AbortSignal) {
    this.video.muted = true; this.video.playsInline = true; this.audio.muted = true;
    const client = await this.create(token, this.video, this.audio);
    this.client = client;
    if (this.closed || signal.aborted) { await client.stop(); throw new DOMException('Aborted', 'AbortError'); }
    client.on('speaking', () => {
      if (!this.closed && !this.audio.muted) {
        this.speakingNow = true; this.speechStarts++; this.playing(true);
      }
    });
    client.on('silent', () => {
      if (!this.closed) { this.speakingNow = false; this.lastSilentAt = performance.now(); this.playing(false); }
    });
    const lost = () => { if (!this.closed && this.connected) { this.connected = false; this.disconnected(); } };
    client.on('stop', lost); client.on('error', lost);
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let abort: (() => void) | undefined;
    try {
      await Promise.race([client.start(), new Promise<never>((_, reject) => {
        abort = () => reject(new DOMException('Aborted', 'AbortError'));
        signal.addEventListener('abort', abort, { once: true });
        timeout = setTimeout(() => reject(new Error('Kết nối avatar Simli quá thời gian. Hãy thử lại.')), 35000);
      })]);
      if (this.closed || signal.aborted) throw new DOMException('Aborted', 'AbortError');
      this.connected = true;
    } catch {
      this.close();
      throw new Error('Không kết nối được avatar Simli. Hãy thử lại hoặc kiểm tra cấu hình máy chủ.');
    } finally {
      if (timeout) clearTimeout(timeout);
      if (abort) signal.removeEventListener('abort', abort);
    }
  }

  stop() {
    this.epoch++; this.audio.muted = true; this.playing(false);
    if (this.connected) { try { this.client?.ClearBuffer(); } catch { /* Disconnect handler owns reconnection. */ } }
  }
  close() {
    if (this.closed) return;
    this.closed = true; this.stop(); this.connected = false;
    void this.client?.stop().catch(() => {});
    this.video.pause(); this.audio.pause(); this.video.srcObject = null; this.audio.srcObject = null;
  }

  async play(response: Response, signal: AbortSignal, waitForPlayback = false) {
    if (!this.connected || !this.client) throw new Error('Avatar Simli chưa kết nối.');
    if (response.headers.get('X-Audio-Format') !== 'pcm') throw new Error('Avatar Simli cần giọng đọc định dạng PCM.');
    const resampler = new SimliPcmResampler(Number(response.headers.get('X-Audio-Sample-Rate')));
    const reader = response.body?.getReader();
    if (!reader) throw new Error('Không nhận được âm thanh.');
    const epoch = this.epoch;
    const cancelled = () => this.closed || !this.connected || signal.aborted || epoch !== this.epoch;
    const began = performance.now();
    const starts = this.speechStarts;
    let lastSentAt = began;
    let duration = 0;
    try {
      while (!cancelled()) {
        const { done, value } = await reader.read();
        if (done || cancelled()) break;
        const pcm = resampler.push(value);
        // 100 ms packets, with at most 400 ms queued ahead of real time.
        for (let offset = 0; offset < pcm.length && !cancelled(); offset += 3200) {
          while (duration - (performance.now() - began) > 400 && !cancelled()) await new Promise(resolve => setTimeout(resolve, 20));
          if (cancelled()) break;
          const chunk = pcm.subarray(offset, offset + 3200);
          this.audio.muted = false;
          this.client.sendAudioData(chunk);
          lastSentAt = performance.now();
          duration += chunk.length / 32;
        }
      }
      if (!cancelled()) resampler.finish();
    } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    if (waitForPlayback && !cancelled()) {
      const timeoutAt = performance.now() + Math.max(15000, duration + 10000);
      while (!cancelled()) {
        if (this.speechStarts > starts && !this.speakingNow && this.lastSilentAt >= lastSentAt
            && performance.now() - this.lastSilentAt >= 300) return;
        if (performance.now() >= timeoutAt) throw new Error('Chưa xác nhận được avatar đã đọc xong. Bạn có thể nghe lại hoặc tiếp tục bằng nút bên dưới.');
        await new Promise(resolve => setTimeout(resolve, 30));
      }
    }
  }
}
