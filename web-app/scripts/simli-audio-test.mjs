import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';
const moduleUrl = async (path, replace = value => value) => {
  const source = replace(await fs.readFile(new URL(path, import.meta.url), 'utf8'));
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  return `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
};
const audioUrl = await moduleUrl('../src/lib/simliAudio.ts');
const { SimliPcmResampler } = await import(audioUrl);
for (const rate of [16000, 22050, 24000, 44100, 48000]) {
  const input = Buffer.alloc(rate * 2);
  for (let i = 0; i < rate; i++) input.writeInt16LE(Math.round(Math.sin(i / rate * Math.PI * 440 * 2) * 12000), i * 2);
  const whole = new SimliPcmResampler(rate), split = new SimliPcmResampler(rate);
  const expected = whole.push(input), chunks = [];
  for (let i = 0; i < input.length; i += 997) chunks.push(split.push(input.subarray(i, i + 997)));
  whole.finish(); split.finish();
  assert.equal(expected.length, 32000, `One second at ${rate} Hz must become one second of PCM16 16 kHz`);
  assert.deepEqual(Buffer.concat(chunks), Buffer.from(expected), 'Resampling must not depend on network chunk boundaries');
}
const broken = new SimliPcmResampler(16000); broken.push(Uint8Array.of(1)); assert.throws(() => broken.finish(), /ngắt/);
assert.throws(() => new SimliPcmResampler(0), /Tần số/);

const avatarUrl = await moduleUrl('../src/lib/simliAvatar.ts', value => value.replace("'./simliAudio'", JSON.stringify(audioUrl)));
const { SimliAvatar } = await import(avatarUrl);
const media = () => ({ muted: false, playsInline: false, srcObject: {}, pauses: 0, pause() { this.pauses++; } });
const handlers = new Map(), sent = [], events = { stops: 0, clears: 0, lost: 0 };
const client = {
  async start() {}, async stop() { events.stops++; handlers.get('stop')?.(); },
  on(name, callback) { handlers.set(name, callback); },
  sendAudioData(bytes) { sent.push(new Uint8Array(bytes)); handlers.get('speaking')?.(); },
  ClearBuffer() { events.clears++; handlers.get('silent')?.(); },
};
const video = media(), audio = media(), playing = [];
const avatar = new SimliAvatar(video, audio, value => playing.push(value), () => events.lost++, async () => client);
await avatar.start('temporary-token', new AbortController().signal);
const pcm = Buffer.alloc(4800); pcm.fill(1);
await avatar.play(new Response(pcm, { headers: { 'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '24000' } }), new AbortController().signal);
assert.equal(Buffer.concat(sent.map(Buffer.from)).length, 3200);
assert.equal(audio.muted, false); assert.ok(playing.includes(true));
avatar.stop(); assert.equal(audio.muted, true); assert.equal(events.clears, 1);
let push;
const late = new ReadableStream({ start(controller) { push = controller; } });
const previous = sent.length;
const pending = avatar.play(new Response(late, { headers: { 'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '44100' } }), new AbortController().signal);
avatar.stop(); push.enqueue(pcm); push.close(); await pending;
assert.equal(sent.length, previous, 'Late TTS audio must not reach Simli after interruption');
avatar.close(); avatar.close();
assert.equal(events.stops, 1); assert.equal(events.lost, 0);
assert.equal(video.srcObject, null); assert.equal(audio.srcObject, null);
const fail = new SimliAvatar(media(), media(), () => {}, () => {}, async () => ({ ...client, async start() { throw new Error('provider-private-detail'); } }));
await assert.rejects(() => fail.start('token', new AbortController().signal), error => !error.message.includes('provider-private-detail'));
const aborted = new AbortController(); aborted.abort();
let abortedStops = 0;
const cancelled = new SimliAvatar(media(), media(), () => {}, () => {}, async () => ({
  ...client, async stop() { abortedStops++; }, async start() { assert.fail('An aborted startup must never connect'); },
}));
await assert.rejects(() => cancelled.start('token', aborted.signal), { name: 'AbortError' });
assert.equal(abortedStops, 1, 'A cancelled connection must dispose the SDK instance');
const completionHandlers = new Map();
const completed = new SimliAvatar(media(), media(), () => {}, () => {}, async () => ({
  ...client, on(name, callback) { completionHandlers.set(name, callback); },
  sendAudioData() { completionHandlers.get('speaking')?.(); },
  ClearBuffer() { completionHandlers.get('silent')?.(); },
}));
await completed.start('token', new AbortController().signal);
let finished = false;
const finishAbort = new AbortController();
const playback = completed.play(new Response(pcm, { headers: { 'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '24000' } }), finishAbort.signal, true)
  .then(() => { finished = true; });
await new Promise(resolve => setTimeout(resolve, 50));
assert.equal(finished, false, 'Downloading all TTS audio must not finish the conversation');
completionHandlers.get('silent')();
await playback;
assert.equal(finished, true, 'A settled Simli silent event confirms playback completion');
completed.close();
console.log('PASS: PCM 16 kHz conversion, arbitrary chunks, Simli-only playback, interruption, late audio, startup failure and cleanup.');
