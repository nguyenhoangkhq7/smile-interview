// Run against next dev with SIMLI_TEST_DRIVER=1. HTTP and microphone input are local fixtures.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://127.0.0.1:3238';
const profile = 'practice-sql';
const description = 'Vận dụng tiêu chí SQL';
const spoken = 'Em dùng truy vấn để tìm bản ghi phù hợp.';
const code = 'SELECT id\nFROM events\nORDER BY id;';
const task = { id: 1, title: 'Ôn SQL', skillId: 'sql', status: 'TODO', sortOrder: 0,
  gapSourceObjectiveId: 'obj', gapSourceSkillId: 'sql', gapSourceSessionId: 'source', gapSourceAttemptNumber: 1 };
const checklist = [{ id: 2, content: 'Soạn lại truy vấn', isCompleted: false, sortOrder: 0,
  sourceSessionId: 'source', sourceCriterionId: 'crit', sourceAttemptNumber: 1 }];
const objective = { objective_id: 'obj', skill_id: 'sql', claim: description, assessment: 'NOT_ASSESSED',
  jd_evidence_spans: [], strengths: [], weaknesses: [], evidence: [],
  criteria: [{ criterion_id: 'crit', description, essential: true, assessment: 'NOT_ASSESSED' }] };
const browser = await puppeteer.launch({ headless: true, args: ['--autoplay-policy=no-user-gesture-required', '--enable-unsafe-swiftshader'] });
try {
  for (const scenario of ['TEXT', 'VOICE', 'VOICE_CODE']) {
    const page = await browser.newPage();
    const errors = [], writes = [], results = [];
    let createdAttempts = 0;
    const before = { sessionId: 'source', assessment: 'DEMONSTRATED_BELOW_TARGET',
      turns: [{ question: 'Đề cũ', answer: 'Câu trước khi ôn' }] };
    let session, failRecognition = scenario === 'VOICE_CODE', loseReceipt = scenario === 'VOICE_CODE';
    const id = 'recheck-' + scenario;
    const finalAssessment = 'DEMONSTRATED_AT_TARGET';
    await page.setViewport({ width: 1365, height: 1000 });
    page.on('pageerror', error => errors.push(error.message));
    await page.evaluateOnNewDocument(() => {
      localStorage.setItem('auth-storage', JSON.stringify({ state: { user: { id: 'fixture', username: 'SV', role: 'USER' },
        token: 'e30.' + btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })) + '.fixture', isAuthenticated: true }, version: 0 }));
      const context = new AudioContext();
      navigator.mediaDevices.getUserMedia = async () => context.createMediaStreamDestination().stream;
      Object.getPrototypeOf(context.audioWorklet).addModule = async () => {};
      window.AudioWorkletNode = class extends GainNode {
        constructor(ctx) { super(ctx); this.port = {}; window.__frames = this.port; window.__captureRate = ctx.sampleRate; }
      };
    });
    await page.setRequestInterception(true);
    page.on('request', async request => {
      const url = new URL(request.url()), path = url.pathname;
      if (!path.startsWith('/api/')) return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
      const headers = { 'access-control-allow-origin': base, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*',
        'access-control-expose-headers': 'X-Audio-Sample-Rate, X-Audio-Format', 'content-type': 'application/json' };
      const send = (obj, status = 200) => request.respond({ status, headers, body: JSON.stringify(obj) });
      if (request.method() === 'OPTIONS') return send({});
      if (path.endsWith('/limits')) return send({ voiceEnabled: true, maxQuestions: 10, durationSeconds: 900, maxQuestionsPerObjective: 8 });
      if (path.endsWith('/study-plan')) return send({ plan: { title: 'Ôn SQL', targetCompletionPercent: 80, sourceSessionId: 'source' },
        progress: { done: 0, total: 1, percent: 0 }, tasks: [{ task, checklist, resources: [] }] });
      if (path.endsWith('/knowledge-gaps')) return send({ completedAttempts: 1, weak: [], needsVerification: [], notAssessedSkillIds: [], objectiveSuggestions: [] });
      if (path.endsWith('/rechecks')) return send(results);
      if (path.endsWith('/checklist/2/recheck')) return send({ description, before });
      if (path.endsWith('/attempts')) {
        createdAttempts++;
        return send({ id, number: 2, status: 'Not started' });
      }
      if (path.endsWith('/application-profiles/' + profile)) return send({ id: profile, roleTitle: 'Developer', title: 'SQL',
        cvFilename: 'CV.pdf', jdTitle: 'Developer', skills: [{ jd_skill_id: 'sql' }], attempts: [], analysis: {} });
      if (path === '/api/v1/sessions/' + id) return send({ id, applicationProfileId: profile, attemptNumber: 2, turns: [] });
      if (path.endsWith('/interview')) return session ? send(session) : send({}, 404);
      if (path.endsWith('/start')) {
        const config = JSON.parse(request.postData());
        assert.deepEqual(config.recheck, { taskId: 1, checklistItemId: 2 });
        assert.equal(config.interaction_mode, scenario === 'TEXT' ? 'TEXT' : 'VOICE');
        session = { session_id: id, schema_version: 2, state_version: 1, is_finished: false, deadline_at: new Date(Date.now()+300000).toISOString(),
          config, turns: [], report: { objectives: [objective] }, pending_turn: { turn_id: 't', objective_id: 'obj', mode: 'CODING',
            requires_code: scenario === 'VOICE_CODE', question: 'Hãy xử lý tình huống SQL mới.' } };
        return send(session);
      }
      if (path.endsWith('/voice/config')) return send({ enabled: true, format: 'pcm', sample_rate: 24000, avatar: { configured: true } });
      if (path.endsWith('/avatar-session')) return send({ session_token: 'fixture' });
      if (path.endsWith('/speech')) return request.respond({ headers: { ...headers, 'content-type': 'audio/pcm',
        'X-Audio-Format': 'pcm', 'X-Audio-Sample-Rate': '24000' }, body: Buffer.alloc(4800) });
      if (path.endsWith('/transcribe')) {
        if (failRecognition) { failRecognition = false; return send({ message: 'Nhận diện lỗi thử nghiệm' }, 503); }
        return send({ text: spoken, phase: 'final', review_required: false, verification: 'agreed' });
      }
      if (path.endsWith('/respond')) {
        const body = JSON.parse(request.postData());
        writes.push(body);
        if (!session.is_finished) {
          const turn = { ...session.pending_turn, answer: body.candidate_response, submitted_code: body.submitted_code, transcript: body.candidate_response };
          session = { ...session, is_finished: true, pending_turn: null, turns: [turn], state_version: 2,
            report: { objectives: [{ ...objective, assessment: finalAssessment }], recheck_criterion: { description, assessment: finalAssessment },
              termination_reason: 'SUFFICIENT_EVIDENCE' } };
          results.push({ checklistItemId: 2, before, after: { sessionId: id, assessment: finalAssessment,
            turns: [{ question: turn.question, answer: turn.answer, code: turn.submitted_code, transcript: turn.transcript }] } });
        }
        if (loseReceipt) { loseReceipt = false; return request.abort('failed'); }
        return send(session);
      }
      return send([]);
    });
    const click = async text => { const sel = 'button::-p-text(' + text + ')'; await page.waitForSelector(sel); await page.click(sel); };
    const waitText = text => page.waitForFunction(text => document.body.innerText.includes(text), {}, text);
    try {
      await page.goto(base + '/practice/' + profile + '?task=1');
      await page.waitForSelector('summary::-p-text(Bằng chứng ban đầu)');
      await page.click('summary::-p-text(Bằng chứng ban đầu)');
      await waitText('Câu trước khi ôn');
      const channel = scenario === 'TEXT' ? 'Văn bản' : 'Giọng nói';
      await page.click('button::-p-text(' + channel + ')', { clickCount: 2 });
      await waitText(description);
      await click('Bắt đầu phỏng vấn');
      await waitText('Hãy xử lý tình huống SQL mới.');
      await page.reload();
      await waitText('Hãy xử lý tình huống SQL mới.');
      assert.equal(createdAttempts, 1);
      if (scenario === 'TEXT') {
        await page.waitForSelector('#interview-answer'); await page.type('#interview-answer', spoken);
        await click('Gửi câu trả lời');
      } else {
        await click('Bắt đầu trò chuyện');
        await page.waitForFunction(() => window.__frames?.onmessage && window.__simliMock?.bytes > 0);
        if (scenario === 'VOICE_CODE') await page.type('#voice-code', code.split('\n', 1)[0]);
        await page.evaluate(() => {
          for (let i = 0; i < Math.ceil(window.__captureRate * 0.5 / 2048); i++)
            window.__frames.onmessage({ data: new Float32Array(2048).fill(0.14) });
          for (let i = 0; i < Math.ceil(window.__captureRate * 1.5 / 2048); i++)
            window.__frames.onmessage({ data: new Float32Array(2048) });
        });
        if (scenario === 'VOICE_CODE') {
          await click('Nhận diện lại bản ghi');
          await waitText(spoken);
          await page.type('#voice-code', code.slice(code.indexOf('\n')));
          await new Promise(resolve => setTimeout(resolve, 900));
          assert.equal(writes.length, 0);
          await click('Nộp bài');
          await page.waitForFunction(() => document.querySelector('[role="alert"]') && !document.querySelector('#voice-code')?.disabled);
          assert.equal(await page.$eval('#voice-code', el => el.value), code);
          await click('Nộp bài');
        }
      }
      await page.waitForSelector('a::-p-text(Về đầu việc)');
      assert.equal(writes[0].candidate_response, spoken);
      if (scenario === 'VOICE_CODE') {
        assert.equal(writes[0].submitted_code, code);
        assert.deepEqual(writes[0], writes[1]);
      }
      await page.click('a::-p-text(Về đầu việc)');
      await page.waitForSelector('summary::-p-text(Kết quả kiểm chứng)');
      assert.equal(new URL(page.url()).hash, '#checklist-2');
      await page.click('summary::-p-text(Kết quả kiểm chứng)');
      await waitText('Câu trước khi ôn');
      await waitText(spoken);
      if (scenario === 'VOICE_CODE') assert.equal(await page.$eval('#checklist-2 pre', pre => pre.textContent), code);
      assert.equal(results.length, 1);
      assert.deepEqual(errors, []);
      console.log('PASS', scenario);
    } catch (error) {
      console.error(scenario, errors, (await page.$eval('body', el => el.innerText)).slice(-2200));
      throw error;
    } finally { await page.close(); }
  }
} finally { await browser.close(); }
