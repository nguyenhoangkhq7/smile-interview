// The internal audit table remains available in the HR workspace.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const report = readFileSync(new URL('./fixtures/skill-gap-markdown.md', import.meta.url), 'utf8');
const errors = [];
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewport({ width: 1365, height: 1000 });
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'HR' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`, isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = body => request.respond({ status: 200, headers: { 'content-type': 'application/json',
      'access-control-allow-origin': base, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (url.pathname === '/api/auth/me') return send({ username: 'Test', role: 'HR' });
    return send({ id: 'math', roleTitle: 'Frontend Developer', status: 'Completed', turns: [],
      skillGapJson: '[]', gapReportJson: JSON.stringify({ markdown_summary: report }) });
  });
  await page.goto(`${base}/hr-dashboard/math`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('table .katex');
  assert.equal(await page.$$eval('table th', elements => elements.length), 11);
  assert.equal(await page.$$eval('table tbody tr', elements => elements.length), 1);
  assert.equal(await page.$$eval('table .katex', elements => elements.length), 4);
  const formulas = await page.$$eval('table annotation', elements => elements.map(e => e.textContent));
  assert.deepEqual(formulas, ['w_j', 's_{jd}', 's_{cv}', 'c_{\\text{evidence}}']);
  assert.equal(await page.$$eval('.katex-error', elements => elements.length), 0);
  assert.equal(await page.$$eval('.katex-display', elements => elements.length), 1);
  assert.equal(await page.$eval('pre code.language-sql', e => e.textContent.trim()), "SELECT html_css, s\\_{jd}, '$w_j$' FROM report;");
  assert.equal(await page.$$eval('p code', elements => elements.some(e => e.textContent === 's\\_{jd}')), true);
  assert.equal(await page.$eval('table', e => e.parentElement.scrollWidth > e.parentElement.clientWidth), true);
  assert.equal(await page.$eval('table td:nth-child(4)', e => getComputedStyle(e).whiteSpace), 'nowrap');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: '.next/markdown-math-desktop.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  assert.equal(await page.$eval('table', e => e.parentElement.scrollWidth > e.parentElement.clientWidth), true);
  assert.equal(await page.$eval('table', e => getComputedStyle(e.querySelector('th')).whiteSpace), 'nowrap');
  await page.$eval('table', e => { e.parentElement.scrollLeft = e.parentElement.scrollWidth; });
  assert.ok(await page.$eval('table', e => e.parentElement.scrollLeft > 0));
  await page.screenshot({ path: '.next/markdown-math-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: exact 11-column report, escaped subscripts, KaTeX, display math, unchanged code and responsive table scrolling.');
} finally { await browser.close(); }
