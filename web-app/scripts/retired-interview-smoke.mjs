// Archived interviews must never invoke the removed execution engine.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3000';
const id = 'retired-interview-smoke';
const writes = [];
const errors = [];
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = (status, body) => request.respond({ status,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': base,
        'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send(200, {});
    if (request.method() !== 'GET') writes.push(url.pathname);
    if (url.pathname === `/api/v1/sessions/${id}`) return send(200, {
      id, status: 'In progress', roleTitle: 'Backend', aiInterviewSessionId: 'archived-engine-session', turns: [],
    });
    return send(404, {});
  });
  await page.goto(`${base}/interview/session/${id}`, { waitUntil: 'networkidle0' });
  await page.waitForFunction(() => document.body.innerText.includes('Phiên phỏng vấn cũ'));
  assert.equal(await page.$('textarea'), null);
  assert.ok(await page.$(`a[href="/interview/session/${id}/result"]`));
  assert.ok(await page.$('a[href="/interview/new"]'));
  assert.deepEqual(writes, []);
  assert.deepEqual(errors, []);
  console.log('PASS: archived interview is read-only, links to saved results/new interview, no execution requests.');
} finally {
  await browser.close();
}
