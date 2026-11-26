// Production UI smoke test with controlled API fixtures; no real user data is written.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const profileId = 'c4b168e3-6888-4686-855b-e9cdc4a1a524';
const errors = [];
let profile = null;
let creationPayload;
let analysisCalls = 0;
let jobReady = false;
let subscribedJob;
const states = new Map();
const skills = [{ jd_skill_id: 'postgresql', semantic_alignment: 'MATCH',
  required_proficiency: 4, priority: 0, importance_weight: 0.9,
  cv_evidence_spans: ['SQL'], job_tasks: [] }];
const analysis = { matching_score: 0.8, degraded: false };
const emptyReport = { termination_reason: null,
  objectives: [{ objective_id: 'objective', skill_id: 'postgresql', claim: 'Chẩn đoán truy vấn SQL chậm',
    jd_evidence_spans: ['SQL'], assessment: 'NOT_ASSESSED', stop_reason: null, strengths: [], weaknesses: [], evidence: [] }] };
const attempt = number => ({ id: number === 1 ? 'prepared' : `attempt-${number}`, number,
  status: 'Not started', startedAt: new Date().toISOString(), endedAt: null, answeredCount: 0, terminationReason: null });
const metadata = id => ({ id, roleTitle: 'Backend Developer', resumeFileName: 'Backend CV.pdf', jdTitle: 'Backend Developer',
  skillGapJson: JSON.stringify(skills), gapReportJson: JSON.stringify(analysis), turns: [],
  status: profile?.attempts.find(a => a.id === id)?.status || 'Not started',
  ...(profile ? { applicationProfileId: profileId, applicationProfileTitle: profile.title,
    attemptNumber: profile.attempts.find(a => a.id === id)?.number } : {}) });
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1365, height: 1000 });
  page.on('pageerror', error => errors.push(error.message));
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(Notification, 'requestPermission', { value: async () => {
      Object.defineProperty(Notification, 'permission', { configurable: true, value: 'granted' });
      return 'granted';
    } });
    PushManager.prototype.subscribe = async () => ({ toJSON: () => ({ endpoint: 'https://example.test/device' }) });
  });
  await page.evaluateOnNewDocument(() => localStorage.setItem('auth-storage', JSON.stringify({
    state: { user: { id: 'test', username: 'Test', role: 'USER' },
      token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
      isAuthenticated: true }, version: 0,
  })));
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    const send = (body, status = 200) => request.respond({ status,
      headers: { 'access-control-allow-origin': base, 'access-control-allow-headers': '*',
        'access-control-allow-methods': '*', 'content-type': 'application/json' }, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    const path = url.pathname;
    if (path === '/api/v1/analysis-push/config') return send({ publicKey: 'fixture' });
    if (path === '/api/v1/analysis-push' && request.method() === 'PUT') {
      subscribedJob = JSON.parse(request.postData()).jobId;
      return send({});
    }
    if (path.endsWith('/analyze-gap')) {
      if (url.searchParams.get('forceRefresh') !== 'true')
        return send({ analysis_id: 'prepared', skills, report: analysis });
      analysisCalls++;
      return send({ job_id: 'fixture-job', status: 'PENDING', result: null }, 202);
    }
    if (path.endsWith('/analyze-gap/fixture-job')) return send({
      job_id: 'fixture-job', status: jobReady ? 'SUCCEEDED' : 'RUNNING',
      result: jobReady ? { analysis_id: 'prepared', skills, report: analysis } : null,
    });
    if (path === '/api/v1/application-profiles' && request.method() === 'POST') {
      creationPayload = JSON.parse(request.postData());
      profile = { id: profileId, title: creationPayload.title, company: creationPayload.company,
        roleTitle: 'Backend Developer', cvFilename: 'Backend CV.pdf', jdTitle: 'Backend Developer',
        createdAt: new Date().toISOString(), skills, analysis, attempts: [attempt(1)] };
      return send(profile);
    }
    if (path === '/api/v1/application-profiles') return send(profile ? [profile] : []);
    if (path === `/api/v1/application-profiles/${profileId}`) return send(profile);
    if (path === `/api/v1/application-profiles/${profileId}/competency`) {
      const completed = profile.attempts.filter(a => a.answeredCount && !['Not started', 'In progress'].includes(a.status));
      return send({ completedAttempts: completed.length, incompatibleAssessments: 0,
        skills: [{ skillId: 'postgresql', baselineAlignment: 'MATCH', assessment: completed.length ? 'INSUFFICIENT_EVIDENCE' : 'NOT_ASSESSED',
          objectives: [] }] });
    }
    if (path.endsWith('/attempts')) {
      const fresh = profile.attempts.find(a => a.status === 'Not started') || attempt(profile.attempts.length + 1);
      if (!profile.attempts.includes(fresh)) profile.attempts.unshift(fresh);
      return send(fresh);
    }
    if (path === '/api/v1/sessions/user') return send(profile ? profile.attempts.map(a => metadata(a.id)) : [metadata('prepared')]);
    if (path.startsWith('/api/v1/sessions/')) return send(metadata(path.split('/')[4]));
    if (path === '/api/v1/resumes' || path === '/api/v1/job-descriptions') return send([]);
    const match = path.match(/^\/api\/v2\/sessions\/([^/]+)\/interview(?:\/(\w+))?$/);
    if (match) {
      const [, id, operation] = match;
      const item = profile?.attempts.find(a => a.id === id);
      let state = states.get(id);
      if (!operation) return send(state || {}, state ? 200 : 404);
      if (operation === 'start') {
        item.status = 'In progress';
        state = { schema_version: 2, session_id: id, state_version: 1, is_finished: false,
          config: JSON.parse(request.postData()), deadline_at: new Date(Date.now() + 900000).toISOString(),
          turns: [], pending_turn: { turn_id: `${id}-turn`, objective_id: 'objective', mode: 'DEBUGGING',
            question: 'Bạn sẽ chẩn đoán một truy vấn SQL chậm như thế nào?' }, report: { ...emptyReport } };
      }
      if (operation === 'respond') {
        const payload = JSON.parse(request.postData());
        state.turns.push({ turn_id: state.pending_turn.turn_id, objective_id: state.pending_turn.objective_id,
          mode: state.pending_turn.mode, question: state.pending_turn.question,
          answer: payload.candidate_response, feedback: 'Đã ghi nhận cách kiểm chứng.' });
        state.pending_turn = { ...state.pending_turn, turn_id: `${id}-followup`, question: 'Bạn sẽ kiểm chứng kết quả tối ưu như thế nào?' };
        state.state_version++; item.answeredCount++;
      }
      if (operation === 'stop') {
        state.is_finished = true; state.state_version++; state.pending_turn = null;
        state.report = { ...emptyReport, termination_reason: 'USER_STOP' };
        item.status = state.turns.length ? 'Stopped early' : 'Cancelled';
        item.endedAt = new Date().toISOString(); item.terminationReason = 'USER_STOP';
      }
      states.set(id, state); return send(state);
    }
    return send({});
  });
  const visit = path => page.goto(`${base}${path}`, { waitUntil: 'networkidle0' });
  const text = value => page.waitForFunction(value => document.body.innerText.includes(value), {}, value);
  const click = async label => {
    await page.waitForFunction(label => [...document.querySelectorAll('button,a')].some(e => e.textContent.trim() === label && !e.disabled), {}, label);
    await page.evaluate(label => [...document.querySelectorAll('button,a')].find(e => e.textContent.trim() === label && !e.disabled).click(), label);
  };
  const historyTab = () => page.evaluate(() => [...document.querySelectorAll('[role="tab"]')].find(e => e.textContent.includes('Lịch sử phỏng vấn')).click());
  await visit('/applications'); await text('Bạn đang chuẩn bị ứng tuyển ở đâu?');
  await visit('/interview/new?sessionId=prepared'); await text('Đặt tên hồ sơ ứng tuyển');
  await click('Phân tích lại');
  await text('Đã nhận hồ sơ');
  await text('Nhận thông báo khi phân tích xong?');
  await click('Bỏ qua');
  await page.reload({ waitUntil: 'networkidle0' });
  await text('Đã nhận hồ sơ');
  await text('Báo cho tôi khi phân tích xong');
  assert.equal(await page.$('[role="dialog"]'), null, 'Dismissed prompt stays hidden while the job runs');
  assert.equal(new URL(page.url()).searchParams.get('jobId'), 'fixture-job');
  await page.evaluate(() => localStorage.removeItem('analysis-push-prompt:test'));
  await page.reload({ waitUntil: 'networkidle0' });
  await text('Nhận thông báo khi phân tích xong?');
  await page.evaluate(() => { window.documentBeforeConsent = document; });
  await click('Bật thông báo');
  await text('Tắt thông báo kết quả trên thiết bị này');
  assert.equal(subscribedJob, 'fixture-job');
  assert.ok(await page.evaluate(() => window.documentBeforeConsent === document), 'Consent must keep the same page');
  assert.equal(new URL(page.url()).searchParams.get('jobId'), 'fixture-job');
  await text('Đã nhận hồ sơ');
  await visit('/interview/new');
  await text('Đã nhận hồ sơ');
  assert.equal(new URL(page.url()).searchParams.get('jobId'), 'fixture-job');
  jobReady = true;
  await text('Đặt tên hồ sơ ứng tuyển');
  await page.type('input[placeholder="Ví dụ: Công ty A"]', 'Công ty A');
  await click('Lưu hồ sơ ứng tuyển'); await text('Năng lực hiện tại theo JD');
  assert.equal(creationPayload.title, 'Backend Developer');
  assert.equal(creationPayload.company, 'Công ty A');
  await click('Bắt đầu lượt 1'); await text('Chuẩn bị phỏng vấn');
  await click('Bắt đầu phỏng vấn'); await page.waitForSelector('textarea');
  await click('Kết thúc phiên'); await text('Kết thúc lượt phỏng vấn?');
  assert.equal(states.get('prepared').is_finished, false, 'Confirmation must precede stop');
  await click('Kết thúc lượt'); await text('Chưa có dữ liệu để đánh giá năng lực.');
  assert.equal(profile.attempts[0].status, 'Cancelled');
  await click('Phỏng vấn lượt mới'); await text('Chuẩn bị phỏng vấn');
  await click('Bắt đầu phỏng vấn'); await page.waitForSelector('textarea');
  await page.type('textarea', 'EXPLAIN ANALYZE để đối chiếu estimated rows và actual rows.');
  await click('Gửi câu trả lời'); await text('Bạn sẽ kiểm chứng kết quả tối ưu như thế nào?');
  await page.reload({ waitUntil: 'networkidle0' });
  await click('Lịch sử (1 câu)');
  await text('EXPLAIN ANALYZE');
  await click('Đóng lịch sử');
  await click('Kết thúc phiên'); await click('Kết thúc lượt');
  await click('Về hồ sơ ứng tuyển');
  assert.equal(profile.attempts.find(item => item.number === 2)?.status, 'Stopped early');
  await text('Năng lực hiện tại theo JD'); await historyTab(); await text('Kết thúc sớm'); await text('Kết thúc trước khi trả lời');
  await page.screenshot({ path: '.next/application-profile-desktop.png', fullPage: true });
  await click('Phỏng vấn lượt mới'); await text('Chuẩn bị phỏng vấn');
  await click('Bắt đầu phỏng vấn'); await page.waitForSelector('textarea');
  await click('← Về hồ sơ ứng tuyển'); await text('Tiếp tục lượt 3');
  await click('Bắt đầu lại'); await text('Kết thúc lượt hiện tại và bắt đầu lại?');
  await click('Kết thúc và tạo lượt mới'); await text('Chuẩn bị phỏng vấn');
  assert.equal(profile.attempts.length, 4);
  assert.equal(states.get('attempt-3').is_finished, true);
  assert.equal(states.has('attempt-4'), false, 'New attempt starts without copied answers');
  await visit(`/applications/${profileId}`);
  await historyTab(); await page.setViewport({ width: 390, height: 844 }); await text('Các lượt phỏng vấn');
  await page.screenshot({ path: '.next/application-profile-mobile.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile must not overflow horizontally');
  assert.equal(analysisCalls, 1, 'Reload and repeat interviews must reuse the submitted analysis');
  assert.deepEqual(errors, []);
  console.log('PASS: empty state, save profile, start, confirmed cancellation, repeat, reload, early stop, restart, mobile layout.');
} finally { await browser.close(); }
