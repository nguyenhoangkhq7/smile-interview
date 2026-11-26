// Local browser tests only, selected by next.config.ts in development.
export const LogLevel = { CRITICAL: 3 };
declare global {
  interface Window { __simliMock?: { starts: number; stops: number; clears: number; bytes: number; packets: number }; }
}
export class SimliClient {
  private handlers = new Map<string, Array<() => void>>();
  private stream: MediaStream | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;
  constructor(private token: string, private video: HTMLVideoElement) {
    window.__simliMock ??= { starts: 0, stops: 0, clears: 0, bytes: 0, packets: 0 };
  }
  on(event: string, callback: () => void) { this.handlers.set(event, [...(this.handlers.get(event) || []), callback]); }
  private emit(event: string) { for (const handler of this.handlers.get(event) || []) handler(); }
  async start() {
    if (!this.token) throw new Error('Missing fixture token');
    window.__simliMock!.starts++;
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 512;
    const ctx = canvas.getContext('2d')!; ctx.fillStyle = '#edf2ef'; ctx.fillRect(0, 0, 512, 512);
    ctx.fillStyle = '#35564b'; ctx.textAlign = 'center'; ctx.font = '20px sans-serif';
    ctx.fillText('SIMLI · TEST STREAM', 256, 256);
    this.stream = canvas.captureStream(1); this.video.srcObject = this.stream;
    await this.video.play();
    // A delayed first frame lets the interview timer rerender during startup.
    await new Promise(resolve => setTimeout(resolve, 1200));
    this.emit('start');
  }
  sendAudioData(bytes: Uint8Array) {
    if (this.stopped || bytes.length % 2) throw new Error('Invalid fixture audio');
    window.__simliMock!.bytes += bytes.length; window.__simliMock!.packets++;
    this.emit('speaking');
    clearTimeout(this.timer); this.timer = setTimeout(() => this.emit('silent'), 180);
  }
  ClearBuffer() { window.__simliMock!.clears++; clearTimeout(this.timer); this.emit('silent'); }
  async stop() {
    if (this.stopped) return; this.stopped = true;
    window.__simliMock!.stops++; clearTimeout(this.timer);
    this.stream?.getTracks().forEach(track => track.stop()); this.emit('stop');
  }
}
