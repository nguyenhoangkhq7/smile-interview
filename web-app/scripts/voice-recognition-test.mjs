// Exercise production capture/queue/review lifecycle without paid API calls or a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const asModule = source => {
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  return `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
};
const audioModule = asModule(await fs.readFile(new URL('../src/lib/voiceAudio.ts', import.meta.url), 'utf8'));
const source = (await fs.readFile(new URL('../src/hooks/useEvidenceVoice.ts', import.meta.url), 'utf8'))
  .split('export function useEvidenceVoice')[0].replace(/^import .*;\r?\n/gm, '');
globalThis.__recognizer = {};
const { VoiceConversation } = await import(asModule(`
import { encodeWav, VoiceDetector } from '${audioModule}';
const interviewVoice = globalThis.__recognizer;
const interviewError = error => error.message;
${source}
export { VoiceConversation };
`));
const settled = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
const accepted = (phase, text = 'Em dùng PostgreSQL.') => ({ text, phase, review_required: false,
  verification: phase === 'preview' ? 'not_requested' : 'agreed' });
const harness = handler => {
  const calls = [], state = {}, options = { id: 's', answer: '', busy: false, suspended: false,
    setAnswer: text => { options.answer = text; }, submit: async () => { throw new Error('Unexpected grading'); } };
  globalThis.__recognizer.transcribe = async (id, turn, audio, signal, phase) => {
    const request = { id, turn, audio, signal, phase }; calls.push(request); return handler(request);
  };
  const engine = new VoiceConversation(() => options, patch => Object.assign(state, patch));
  engine.context = { sampleRate: 16000, close: async () => {} };
  engine.turn = { turn_id: 't', expected_state_version: 1 };
  engine.setAuto(false);
  const feed = (seconds, level = 0.1) => {
    for (let i = 0; i < seconds * 10; i++) engine.frame(new Float32Array(1600).fill(level));
  };
  return { engine, calls, state, options, feed };
};

{
  const h = harness(({ phase }) => accepted(phase, phase === 'preview' ? 'từ tạm sai' : 'Em dùng PostgreSQL.'));
  h.feed(4.5); await settled();
  assert.equal(h.options.answer, '', 'Preview text never becomes the gradeable answer');
  assert.match(h.state.captions, /từ tạm sai/);
  h.feed(4.2); await settled(); h.feed(1.2, 0); await settled();
  assert.equal(h.options.answer, 'Em dùng PostgreSQL.', 'Final context replaces every preview in its range');
  assert.equal(h.state.captions, h.options.answer);
  assert.equal(h.engine.canSubmit(), true);
  const final = h.calls.find(call => call.phase === 'final');
  assert.equal(Buffer.from(final.audio, 'base64').readUInt32LE(40), 9.9 * 32000);
  h.engine.stop();
}
{
  const h = harness(({ phase }) => ({ ...accepted(phase, 'Em commit.'), review_required: true,
    verification: 'disagreed', alternative_text: 'Em rollback.' }));
  h.feed(0.5); h.engine.pause(true); await settled();
  assert.equal(h.calls[0].phase, 'final');
  assert.equal(Buffer.from(h.calls[0].audio, 'base64').readUInt32LE(40), 0.5 * 32000,
    'Pausing finalizes audio that has not reached a preview boundary');
  assert.equal(h.engine.canSubmit(), false, 'Model disagreement blocks manual and automatic submit');
  h.engine.confirmReview(h.state.review.segment, true);
  assert.equal(h.options.answer, 'Em rollback.');
  assert.equal(h.engine.canSubmit(), true);
  h.engine.stop();
}
{
  let fail = true;
  const h = harness(({ phase }) => { if (fail) { fail = false; throw new Error('Provider offline'); } return accepted(phase); });
  h.feed(0.5); h.feed(1.2, 0); await settled();
  assert.equal(h.state.retryAvailable, true);
  assert.equal(h.engine.canSubmit(), false);
  h.engine.retry(); await settled();
  assert.equal(h.calls[0].audio, h.calls[1].audio, 'Retry sends the exact retained final recording');
  assert.equal(h.options.answer, 'Em dùng PostgreSQL.'); h.engine.stop();
}
{
  let release;
  const h = harness(() => new Promise(resolve => { release = resolve; }));
  h.feed(4.5); await settled();
  h.engine.stop(); release(accepted('preview', 'stale result')); await settled();
  assert.equal(h.options.answer, '', 'A late result after disposal cannot mutate the answer');
  assert.notEqual(h.state.captions, 'stale result');
}
{
  const h = harness(({ phase }) => { if (phase === 'preview') throw new Error('Preview offline'); return accepted(phase); });
  h.feed(4.5); await settled(); h.feed(1.2, 0); await settled();
  assert.equal(h.options.answer, 'Em dùng PostgreSQL.', 'Preview failure cannot lose the contextual audio');
  assert.equal(h.state.retryAvailable, undefined); h.engine.stop();
}
{
  const h = harness(({ phase }) => accepted(phase));
  h.feed(52); h.feed(1.2, 0); await settled();
  const finals = h.calls.filter(call => call.phase === 'final');
  assert.equal(finals.length, 3, 'Long speech has bounded contextual windows');
  assert.equal(finals.reduce((sum, call) => sum + Buffer.from(call.audio, 'base64').readUInt32LE(40), 0), 52 * 32000,
    'No speech frame is dropped or duplicated; the silence-only tail is not submitted');
  h.engine.stop();
}
console.log('PASS: provisional/final isolation, contextual audio, review gate, pause flush, retry, cancellation and long speech.');
