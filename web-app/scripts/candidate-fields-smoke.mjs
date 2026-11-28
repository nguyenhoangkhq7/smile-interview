// Check candidate wording using fixture responses only.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const errors = [];
const requiredJdQuote = 'Bắt buộc xây dựng dịch vụ quản lý đơn hàng bằng Spring Boot.';
const marketJdQuote = 'Giải thích biến động giá trong báo cáo tuần cho Thị trường chứng khoán.';
const cvQuote = 'Tối ưu SQL trong dự án bán hàng.';
const skills = ['MATCH', 'PARTIAL', 'MISSING'].map((alignment, index) => ({
  jd_skill_id: ['postgresql', 'spring_boot', 'docker'][index], semantic_alignment: alignment,
  matched_cv_skill_id: index === 1 ? 'java' : null,
  cv_evidence_spans: index < 2 ? [cvQuote] : [],
  context_job: 'Xây dựng dịch vụ quản lý đơn hàng', required_proficiency: 4,
  priority: 0.8, importance_weight: 0.9,
  job_tasks: index === 1 ? [{
    task_id: 'spring-orders', description: 'Xây dựng dịch vụ quản lý đơn hàng',
    evidence_spans: [requiredJdQuote], required_level: 4, requirement_kind: 'REQUIRED', level_basis: 'INFERRED',
  }] : [],
}));
const audit = { matching_score: 0.7654, degraded: false, items: [],
  markdown_summary: 'INTERNAL_AUDIT PROBE_DEPTH P_JD P_CV Priority' };
