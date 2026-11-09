import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const source = await fs.readFile(new URL('../src/lib/voiceAudio.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { encodeWav, VoiceDetector } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const wav = Buffer.from(encodeWav([new Float32Array(48000).fill(0.25)], 48000), 'base64');
assert.equal(wav.toString('ascii', 0, 4), 'RIFF');
assert.equal(wav.readUInt32LE(24), 16000);
assert.equal(wav.readUInt16LE(22), 1);
assert.equal(wav.readUInt32LE(40), 32000, 'One second at 16 kHz, signed 16-bit');
assert.ok(wav.readInt16LE(44) > 8000 && wav.readInt16LE(44) < 8300);

const detector = new VoiceDetector();
const frame = level => new Float32Array(1600).fill(level); // 100 ms at 16 kHz
for (let i = 0; i < 20; i++) assert.equal(detector.feed(frame(0.001), 16000, 0.015, 1200).frames, null);
assert.equal(detector.feed(frame(0.1), 16000, 0.015, 1200).started, false);
assert.equal(detector.feed(frame(0.1), 16000, 0.015, 1200).started, true);
for (let i = 0; i < 11; i++) assert.equal(detector.feed(frame(0), 16000, 0.015, 1200).frames, null);
const ended = detector.feed(frame(0), 16000, 0.015, 1200);
assert.ok(ended.frames.length >= 14, 'Retain speech and pre-roll');
assert.equal(ended.continued, false);
assert.equal(detector.active, false);

let split = null;
for (let i = 0; i < 260; i++) {
  const result = detector.feed(frame(0.1), 16000, 0.015, 1200);
  if (result.frames) split = result;
}
assert.equal(split.continued, true, 'Long answers split without treating a segment as a finished answer');
detector.reset();
assert.equal(detector.active, false);

const captions = new VoiceDetector(4000);
const captionChunks = [];
for (let i = 0; i < 90; i++) {
  const result = captions.feed(frame(0.1), 16000, 0.015, 1200);
  if (result.frames) {
    captionChunks.push(result.frames);
    assert.equal(result.continued, true);
    assert.equal(result.ended, false);
    assert.equal(captions.active, true, 'Caption updates must keep the speaking turn active');
  }
}
assert.equal(captionChunks.length, 2, 'Long speech produces captions before a pause');
let captionEnd;
for (let i = 0; i < 12; i++) captionEnd = captions.feed(frame(0), 16000, 0.015, 1200);
captionChunks.push(captionEnd.frames);
assert.equal(captionEnd.ended, true);
assert.equal(captionChunks.flat().reduce((sum, chunk) => sum + chunk.length, 0), 102 * 1600,
  'No audio frame is lost or transcribed twice across caption chunks');
captions.reset();
for (let i = 0; i < 80; i++) captions.feed(frame(0.1), 16000, 0.015, 1200);
for (let i = 0; i < 12; i++) captionEnd = captions.feed(frame(0), 16000, 0.015, 1200);
assert.equal(captionEnd.ended, true);
assert.equal(captionEnd.frames, null, 'Do not send a silence-only tail to ASR or invent a caption');

detector.reset();
for (let i = 0; i < 8; i++) detector.feed(frame(0.1), 16000, 0.015, 1200);
assert.equal(detector.flush().reduce((sum, item) => sum + item.length, 0), 8 * 1600,
  'Pausing keeps every unfinished speech frame');
assert.equal(detector.flush(), null, 'Flushing twice cannot transcribe the same speech twice');

console.log('PASS: WAV resampling, sustained speech, silence and continuous caption segments.');
