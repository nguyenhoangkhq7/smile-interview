// Exercise the real countdown, including recovery after grading and stop errors.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const browser = await puppeteer.launch({ headless: true });
try {
  for (const scenario of ['idle', 'grading-error', 'stop-error', 'conflict', 'busy', 'voice', 'read-only']) {
    const page = await browser.newPage();
    const id = `expiry-${scenario}`;
    const stops = [], answers = [], errors = [];
    let session = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
      deadline_at: new Date(Date.now() + 8000).toISOString(),
      config: { interaction_mode: scenario === 'voice' ? 'VOICE' : 'TEXT', mode: 'MIXED',
        max_questions: 10, duration_seconds: 60, max_questions_per_objective: 8 },
      turns: [], pending_turn: { turn_id: 'turn', objective_id: 'objective', skill_id: 'javascript',
        mode: 'CODING', question: 'Viết một hàm JavaScript.', answer: null, feedback: null },
      report: { schema_version: 2, state_version: 1, is_finished: false, termination_reason: null,
        progress: 0, evidence_coverage: 0, target_attainment: null, objectives: [] } };
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
          report: { ...session.report, is_finished: true, termination_reason: 'TIME_BUDGET' } };
      }
      if (url.pathname.endsWith('/interview') && request.method() === 'GET') {
        // Start the short deadline when the fixture is actually loaded, after compilation.
        if (!page.fixtureLoaded) {
          page.fixtureLoaded = true;
          session.deadline_at = new Date(Date.now() + (scenario === 'read-only' ? -1000 : 4000)).toISOString();
        }
      }
      return send(200, session);
    });
    await page.goto(`${base}/interview/session/${id}${scenario === 'read-only' ? '/result' : ''}`, { waitUntil: 'networkidle0' });
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