let degraded = false;
let empty = false;
let many = false;
let vietnamese = false;
let documentRequests = 0;
let failDocuments = false;
const vietnameseSkills = [
  { ...skills[0], jd_skill_id: 'ph-t-tri-n-ai-coding-agent', jd_skill_name: 'Phát triển AI Coding Agent' },
  { ...skills[1], jd_skill_id: 'th-tr-ng-ch-ng-kho-n', job_tasks: [
    { task_id: 'market-report', description: 'Lập báo cáo định kỳ', evidence_spans: ['Ưu tiên từng lập báo cáo định kỳ.'],
      required_level: 3, requirement_kind: 'OPTIONAL', level_basis: 'INFERRED' },
    { task_id: 'market-change', description: 'Giải thích biến động thị trường trong báo cáo tuần',
      evidence_spans: ['Có kiến thức Thị trường chứng khoán.', marketJdQuote],
      required_level: 4, requirement_kind: 'REQUIRED', level_basis: 'INFERRED' },
  ] },
  { ...skills[2], jd_skill_id: 'khoa-h-c-m-y-t-nh', jd_evidence_spans: ['Tốt nghiệp ngành Khoa học máy tính.'] },
  { ...skills[2], jd_skill_id: 'unsupported_source', job_tasks: [{
    task_id: 'unrelated-quote', description: 'Thiết kế API REST', evidence_spans: ['Có khả năng làm việc nhóm.'],
    required_level: 3, requirement_kind: 'OPTIONAL', level_basis: 'INFERRED',
  }] },
  ...['react', 'git', 'python'].map(jd_skill_id => ({ ...skills[0], jd_skill_id })),
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
    if (url.pathname.endsWith('/analyze-gap')) return send({
      analysis_id: 'candidate', skills, report: { matching_score: audit.matching_score, degraded },
    });
    if (url.pathname === '/api/v1/resumes' || url.pathname === '/api/v1/job-descriptions') return send([]);
    if (url.pathname === '/api/v1/sessions/user') return send([]);
    if (url.pathname === '/api/v1/application-profiles/candidate/documents') {
      documentRequests++;
      if (failDocuments) return send({ message: 'Fixture unavailable' }, 503);
      return send({ cvFilename: 'CV.pdf', cvFileUrl: '/uploads/resumes/CV.pdf', cvText: cvQuote,
        jdTitle: 'Backend JD', jdFilename: '', jdFileUrl: null, jdText: requiredJdQuote });
    }
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
  const clickButton = label => page.locator(`::-p-aria([name="${label}"][role="button"])`).click();
  const checkAnalysis = async () => {
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
  const openEvidence = async (id, keyboard = false) => {
    const row = `${summary} [data-cv-skill="${id}"]`;
    if (keyboard) {
      await page.focus(row);
      await page.keyboard.press('Enter');
    } else {
      await page.click(row);
    }
    await page.waitForFunction(selector => document.querySelector(selector)?.closest('details')?.open, {}, row);
    return `${row} + [role="region"]`;
  };
  await page.setViewport({ width: 1365, height: 1000 });
  await visit('/interview/new?sessionId=candidate');
  await checkAnalysis();
  await page.screenshot({ path: '.next/candidate-analysis-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  await checkAnalysis();
  await page.screenshot({ path: '.next/candidate-analysis-mobile.png', fullPage: true });
  await visit('/applications/candidate#documents');
  await page.waitForSelector(`${summary} [data-cv-skill]`);
  const profileSummary = await page.$eval(summary, element => element.innerText);
  assert.doesNotMatch(profileSummary, /77%|INTERNAL_AUDIT|PROBE_DEPTH|P_JD|P_CV|Priority/);
  assert.equal(await page.$eval(`${summary} [data-cv-skill]`, element => element.dataset.cvSkill), 'spring_boot');
  assert.match(await page.$eval('[data-cv-skill="spring_boot"]', element => element.innerText), /Có yêu cầu bắt buộc/);
  assert.doesNotMatch(await page.$eval('[data-cv-skill="docker"]', element => element.innerText), /Có yêu cầu bắt buộc/);
  const springEvidence = await openEvidence('spring_boot', true);
  const springText = await page.$eval(springEvidence, element => element.innerText);
  assert.ok(springText.includes(requiredJdQuote) && springText.includes(cvQuote));
  assert.match(springText, /Gợi ý chuẩn bị/);
  assert.match(springText, /Chuẩn bị một luồng xử lý và cách kiểm tra/);
  assert.match(springText, /Theo nhiệm vụ “Xây dựng dịch vụ quản lý đơn hàng”/);
  assert.match(springText, /một tình huống cần xử lý riêng và cách bạn kiểm tra kết quả/);
  assert.equal(await page.$('[role="dialog"]'), null);
  const dockerEvidence = await openEvidence('docker');
  const dockerText = await page.$eval(dockerEvidence, element => element.innerText);
  assert.match(dockerText, /Chưa có trích dẫn từ JD/);
  assert.doesNotMatch(dockerText, /Gợi ý chuẩn bị/);
  assert.deepEqual(await page.$$eval(`${summary} details[open] > summary`, rows => rows.map(row => row.dataset.cvSkill)), ['docker']);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

  assert.equal(documentRequests, 0, 'Document text is loaded on demand');
  failDocuments = true;
  await clickButton('Xem tài liệu');
  await page.waitForFunction(() => document.body.innerText.includes('Chưa tải được tài liệu'));
  failDocuments = false;
  await clickButton('Thử lại');
  await page.waitForSelector('[aria-label="Nội dung CV"]', { visible: true });
  assert.match(await page.$eval('[aria-label="Nội dung CV"]', element => element.innerText), /Tối ưu SQL/);
  assert.match(await page.$eval('[aria-label="Nội dung Mô tả công việc"]', element => element.innerText), /Bắt buộc xây dựng/);
  assert.equal(await page.$$eval('a[aria-label^="Mở file gốc"]', elements => elements.length), 1);
  assert.ok(await page.$$eval('a[href="/interview/new"]', links => links.some(link => link.innerText.trim() === 'Tạo hồ sơ với tài liệu mới')));
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: '.next/candidate-documents-mobile.png', fullPage: true });
  const loadedRequests = documentRequests;
  await clickButton('Thu gọn tài liệu');
  await page.waitForSelector('[aria-label="Nội dung CV"]', { hidden: true });
  await clickButton('Xem tài liệu');
  await page.waitForSelector('[aria-label="Nội dung CV"]', { visible: true });
  assert.equal(documentRequests, loadedRequests, 'Reopening reuses the loaded documents');

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
  const longEvidence = await openEvidence('extra_skill_24', true);
  assert.ok(await page.$eval(longEvidence, element => element.scrollHeight > element.clientHeight), 'Long evidence scrolls inside the expanded row');
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
  assert.doesNotMatch(await page.$eval(summary, element => element.innerText), /Một phần phân tích chưa đầy đủ/);
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
  const legacyEvidence = await openEvidence('khoa-h-c-m-y-t-nh');
  const legacyText = await page.$eval(legacyEvidence, element => element.innerText);
  assert.match(legacyText, /Tốt nghiệp ngành Khoa học máy tính/);
  assert.doesNotMatch(legacyText, /Gợi ý chuẩn bị/);
  const unsupportedEvidence = await openEvidence('unsupported_source');
  const unsupportedText = await page.$eval(unsupportedEvidence, element => element.innerText);
  assert.match(unsupportedText, /Có khả năng làm việc nhóm/);
  assert.doesNotMatch(unsupportedText, /Gợi ý chuẩn bị/);
  await page.type('[aria-label="Tìm kỹ năng trong CV và JD"]', 'thi truong chung khoan');
  assert.equal(await page.$$eval('[data-cv-skill]', elements => elements.length), 1);
  const marketEvidence = await openEvidence('th-tr-ng-ch-ng-kho-n');
  const marketText = await page.$eval(marketEvidence, element => element.innerText);
  assert.match(marketText, /Thị trường chứng khoán/);
  assert.match(marketText, /Tập giải thích một biến động bằng dữ liệu/);
  assert.match(marketText, /trong khoảng một phút.*căn cứ cho nhận định và cách bạn kiểm tra lại/);
  assert.doesNotMatch(marketText, /Chuẩn bị phần tóm tắt một báo cáo/);
  assert.equal(await page.$eval(`${marketEvidence} blockquote`, element => element.textContent), `“${marketJdQuote}”`);
  await visit('/applications/candidate/documents');
  await page.waitForSelector('[aria-label="Nội dung CV đã tải lên"]', { visible: true });
  assert.match(await page.$eval('[aria-label="Nội dung JD đã tải lên hoặc nhập"]', element => element.innerText), /Bắt buộc xây dựng/);
  await visit('/interview/session/legacy/result');
  await page.waitForSelector('table');
  assert.match(await page.$eval('table', element => element.innerText), /Spring Boot/);
  const legacy = await page.$eval('body', element => element.innerText);
  assert.doesNotMatch(legacy, /INTERNAL_AUDIT|INTERNAL_REASONING|Judge|Abductive|Suy luận khởi tạo|Gap/);
  assert.equal(await page.$$eval('table th', elements => elements.length), 3);
  assert.deepEqual(errors, []);
  console.log('PASS: candidate analysis, documents and retry, source-backed task preparation, accessible pagination/search and mobile layouts.');
} finally { await browser.close(); }
