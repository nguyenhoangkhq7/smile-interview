// Real browser checks with fixture API responses; no live sessions are changed.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const id = 'layout-smoke';
const errors = [];
const config = { mode: 'MIXED', focused_question_mode: null, max_questions: 40,
  duration_seconds: 3600, max_questions_per_objective: 8 };
const code = `SELECT ${'very_long_column_name, '.repeat(20)}id FROM users;`;
const markdown = `## Phân tích truy vấn\n\n**Bối cảnh:** truy vấn chậm.\n\n- Đọc kế hoạch thực thi\n- Kiểm tra chỉ mục\n\n\`\`\`sql\n${code}\n\`\`\`\n\n| Chỉ số | Giá trị |\n| --- | --- |\n| Rows | 100 |\n\n[Liên kết không an toàn](javascript:alert(1))`;
const turn = number => ({ turn_id: `turn-${number}`, objective_id: 'objective', skill_id: 'postgresql',
  mode: 'DEBUGGING', question: `${markdown}\n\nCâu hỏi số ${number}.`, answer: null, feedback: null });
let session = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
  config, deadline_at: new Date(Date.now() + 3600000).toISOString(), turns: [], pending_turn: turn(1),
  report: { schema_version: 2, state_version: 1, is_finished: false, termination_reason: null,
    progress: 0, evidence_coverage: 0, target_attainment: null, objectives: [] } };
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewport({ width: 1365, height: 900 });
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = body => request.respond({ status: 200, headers: { 'content-type': 'application/json',
      'access-control-allow-origin': base, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (url.pathname === `/api/v1/sessions/${id}`) return send({ id, status: 'In progress', roleTitle: 'Backend', turns: [] });
    if (url.pathname.endsWith('/respond')) {
      const answer = JSON.parse(request.postData());
      session = { ...session, state_version: session.state_version + 1,
        turns: [...session.turns, { ...session.pending_turn, answer: answer.candidate_response,
          feedback: 'Bạn đã nêu cách kiểm tra kế hoạch thực thi.' }],
        pending_turn: { ...turn(session.turns.length + 2),
          introduction: 'Bạn đã nêu cách kiểm tra kế hoạch thực thi.\n\nMình muốn làm rõ thêm một ý trong câu trả lời vừa rồi.' } };
    }
    return send(session);
  });
  const click = async label => {
    await page.waitForFunction(label => [...document.querySelectorAll('button,summary')].some(e => e.textContent.trim() === label && !e.disabled), {}, label);
    await page.evaluate(label => [...document.querySelectorAll('button,summary')].find(e => e.textContent.trim() === label && !e.disabled).click(), label);
  };
  const metrics = () => page.evaluate(() => ({ height: document.documentElement.scrollHeight,
    answerTop: document.querySelector('textarea').getBoundingClientRect().top,
    answerBottom: document.querySelector('textarea').getBoundingClientRect().bottom,
    overflow: document.documentElement.scrollWidth > innerWidth }));
  await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('textarea');
  assert.equal(await page.$eval('[aria-label="Nội dung câu hỏi"] h2', e => e.textContent), 'Phân tích truy vấn');
  assert.equal(await page.$eval('[aria-label="Nội dung câu hỏi"] strong', e => e.textContent), 'Bối cảnh:');
  assert.equal(await page.$$eval('[aria-label="Nội dung câu hỏi"] li', e => e.length), 2);
  assert.equal(await page.$eval('pre code', e => e.textContent.trim()), code);
  assert.equal(await page.$$eval('table tbody tr', e => e.length), 1);
  assert.equal(await page.$$eval('a[href^="javascript:"]', e => e.length), 0);
  const initial = await metrics();
  assert.equal(initial.overflow, false);
  assert.ok(initial.answerBottom < 900, 'Desktop answer must remain in the viewport');
  for (let i = 1; i <= 15; i++) {
    await page.type('textarea', `Câu trả lời ${i}: **EXPLAIN ANALYZE**.\n\n${'Giải thích kế hoạch thực thi. '.repeat(30)}`);
    await click('Gửi câu trả lời');
    await page.waitForFunction(count => document.body.innerText.includes(`Lịch sử (${count} câu)`), {}, i);
    await page.waitForFunction(() => !document.querySelector('textarea').disabled);
  }
  const after = await metrics();
  assert.ok(Math.abs(after.height - initial.height) <= 2, 'Fifteen turns must not grow the page');
  assert.ok(Math.abs(after.answerTop - initial.answerTop) <= 2, 'Answer position must remain stable');
  await page.screenshot({ path: '.next/interview-layout-desktop.png', fullPage: true });
  assert.ok(await page.$eval('[aria-label="Phản hồi và chuyển tiếp"]', e => e.innerText.includes('Bạn đã nêu cách kiểm tra kế hoạch thực thi.')));
  assert.ok(await page.$eval('[aria-label="Phản hồi và chuyển tiếp"]', e => e.innerText.includes('Mình muốn làm rõ thêm một ý')));
  assert.ok(await page.$eval('[aria-label="Phản hồi và chuyển tiếp"]', e => e.getBoundingClientRect().bottom < document.querySelector('[aria-label="Nội dung câu hỏi"] h2').getBoundingClientRect().top), 'Feedback and bridge precede the next question');
  await click('Lịch sử (15 câu)');
  await page.waitForSelector('[aria-label="Nội dung lịch sử"]');
  assert.equal(await page.$$eval('[aria-label="Nội dung lịch sử"] details', e => e.length), 15);
  assert.ok(await page.$eval('[aria-label="Nội dung lịch sử"]', e => e.clientHeight <= innerHeight * 0.65 + 1));
  assert.equal(await page.$eval('[aria-label="Nội dung lịch sử"] details summary', e => e.textContent.startsWith('Câu 15')), true);
  await click('Đóng lịch sử');
  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForSelector('textarea');
  assert.equal(session.turns.length, 15);
  assert.ok(await page.$('[aria-label="Phản hồi và chuyển tiếp"]'), 'Feedback survives reload');
  assert.ok((await metrics()).height <= initial.height + 2, 'Reload must preserve the compact layout');
  await page.setViewport({ width: 390, height: 844 });
  const mobile = await metrics();
  assert.equal(mobile.overflow, false);
  assert.ok(await page.$eval('[aria-label="Nội dung câu hỏi"]', e => e.clientHeight <= innerHeight * 0.45 + 1));
  await page.screenshot({ path: '.next/interview-layout-mobile.png', fullPage: true });
  await click('Lịch sử (15 câu)');
  assert.equal((await metrics()).overflow, false);
  assert.deepEqual(errors, []);
  console.log('PASS: Markdown headings/lists/code/tables, safe URLs, 15-turn stable layout, scrollable history, reload and mobile.');
} finally { await browser.close(); }
