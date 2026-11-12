// Run against a local production build. All API responses are controlled fixtures.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const id = 'test-v2-smoke';
const config = { mode: 'FOCUSED', focused_question_mode: 'DEBUGGING', max_questions: 10,
  duration_seconds: 900, max_questions_per_objective: 8 };
const turn = { turn_id: 'turn-1', objective_id: 'objective-1', skill_id: 'postgresql',
  mode: 'DEBUGGING', question: 'Bạn dùng EXPLAIN ANALYZE để kiểm tra truy vấn chậm như thế nào?', answer: null, feedback: null };
const report = { schema_version: 2, state_version: 1, is_finished: false, termination_reason: null,
  progress: 0, evidence_coverage: 0, target_attainment: null, objectives: [] };
let session = null;
const answers = [];
const errors = [];
const voiceRequests = [];
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
      isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (url.pathname.includes('/voice/') || (url.pathname.startsWith('/models/') && url.pathname.endsWith('.glb'))) voiceRequests.push(url.pathname);
    if (!url.pathname.startsWith('/api/')) {
      return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    }
    const headers = { 'access-control-allow-origin': base, 'access-control-allow-headers': '*',
      'access-control-allow-methods': '*', 'content-type': 'application/json' };
    const send = (body, status = 200) => request.respond({ status, headers, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (url.pathname === `/api/v1/sessions/${id}`) return send({ id, status: 'Not started', turns: [] });
    if (url.pathname.endsWith('/interview/start')) {
      assert.equal(JSON.parse(request.postData()).focused_question_mode, 'DEBUGGING');
      assert.equal(JSON.parse(request.postData()).interaction_mode, 'TEXT');
      assert.equal(JSON.parse(request.postData()).max_questions_per_objective, 8);
      session = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
        config, deadline_at: new Date(Date.now() + 900000).toISOString(), pending_turn: turn, turns: [], report };
      return send(session);
    }
    if (url.pathname.endsWith('/interview/respond')) {
      const payload = JSON.parse(request.postData()); answers.push(payload);
      if (answers.length === 1) return send({ message: 'Lỗi mạng thử nghiệm, hãy thử lại.' }, 502);
      assert.deepEqual(answers[0], payload, 'Retry must preserve the exact request ID and payload');
      session = { ...session, state_version: 2, is_finished: true, pending_turn: null,
        turns: [{ ...turn, answer: payload.candidate_response, feedback: 'Đã chỉ ra cách kiểm chứng.' }],
        report: { ...report, state_version: 2, is_finished: true, termination_reason: 'PLAN_COMPLETE',
          progress: 1, evidence_coverage: 0.5, target_attainment: null, objectives: [{ objective_id: 'objective-1',
            skill_id: 'postgresql', claim: 'Chẩn đoán truy vấn chậm', inferred: false, jd_evidence_spans: ['Optimize SQL'],
            assessment: 'INSUFFICIENT_EVIDENCE', lifecycle: 'CLOSED', stop_reason: 'NO_PROGRESS',
            excluded_reason: null, covered_criteria: ['c1'], missing_criteria: ['Kiểm chứng giả thuyết'], strengths: ['Biết đọc kế hoạch thực thi'],
            weaknesses: [], evidence: [{ turn_id: 'turn-1', criterion_id: 'c1', response_excerpt: payload.candidate_response,
              rationale: 'Có cách kiểm chứng', observation: 'SUPPORTS', performance: 'AT_TARGET' }], evidence_turn_ids: ['turn-1'],
            criteria: [{ criterion_id: 'c1', description: 'Đọc kế hoạch thực thi', assessment: 'DEMONSTRATED_AT_TARGET',
              turns_spent: 4, stop_reason: 'SUFFICIENT_EVIDENCE' },
              { criterion_id: 'c2', description: 'Kiểm chứng giả thuyết', assessment: 'INSUFFICIENT_EVIDENCE',
                turns_spent: 3, stop_reason: 'NO_PROGRESS' }] }] } };
      return send(session);
    }
    if (url.pathname.endsWith('/interview')) return send(session || {}, session ? 200 : 404);
    return send({});
  });
  await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('select');
  await page.select('select', 'DEBUGGING');
  const click = async text => {
    const button = await page.waitForSelector(`::-p-text(${text})`);
    await button.click();
  };
  await click('Bắt đầu phỏng vấn');
  await page.waitForSelector('textarea');
  await page.reload({ waitUntil: 'networkidle0' });
  assert.equal(await page.$('[aria-label="Avatar người phỏng vấn"]'), null);
  assert.equal(await page.$('button::-p-text(Bắt đầu trò chuyện)'), null);
  await page.type('textarea', 'EXPLAIN ANALYZE: so sánh estimated rows và actual rows.');
  await click('Gửi câu trả lời');
  await page.waitForSelector('[role="alert"]');
  assert.match(await page.$eval('textarea', e => e.value), /EXPLAIN ANALYZE/);
  await click('Gửi câu trả lời');
  await page.waitForSelector('::-p-text(Kết quả phỏng vấn)');
  await page.goto(`${base}/interview/session/${id}/result`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('::-p-text(Kết quả phỏng vấn)');
  await click('Chi tiết từng tiêu chí');
  assert.match(await page.$eval('body', e => e.innerText), /Đọc kế hoạch thực thi: Đáp ứng yêu cầu đã kiểm tra/);
  assert.match(await page.$eval('body', e => e.innerText), /Chưa đủ thông tin mới để kết luận thêm/);
  await page.screenshot({ path: '.next/evidence-smoke.png', fullPage: true });
  assert.equal(answers.length, 2);
  assert.deepEqual(errors, []);
  assert.deepEqual(voiceRequests, [], 'Text mode must never load an avatar or call voice APIs');
  console.log('PASS: adaptive defaults, focused setup, reload, retry, candidate criterion labels and stop reasons.');
} finally {
  await browser.close();
}
