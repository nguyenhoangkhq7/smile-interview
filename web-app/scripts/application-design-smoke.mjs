// UI verification with realistic quantities, long text and controlled API responses.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const statuses = ['NEEDS_VERIFICATION', 'DEMONSTRATED_BELOW_TARGET', 'DEMONSTRATED_BELOW_TARGET',
  'INSUFFICIENT_EVIDENCE', 'PARTIALLY_ASSESSED', 'NOT_ASSESSED', 'NOT_ASSESSED',
  ...Array(5).fill('DEMONSTRATED_AT_TARGET')];
const names = ['sql', 'java', 'docker', 'react', 'aws', 'html_css', 'git', 'typescript', 'javascript', 'python', 'postgresql', 'spring_boot'];
const source = { sessionId: 'session-11', attemptNumber: 11, assessedAt: '2026-11-07T10:30:00' };
const evidence = { source, turnId: 'sql-turn', question: '## Truy vấn chậm\n\nBạn kiểm tra **execution plan** như thế nào?',
  responseExcerpt: 'Tôi dùng EXPLAIN ANALYZE để kiểm tra actual rows.', rationale: '**Bằng chứng:** Có cách kiểm chứng rõ ràng.', performance: 'AT_TARGET', context: 'query-a' };
const competency = {
  policyVersion: 'competency-1', completedAttempts: 11, incompatibleAssessments: 0, lastAssessment: source,
  summary: { totalSkills: 12, meetingTarget: 5, belowTarget: 2, needsVerification: 1, incomplete: 2, notAssessed: 2 },
  skills: names.map((skillId, index) => ({ skillId, assessment: statuses[index], baselineAlignment: 'PARTIAL',
    evidencedCriteria: index < 5 || index > 6 ? 2 : 0, totalCriteria: 3, lastChecked: source,
    objectives: [{ id: `${skillId}-objective`, claim: skillId === 'sql' ? 'Chẩn đoán và tối ưu hiệu năng truy vấn SQL' : `Thực hiện công việc với ${skillId}`,
      assessment: statuses[index], lastChecked: source, lastAssessment: source,
      explanation: index === 0 ? 'Có bằng chứng mâu thuẫn. Cần kiểm chứng lại với bối cảnh độc lập.' : 'Kết luận áp dụng cho nội dung đã được kiểm tra.',
      criteria: [{ id: `${skillId}-criterion`, description: 'Giải thích nguyên nhân và đề xuất cách kiểm chứng bằng dữ liệu thực tế.',
        essential: true, assessment: statuses[index], lastAssessment: source, evidence: [evidence] }] }] })),
};
const profile = {
  id: 'design', title: 'Backend Developer · Công ty A', company: 'Công ty A', roleTitle: 'Backend Developer',
  cvFilename: 'Nguyen_Hoang_Khang_Backend_Developer_CV_2026.pdf', jdTitle: 'Backend Developer — Java / Spring Boot', createdAt: '2026-11-01T09:00:00',
  skills: names.map((jd_skill_id, index) => ({ jd_skill_id, semantic_alignment: index < 4 ? 'MATCH' : index < 8 ? 'PARTIAL' : 'MISSING' })),
  analysis: { markdown_summary: '# Báo cáo CV–JD\n\n**Kết luận ban đầu:** cần kiểm chứng thêm qua phỏng vấn.\n\n| Kỹ năng | Trọng số |\n| --- | --- |\n| SQL | $w_j = 0.8$ |' },
  attempts: Array.from({ length: 12 }, (_, index) => ({ id: `session-${12 - index}`, number: 12 - index,
    status: index === 0 ? 'In progress' : index === 4 ? 'Stopped early' : index === 7 ? 'Cancelled' : 'Completed',
    startedAt: '2026-11-07T09:00:00', endedAt: index ? '2026-11-07T09:15:00' : null,
    answeredCount: index === 7 ? 0 : 8, terminationReason: null })),
};
const profiles = [profile, { ...profile, id: 'frontend', title: 'Frontend Developer', company: 'Công ty B', attempts: [{ ...profile.attempts[0], status: 'Not started' }] },
  { ...profile, id: 'finished', title: 'Fullstack Developer', company: 'Công ty C', attempts: profile.attempts.slice(1) },
  { ...profile, id: 'long', title: 'Kỹ sư phần mềm phụ trách nền tảng dữ liệu và tích hợp hệ thống cho doanh nghiệp quốc tế', company: 'Doanh nghiệp quốc tế', cvFilename: `${'very_long_filename_'.repeat(8)}.pdf`, attempts: [] }];
