// Real browser + real React/Web Audio; synthetic microphone frames and HTTP fixtures.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const unconfigured = process.argv.includes('--unconfigured');
const id = 'voice-smoke';
const report = { schema_version: 2, state_version: 1, is_finished: false, objectives: [], progress: 0,
  evidence_coverage: 0, target_attainment: null, termination_reason: null };
const firstSession = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
  deadline_at: new Date(Date.now() + 900000).toISOString(), config: { interaction_mode: 'VOICE', mode: 'MIXED', max_questions: 10, duration_seconds: 900 },
  pending_turn: { turn_id: 't1', objective_id: 'o1', skill_id: 'postgresql', mode: 'TECHNICAL_EXPLANATION',
    question: 'Bạn xử lý transaction như thế nào?', answer: null, feedback: null }, turns: [], report };
let session = null;
const errors = [], answers = [], transcriptions = [], speeches = [], requests = [];
let failRecognition = false;
const browser = await puppeteer.launch({ headless: true, args: ['--autoplay-policy=no-user-gesture-required', '--enable-unsafe-swiftshader'] });
let testPage;
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  testPage = page;
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error' && /Maximum update depth|Cannot update a component|Unhandled/.test(message.text())) errors.push(message.text());
  });
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('auth-storage', JSON.stringify({ state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0 }));
    const context = new AudioContext();
    navigator.mediaDevices.getUserMedia = async () => {
      const stream = context.createMediaStreamDestination().stream;
      window.__voiceStream = stream;
      return stream;
    };
    Object.getPrototypeOf(context.audioWorklet).addModule = async () => {};
    window.AudioWorkletNode = class extends GainNode {
      constructor(ctx) { super(ctx); this.port = { onmessage: null }; window.__capture = this.port; window.__captureRate = ctx.sampleRate; }
    };
  });
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = new URL(request.url()); requests.push(url.href);
    const headers = { 'access-control-allow-origin': base, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*',
      'access-control-expose-headers': 'X-Audio-Sample-Rate, X-Audio-Format', 'content-type': 'application/json' };
    const send = (body, status = 200) => request.respond({ status, headers, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    if (url.pathname === `/api/v1/sessions/${id}`) return send({ id, status: 'In progress', turns: [] });
    if (url.pathname.endsWith('/interview/start')) {
      const config = JSON.parse(request.postData());
      assert.equal(config.interaction_mode, 'VOICE', 'The setup choice is sent to the server');
      session = { ...firstSession, config };
      return send(session);
    }
    if (url.pathname.endsWith('/voice/config')) return send({ enabled: true, format: 'pcm', sample_rate: 24000,
      avatar: { provider: 'simli', configured: !unconfigured, sample_rate: 16000 } });
    if (url.pathname.endsWith('/voice/avatar-session')) {
      assert.equal(JSON.parse(request.postData()).turn_id, session.pending_turn.turn_id);
      return send({ session_token: 'simli-fixture-token' });
    }
    if (url.pathname.endsWith('/voice/speech')) {
      const payload = JSON.parse(request.postData()); speeches.push(payload);
      assert.equal(payload.turn_id, session.pending_turn.turn_id);
      assert.equal('text' in payload, false, 'The client cannot choose arbitrary paid TTS input');
      return request.respond({ status: 200, headers: { ...headers, 'content-type': 'audio/pcm', 'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '24000' }, body: Buffer.alloc(24000 * 2 * 3) });
    }
    if (url.pathname.endsWith('/voice/transcribe')) {
      const payload = JSON.parse(request.postData()); transcriptions.push(payload);
      assert.equal(Buffer.from(payload.audio, 'base64').toString('ascii', 0, 4), 'RIFF');
      if (failRecognition) { failRecognition = false; return send({ message: 'Nhận diện đang lỗi thử nghiệm.' }, 503); }
      assert.ok(['preview', 'final'].includes(payload.phase));
      return send({ phase: payload.phase, review_required: payload.phase === 'final' && payload.turn_id === 't3',
        verification: payload.phase === 'preview' ? 'not_requested' : payload.turn_id === 't3' ? 'disagreed' : 'agreed',
        alternative_text: payload.turn_id === 't3' ? 'Em dùng reduce để cộng các phần tử và kiểm tra mảng rỗng.' : undefined,
        text: payload.turn_id === 't3'
        ? 'Em duyệt từng phần tử, cộng vào tổng và kiểm tra mảng rỗng.'
        : 'Em dùng transaction để bảo đảm tính nhất quán.' });
    }
    if (url.pathname.endsWith('/interview/respond')) {
      const payload = JSON.parse(request.postData()); answers.push(payload);
      session = { ...session, state_version: session.state_version + 1,
        turns: [...session.turns, { ...session.pending_turn, answer: payload.candidate_response, feedback: 'Đã nhận.' }],
        pending_turn: { ...session.pending_turn, turn_id: `t${session.state_version + 1}`,
          mode: session.state_version === 2 ? 'CODING' : 'TECHNICAL_EXPLANATION',
          question: session.state_version === 2 ? 'Giải thích cách tính tổng mảng và độ phức tạp.' : 'Nếu giao dịch lỗi thì sao?' } };
      return send(session);
    }
    if (url.pathname.endsWith('/interview/stop')) {
      session = { ...session, state_version: session.state_version + 1, is_finished: true, pending_turn: null,
        report: { ...report, is_finished: true, termination_reason: 'USER_STOP' } };
      return send(session);
    }
    if (url.pathname.endsWith('/interview')) return send(session || {}, session ? 200 : 404);
    return send({});
  });
  const click = async text => { const button = await page.waitForFunction(label => [...document.querySelectorAll('button')].find(node => node.textContent.includes(label) || node.getAttribute('aria-label') === label), {}, text); await button.asElement().click(); };
  const feed = async () => page.evaluate(() => {
    const rate = window.__captureRate;
    // Sustained speech + silence pass through the production local VAD.
    for (let i = 0; i < Math.ceil(rate * 0.5 / 2048); i++) window.__capture.onmessage({ data: new Float32Array(2048).fill(0.12) });
    for (let i = 0; i < Math.ceil(rate * 1.5 / 2048); i++) window.__capture.onmessage({ data: new Float32Array(2048) });
  });
  await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
  assert.equal(transcriptions.length, 0); assert.equal(speeches.length, 0);
  await page.click('input[name="interaction-mode"][value="VOICE"]');
  await click('Bắt đầu phỏng vấn');
  await page.waitForSelector('[data-interview-mode="VOICE"]');
  assert.equal(await page.$('textarea'), null, 'Voice mode has no text answer box');
  assert.match(await page.$eval('[aria-label="Nội dung câu hỏi"]', node => node.textContent), /Bạn xử lý transaction như thế nào/);
  assert.equal(await page.$$('section[aria-label="Câu hỏi của AI"]').then(nodes => nodes.length), 1, 'Exactly one AI question panel');
  await page.waitForNetworkIdle({ idleTime: 300 });
  await page.screenshot({ path: '.next/voice-room-ready.png', fullPage: true });
  await (await page.$('[aria-label="Người phỏng vấn"]')).screenshot({ path: '.next/simli-avatar-preview.png' });
  for (const viewport of [{ width: 800, height: 600 }, { width: 320, height: 740 }]) {
    await page.setViewport(viewport);
    assert.ok(await page.evaluate(() => {
      const button = [...document.querySelectorAll('button')].find(element => element.textContent.includes('Bắt đầu trò chuyện'));
      const box = button.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight && document.documentElement.scrollWidth <= innerWidth;
    }), 'The start action stays visible without horizontal scrolling on small screens');
  }
  await page.screenshot({ path: '.next/voice-room-ready-mobile.png', fullPage: true });
  await page.setViewport({ width: 1440, height: 900 });
  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForSelector('[data-interview-mode="VOICE"]');
  assert.equal(speeches.length, 0, 'Reload preserves the channel but never auto-opens the microphone');
  if (unconfigured) {
    await click('Bắt đầu trò chuyện');
    await page.waitForSelector('[role="alert"]');
    assert.ok(await page.$eval('[role="alert"]', element => element.textContent.includes('Simli')));
    assert.equal(await page.evaluate(() => window.__voiceStream), undefined, 'Missing credentials must not open the microphone');
    assert.equal(speeches.length, 0); assert.equal(transcriptions.length, 0);
    assert.ok(!requests.some(url => new URL(url).pathname.includes('/models/')));
    console.log('PASS: missing Simli configuration is actionable, with no microphone, TTS charges or old avatar fallback.');
  } else {
  await click('Bắt đầu trò chuyện');
  await page.waitForSelector('video[data-ready="true"]');
  await page.waitForSelector('::-p-text(Người phỏng vấn đang nói)');
  await feed();
  await page.waitForSelector('[data-answered-count="1"]');
  assert.equal(answers.length, 1, 'Silence automatically submits exactly one V2 answer');
  assert.equal(answers[0].turn_id, 't1');
  assert.ok(await page.$eval('[aria-label="Nội dung lời nói"]', element => element.textContent.includes('Em dùng transaction')), 'The last submitted speech stays visible');
  await page.waitForSelector('::-p-text(Người phỏng vấn đang nói)');
  await page.click('button[aria-label="Tùy chỉnh cuộc trò chuyện"]');
  await page.waitForSelector('[role="dialog"]');
  await page.screenshot({ path: '.next/voice-room-settings.png', fullPage: true });
  await page.click('input[type="checkbox"]'); // Keep subsequent speech for manual completion.
  await click('Xong');
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  failRecognition = true;
  await feed();
  await page.waitForSelector('button::-p-text(Nhận diện lại bản ghi)');
  assert.ok(!await page.$eval('[aria-label="Nội dung lời nói"]', element => element.textContent.includes('Em dùng transaction')), 'A failed new recording must not be presented as the previous submitted answer');
  await page.screenshot({ path: '.next/voice-room-recognition-error.png', fullPage: true });
  const failedAudio = transcriptions.at(-1).audio;
  await click('Nhận diện lại bản ghi');
  await page.waitForSelector('button::-p-text(Tôi đã trả lời xong)');
  await page.waitForFunction(() => !document.body.textContent.includes('Đang nhận diện lời nói…'));
  assert.equal(transcriptions.at(-1).audio, failedAudio, 'Recognition retry reuses the exact recording');
  assert.equal(answers.length, 1, 'Manual mode does not auto-grade the recovered recording');
  assert.ok(await page.$eval('[aria-label="Nội dung lời nói"]', element => element.textContent.includes('Em dùng transaction')), 'Recovered speech is shown as read-only captions');
  await click('Tạm dừng micro');
  assert.equal(await page.evaluate(() => window.__voiceStream.getAudioTracks()[0].enabled), false);
  await page.click('button[aria-label="Tùy chỉnh cuộc trò chuyện"]');
  await page.waitForSelector('[role="dialog"]');
  await page.click('input[type="checkbox"]'); // Oral programming uses the same automatic turn flow.
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'Tùy chỉnh cuộc trò chuyện', 'Closing settings returns keyboard focus to its trigger');
  await click('Tôi đã trả lời xong');
  await page.waitForSelector('[data-answered-count="2"]');
  assert.equal(await page.$('textarea'), null, 'Oral programming must have no code or text editor');
  assert.equal(await page.$('button::-p-text(Mở editor coding)'), null);
  await click('Tiếp tục nghe');
  await page.waitForSelector('::-p-text(Người phỏng vấn đang nói)');
  const feedSpeech = async seconds => page.evaluate(seconds => {
    for (let i = 0; i < Math.ceil(window.__captureRate * seconds / 2048); i++) {
      window.__capture.onmessage({ data: new Float32Array(2048).fill(0.12) });
    }
  }, seconds);
  const oral = 'Em duyệt từng phần tử, cộng vào tổng và kiểm tra mảng rỗng.';
  await feedSpeech(4.5);
  await page.waitForFunction(text => document.querySelector('[aria-label="Nội dung lời nói"]')?.textContent.includes(text), {}, oral);
  assert.match(await page.$eval('[role="status"]', node => node.textContent), /Đang nghe bạn/, 'Microphone feedback stays active while captions arrive');
  assert.equal(answers.length, 2, 'A caption segment must not submit an unfinished answer');
  assert.equal(await page.$('textarea, [contenteditable="true"]'), null, 'Captions are read-only');
  await page.screenshot({ path: '.next/voice-captions-speaking.png', fullPage: true });
  await feedSpeech(4.2);
  await page.waitForFunction(text => document.querySelector('[aria-label="Nội dung lời nói"]')?.textContent.includes(`${text} ${text}`), {}, oral);
  assert.equal(answers.length, 2, 'Multiple caption segments still belong to one spoken answer');
  await page.evaluate(() => {
    for (let i = 0; i < Math.ceil(window.__captureRate * 1.5 / 2048); i++) {
      window.__capture.onmessage({ data: new Float32Array(2048) });
    }
  });
  await page.waitForSelector('[aria-label="Xác nhận lời nói"]');
  await new Promise(resolve => setTimeout(resolve, 1300));
  assert.equal(answers.length, 2, 'Disagreement blocks automatic grading even after silence');
  assert.equal(await page.$eval('button::-p-text(Tôi đã trả lời xong)', element => element.disabled), true);
  assert.ok(await page.$('[aria-label="Nghe lại đoạn cần xác nhận"]'), 'The original audio can be replayed');
  await page.screenshot({ path: '.next/voice-recognition-review.png', fullPage: true });
  await page.setViewport({ width: 320, height: 740 });
  assert.ok(await page.evaluate(() => {
    const box = document.querySelector('[aria-label="Xác nhận lời nói"]').getBoundingClientRect();
    return box.height <= innerHeight * 0.5 && document.documentElement.scrollWidth <= innerWidth;
  }), 'Long review content remains scrollable and fits the mobile viewport');
  await page.screenshot({ path: '.next/voice-recognition-review-mobile.png', fullPage: true });
  await page.setViewport({ width: 1440, height: 900 });
  const contextual = transcriptions.filter(item => item.turn_id === 't3' && item.phase === 'final').at(-1);
  assert.ok(Buffer.from(contextual.audio, 'base64').readUInt32LE(40) / 32000 > 9,
    'Final recognition receives the full contextual audio, not the last caption chunk');
  await page.keyboard.press('Escape');
  assert.ok(await page.$('[aria-label="Xác nhận lời nói"]'), 'Closing the review cannot silently discard recognized speech');
  await click('Dùng bản đối chiếu');
  await page.waitForSelector('[data-answered-count="3"]');
  assert.equal(answers[2].candidate_response, 'Em dùng reduce để cộng các phần tử và kiểm tra mảng rỗng.',
    'Only the selected final result is graded; preview captions are replaced, not appended');
  assert.ok(!answers[2].candidate_response.includes('BÀI LÀM'));
  await page.waitForSelector('::-p-text(Người phỏng vấn đang nói)');
  await page.screenshot({ path: '.next/voice-smoke-active.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  await page.screenshot({ path: '.next/voice-smoke-mobile.png', fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Mobile voice controls must not overflow horizontally');
  await page.click('button[aria-label="Tùy chỉnh cuộc trò chuyện"]');
  await page.waitForSelector('[role="dialog"]');
  assert.ok(await page.evaluate(() => {
    const box = document.querySelector('[role="dialog"]').getBoundingClientRect();
    return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
  }), 'Settings must fit the mobile viewport');
  await page.screenshot({ path: '.next/voice-room-settings-mobile.png', fullPage: true });
  await click('Xong');
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  await click('Tùy chỉnh cuộc trò chuyện');
  await click('Kết thúc phiên');
  await click('Kết thúc lượt');
  await page.waitForFunction(() => window.__voiceStream.getAudioTracks()[0].readyState === 'ended');
  assert.equal(await page.evaluate(() => window.__voiceStream.getAudioTracks()[0].readyState), 'ended');
  await page.screenshot({ path: '.next/voice-smoke.png', fullPage: true });
  assert.equal(answers.length, 3);
  assert.equal(speeches.length, 4, 'Each new question is synthesized once; rerenders must not create paid requests');
  assert.ok(!requests.some(url => url.includes('localhost:8001')), 'Controlled avatar must not connect to the legacy streaming service');
  assert.ok(!requests.some(url => new URL(url).pathname.startsWith('/models/')), 'Simli must not load any old 3D avatar');
  const simli = await page.evaluate(() => window.__simliMock);
  assert.equal(simli.starts, 1, 'New questions reuse the same Simli session');
  assert.equal(simli.stops, 1, 'Ending the interview closes Simli');
  assert.ok(simli.clears > 0 && simli.bytes > 0, 'Interruption clears Simli audio, and TTS is sent as PCM');
  assert.deepEqual(errors, []);
  console.log('PASS: voice setup, persistence, isolated voice UI, barge-in, retry, live read-only captions, oral programming, continuous-speech segmentation and media cleanup.');
  }
} catch (error) {
  console.error('Browser errors:', errors);
  console.error('Voice requests:', { speeches, transcriptionCount: transcriptions.length, answers });
  if (testPage) {
    console.error((await testPage.$eval('body', element => element.innerText)).slice(-6500));
    await testPage.screenshot({ path: '.next/voice-smoke-failure.png', fullPage: true });
  }
  throw error;
} finally { await browser.close(); }
