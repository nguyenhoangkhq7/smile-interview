// UI verification with realistic quantities, long text and controlled API responses.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const statuses = ['NEEDS_VERIFICATION', 'DEMONSTRATED_BELOW_TARGET', 'DEMONSTRATED_BELOW_TARGET',
  'INSUFFICIENT_EVIDENCE', 'PARTIALLY_ASSESSED', 'NOT_ASSESSED', 'NOT_ASSESSED',
  'INSUFFICIENT_EVIDENCE', ...Array(4).fill('DEMONSTRATED_AT_TARGET')];
const names = ['ai_tools_usage', 'java', 'docker', 'react', 'aws', 'html_css', 'git', 'typescript', 'javascript', 'python', 'postgresql', 'spring_boot'];
const aiSkill = '[data-skill="ai_tools_usage"]';
const typeScriptSkill = '[data-skill="typescript"]';
const source = { sessionId: 'session-11', attemptNumber: 11, assessedAt: '2026-11-07T10:30:00' };
const checked = { ...source, sessionId: 'session-12', attemptNumber: 12 };
const evidence = { source, turnId: 'ai-turn', question: 'Đoạn mã do AI gợi ý có thể chạy sai với đầu vào nào?',
  responseExcerpt: 'Với mảng rỗng, đoạn mã chia tổng cho 0.', rationale: 'Chỉ ra được lỗi và đầu vào làm lỗi xảy ra.', performance: 'AT_TARGET' };
const earlierEvidence = { ...evidence, source: { ...source, sessionId: 'session-10', attemptNumber: 10 },
  turnId: 'earlier-ai-turn', responseExcerpt: 'Tôi nghĩ chỉ cần chạy thử vài đầu vào thông thường.',
  rationale: 'Chưa chỉ ra được lỗi cụ thể.', performance: 'BELOW' };
