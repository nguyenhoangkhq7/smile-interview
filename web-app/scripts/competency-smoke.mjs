// Browser contract checks. Projection rules are covered by backend tests.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const id = 'competency-profile';
let phase = 0;
let failNext = false;
const errors = [];
const source = number => ({ sessionId: `s${number}`, attemptNumber: number, assessedAt: '2026-11-07T10:00:00' });
const status = ['NOT_ASSESSED', 'DEMONSTRATED_BELOW_TARGET', 'NEEDS_VERIFICATION', 'DEMONSTRATED_AT_TARGET'];
function view() {
  const evidence = Array.from({ length: phase }, (_, index) => ({ source: source(index + 1), turnId: `turn-${index + 1}`,
    question: '## Chẩn đoán truy vấn\n\nBạn sẽ kiểm tra truy vấn SQL chậm như thế nào?',
    responseExcerpt: index ? 'EXPLAIN ANALYZE để kiểm chứng kế hoạch thực thi.' : 'Tôi chưa biết cách đọc kế hoạch thực thi.',
    rationale: index ? '**Có bằng chứng:** đối chiếu estimated rows và actual rows.' : 'Chưa thể hiện cách chẩn đoán.',
    performance: index ? 'AT_TARGET' : 'BELOW', context: `query-${index}` }));
  return { policyVersion: 'competency-1', completedAttempts: phase, incompatibleAssessments: 0,
    lastAssessment: phase ? source(phase) : null,
    summary: { totalSkills: 2, meetingTarget: phase === 3 ? 1 : 0, belowTarget: phase === 1 ? 1 : 0,
      needsVerification: phase === 2 ? 1 : 0, incomplete: 0, notAssessed: phase ? 1 : 2 },
    skills: [{ skillId: 'sql', baselineAlignment: 'MISSING', assessment: status[phase], evidencedCriteria: phase ? 1 : 0,
      totalCriteria: 1, lastChecked: phase ? source(phase) : null,
      objectives: [{ id: 'sql-task', claim: 'Chẩn đoán hiệu năng truy vấn SQL', assessment: status[phase],
        lastChecked: phase ? source(phase) : null, lastAssessment: phase ? source(phase) : null,
        explanation: phase === 2 ? 'Có bằng chứng mâu thuẫn. Cần hai lượt xác nhận nhất quán về sau ở các bối cảnh độc lập để cập nhật kết luận.' : 'Đánh giá theo bằng chứng đã lưu.',
        criteria: [{ id: 'sql-c1', description: 'Đọc và giải thích `EXPLAIN ANALYZE`', essential: true,
          assessment: status[phase], lastAssessment: phase ? source(phase) : null, evidence }] }] },
    { skillId: 'java', baselineAlignment: 'MATCH', assessment: 'NOT_ASSESSED', evidencedCriteria: 0, totalCriteria: 1,
      lastChecked: null, objectives: [] }] };
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
      analysis: {}, attempts: [] });
  });
  const text = value => page.waitForFunction(value => document.body.innerText.includes(value), {}, value);
  const click = async label => {
    await page.waitForFunction(label => [...document.querySelectorAll('#competency button,#competency summary')].some(e => e.textContent.trim() === label && !e.disabled), {}, label);
    await page.evaluate(label => [...document.querySelectorAll('#competency button,#competency summary')].find(e => e.textContent.trim() === label && !e.disabled).click(), label);
  };
  await page.goto(`${base}/applications/${id}`, { waitUntil: 'networkidle0' });
  await text('Hoàn thành một lượt phỏng vấn');
  phase = 1; await click('Cập nhật'); await text('Dưới yêu cầu đã kiểm tra');
  await page.$eval('[data-skill="sql"] > summary', e => e.click());
  await click('Xem bằng chứng (1)'); await text('Tôi chưa biết cách đọc kế hoạch thực thi.');
  await page.evaluate(() => [...document.querySelectorAll('[role="dialog"] button')].find(e => e.textContent.trim() === 'Đóng bằng chứng').click());
  phase = 2; await click('Cập nhật'); await text('Cần kiểm chứng lại'); await text('hai lượt xác nhận');
  phase = 3; await click('Cập nhật'); await text('Đáp ứng yêu cầu đã kiểm tra');
  await text('Mốc CV–JD: Chưa có bằng chứng tương ứng trong CV');
  assert.equal(await page.$$eval('#competency a[href="/interview/session/s3/result"]', elements => elements.length > 0), true);
  assert.equal(await page.$eval('[data-skill="java"] > summary', e => e.textContent.includes('Chưa được kiểm tra')), true);
  await click('Xem bằng chứng (3)');
  await page.waitForSelector('[role="dialog"] strong');
  await page.evaluate(() => [...document.querySelectorAll('[role="dialog"] button')].find(e => e.textContent.trim() === 'Đóng bằng chứng').click());
  await page.screenshot({ path: '.next/competency-desktop.png', fullPage: true });
  failNext = true; await click('Cập nhật'); await text('Không thể tải đánh giá thử nghiệm.');
  await click('Thử lại'); await text('Đáp ứng yêu cầu đã kiểm tra');
  await page.reload({ waitUntil: 'networkidle0' }); await text('Đáp ứng yêu cầu đã kiểm tra');
  await page.setViewport({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: '.next/competency-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: unassessed state, updated competency, conflicts, evidence links, unchanged CV diagnosis, untouched skills, retry, reload, mobile.');
} finally { await browser.close(); }
