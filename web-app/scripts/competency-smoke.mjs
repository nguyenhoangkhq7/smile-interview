// Browser contract checks. Projection rules are covered by backend tests.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const id = 'competency-profile';
let phase = 0;
let failNext = false;
const errors = [];
const source = number => ({ sessionId: `s${number}`, attemptNumber: number, assessedAt: '2026-11-07T10:00:00' });
const status = ['NOT_ASSESSED', 'DEMONSTRATED_BELOW_TARGET', 'NEEDS_VERIFICATION', 'DEMONSTRATED_AT_TARGET', 'INSUFFICIENT_EVIDENCE'];
function view() {
  const evidence = Array.from({ length: phase === 4 ? 0 : phase }, (_, index) => ({ source: source(index + 1), turnId: `turn-${index + 1}`,
    question: '## Chẩn đoán truy vấn\n\nBạn sẽ kiểm tra truy vấn SQL chậm như thế nào?',
    responseExcerpt: index ? 'EXPLAIN ANALYZE để kiểm chứng kế hoạch thực thi.' : 'Tôi chưa biết cách đọc kế hoạch thực thi.',
    rationale: index ? '**Có bằng chứng:** đối chiếu estimated rows và actual rows.' : 'Chưa thể hiện cách chẩn đoán.',
    performance: index ? 'AT_TARGET' : 'BELOW' }));
  return { completedAttempts: phase, incompatibleAssessments: 0,
    skills: [{ skillId: 'sql', baselineAlignment: 'MISSING', assessment: status[phase],
      objectives: [{ id: 'sql-task', claim: 'Chẩn đoán hiệu năng truy vấn SQL', assessment: status[phase],
        lastChecked: phase ? source(phase) : null, lastAssessment: evidence.length ? source(phase) : null,
        explanation: phase === 2 ? 'Có bằng chứng mâu thuẫn. Cần hai lượt xác nhận nhất quán về sau ở các bối cảnh độc lập để cập nhật kết luận.' : 'Đánh giá theo bằng chứng đã lưu.',
        criteria: [{ id: 'sql-c1', description: 'Đọc và giải thích `EXPLAIN ANALYZE`', essential: true,
          atTarget: phase ? 'Chỉ ra thao tác chiếm nhiều thời gian nhất.' : undefined,
          assessment: evidence.length ? status[phase] : 'NOT_ASSESSED', lastAssessment: evidence.length ? source(phase) : null, evidence },
        { id: 'sql-c2', description: 'Đề xuất cách đo lại sau khi tối ưu.', essential: false,
          assessment: 'NOT_ASSESSED', lastAssessment: null, evidence: [] }] }] },
    { skillId: 'java', baselineAlignment: 'MATCH', assessment: 'NOT_ASSESSED', objectives: [] }] };
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
    if (url.pathname.endsWith('/competency')) {
      if (failNext) { failNext = false; return send({ message: 'Không thể tải đánh giá thử nghiệm.' }, 503); }
      return send(view());
    }
    return send({ id, title: 'Backend Developer · Công ty A', company: 'Công ty A', roleTitle: 'Backend Developer',
      cvFilename: 'Backend CV.pdf', jdTitle: 'Backend Developer', createdAt: '2026-11-07T09:00:00',
      skills: [{ jd_skill_id: 'sql', semantic_alignment: 'MISSING' }, { jd_skill_id: 'java', semantic_alignment: 'MATCH' }],
      analysis: {}, attempts: phase ? [{ id: 's1', number: 1, status: 'Stopped early',
        startedAt: '2026-11-07T10:00:00', answeredCount: 1 }, { id: 's0', number: phase + 1, status: 'Completed',
        startedAt: '2026-11-07T11:00:00', answeredCount: 0 }] : [] });
  });
  const text = value => page.waitForFunction(value => document.body.innerText.includes(value), {}, value);
  const coverage = value => page.waitForFunction(value => document.querySelector('[role="meter"]')?.getAttribute('aria-valuenow') === String(value), {}, value);
  const click = async label => {
    await page.waitForFunction(label => [...document.querySelectorAll('#competency button,#competency summary')].some(e => e.textContent.trim() === label && !e.disabled), {}, label);
    await page.evaluate(label => [...document.querySelectorAll('#competency button,#competency summary')].find(e => e.textContent.trim() === label && !e.disabled).click(), label);
  };
  await page.goto(`${base}/applications/${id}`, { waitUntil: 'networkidle0' });
  await text('Bắt đầu lượt đầu'); await coverage(0);
  phase = 1; await click('Cập nhật'); await text('Dưới yêu cầu'); await coverage(1);
  await page.$eval('[data-skill="sql"] > summary', e => e.click());
  await text('Mục tiêu'); await text('Chẩn đoán hiệu năng truy vấn SQL'); await text('Tiêu chí đánh giá');
  await text('Cần đạt'); await text('Bổ sung'); await text('Đạt khi'); await text('Chỉ ra thao tác chiếm nhiều thời gian nhất.');
  assert.ok(await page.$(`#competency a[href="/practice/${id}"]`));
  await click('Xem bằng chứng (1)'); await text('Tôi chưa biết cách đọc kế hoạch thực thi.');
  await page.evaluate(() => [...document.querySelectorAll('[role="dialog"] button')].find(e => e.textContent.trim() === 'Đóng bằng chứng').click());
  phase = 2; await click('Cập nhật'); await text('Cần kiểm chứng lại'); await text('hai lượt xác nhận');
  phase = 3; await click('Cập nhật'); await text('Đáp ứng yêu cầu');
  assert.equal(await page.$$eval('#competency a[href="/interview/session/s3/result"]', elements => elements.length > 0), true);
  assert.equal(await page.$eval('[data-skill="java"] > summary', e => e.textContent.includes('Chưa có dữ liệu')), true);
  await click('Xem bằng chứng (3)');
  await page.waitForSelector('[role="dialog"] strong');
  await page.evaluate(() => [...document.querySelectorAll('[role="dialog"] button')].find(e => e.textContent.trim() === 'Đóng bằng chứng').click());
  await page.screenshot({ path: '.next/competency-desktop.png', fullPage: true });
  failNext = true; await click('Cập nhật'); await text('Không thể tải đánh giá thử nghiệm.');
  await click('Thử lại'); await text('Đáp ứng yêu cầu');
  await page.reload({ waitUntil: 'networkidle0' }); await text('Đáp ứng yêu cầu');
  assert.equal(await page.$$eval('main button', elements => elements.filter(e => e.textContent.trim() === 'Phỏng vấn lượt mới').length), 1);
  phase = 4; await click('Cập nhật'); await text('Chưa đủ bằng chứng'); await coverage(1);
  assert.equal(await page.$$eval('[data-skill]', elements => elements.map(e => e.dataset.skill).join()), 'sql');
  await page.$eval('[data-skill="sql"] > summary', e => e.click());
  await text('Xem kết quả lượt 4');
  await page.type('[aria-label="Tìm kỹ năng"]', 'java');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.map(e => e.dataset.skill).join()), 'java');
  await page.setViewport({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: '.next/competency-mobile.png', fullPage: true });
  await page.click('#competency a[href="#history"]');
  await text('Kết thúc trước khi trả lời'); await text('Xem chi tiết lượt');
  assert.equal(new URL(page.url()).hash, '#history');
  assert.deepEqual(errors, []);
  console.log('PASS: coverage, objective and criteria, follow-up actions, conflict and evidence details, search, retry, mobile and history.');
} finally { await browser.close(); }
