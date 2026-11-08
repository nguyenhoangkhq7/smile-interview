// Microphone frames only. No audio is sent anywhere until the user enables voice.
class VoiceCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frames = new Float32Array(2048);
    this.offset = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (input) {
      for (let i = 0; i < input.length; i++) {
        this.frames[this.offset++] = input[i];
        if (this.offset === this.frames.length) {
          this.port.postMessage(this.frames, [this.frames.buffer]);
          this.frames = new Float32Array(2048);
          this.offset = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('voice-capture', VoiceCaptureProcessor);