const aiObjectives = [{
  id: 'ai-review', claim: 'Đánh giá kiến thức thực hành ai_tools_usage', assessment: 'NEEDS_VERIFICATION',
  lastChecked: checked, lastAssessment: source,
  criteria: [{
    id: 'ai-edge-case', description: 'Phát hiện lỗi logic hoặc trường hợp biên bị bỏ sót trong đoạn mã do AI gợi ý',
    atTarget: 'Chỉ ra đoạn logic sai và một đầu vào cụ thể làm chương trình chạy sai.',
    essential: true, assessment: 'NEEDS_VERIFICATION', lastAssessment: source, evidence: [earlierEvidence, evidence],
  }, {
    id: 'ai-explain', description: 'Giải thích chức năng của đoạn mã do AI gợi ý',
    essential: true, assessment: 'DEMONSTRATED_AT_TARGET', lastAssessment: source, evidence: [],
  }, {
    id: 'ai-test', description: 'Viết kiểm thử để phát hiện lỗi trước khi dùng đoạn mã',
    essential: true, assessment: 'DEMONSTRATED_BELOW_TARGET', lastAssessment: earlierEvidence.source, evidence: [],
  }, {
    id: 'ai-improve', description: 'So sánh hai cách sửa lỗi và nêu điểm đánh đổi',
    essential: false, assessment: 'NOT_ASSESSED', lastAssessment: null, evidence: [],
  }],
}, {
  id: 'ai-privacy', claim: 'Bảo vệ dữ liệu nhạy cảm khi sử dụng công cụ AI', assessment: 'NOT_ASSESSED',
  lastChecked: null, lastAssessment: null, criteria: [{
    id: 'ai-redact', description: 'Loại bỏ thông tin nhạy cảm trước khi gửi nội dung cho công cụ AI',
    essential: true, assessment: 'NOT_ASSESSED', lastAssessment: null, evidence: [],
  }],
}];
const typeScriptObjective = {
  id: 'typescript-api-types', claim: 'Đánh giá kiến thức thực hành typescript', assessment: 'INSUFFICIENT_EVIDENCE',
  lastChecked: checked, lastAssessment: null,
  explanation: 'Đã kiểm tra nhưng chưa đủ bằng chứng để kết luận.',
  criteria: [{
    id: 'typescript-api-interface', description: 'Xây dựng interface và type cho đối tượng dữ liệu API',
    atTarget: 'Khai báo các thuộc tính và kiểu dữ liệu phù hợp với phản hồi API.',
    essential: true, assessment: 'NOT_ASSESSED', lastAssessment: null, evidence: [],
  }],
};
const competency = {
  completedAttempts: 11, incompatibleAssessments: 240,
  skills: names.map((skillId, index) => ({ skillId, assessment: statuses[index], baselineAlignment: 'PARTIAL',
    objectives: index === 0 ? aiObjectives : skillId === 'typescript' ? [typeScriptObjective] : [{ id: `${skillId}-objective`, claim: `Thực hiện công việc với ${skillId}`,
      assessment: statuses[index], lastChecked: source, lastAssessment: source,
      explanation: 'Kết luận áp dụng cho nội dung đã được kiểm tra.',
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
  assert.equal(await page.$$eval('article:has(a[href^="/applications/"])', elements => elements.length), 1);
  assert.ok(await page.$('article a[href="/applications/frontend"]'));
  await page.type('[aria-label="Tìm hồ sơ ứng tuyển"]', ' impossible'); await text('Không tìm thấy hồ sơ phù hợp');
  await click('Xóa bộ lọc'); await click('Đang phỏng vấn'); await text('1 hồ sơ');
  await click('Tất cả');
  await page.setViewport({ width: 390, height: 844 }); await noOverflow();
  await page.screenshot({ path: '.next/applications-list-mobile.png', fullPage: true });

  await page.setViewport({ width: 1440, height: 1050 }); await visit('/applications/design');
  await text('Năng lực hiện tại theo JD'); await page.waitForSelector('[data-skill]');
  assert.doesNotMatch(await page.$eval('body', element => element.innerText), /đánh giá có bộ tiêu chí khác/);
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 1);
  assert.equal(await page.$eval(`${aiSkill} > summary`, element => element.textContent.includes('Cần kiểm chứng lại')), true);
  assert.equal(await page.$$eval('[role="tabpanel"]', elements => elements.filter(e => !e.hidden && getComputedStyle(e).display !== 'none').length), 1);
  await page.screenshot({ path: '.next/application-overview-desktop.png', fullPage: true });
  await click('Dưới yêu cầu 2');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 2);
  await click('Tất cả'); await click('Xem thêm kỹ năng (6)');
  assert.equal(await page.$$eval('[data-skill]', elements => elements.length), 12);
  await page.$eval(`${aiSkill} > summary`, e => e.click());
  await text('Mục tiêu đánh giá');
  await text('Tiêu chí phỏng vấn');
  assert.equal(await page.$eval(aiSkill, e => e.innerText.includes('ai_tools_usage')), false);
  assert.equal(await page.$eval(aiSkill, e => e.innerText.includes('Để đạt yêu cầu')), false);
  assert.equal(await page.$eval(aiSkill, e => e.innerText.includes('Kết quả từ các câu trả lời chưa nhất quán.')), false);
  assert.deepEqual(await page.$$eval(`${aiSkill} article [role="heading"]`, elements => elements.map(e => e.textContent.trim())), [
    'Thực hành · Sử dụng công cụ AI',
    'Bảo vệ dữ liệu nhạy cảm khi sử dụng công cụ AI',
  ]);
  const criteria = await page.$$eval(`${aiSkill} article ul > li`, elements => elements.map(e => e.innerText));
  assert.equal(criteria.length, 4);
  assert.match(criteria[0], /Phát hiện lỗi logic[\s\S]+Cần kiểm chứng lại/);
  assert.match(criteria[1], /Giải thích chức năng[\s\S]+Đạt yêu cầu/);
  assert.match(criteria[2], /Viết kiểm thử[\s\S]+Chưa đạt/);
  assert.match(criteria[3], /So sánh hai cách sửa lỗi[\s\S]+Chưa đánh giá/);
  const firstObjectiveToggle = `${aiSkill} article:first-child > header button`;
  const secondObjectiveToggle = `${aiSkill} article:last-child > header button`;
  await page.click(secondObjectiveToggle);
  assert.match(await page.$eval(`${aiSkill} article ul > li`, e => e.innerText), /Loại bỏ thông tin nhạy cảm[\s\S]+Chưa đánh giá/);
  assert.equal(await page.$eval(firstObjectiveToggle, e => e.getAttribute('aria-expanded')), 'false');
  await page.focus(firstObjectiveToggle); await page.keyboard.press('Enter');
  await page.waitForSelector(`${aiSkill} article details > summary`, { visible: true });
  await (await page.$(aiSkill)).screenshot({ path: '.next/application-skill-desktop.png' });
  await page.click(`${aiSkill} article details > summary`);
  await text('Kết quả từ các câu trả lời chưa nhất quán.');
  assert.ok(await page.$(`${aiSkill} a[href="/interview/session/session-12/result"]`));
  assert.equal(await page.$eval(`${aiSkill} a[href="/interview/session/session-11/result"]`, e => e.textContent.trim()), 'Xem căn cứ đánh giá ở lượt 11');
  const criterionButton = `${aiSkill} ul button[aria-haspopup="dialog"]`;
  await page.focus(criterionButton); await page.keyboard.press('Enter');
  await text('Chi tiết tiêu chí'); await text('Để đạt yêu cầu'); await text('Câu trả lời và nhận xét (2)');
  assert.equal(await page.$$eval('[role="dialog"] a[href="/interview/session/session-11/result"]', elements => elements.length), 1);
  await text('Nhận xét về câu trả lời');
  assert.deepEqual(await page.$$eval('[role="dialog"] article span', elements => elements.map(e => e.textContent.trim())), ['Đạt yêu cầu', 'Chưa đạt']);
  await page.keyboard.press('Escape'); await page.waitForSelector('[role="dialog"]', { hidden: true });
  await page.waitForFunction(selector => document.activeElement === document.querySelector(selector), {}, criterionButton);
  await page.click(`${typeScriptSkill} > summary`);
  const typeScriptOverview = await page.$eval(`${typeScriptSkill} > summary`, e => e.innerText);
  assert.match(typeScriptOverview, /TypeScript[\s\S]+Kết quả kỹ năng · Chưa đủ bằng chứng/);
  const typeScriptCriterion = await page.$eval(`${typeScriptSkill} article ul > li`, e => e.innerText);
  assert.equal(await page.$eval(`${typeScriptSkill} article [role="heading"]`, e => e.innerText), typeScriptObjective.criteria[0].description);
  assert.match(typeScriptCriterion, /Khai báo các thuộc tính và kiểu dữ liệu phù hợp với phản hồi API\.[\s\S]+Chưa đánh giá/);
  assert.equal(await page.$(`${typeScriptSkill} button[aria-haspopup="dialog"]`), null);
  await (await page.$(typeScriptSkill)).screenshot({ path: '.next/application-typescript-skill-desktop.png' });
  await page.focus('[role="tab"][aria-selected="true"]'); await page.keyboard.press('ArrowRight');
  assert.equal(await page.evaluate(() => document.activeElement?.textContent.includes('Lịch sử phỏng vấn')), true);
  await page.keyboard.press('Enter');
  await text('Các lượt phỏng vấn');
  assert.equal(new URL(page.url()).hash, '#history');
  await page.reload({ waitUntil: 'networkidle0' }); await text('Các lượt phỏng vấn');
  await page.screenshot({ path: '.next/application-history-desktop.png', fullPage: true });
  await tab('CV & JD'); await text('Tài liệu đã dùng');
  await text('Kết quả đối chiếu CV và JD');
  await page.waitForSelector('[data-cv-skill]');
  await page.screenshot({ path: '.next/application-documents-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 }); await noOverflow();
  await tab('Năng lực hiện tại'); await text('Năng lực hiện tại theo JD'); await page.waitForSelector('[data-skill]');
  assert.equal(await page.$$eval('[role="tab"]', elements => elements.every(e => {
    const rect = e.getBoundingClientRect(); return rect.left >= 0 && rect.right <= innerWidth;
  })), true, 'All profile tabs must be visible on mobile');
  await noOverflow(); await page.screenshot({ path: '.next/application-overview-mobile.png', fullPage: true });
  await page.$eval(`${aiSkill} > summary`, e => e.click());
  await text('Phát hiện lỗi logic'); await noOverflow();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  const mobileSkillBounds = await (await page.$(aiSkill)).boundingBox();
  await page.screenshot({ path: '.next/application-skill-mobile.png', clip: mobileSkillBounds, captureBeyondViewport: true });
  await visit('/applications/long#documents'); await text('Tài liệu đã dùng'); await noOverflow();
  assert.deepEqual(errors, []);
  console.log('PASS: profile search/filters, long names, focused overview, pagination, evidence dialog, persistent tabs, CV & JD and mobile layouts.');
} finally { await browser.close(); }
