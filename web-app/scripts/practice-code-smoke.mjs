// End-to-end browser smoke test for KLTN upgrades:
// Practice mode + Clarify/Hint + CodeMirror 6 /run-code + Weighted Readiness/Badges/Coaching + Competency Progress Timeline.
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer';

const base = process.argv[2] || 'http://localhost:3217';
const sessionId = 'practice-code-smoke';
const profileId = 'timeline-profile';
const errors = [];
const clarifyCalls = [];
const runCodeCalls = [];
const respondCalls = [];
let session = null;

const codingSpec = {
  language: 'python',
  entry_point: 'deduplicate_events',
  starter_code: 'def deduplicate_events(events):\n    return list(dict.fromkeys(events))\n',
  sample_tests: [
    { name: 'basic', input_data: "['a', 'b', 'a']", expected_output: "['a', 'b']" },
    { name: 'empty', input_data: '[]', expected_output: '[]' },
  ],
};

const pendingTurn = {
  turn_id: 'turn-code-1',
  objective_id: 'obj-python',
  mode: 'CODING',
  requires_code: true,
  coding_spec: codingSpec,
  question: 'Hãy viết hàm `deduplicate_events(events)` giữ nguyên thứ tự xuất hiện đầu tiên.',
  clarifications: [],
};

const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1365, height: 1000 });
  page.on('pageerror', err => errors.push(err.message));
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('auth-storage', JSON.stringify({
      state: {
        user: { id: 'student-1', username: 'SinhVien', role: 'USER' },
        token: `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.fixture`,
        isAuthenticated: true,
      },
      version: 0,
    }));
  });

  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    const path = url.pathname;
    if (!path.startsWith('/api/')) {
      return url.origin === base || url.protocol === 'data:' ? request.continue() : request.abort();
    }
    const headers = {
      'access-control-allow-origin': base,
      'access-control-allow-headers': '*',
      'access-control-allow-methods': '*',
      'content-type': 'application/json',
    };
    const send = (body, status = 200) => request.respond({ status, headers, body: JSON.stringify(body) });
    if (request.method() === 'OPTIONS') return send({});
    if (path.endsWith('/limits')) {
      return send({ voiceEnabled: true, maxQuestions: 10, durationSeconds: 900, maxQuestionsPerObjective: 8 });
    }
    if (path === `/api/v1/sessions/${sessionId}`) {
      return send({ id: sessionId, applicationProfileId: profileId, attemptNumber: 2, status: 'Not started', turns: [] });
    }
    if (path.endsWith('/interview/start')) {
      const config = JSON.parse(request.postData());
      assert.equal(config.session_purpose, 'PRACTICE');
      assert.equal(config.include_mastered_skills, true);
      session = {
        schema_version: 2,
        session_id: sessionId,
        state_version: 1,
        is_finished: false,
        config,
        deadline_at: new Date(Date.now() + 900000).toISOString(),
        pending_turn: { ...pendingTurn, clarifications: [] },
        turns: [],
        report: {
          termination_reason: null,
          objectives: [{
            objective_id: 'obj-python',
            skill_id: 'python',
            claim: 'Xử lý tập dữ liệu sự kiện theo thứ tự',
            target_depth: 3,
            importance_weight: 0.9,
            is_core: true,
            jd_evidence_spans: ['Process event streams in Python'],
            assessment: 'NOT_ASSESSED',
            stop_reason: null,
            strengths: [],
            weaknesses: [],
            evidence: [],
            criteria: [
              { criterion_id: 'c1', description: 'Giữ nguyên thứ tự phần tử', essential: true, assessment: 'NOT_ASSESSED' },
              { criterion_id: 'c2', description: 'Ghi chú độ phức tạp bộ nhớ', essential: false, assessment: 'NOT_ASSESSED' },
            ],
          }],
        },
      };
      return send(session);
    }
    if (path.endsWith('/interview/clarify')) {
      const payload = JSON.parse(request.postData());
      clarifyCalls.push(payload);
      const entry = payload.kind === 'HINT'
        ? { kind: 'HINT', question: '', answer: 'Hãy cân nhắc cấu trúc dữ liệu tra cứu O(1) kết hợp giữ thứ tự chèn.' }
        : { kind: 'CLARIFY_PROMPT', question: payload.question, answer: 'Danh sách đầu vào có thể rỗng và chứa các chuỗi có thể trùng nhau.' };
      session = {
        ...session,
        state_version: session.state_version + 1,
        pending_turn: {
          ...session.pending_turn,
          clarifications: [...(session.pending_turn.clarifications || []), entry],
        },
      };
      return send(session);
    }
    if (path.endsWith('/interview/run-code')) {
      const payload = JSON.parse(request.postData());
      runCodeCalls.push(payload);
      return send({
        language: payload.language || 'python',
        passed: 2,
        total: 2,
        compile_error: '',
        stdout: '',
        results: [
          { name: 'basic', passed: true, expected_output: "['a', 'b']", actual_output: "['a', 'b']", error: '', elapsed_ms: 8 },
          { name: 'empty', passed: true, expected_output: '[]', actual_output: '[]', error: '', elapsed_ms: 6 },
        ],
      });
    }
    if (path.endsWith('/interview/respond')) {
      const payload = JSON.parse(request.postData());
      respondCalls.push(payload);
      const answeredTurn = {
        ...session.pending_turn,
        answer: payload.candidate_response,
        submitted_code: payload.submitted_code,
        feedback: 'Code chạy đúng test mẫu nhưng cần phân tích thêm edge-case cho phần tử không hashable.',
      };
      session = {
        ...session,
        state_version: session.state_version + 1,
        is_finished: true,
        pending_turn: null,
        turns: [answeredTurn],
        report: {
          termination_reason: 'PLAN_COMPLETE',
          objectives: [
            {
              objective_id: 'obj-python',
              skill_id: 'python',
              claim: 'Xử lý tập dữ liệu sự kiện theo thứ tự',
              target_depth: 3,
              importance_weight: 0.9,
              is_core: true,
              jd_evidence_spans: ['Process event streams in Python'],
              assessment: 'DEMONSTRATED_BELOW_TARGET',
              stop_reason: 'CRITERIA_EVALUATED',
              strengths: ['Viết code sạch và chạy qua kiểm thử mẫu'],
              weaknesses: ['Chưa xử lý dữ liệu dict chưa hashable'],
              evidence: [{
                turn_id: 'turn-code-1',
                criterion_id: 'c1',
                response_excerpt: payload.candidate_response,
                rationale: 'Đạt phần lớn nhưng thiếu biên',
                performance: 'BELOW',
              }],
              criteria: [
                { criterion_id: 'c1', description: 'Giữ nguyên thứ tự phần tử', essential: true, assessment: 'DEMONSTRATED_BELOW_TARGET' },
                { criterion_id: 'c2', description: 'Ghi chú độ phức tạp bộ nhớ', essential: false, assessment: 'NOT_ASSESSED' },
              ],
            },
            {
              objective_id: 'obj-git',
              skill_id: 'git',
              claim: 'Quản lý nhánh rebase gọn gàng',
              target_depth: 2,
              importance_weight: 0.4,
              is_core: false,
              jd_evidence_spans: ['Git workflow'],
              assessment: 'DEMONSTRATED_AT_TARGET',
              stop_reason: 'CRITERIA_EVALUATED',
              strengths: ['Hiểu rebase vs merge'],
              weaknesses: [],
              evidence: [{
                turn_id: 'turn-code-1',
                criterion_id: 'g1',
                response_excerpt: 'Trình bày rõ ràng',
                rationale: 'Đạt yêu cầu phụ',
                performance: 'AT_TARGET',
              }],
              criteria: [
                { criterion_id: 'g1', description: 'Phân biệt merge và rebase', essential: true, assessment: 'DEMONSTRATED_AT_TARGET' },
              ],
            },
          ],
          turn_reviews: [{
            turn_id: 'turn-code-1',
            excerpt: payload.candidate_response,
            reason: 'Code ngắn gọn, độ phức tạp O(n) nhưng thiếu xử lý phần tử không hashable.',
            gaps: ['Chưa đề cập ràng buộc hashable của phần tử'],
            next_step: 'Kiểm tra đầu vào None và bổ sung test cho object không hashable',
            reference_answer: 'Dùng `dict.fromkeys` cho phần tử hashable, hoặc chuẩn hóa key trước khi lọc trùng với độ phức tạp O(n).',
            delivery_notes: ['Trình bày rõ độ phức tạp thời gian O(n) và bộ nhớ O(n) trước khi kết thúc.'],
          }],
          coaching: {
            overall_summary: 'Bạn có nền tảng Python tốt nhưng cần chú ý kỹ năng Cốt lõi về xử lý biên.',
            introduction_feedback: 'Phần giới thiệu ngắn gọn, nên bổ sung 1 số liệu dự án thực tế.',
            top_strengths: ['Triển khai code nhanh'],
            priority_gaps: ['Xử lý edge-case dữ liệu sự kiện'],
            actionable_study_steps: ['Luyện thêm kiểm thử biên với Python'],
          },
        },
      };
      return send(session);
    }
    if (path.endsWith('/interview')) return send(session || {}, session ? 200 : 404);
    if (path.endsWith(`/application-profiles/${profileId}/competency`)) {
      return send({
        completedAttempts: 2,
        practiceAttempts: 1,
        incompatibleAssessments: 0,
        timeline: [
          {
            sessionId: 'att-1',
            attemptNumber: 1,
            assessedAt: '2026-11-20T09:00:00',
            kind: 'ASSESSMENT',
            weightedReadinessPercent: 35,
            coreObjectivesMet: 0,
            coreObjectivesTotal: 2,
            essentialCriteriaMet: 2,
            essentialCriteriaTotal: 6,
          },
          {
            sessionId: 'att-2',
            attemptNumber: 2,
            assessedAt: '2026-11-27T09:00:00',
            kind: 'RECHECK',
            weightedReadinessPercent: 75,
            coreObjectivesMet: 2,
            coreObjectivesTotal: 2,
            essentialCriteriaMet: 5,
            essentialCriteriaTotal: 6,
          },
        ],
        skills: [{
          skillId: 'python',
          baselineAlignment: 'MATCH',
          assessment: 'DEMONSTRATED_AT_TARGET',
          objectives: [],
        }],
      });
    }
    if (path.endsWith(`/application-profiles/${profileId}`)) {
      return send({
        id: profileId,
        title: 'Backend Engineer · Acme',
        company: 'Acme',
        roleTitle: 'Backend Engineer',
        cvFilename: 'CV.pdf',
        jdTitle: 'Backend Engineer',
        createdAt: '2026-11-20T08:00:00',
        skills: [{ jd_skill_id: 'python', semantic_alignment: 'MATCH' }],
        analysis: {},
        attempts: [
          { id: 'att-1', number: 1, status: 'Completed', startedAt: '2026-11-20T09:00:00', answeredCount: 5 },
          { id: 'att-2', number: 2, status: 'Completed', startedAt: '2026-11-27T09:00:00', answeredCount: 2 },
        ],
      });
    }
    return send({});
  });

  const waitText = text => page.waitForFunction(t => document.body.innerText.includes(t), {}, text);
  const clickButton = async text => {
    const sel = `button::-p-text(${text})`;
    await page.waitForSelector(sel);
    await page.click(sel);
  };

  // 1. Setup screen: choose Practice mode + include_mastered_skills
  await page.goto(`${base}/interview/session/${sessionId}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('input[name="session-purpose"][value="PRACTICE"]');
  await page.click('input[name="session-purpose"][value="PRACTICE"]');
  await waitText('Bao gồm cả các kỹ năng đã từng đạt ở lượt trước');
  await page.click('input[type="checkbox"]');
  await clickButton('Bắt đầu phỏng vấn');

  // 2. Interview room: CodeMirror 6 editor mounted with starter code
  await page.waitForSelector('[data-code-editor="codemirror"] .cm-content');
  const starterInEditor = await page.$eval('[data-code-editor="codemirror"] .cm-content', el => el.innerText);
  assert.match(starterInEditor, /def deduplicate_events/);

  // 3. Clarify prompt + Hint flow without consuming max_questions
  await clickButton('Hỏi làm rõ đề bài');
  await page.waitForSelector('input[aria-label="Nội dung cần làm rõ đề bài"]');
  await page.type('input[aria-label="Nội dung cần làm rõ đề bài"]', 'Input có thể rỗng không?');
  await clickButton('Gửi câu hỏi');
  await waitText('Danh sách đầu vào có thể rỗng');
  await clickButton('Xin gợi ý nhỏ');
  await waitText('cấu trúc dữ liệu tra cứu O(1)');
  assert.equal(clarifyCalls.length, 2);
  assert.equal(clarifyCalls[0].kind, 'CLARIFY_PROMPT');
  assert.equal(clarifyCalls[1].kind, 'HINT');
  await waitText('Đã trả lời 0/10 câu');

  // 4. Dry-run code against /run-code
  await clickButton('Chạy thử');
  await waitText('2/2');
  assert.equal(runCodeCalls.length, 1);
  assert.equal(runCodeCalls[0].language, 'python');

  // 5. Submit explanation + code
  await page.type('#interview-answer', 'Hàm dùng dict.fromkeys chạy O(n) và giữ đúng thứ tự.');
  await clickButton('Gửi câu trả lời');
  await waitText('Chế độ Luyện tập');

  // 6. Verify result dashboard: Practice badge, weighted readiness (33%), Core/L3 badges, coaching & reference answer
  await page.goto(`${base}/interview/session/${sessionId}/result`, { waitUntil: 'networkidle0' });
  await waitText('Chế độ Luyện tập');
  await waitText('33%');
  await waitText('Kỹ năng cốt lõi đạt: 0/1');
  await waitText('Phần giới thiệu ngắn gọn');
  await waitText('L3 · Phân tích');
  await page.waitForSelector('#questions details > summary');
  await page.click('#questions details > summary');
  await waitText('Trình bày rõ độ phức tạp thời gian O(n)');
  await page.waitForSelector('summary::-p-text(Gợi ý khung trả lời chuẩn)');
  await page.click('summary::-p-text(Gợi ý khung trả lời chuẩn)');
  await waitText('Dùng `dict.fromkeys` cho phần tử hashable');
  assert.equal(respondCalls.length, 1);
  assert.match(respondCalls[0].submitted_code, /def deduplicate_events/);

  // 7. Verify application detail competency progress timeline & practiceAttempts counter
  await page.goto(`${base}/applications/${profileId}`, { waitUntil: 'networkidle0' });
  await waitText('Tiến bộ mức độ sẵn sàng (có trọng số Core)');
  await waitText('+40% so với lượt đầu');
  await waitText('1 lượt luyện tập');
  assert.ok(await page.$('svg[aria-label="Biểu đồ tiến bộ sẵn sàng qua từng lượt"]'));

  assert.deepEqual(errors, []);
  console.log('PASS: Practice mode, clarify/hint, CodeMirror 6 /run-code, weighted readiness, L1-L4/Core badges, reference answer, delivery notes, and progress timeline.');
} catch (error) {
  console.error('FAILED:', errors);
  throw error;
} finally {
  await browser.close();
}
