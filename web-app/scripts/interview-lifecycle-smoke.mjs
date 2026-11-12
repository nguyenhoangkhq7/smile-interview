// Real UI/Web Audio with isolated HTTP and avatar fixtures; no live interview writes.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3220';
const browser = await puppeteer.launch({ headless: true, args: ['--autoplay-policy=no-user-gesture-required'] });
const question = 'Bạn kiểm tra truy vấn SQL chậm như thế nào?';
const openingText = 'Chào bạn, mình là Minh, người phỏng vấn AI tại Smile. Hôm nay chúng ta trao đổi về Backend Developer. Bạn có thể giới thiệu bản thân được không?';
const intro = 'Em tên Nam, em đã làm backend bằng Spring Boot.';
const future = seconds => new Date(Date.now() + seconds * 1000).toISOString();

async function scenario(mode, action) {
  const id = `lifecycle-${mode}-${action}`;
  const page = await browser.newPage();
  const errors = [], commands = [], answers = [], transcriptions = [], speeches = [];
  let session = null, failedIntro = false, failedSpeech = false;
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewport({ width: 1280, height: 900 });
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('auth-storage', JSON.stringify({ state: {
      user: { id: 'test', username: 'Test', role: 'USER' }, isAuthenticated: true,
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
    }, version: 0 }));
    const context = new AudioContext();
    navigator.mediaDevices.getUserMedia = async () => {
      const stream = context.createMediaStreamDestination().stream; window.__voiceStream = stream; return stream;
    };
    Object.getPrototypeOf(context.audioWorklet).addModule = async () => {};
    window.AudioWorkletNode = class extends GainNode {
      constructor(ctx) { super(ctx); this.port = { onmessage: null }; window.__capture = this.port; window.__captureRate = ctx.sampleRate; }
    };
  });
  const finish = reason => {
    session.is_finished = true; session.pending_turn = null;
    session.conversation.phase = 'CLOSING'; session.conversation.expires_at = future(120);
    session.conversation.message = { message_id: 'farewell', text: 'Cảm ơn bạn đã tham gia. Chúc bạn một ngày tốt lành, chào bạn!' };
    session.report = { ...session.report, is_finished: true, termination_reason: reason };
  };
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    const headers = { 'content-type': 'application/json', 'access-control-allow-origin': base,
      'access-control-allow-headers': '*', 'access-control-allow-methods': '*',
      'access-control-expose-headers': 'X-Audio-Sample-Rate, X-Audio-Format' };
    const send = (body, status = 200) => request.respond({ status, headers, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    if (url.pathname === `/api/v1/sessions/${id}`) return send({ id, status: 'In progress', turns: [] });
    if (url.pathname.endsWith('/interview/start')) {
      session = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
        deadline_at: future(900), config: JSON.parse(request.postData()), pending_turn: null, turns: [],
        report: { schema_version: 2, state_version: 1, is_finished: false, termination_reason: null,
          progress: 0, evidence_coverage: 0, target_attainment: null, objectives: [] },
        conversation: { phase: 'OPENING', message: { message_id: 'greeting', text: openingText },
          opening: { interviewer_name: 'Minh', company: 'Smile', role_title: 'Backend Developer', company_description: '' },
          opening_text: openingText, introduction: '', introduction_skipped: false, expires_at: future(180) } };
      return send(session);
    }
    if (url.pathname.endsWith('/interview/conversation')) {
      const command = JSON.parse(request.postData()); commands.push({ ...command, phase: session.conversation.phase, at: Date.now() });
      assert.equal(command.expected_state_version, session.state_version);
      assert.equal(command.message_id, session.conversation.message.message_id);
      if (action === 'retry' && command.action === 'SUBMIT_INTRODUCTION' && !failedIntro) {
        failedIntro = true; return send({ message: 'Lỗi tạm thời, hãy gửi lại giới thiệu.' }, 503);
      }
      const c = session.conversation;
      if (command.action === 'NEXT') {
        c.phase = c.phase === 'OPENING' ? 'SELF_INTRODUCTION' : 'FINISHED';
        c.expires_at = future(action === 'timeout' ? 1 : 120);
      } else {
        assert.equal(session.turns.length, 0);
        c.introduction = command.introduction; c.introduction_skipped = command.action === 'SKIP_INTRODUCTION';
        c.phase = 'INTERVIEW'; session.deadline_at = future(900);
        session.pending_turn = { turn_id: 'technical-1', objective_id: 'o1', skill_id: 'postgresql', mode: 'DEBUGGING',
          question, introduction: 'Cảm ơn bạn. Mình bắt đầu phần chuyên môn nhé.', answer: null, feedback: null };
      }
      session.state_version++; return send(session);
    }
    if (url.pathname.endsWith('/interview/respond')) {
      const command = JSON.parse(request.postData()); answers.push(command);
      assert.equal(session.conversation.phase, 'INTERVIEW');
      assert.equal(command.turn_id, 'technical-1');
      session.turns.push({ ...session.pending_turn, answer: command.candidate_response, feedback: 'Đã ghi nhận.' });
      session.state_version++; finish('PLAN_COMPLETE'); return send(session);
    }
    if (url.pathname.endsWith('/interview/stop')) {
      session.state_version++; finish('USER_STOP'); return send(session);
    }
    if (url.pathname.endsWith('/voice/config')) return send({ enabled: true, format: 'pcm', sample_rate: 24000,
      avatar: { provider: 'simli', configured: true, sample_rate: 16000 } });
    if (url.pathname.endsWith('/voice/avatar-session')) return send({ session_token: 'fixture-token' });
    if (url.pathname.endsWith('/voice/speech')) {
      speeches.push({ ...JSON.parse(request.postData()), phase: session.conversation.phase, at: Date.now() });
      if (action === 'speech-error' && session.conversation.phase === 'OPENING' && !failedSpeech) {
        failedSpeech = true; return send({ message: 'Không thể phát lời mở đầu. Hãy thử lại.' }, 503);
      }
      return request.respond({ status: 200, headers: { ...headers, 'content-type': 'audio/pcm',
        'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '24000' }, body: Buffer.alloc(4800, 1) });
    }
    if (url.pathname.endsWith('/voice/transcribe')) {
      const command = JSON.parse(request.postData()); transcriptions.push({ ...command, stage: session.conversation.phase });
      assert.ok(['SELF_INTRODUCTION', 'INTERVIEW'].includes(session.conversation.phase));
      return send({ phase: command.phase, verification: 'not_requested', review_required: false,
        text: session.conversation.phase === 'SELF_INTRODUCTION' ? intro : 'Em dùng EXPLAIN ANALYZE.' });
    }
    if (url.pathname.endsWith('/interview')) return send(session || {}, session ? 200 : 404);
    return send({});
  });
  const click = async label => { const button = await page.waitForFunction(text => [...document.querySelectorAll('button')].find(node => node.textContent.includes(text) || node.getAttribute('aria-label') === text), {}, label); await button.asElement().click(); };
  const waitPhase = phase => page.waitForSelector(`[data-conversation-phase="${phase}"]`);
  const feed = () => page.evaluate(() => {
    for (let i = 0; i < 6; i++) window.__capture.onmessage({ data: new Float32Array(1600).fill(0.12) });
    for (let i = 0; i < 16; i++) window.__capture.onmessage({ data: new Float32Array(1600) });
  });
  try {
    await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
    await page.click(`input[name="interaction-mode"][value="${mode}"]`);
    await click('Bắt đầu phỏng vấn'); await waitPhase(mode === 'VOICE' ? 'OPENING' : 'SELF_INTRODUCTION');
    assert.equal(answers.length, 0); assert.equal(session.pending_turn, null);
    await page.setViewport({ width: 320, height: 740 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `.next/lifecycle-${mode}-opening.png`, fullPage: true });
    await page.setViewport({ width: 1280, height: 900 });
    if (mode === 'VOICE') {
      assert.equal(await page.$('button::-p-text(Tiếp tục giới thiệu bản thân)'), null);
      assert.equal(await page.$('button::-p-text(Xem kết quả)'), null);
      assert.equal(await page.$eval('[aria-label="Nội dung câu hỏi"]', node => node.textContent), openingText, 'One panel displays what AI is saying');
      await click('Bắt đầu trò chuyện');
      await page.waitForFunction(() => window.__capture?.onmessage);
      await feed();
      assert.equal(transcriptions.length, 0, 'Opening cannot become a candidate answer');
      if (action === 'speech-error') {
        await page.waitForSelector('[role="alert"]');
        assert.ok(await page.$('button::-p-text(Tiếp tục trò chuyện)'), 'Manual transition is only a recovery action');
        await click('Thử lại giọng đọc');
      }
      await waitPhase('SELF_INTRODUCTION');
      assert.ok(commands[0].at - speeches[0].at >= 300, 'Wait for avatar playback, beyond download completion');
      const spoken = speeches.length;
      await page.reload({ waitUntil: 'networkidle0' }); await waitPhase('SELF_INTRODUCTION');
      await click('Bắt đầu trò chuyện'); await page.waitForSelector('video[data-ready="true"]');
      assert.equal(speeches.length, spoken, 'Reload resumes introduction without repeating the greeting');
      await page.evaluate(() => { window.__room = document.querySelector('[data-interview-mode="VOICE"]'); window.__avatar = document.querySelector('video'); });
      await feed(); await waitPhase('INTERVIEW');
      assert.ok(await page.evaluate(() => window.__room === document.querySelector('[data-interview-mode="VOICE"]') && window.__avatar === document.querySelector('video')), 'One room and avatar persist across conversation phases');
      assert.equal(answers.length, 0); assert.equal(session.conversation.introduction, intro);
      await page.waitForFunction(() => window.__simliMock.packets > 0);
      if (action === 'paused-stop') {
        await click('Tạm dừng micro'); await click('Tùy chỉnh cuộc trò chuyện'); await click('Kết thúc phiên'); await click('Kết thúc lượt');
      } else await feed();
      await waitPhase('CLOSING');
      assert.equal(await page.$('button::-p-text(Xem kết quả)'), null, 'Farewell needs no navigation action');
      assert.match(await page.$eval('[aria-label="Nội dung câu hỏi"]', node => node.textContent), /chào bạn!/, 'The same AI panel displays the farewell');
      assert.equal(await page.$eval('h1', node => node.textContent), 'Phỏng vấn giọng nói');
      await page.waitForFunction(() => !document.querySelector('[data-interview-mode="VOICE"]'), { timeout: 10000 });
      const closing = speeches.find(item => item.phase === 'CLOSING');
      assert.ok(closing, 'Farewell is spoken');
      assert.ok(commands.at(-1).at - closing.at >= 300, 'Results wait for farewell playback');
      assert.equal(session.conversation.phase, 'FINISHED');
      assert.equal(answers.length, action === 'paused-stop' ? 0 : 1);
    } else {
      await waitPhase('SELF_INTRODUCTION');
      assert.equal(await page.$('button::-p-text(Giới thiệu bản thân)'), null, 'Reading the greeting requires no next-step button');
      if (action === 'stop') {
        await click('Kết thúc phiên'); await click('Kết thúc lượt');
      } else {
        if (action === 'skip') await click('Bỏ qua giới thiệu');
        else if (action !== 'timeout') {
          await page.reload({ waitUntil: 'networkidle0' }); await waitPhase('SELF_INTRODUCTION');
          await page.type('#interview-answer', intro);
          await click('Gửi câu trả lời');
          if (action === 'retry') {
            await page.waitForSelector('[role="alert"]');
            assert.equal(await page.$eval('#interview-answer', node => node.value), intro);
            await click('Gửi câu trả lời');
            await waitPhase('INTERVIEW');
            const submitted = commands.filter(item => item.action === 'SUBMIT_INTRODUCTION');
            assert.equal(submitted[0].request_id, submitted[1].request_id);
          }
        }
        await waitPhase('INTERVIEW');
        assert.match(await page.$eval('body', node => node.innerText), new RegExp(question.replace('?', '\\?')));
        assert.equal(session.turns.length, 0, 'Introduction does not spend a technical question');
        if (action === 'skip' || action === 'timeout') assert.equal(session.conversation.introduction_skipped, true);
        await click('Lịch sử');
        assert.match(await page.$eval('[role="dialog"]', node => node.textContent), /Mở đầu và giới thiệu bản thân/);
        await click('Đóng lịch sử');
        await page.type('#interview-answer', 'Em dùng EXPLAIN ANALYZE.'); await click('Gửi câu trả lời');
      }
      await waitPhase('CLOSING');
      assert.match(await page.$eval('body', node => node.innerText), /chào bạn/);
      await page.reload({ waitUntil: 'networkidle0' }); await waitPhase('CLOSING');
      await page.setViewport({ width: 320, height: 740 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: `.next/lifecycle-${mode}-${action}.png`, fullPage: true });
      await click('Xem kết quả');
      await page.waitForFunction(() => !document.querySelector('[data-conversation-phase]'));
      assert.equal(session.conversation.phase, 'FINISHED');
      assert.equal(speeches.length, 0, 'Text mode never calls TTS');
    }
    assert.deepEqual(errors, []);
    console.log(`PASS: ${mode} ${action}, separate introduction, reload and farewell before results`);
  } finally { await page.close(); }
}
try {
  for (const action of ['retry', 'skip', 'timeout', 'stop']) await scenario('TEXT', action);
  await scenario('VOICE', 'success');
  await scenario('VOICE', 'paused-stop');
  await scenario('VOICE', 'speech-error');
} finally { await browser.close(); }
