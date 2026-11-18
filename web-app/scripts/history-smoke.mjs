// Run against the local app: node scripts/history-smoke.mjs http://localhost:3218
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3218';
const browser = await puppeteer.launch({ headless: true });
const errors = [];
const requests = [];
let fail = false;
let empty = false;
const sessions = [
  { id: 'completed-fixture', roleTitle: 'Backend Developer', resumeFileName: 'Nguyen CV.pdf',
    applicationProfileId: 'profile-fixture', applicationProfileTitle: 'Java tại Smile', attemptNumber: 2,
    status: 'Completed', overallScore: 85, startedAt: new Date().toISOString(), turns: [] },
  { id: 'active-fixture', roleTitle: 'Frontend Developer', resumeFileName: 'React CV.pdf',
    status: 'In progress', startedAt: new Date().toISOString(), turns: [] },
];
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'history-user', username: 'History Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
      isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) {
      return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    }
    const headers = { 'access-control-allow-origin': base,
      'access-control-allow-headers': 'authorization,content-type',
      'access-control-allow-methods': 'GET,OPTIONS', 'content-type': 'application/json' };
    if (request.method() === 'OPTIONS') return request.respond({ status: 204, headers });
    requests.push({ path: url.pathname, auth: request.headers().authorization });
    return request.respond({ status: fail ? 500 : 200, headers,
      body: JSON.stringify(fail ? { message: 'Unavailable' } : empty ? [] : sessions) });
  });
  await page.goto(`${base}/history`, { waitUntil: 'networkidle0' });
  await page.waitForFunction(() => document.body.innerText.includes('Backend Developer'));
  assert.ok(requests.some(r => r.path === '/api/v1/sessions/user' && r.auth?.startsWith('Bearer ')));
  assert.ok(!requests.some(r => r.path === '/api/v1/sessions'));
  assert.equal(await page.$eval('nav a[href="/history"]', el => el.textContent), 'Lịch sử phỏng vấn');
  assert.ok(await page.$('a[href="/interview/session/completed-fixture/result"]'));
  assert.ok(await page.$('a[href="/interview/session/active-fixture"]'));
  await page.type('input[type="text"]', 'Nguyen');
  await page.waitForFunction(() => document.body.innerText.includes('Tổng cộng: 1'));
  assert.ok(await page.$('a[href="/interview/session/completed-fixture/result"]'));
  assert.equal(await page.$('a[href="/interview/session/active-fixture"]'), null);

  fail = true;
  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForSelector('[role="alert"] button');
  assert.ok((await page.$eval('[role="alert"]', el => el.textContent)).includes('Không thể tải lịch sử'));
  assert.ok(!(await page.$eval('body', el => el.textContent)).includes('Không có phiên phỏng vấn nào'));
  fail = false;
  await page.click('[role="alert"] button');
  await page.waitForFunction(() => document.body.innerText.includes('Backend Developer'));
  assert.equal(await page.$('[role="alert"]'), null);

  empty = true;
  await page.reload({ waitUntil: 'networkidle0' });
  await page.waitForFunction(() => document.body.innerText.includes('Không có phiên phỏng vấn nào'));
  assert.equal(await page.$('[role="alert"]'), null);
  for (const width of [390, 1024, 1365]) {
    await page.setViewport({ width, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Overflow at ${width}px`);
  }
  assert.deepEqual(errors, []);
  console.log('PASS: authenticated history, result/continue links, CV search, API error/retry, empty state, responsive layout.');
} finally {
  await browser.close();
}
