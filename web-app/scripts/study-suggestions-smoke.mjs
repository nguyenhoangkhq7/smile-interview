import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://127.0.0.1:3217';
const profileId = 'study-objective-profile';
const source = number => ({ sessionId: `s${number}`, attemptNumber: number, assessedAt: '2026-11-12T10:00:00' });
let phase = 1;
let failNext = false;
const requests = [];
const tasks = [];
const errors = [];
function objective() {
  return { skillId: 'sql', objectiveId: 'objective-a', claim: 'Phân tích truy vấn SQL chậm',
    assessment: phase === 3 ? 'DEMONSTRATED_AT_TARGET' : 'DEMONSTRATED_BELOW_TARGET', source: source(phase),
    criteria: Array.from({ length: 5 }, (_, i) => {
      const number = i + 1;
      const kind = number === 1 || (phase > 1 && number === 2) || (phase === 3 && number === 3) ? 'MET'
        : number <= 3 ? 'REVIEW' : 'UNASSESSED';
      const assessed = kind !== 'UNASSESSED';
      return { criterionId: `c${number}`, description: `Tiêu chí ${number}`, essential: true,
        assessment: kind === 'MET' ? 'DEMONSTRATED_AT_TARGET' : kind === 'REVIEW' ? 'DEMONSTRATED_BELOW_TARGET' : 'NOT_ASSESSED',
        kind, selectedByDefault: kind === 'REVIEW', reason: assessed ? 'Dựa trên bằng chứng phỏng vấn.' : 'Chưa đánh giá; có thể chọn ôn thêm.',
        goal: `Kết quả cần đạt ${number}`, source: assessed ? source(phase) : null, lastAssessment: assessed ? source(phase) : null };
    }) };
}
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1365, height: 1000 });
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = (body, status = 200) => request.respond({ status, headers: { 'content-type': 'application/json',
      'access-control-allow-origin': base, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (url.pathname.endsWith('/knowledge-gaps')) return send({ completedAttempts: phase, weak: [], needsVerification: [],
      notAssessedSkillIds: [], reportWeaknesses: [], objectiveSuggestions: [objective()] });
    if (url.pathname.endsWith('/tasks') && request.method() === 'POST') {
      const input = JSON.parse(request.postData()); requests.push(input);
      if (failNext) { failNext = false; return send({ message: 'Không lưu được dữ liệu thử nghiệm.' }, 503); }
      const id = tasks.length + 1;
      const task = { id, ...input, gapSourceSkillId: input.gapOrigin.skillId,
        gapSourceObjectiveId: input.gapOrigin.objectiveId, gapSourceSessionId: input.gapOrigin.sessionId,
        gapSourceAttemptNumber: input.gapOrigin.attemptNumber };
      tasks.push({ task, checklist: input.checklist.map((item, index) => ({ id: id * 10 + index,
        ...item, isCompleted: false })), resources: [] });
      return send(task, 201);
    }
    if (url.pathname.endsWith('/study-plan')) return send({ plan: { title: 'Kế hoạch SQL', description: null,
      targetCompletionPercent: 80, targetDate: null, sourceSessionId: null },
      progress: { done: 0, total: tasks.length, percent: tasks.length ? 0 : null, meetsTarget: false }, tasks });
    return send({ id: profileId, title: 'Kế hoạch SQL', roleTitle: 'Backend Developer', cvFilename: 'CV.pdf',
      jdTitle: 'Backend', createdAt: '2026-11-12T09:00:00', skills: [{ jd_skill_id: 'sql' }], analysis: {},
      attempts: Array.from({ length: phase }, (_, i) => ({ id: `s${i + 1}`, number: i + 1, status: 'Completed', answeredCount: 3 })) });
  });
  const waitText = text => page.waitForFunction(text => document.body.innerText.includes(text), {}, text);
  const clickText = async (selector, text) => {
    await page.waitForFunction(({ selector, text }) => [...document.querySelectorAll(selector)].some(el => el.textContent.trim() === text), {}, { selector, text });
    await page.evaluate(({ selector, text }) => [...document.querySelectorAll(selector)].find(el => el.textContent.trim() === text).click(), { selector, text });
  };
  const openDraft = async () => {
    await page.click('summary[aria-label="Lỗ hổng kiến thức"]');
    await page.waitForSelector('[aria-label="Thêm đầu việc cho Phân tích truy vấn SQL chậm"]');
    await page.click('[aria-label="Thêm đầu việc cho Phân tích truy vấn SQL chậm"]');
    await page.waitForSelector('[role="dialog"]');
  };
  await page.goto(`${base}/practice/${profileId}`, { waitUntil: 'networkidle0' });
  await openDraft();
  const checked = () => page.$$eval('[role="dialog"] input[type="checkbox"]', inputs => inputs.map(input => input.checked));
  assert.deepEqual(await checked(), [false, true, true, false, false]);
  assert.equal(await page.$eval('[role="dialog"]', el => el.innerText.includes('Kết quả cần đạt')), false,
    'Assessment details should be collapsed in the initial view');
  assert.equal(await page.$eval('[role="dialog"] textarea', el => el.checkVisibility()), false,
    'Notes should be optional rather than occupying the initial view');
  await page.click('input[aria-label="Ôn Tiêu chí 4"]');
  assert.deepEqual(await checked(), [false, true, true, true, false]);
  await clickText('[role="dialog"] button', 'Hủy');
  assert.equal(requests.length, 0, 'Opening and cancelling must not create tasks');

  // Closing a draft must reset optional selections on the next opening.
  await page.evaluate(() => { document.querySelector('summary[aria-label="Lỗ hổng kiến thức"]').parentElement.open = false; });
  await openDraft();
  assert.deepEqual(await checked(), [false, true, true, false, false]);
  await page.click('[aria-label="Sửa nội dung Tiêu chí 2"]');
  await page.focus('[aria-label="Nội dung checklist Tiêu chí 2"]');
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await page.type('[aria-label="Nội dung checklist Tiêu chí 2"]', 'Tiêu chí 2 đã chỉnh');
  await page.click('[aria-label="Sửa nội dung Tiêu chí 2"]');
  await clickText('[role="dialog"] summary', 'Thông tin thêm');
  await waitText('Kết quả cần đạt 2');
  await clickText('[role="dialog"] summary', 'Thông tin thêm');
  failNext = true;
  await clickText('[role="dialog"] button', 'Tạo đầu việc · 2 mục');
  await waitText('Không tạo được đầu việc. Hãy thử lại.');
  assert.deepEqual(await checked(), [false, true, true, false, false]);
  await clickText('[role="dialog"] button', 'Tạo đầu việc · 2 mục');
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  assert.equal(tasks.length, 1);
  assert.deepEqual(requests.at(-1).checklist.map(item => item.sourceCriterionId), ['c2', 'c3']);
  assert.equal(requests.at(-1).checklist[0].content, 'Tiêu chí 2 đã chỉnh');
  assert.equal(requests.at(-1).gapOrigin.objectiveId, 'objective-a');
  assert.ok(requests.at(-1).notes.includes('Kết quả cần đạt 2'));
  assert.equal(requests.at(-1).checklist[0].sourceSessionId, 's1');

  // Dragging a suggestion opens a draft in the destination column without saving it.
  await page.evaluate(() => { document.querySelector('summary[aria-label="Lỗ hổng kiến thức"]').parentElement.open = true; });
  await page.evaluate(() => {
    const card = document.querySelector('article[draggable="true"]');
    const transfer = new DataTransfer();
    card.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: transfer }));
    document.querySelector('section[aria-label="Đang ôn"]').dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
    card.dispatchEvent(new DragEvent('dragend', { bubbles: true, dataTransfer: transfer }));
  });
  await page.waitForSelector('[role="dialog"]');
  await page.click('input[aria-label="Ôn Tiêu chí 4"]');
  await clickText('[role="dialog"] button', 'Tạo đầu việc · 3 mục');
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  assert.equal(requests.at(-1).status, 'IN_PROGRESS');
  assert.deepEqual(requests.at(-1).checklist.map(item => item.sourceCriterionId), ['c2', 'c3', 'c4']);
  assert.ok(!requests.at(-1).checklist[2].sourceSessionId, 'Unassessed criterion has no invented assessment source');

  phase = 2;
  await page.reload({ waitUntil: 'networkidle0' });
  assert.equal(await page.$$eval('[title="Kết quả phỏng vấn mới cho thấy kỹ năng đã cải thiện"]', els => els.length), 0);
  phase = 3;
  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForSelector('[title="Kết quả phỏng vấn mới cho thấy kỹ năng đã cải thiện"]');
  assert.equal(await page.$$eval('[title="Kết quả phỏng vấn mới cho thấy kỹ năng đã cải thiện"]', els => els.length), 1,
    'Only the task whose selected criteria all improved should be marked');

  await page.setViewport({ width: 390, height: 844 });
  await openDraft();
  assert.deepEqual(await checked(), [false, false, false, false, false]);
  await page.click('input[aria-label="Ôn Tiêu chí 4"]');
  await waitText('Nội dung ôn tập (1/5)');
  assert.ok(await page.$eval('[role="dialog"]', el => el.getBoundingClientRect().width <= window.innerWidth));
  await page.screenshot({ path: '.next/study-suggestions-mobile.png' });
  await clickText('[role="dialog"] button', 'Hủy');
  assert.deepEqual(errors, []);
  console.log('PASS: criterion selection, optional review, cancellation, retry, drag/drop, provenance, improvement tracking, mobile dialog');
} finally {
  await browser.close();
}
