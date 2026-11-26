// Exercise the real service worker without contacting a browser vendor's push service.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { once } from 'node:events';
import puppeteer from 'puppeteer';

const script = await readFile(new URL('../public/analysis-push.js', import.meta.url));
const server = createServer((req, res) => {
  if (req.url === '/analysis-push.js') {
    res.setHeader('Content-Type', 'text/javascript');
    return res.end(script);
  }
  res.setHeader('Content-Type', 'text/html');
  res.end('<title>Smile push test</title>');
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const origin = 'http://127.0.0.1:' + server.address().port;
let browser;
try {
  browser = await puppeteer.launch({ headless: true });
  await browser.defaultBrowserContext().overridePermissions(origin, ['notifications']);
  const page = await browser.newPage();
  await page.goto(origin);
  const inspection = await browser.newPage();
  const cdp = await inspection.createCDPSession();
  const registration = new Promise(resolve => cdp.on('ServiceWorker.workerRegistrationUpdated', ({ registrations }) => {
    const entry = registrations.find(r => r.scopeURL === origin + '/' && !r.isDeleted);
    if (entry) resolve(entry.registrationId);
  }));
  await cdp.send('ServiceWorker.enable');
  await page.evaluate(async () => {
    await navigator.serviceWorker.register('/analysis-push.js');
    await navigator.serviceWorker.ready;
  });
  const id = await Promise.race([registration, new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Missing worker registration')), 8000).unref())]);
  await page.close();
  assert.ok(!(await browser.pages()).some(tab => tab.url().startsWith(origin)));
  await cdp.send('ServiceWorker.deliverPushMessage', {
    origin, registrationId: id, data: JSON.stringify({ sessionId: 'demo', jobId: 'test-job' }),
  });
  const target = await browser.waitForTarget(t => t.type() === 'service_worker' && t.url().startsWith(origin));
  const worker = await target.worker();
  let seen;
  for (let i = 0; i < 60 && !seen; i++) {
    seen = await worker.evaluate(async () => {
      const [entry] = await self.registration.getNotifications({ tag: 'analysis-test-job' });
      return entry && { title: entry.title, path: entry.data.path };
    });
    if (!seen) await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.deepEqual(seen, { title: 'Phân tích CV/JD đã hoàn tất', path: '/interview/new?sessionId=demo&jobId=test-job' });
  console.log('PASS: closed-tab push event shows a notification linked to the completed job.');
} finally {
  await browser?.close();
  server.close();
}
