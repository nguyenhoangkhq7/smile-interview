/** Stateful PCM16LE mono resampling; chunk boundaries never reset the sample clock. */
export class SimliPcmResampler {
  private carry: number | null = null;
  private sum = 0;
  private needed: number;
  private ratio: number;
  constructor(sourceRate: number) {
    if (![16000, 22050, 24000, 44100, 48000].includes(sourceRate)) throw new Error('Tần số giọng đọc không được hỗ trợ.');
    this.ratio = sourceRate / 16000; this.needed = this.ratio;
  }
  push(bytes: Uint8Array): Uint8Array {
    const values: number[] = [];
    const sample = (low: number, high: number) => {
      const integer = (low | high << 8); const value = integer >= 32768 ? integer - 65536 : integer;
      let available = 1;
      while (available > 1e-9) {
        const weight = Math.min(available, this.needed);
        this.sum += value * weight; available -= weight; this.needed -= weight;
        if (this.needed < 1e-9) {
          values.push(Math.max(-32768, Math.min(32767, Math.round(this.sum / this.ratio))));
          this.sum = 0; this.needed = this.ratio;
        }
      }
    };
    let offset = 0;
    if (this.carry !== null && bytes.length) { sample(this.carry, bytes[0]); offset = 1; this.carry = null; }
    for (; offset + 1 < bytes.length; offset += 2) sample(bytes[offset], bytes[offset + 1]);
    if (offset < bytes.length) this.carry = bytes[offset];
    const output = new Uint8Array(values.length * 2), view = new DataView(output.buffer);
    values.forEach((value, index) => view.setInt16(index * 2, value, true));
    return output;
  }
  finish() { if (this.carry !== null) throw new Error('Âm thanh bị ngắt giữa chừng. Hãy nghe lại câu hỏi.'); }
}
