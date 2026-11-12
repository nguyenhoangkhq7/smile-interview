// Check candidate wording and the HR boundary using fixture responses only.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const errors = [];
const skills = ['MATCH', 'PARTIAL', 'MISSING'].map((alignment, index) => ({
  jd_skill_id: ['postgresql', 'spring_boot', 'docker'][index], semantic_alignment: alignment,
  matched_cv_skill_id: index === 1 ? 'java' : null, is_substituted: index === 1,
  cv_evidence_spans: index < 2 ? ['Tối ưu SQL trong dự án bán hàng.'] : [],
  context_job: 'Xây dựng dịch vụ quản lý đơn hàng', required_proficiency: 4,
  candidate_proficiency: 3, gap_magnitude: 0.2, priority: 0.8,
  suggested_strategy: 'PROBE_DEPTH',
}));
const audit = { matching_score: 0.7654, degraded: false, items: [],
  markdown_summary: 'INTERNAL_AUDIT PROBE_DEPTH P_JD P_CV Priority' };
let degraded = false;
let empty = false;
let many = false;
let vietnamese = false;
const vietnameseSkills = [
  { ...skills[0], jd_skill_id: 'ph-t-tri-n-ai-coding-agent', jd_skill_name: 'Phát triển AI Coding Agent' },
  { ...skills[1], jd_skill_id: 'th-tr-ng-ch-ng-kho-n', jd_evidence_spans: ['Có kiến thức Thị trường chứng khoán.'] },
  { ...skills[2], jd_skill_id: 'khoa-h-c-m-y-t-nh', jd_evidence_spans: ['Tốt nghiệp ngành Khoa học máy tính.'] },
];
const manySkills = [...skills, ...Array.from({ length: 25 }, (_, index) => ({ ...skills[index % 3],
  jd_skill_id: `extra_skill_${index}`, context_job: 'Xây dựng dịch vụ quản lý đơn hàng. '.repeat(60),
  cv_evidence_spans: Array.from({ length: 20 }, () => 'Kinh nghiệm thực tế trong dự án bán hàng.'),
}))];
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = (body, status = 200) => request.respond({ status,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': base,
        'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (url.pathname.endsWith('/interview')) return send({}, 404);
    if (url.pathname === '/api/auth/me') return send({ username: 'Test', role: 'USER' });
    if (url.pathname === '/api/v1/resumes' || url.pathname === '/api/v1/job-descriptions') return send([]);
    if (url.pathname === '/api/v1/sessions/user') return send([]);
    if (url.pathname.startsWith('/api/v1/application-profiles/')) return send({ id: 'candidate',
      title: 'Backend Developer', roleTitle: 'Backend Developer', cvFilename: 'CV.pdf', jdTitle: 'Backend JD',
      createdAt: new Date().toISOString(), skills: empty ? [] : vietnamese ? vietnameseSkills : many ? manySkills : skills, analysis: { ...audit, degraded }, attempts: [] });
    return send({ id: 'candidate', roleTitle: 'Backend Developer', status: 'Completed',
      skillGapJson: JSON.stringify(skills), gapReportJson: JSON.stringify(audit),
      interviewReportJson: url.pathname.endsWith('/legacy') ? JSON.stringify({ completion_rate: 0.5,
        total_turns: 1, verified_primary_skills: 1, total_initial_primary_skills: 2,
        markdown_summary: audit.markdown_summary, evaluated_skills: [{ jd_skill_id: 'spring_boot',
          is_verified: true, consolidated_finding: 'Đã giải thích cách quản lý giao dịch.' }] }) : null,
      turns: url.pathname.endsWith('/legacy') ? [{ id: 'turn', question: 'Giải thích giao dịch.', answer: 'Dùng transaction.',
        strengths: 'Đã mô tả giao dịch.', suggestedAnswer: 'INTERNAL_REASONING', score: 4 }] : [] });
  });
  const visit = path => page.goto(`${base}${path}`, { waitUntil: 'networkidle0' });
  const summary = '[aria-label="Kết quả đối chiếu CV và mô tả công việc"]';
  const check = async () => {
    await page.waitForSelector(summary);
    const text = await page.$eval(summary, element => element.innerText);
    assert.match(text, /77%/);
    assert.match(text, /CV chưa thể hiện/);
    assert.match(text, /chưa phải kết quả đánh giá qua phỏng vấn/);
    assert.doesNotMatch(await page.$eval('body', element => element.innerText), /INTERNAL_AUDIT|PROBE_DEPTH|P_JD|P_CV|Priority|GNN|Mã phiên phân tích|Độ khớp năng lực/);
    assert.equal(await page.$eval(`${summary} [data-cv-skill]`, element => element.dataset.cvSkill), 'docker');
    await page.click(`${summary} [data-cv-skill="spring_boot"]`);
    await page.waitForSelector('[role="dialog"]');
    assert.match(await page.$eval('[role="dialog"]', element => element.innerText), /Tối ưu SQL/);
    await page.keyboard.press('Escape');
    await page.waitForSelector('[role="dialog"]', { hidden: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  };
  await page.setViewport({ width: 1365, height: 1000 });
  await visit('/interview/new?sessionId=candidate');
  await check();
  await page.screenshot({ path: '.next/candidate-analysis-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  await check();
  await page.screenshot({ path: '.next/candidate-analysis-mobile.png', fullPage: true });
  await visit('/applications/candidate#documents');
  await check();
  many = true;
  await page.setViewport({ width: 1365, height: 1000 });
  await page.reload({ waitUntil: 'networkidle0' });
  assert.equal(await page.$$eval(`${summary} [data-cv-skill]`, elements => elements.length), 5);
  const height = () => page.$eval(summary, element => element.getBoundingClientRect().height);
  assert.ok(await height() < 650, 'Many skills must keep the desktop summary compact');
  const reached = new Set();
  for (;;) {
    for (const id of await page.$$eval(`${summary} [data-cv-skill]`, elements => elements.map(element => element.dataset.cvSkill))) reached.add(id);
    if (await page.$eval('[aria-label="Trang kỹ năng tiếp"]', element => element.disabled)) break;
    await page.click('[aria-label="Trang kỹ năng tiếp"]');
  }
  assert.equal(reached.size, manySkills.length, 'All skills remain reachable through pagination');
  await page.click('[aria-label="Lọc đối chiếu kỹ năng"] button:nth-child(2)');
  assert.equal(await page.$eval('[aria-label="Trang kỹ năng trước"]', element => element.disabled), true, 'Changing filters resets the page');
  assert.ok((await page.$$eval('[data-cv-skill]', elements => elements.map(element => element.dataset.cvSkill)))
    .every(id => manySkills.find(skill => skill.jd_skill_id === id).semantic_alignment === 'MISSING'));
  await page.click('[aria-label="Lọc đối chiếu kỹ năng"] button:first-child');
  await page.type('[aria-label="Tìm kỹ năng trong CV và JD"]', 'extra skill 24');
  assert.equal(await page.$$eval('[data-cv-skill]', elements => elements.length), 1);
  await page.focus('[data-cv-skill="extra_skill_24"]');
  await page.keyboard.press('Enter');
  await page.waitForSelector('[role="dialog"]');
  assert.ok(await page.$eval('[role="dialog"] .overflow-y-auto', element => element.scrollHeight > element.clientHeight), 'Long evidence scrolls inside the detail dialog');
  await page.keyboard.press('Escape');
  await page.waitForSelector('[role="dialog"]', { hidden: true });
  await page.$eval('[aria-label="Tìm kỹ năng trong CV và JD"]', element => { element.focus(); element.select(); });
  await page.keyboard.press('Backspace');
  await page.screenshot({ path: '.next/candidate-compact-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  assert.ok(await height() < 800, 'Many skills must keep the mobile summary compact');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: '.next/candidate-compact-mobile.png', fullPage: true });
  many = false;
  degraded = true;
  await page.reload({ waitUntil: 'networkidle0' });
  assert.match(await page.$eval(summary, element => element.innerText), /Một phần phân tích chưa đầy đủ/);
  empty = true;
  await page.reload({ waitUntil: 'networkidle0' });
  assert.match(await page.$eval(summary, element => element.innerText), /Chưa có kết quả đối chiếu kỹ năng/);
  empty = false;
  degraded = false;
  vietnamese = true;
  await page.reload({ waitUntil: 'networkidle0' });
  for (const [id, name] of [
    ['ph-t-tri-n-ai-coding-agent', 'Phát triển AI Coding Agent'],
    ['th-tr-ng-ch-ng-kho-n', 'Thị trường chứng khoán'],
    ['khoa-h-c-m-y-t-nh', 'Khoa học máy tính'],
  ]) assert.ok(await page.$eval(`[data-cv-skill="${id}"]`, element => element.innerText).then(text => text.includes(name)));
  await page.type('[aria-label="Tìm kỹ năng trong CV và JD"]', 'thi truong chung khoan');
  assert.equal(await page.$$eval('[data-cv-skill]', elements => elements.length), 1);
  await page.click('[data-cv-skill="th-tr-ng-ch-ng-kho-n"]');
  await page.waitForSelector('[role="dialog"]');
  assert.match(await page.$eval('[role="dialog"]', element => element.innerText), /Thị trường chứng khoán/);
  await page.keyboard.press('Escape');
  await visit('/interview/session/legacy/result');
  await page.waitForSelector('table');
  assert.match(await page.$eval('table', element => element.innerText), /Spring Boot/);
  const legacy = await page.$eval('body', element => element.innerText);
  assert.doesNotMatch(legacy, /INTERNAL_AUDIT|INTERNAL_REASONING|Judge|Abductive|Suy luận khởi tạo|Gap/);
  assert.equal(await page.$$eval('table th', elements => elements.length), 3);
  await visit('/hr-dashboard/candidate');
  await page.waitForFunction(() => location.pathname === '/');
  assert.equal(await page.$('::-p-text(INTERNAL_AUDIT)'), null);
  assert.deepEqual(errors, []);
  console.log('PASS: compact 28-skill layout, pagination, filters, search, keyboard detail dialog, mobile, candidate fields and empty/degraded states.');
} finally { await browser.close(); }
