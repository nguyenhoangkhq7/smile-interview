// Exercise the real countdown, including recovery after grading and stop errors.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const browser = await puppeteer.launch({ headless: true });
try {
  for (const scenario of ['idle', 'grading-error', 'stop-error', 'conflict', 'busy', 'voice', 'read-only', 'durable-grading']) {
    const page = await browser.newPage();
    const id = `expiry-${scenario}`;
    const stops = [], answers = [], errors = [];
    let completedGrading = false, questionLoads = 0;
    const nextQuestion = Promise.withResolvers();
    let session = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
      deadline_at: new Date(Date.now() + 8000).toISOString(),
      config: { interaction_mode: scenario === 'voice' ? 'VOICE' : 'TEXT', mode: 'MIXED',
        max_questions: 10, duration_seconds: 60, max_questions_per_objective: 8 },
      turns: [], pending_turn: { turn_id: 'turn', objective_id: 'objective',
        mode: 'CODING', question: 'Viết một hàm JavaScript.' },
      report: { termination_reason: null,
        objectives: [{ objective_id: 'objective', skill_id: 'javascript', claim: 'JS', jd_evidence_spans: [],
          assessment: 'NOT_ASSESSED', stop_reason: null, strengths: [], weaknesses: [], evidence: [] }] } };
    page.on('pageerror', error => errors.push(error.message));
    await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
      state: { user: { id: 'test', username: 'Test', role: 'USER' },
        token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
        isAuthenticated: true }, version: 0,
    })));
    await page.setRequestInterception(true);
    page.on('request', async request => {
      const url = new URL(request.url());
      if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:'
        ? request.continue() : request.abort();
      const send = (status, body) => request.respond({ status,
        headers: { 'content-type': 'application/json', 'access-control-allow-origin': base,
          'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
      if (request.method() === 'OPTIONS') return send(200, {});
      if (url.pathname === `/api/v1/sessions/${id}`) return send(200, { id, status: 'In progress', roleTitle: 'Test', turns: [] });
      if (url.pathname.endsWith('/respond')) {
        answers.push(JSON.parse(request.postData()));
        if (scenario === 'durable-grading') {
          session = { ...session, pending_turn: null, state_version: 2, paused_remaining_seconds: 5,
            deadline_at: new Date(Date.now() - 10000).toISOString(),
            submission: { ...answers[0], status: 'QUEUED', received_at: new Date().toISOString() } };
          return send(200, session);
        }
        if (scenario === 'busy') await new Promise(resolve => setTimeout(resolve, 5000));
        return send(503, { message: 'AI chưa thể chấm câu trả lời một cách hợp lệ.' });
      }
      if (url.pathname.endsWith('/stop')) {
        stops.push({ ...JSON.parse(request.postData()), at: Date.now() });
        if (scenario === 'stop-error' && stops.length === 1) return send(503, { message: 'Temporary stop failure' });
        if (scenario === 'conflict' && stops.length === 1) {
          session = { ...session, state_version: 2 };
          return send(409, {});
        }
        session = { ...session, state_version: session.state_version + 1, is_finished: true, pending_turn: null,
          report: { ...session.report, termination_reason: 'TIME_BUDGET' } };
      }
      if (url.pathname.endsWith('/interview') && request.method() === 'GET') {
        if (completedGrading && session.submission) {
          session = { ...session, state_version: 3, awaiting_question: true, submission: null,
            turns: [{ ...answers[0], answer: answers[0].candidate_response, objective_id: 'objective', mode: 'CODING' }] };
        }
        // Start the short deadline when the fixture is actually loaded, after compilation.
        if (!page.fixtureLoaded) {
          page.fixtureLoaded = true;
          session.deadline_at = new Date(Date.now() + (scenario === 'read-only' ? -1000 : scenario === 'durable-grading' ? 60000 : 4000)).toISOString();
        }
      }
      if (scenario === 'durable-grading' && url.pathname.endsWith('/next-question')) {
        questionLoads++;
        await nextQuestion.promise;
        session = { ...session, state_version: 4, paused_remaining_seconds: null, awaiting_question: false,
          deadline_at: new Date(Date.now() + 5000).toISOString(), pending_turn: { turn_id: 'turn-2',
            objective_id: 'objective', mode: 'TECHNICAL_EXPLANATION', question: 'Bạn sẽ áp dụng cách này ở đâu?' } };
      }
      return send(200, session);
    });
    await page.goto(`${base}/interview/session/${id}${scenario === 'read-only' ? '/result' : ''}`, { waitUntil: 'networkidle0' });
    if (scenario === 'durable-grading') {
      const gradingOverlay = '[role="dialog"][aria-label="Đang chấm câu trả lời…"]';
      const questionOverlay = '[role="dialog"][aria-label="Đang chuẩn bị câu hỏi tiếp theo…"]';
      await page.type('textarea', 'Bài đã nộp của tôi');
      await page.evaluate(() => [...document.querySelectorAll('button')].find(e => e.textContent.includes('Gửi câu trả lời')).click());
      await page.waitForSelector(gradingOverlay, { visible: true });
      await page.waitForSelector('[data-interview-mode="TEXT"]', { visible: true });
      assert.match(await page.$eval('[data-slot="dialog-overlay"]', node => getComputedStyle(node).backdropFilter), /blur\(/);
      assert.equal(await page.$('summary::-p-text(Xem bài đã nộp)'), null);
      await page.keyboard.press('Escape');
      assert.ok(await page.$(gradingOverlay), 'Grading overlay stays open until the server is ready');
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForSelector(gradingOverlay, { visible: true });
      assert.equal(stops.length, 0);
      completedGrading = true;
      await page.waitForSelector(questionOverlay, { visible: true });
      nextQuestion.resolve();
      await page.waitForFunction(() => document.body.innerText.includes('áp dụng cách này'));
      await page.waitForSelector(questionOverlay, { hidden: true });
      assert.equal(questionLoads, 1);
      assert.equal(answers.length, 1);
      assert.deepEqual(errors, []);
      await page.close();
      console.log('PASS: saved submission survives reload and pauses expiration until the next question');
      continue;
    }
    if (scenario === 'grading-error' || scenario === 'busy') {
      await page.waitForSelector('textarea');
      await page.type('textarea', 'function task() {}');
      await page.evaluate(() => [...document.querySelectorAll('button')].find(e => e.textContent.includes('Gửi câu trả lời')).click());
      await page.waitForFunction(() => document.body.innerText.includes('AI chưa thể chấm'));
    }
    if (scenario === 'read-only') {
      await new Promise(resolve => setTimeout(resolve, 5000));
      assert.equal(stops.length, 0);
    } else {
      await page.waitForFunction(() => document.body.innerText.includes('Lượt phỏng vấn đã kết thúc'), { timeout: 20000 });
      assert.equal(session.report.termination_reason, 'TIME_BUDGET');
      assert.equal(stops.length, ['stop-error', 'conflict'].includes(scenario) ? 2 : 1);
      assert.ok(stops[0].at >= Date.parse(session.deadline_at), 'No early expiry');
      if (scenario === 'stop-error') {
        assert.equal(stops[0].request_id, stops[1].request_id);
        assert.ok(stops[1].at - stops[0].at >= 4900, 'Retries must be throttled');
      }
      if (scenario === 'conflict') assert.equal(stops[1].expected_state_version, 2);
      assert.equal(answers.length, ['grading-error', 'busy'].includes(scenario) ? 1 : 0, 'Never auto-submit a draft');
    }
    assert.deepEqual(errors, []);
    console.log(`PASS: ${scenario}`);
    await page.close();
  }
} finally { await browser.close(); }