const errors = [];
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1050 });
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Khang', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const body = request.method() === 'OPTIONS' ? {} : url.pathname.endsWith('/competency') ? competency
      : url.pathname === '/api/v1/application-profiles' ? profiles : profiles.find(p => url.pathname.endsWith(`/${p.id}`)) || profile;
    return request.respond({ status: 200, headers: { 'content-type': 'application/json', 'access-control-allow-origin': base,
      'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
  });
  const visit = path => page.goto(`${base}${path}`, { waitUntil: 'networkidle0' });
  const text = value => page.waitForFunction(value => document.body.innerText.includes(value), {}, value);
  const click = async value => {
    await page.waitForFunction(value => [...document.querySelectorAll('button')].some(e => e.textContent.trim() === value && !e.disabled), {}, value);
    await page.evaluate(value => [...document.querySelectorAll('button')].find(e => e.textContent.trim() === value && !e.disabled).click(), value);
  };
  const tab = label => page.evaluate(label => [...document.querySelectorAll('[role="tab"]')].find(e => e.textContent.includes(label)).click(), label);
  const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

  await visit('/applications'); await text('Fullstack Developer');
  await page.screenshot({ path: '.next/applications-list-desktop.png', fullPage: true });
  await page.type('[aria-label="Tìm hồ sơ ứng tuyển"]', 'cong ty b');
  await text('1 hồ sơ');
  assert.equal(await page.$$eval('a[href^="/applications/"]', elements => elements.length), 1);
  await page.type('[aria-label="Tìm hồ sơ ứng tuyển"]', ' impossible'); await text('Không tìm thấy hồ sơ phù hợp');
  await click('Xóa bộ lọc'); await click('Đang phỏng vấn'); await text('1 hồ sơ');
  await click('Tất cả');
  await page.setViewport({ width: 390, height: 844 }); await noOverflow();
  await page.screenshot({ path: '.next/applications-list-mobile.png', fullPage: true });

  await page.setViewport({ width: 1440, height: 1050 }); await visit('/applications/design');
  await text('Năng lực hiện tại theo JD'); await page.waitForSelector('[data-skill]');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 6);
  assert.equal(await page.$$eval('[data-skill]', elements => elements[0].dataset.skill), 'sql');
  assert.equal(await page.$$eval('[role="tabpanel"]', elements => elements.filter(e => !e.hidden && getComputedStyle(e).display !== 'none').length), 1);
  await page.screenshot({ path: '.next/application-overview-desktop.png', fullPage: true });
  await click('Cần tập trung3');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 3);
  await click('Tất cả12'); await click('Xem thêm kỹ năng (6)');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 12);
  await page.$eval('[data-skill="sql"] > summary', e => e.click());
  await page.focus('[data-skill="sql"] button'); await page.keyboard.press('Enter');
  await text('Bằng chứng đánh giá · SQL');
  assert.equal(await page.$$eval('[role="dialog"] a[href="/interview/session/session-11/result"]', elements => elements.length), 1);
  await page.keyboard.press('Escape'); await page.waitForSelector('[role="dialog"]', { hidden: true });
  await page.waitForFunction(() => document.activeElement?.textContent.includes('Xem bằng chứng (1)'));
  await page.focus('[role="tab"][aria-selected="true"]'); await page.keyboard.press('ArrowRight');
  assert.equal(await page.evaluate(() => document.activeElement?.textContent.includes('Lịch sử phỏng vấn')), true);
  await page.keyboard.press('Enter');
  await text('Các lượt phỏng vấn');
  assert.equal(new URL(page.url()).hash, '#history');
  await page.reload({ waitUntil: 'networkidle0' }); await text('Các lượt phỏng vấn');
  await page.screenshot({ path: '.next/application-history-desktop.png', fullPage: true });
  await tab('CV & JD'); await text('Tài liệu của hồ sơ');
  await page.evaluate(() => [...document.querySelectorAll('summary')].find(e => e.textContent === 'Xem bản phân tích đầy đủ').click());
  await page.waitForSelector('.katex');
  await page.screenshot({ path: '.next/application-documents-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 }); await noOverflow();
  await tab('Năng lực hiện tại'); await text('Năng lực hiện tại theo JD'); await page.waitForSelector('[data-skill]');
  assert.equal(await page.$$eval('[role="tab"]', elements => elements.every(e => {
    const rect = e.getBoundingClientRect(); return rect.left >= 0 && rect.right <= innerWidth;
  })), true, 'All profile tabs must be visible on mobile');
  await noOverflow(); await page.screenshot({ path: '.next/application-overview-mobile.png', fullPage: true });
  await visit('/applications/long#documents'); await text('Tài liệu của hồ sơ'); await noOverflow();
  assert.deepEqual(errors, []);
  console.log('PASS: profile search/filters, long names, focused overview, pagination, evidence dialog, persistent tabs, Markdown and mobile layouts.');
} finally { await browser.close(); }
