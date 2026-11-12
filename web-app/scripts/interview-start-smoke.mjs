// Start through the real setup UI; API fixtures never change live interview data.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const browser = await puppeteer.launch({ headless: true });
try {
  for (const scenario of ['success', 'server-error', 'rate-limit', 'timeout', 'empty', 'no-content', 'missing-question']) {
    const page = await browser.newPage();
    const id = `start-${scenario}`;
    const errors = [], starts = [], voiceRequests = [];
    let releaseStart;
    let startObserved;
    page.on('pageerror', error => errors.push(error.message));
    await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
      state: { user: { id: 'test', username: 'Test', role: 'USER' },
        token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
        isAuthenticated: true }, version: 0,
    })));
    await page.setRequestInterception(true);
    page.on('request', async request => {
      const url = new URL(request.url());
      if (url.pathname.includes('/voice/')) voiceRequests.push(url.pathname);
      if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:'
        ? request.continue() : request.abort();
      const send = (body, status = 200) => request.respond({ status,
        headers: { 'content-type': 'application/json', 'access-control-allow-origin': base,
          'access-control-allow-headers': '*', 'access-control-allow-methods': '*' },
        body: status === 204 ? '' : JSON.stringify(body) });
      if (request.method() === 'OPTIONS') return send({});
      if (url.pathname === `/api/v1/sessions/${id}`) return send({ id, status: 'Not started', turns: [] });
      if (!url.pathname.endsWith('/interview/start')) return send({}, 404);
      const config = JSON.parse(request.postData());
      starts.push(config);
      await new Promise(resolve => { releaseStart = resolve; startObserved(); });
      if (scenario === 'server-error' && starts.length <= 2) return send({ message: 'Chưa thể tạo câu hỏi. Vui lòng thử lại.' }, 503);
      if (starts.length === 1) {
        if (scenario === 'rate-limit') return send({ message: 'Dịch vụ AI đang giới hạn yêu cầu. Vui lòng chờ một chút rồi thử lại; dữ liệu hồ sơ vẫn được giữ nguyên.' }, 503);
        if (scenario === 'timeout') return send({ message: 'Gateway Timeout' }, 504);
        if (scenario === 'empty') return send(null);
        if (scenario === 'no-content') return send(null, 204);
      }
      return send({ schema_version: 2, session_id: id, state_version: 1, is_finished: false,
        config, deadline_at: new Date(Date.now() + 900000).toISOString(), turns: [],
        pending_turn: scenario === 'missing-question' && starts.length === 1 ? null : {
          turn_id: 'first', objective_id: 'objective', skill_id: 'postgresql', mode: 'DEBUGGING',
          question: 'Bạn kiểm tra truy vấn SQL chậm như thế nào?', answer: null, feedback: null },
        report: { schema_version: 2, state_version: 1, is_finished: false, termination_reason: null,
          progress: 0, evidence_coverage: 0, target_attainment: null, objectives: [] } });
    });
    await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('input[name="interaction-mode"][value="TEXT"]');
    await page.click('input[name="interaction-mode"][value="TEXT"]');
    const clickStart = () => page.evaluate(() => [...document.querySelectorAll('button')]
      .find(button => button.textContent.trim() === 'Bắt đầu phỏng vấn').click());
    let requestStarted = new Promise(resolve => { startObserved = resolve; });
    await clickStart();
    await page.waitForFunction(() => [...document.querySelectorAll('button')]
      .some(button => button.disabled && button.textContent.includes('Đang chuẩn bị')));
    await requestStarted;
    assert.equal(starts.length, 1);
    assert.equal(starts[0].interaction_mode, 'TEXT');
    assert.equal(starts[0].mode, 'MIXED');
    let retryStarted;
    if (scenario === 'server-error' || scenario === 'rate-limit') {
      retryStarted = new Promise(resolve => { startObserved = resolve; });
    }
    const firstResponseAt = Date.now();
    releaseStart();
    if (retryStarted) {
      await retryStarted;
      assert.ok(Date.now() - firstResponseAt >= 4900, 'Start retries must be delayed');
      assert.equal(starts.length, 2);
      assert.deepEqual(starts[0], starts[1], 'Retry must preserve the locked configuration');
      assert.equal(await page.$('[role="alert"]'), null, 'A transient failure should recover without a user click');
      releaseStart();
    }
    if (scenario !== 'success' && scenario !== 'rate-limit') {
      await page.waitForSelector('[role="alert"]', { timeout: 5000 });
      assert.equal(await page.$('textarea'), null);
      if (scenario === 'timeout') assert.match(await page.$eval('[role="alert"]', e => e.textContent), /mất quá nhiều thời gian/);
      requestStarted = new Promise(resolve => { startObserved = resolve; });
      await clickStart();
      await page.waitForFunction(() => [...document.querySelectorAll('button')]
        .some(button => button.disabled && button.textContent.includes('Đang chuẩn bị')));
      await requestStarted;
      releaseStart();
    }
    await page.waitForSelector('[data-interview-mode="TEXT"] textarea');
    assert.match(await page.$eval('body', body => body.innerText), /Bạn kiểm tra truy vấn SQL chậm/);
    assert.equal(await page.$('[role="alert"]'), null);
    assert.deepEqual(errors, []);
    assert.deepEqual(voiceRequests, []);
    console.log(`PASS: default text start, loading feedback and recovery (${scenario})`);
    await page.close();
  }
} finally { await browser.close(); }
