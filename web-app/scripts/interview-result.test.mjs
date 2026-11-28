import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/components/features/interview/result/resultData.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const sandbox = { exports: {} };
vm.runInNewContext(compiled.outputText, sandbox);
const { buildResult, percent, isBoilerplateClaim, cleanStudyRecommendation, looksLikeRawCode } = sandbox.exports;
const plain = value => JSON.parse(JSON.stringify(value));

const objective = (id, skill, assessment = 'NOT_ASSESSED', extra = {}) => ({
  objective_id: id, skill_id: skill, claim: id, assessment,
  evidence: [],
  strengths: [], weaknesses: [], study_recommendations: [], ...extra,
});
const turn = (id, objectiveId) => ({ turn_id: id, objective_id: objectiveId });
const session = (objectives, turns, extra = {}) => ({ turns, report: { objectives, ...extra } });

test('excludes unasked skills, objectives and their findings from this session result', () => {
  const data = buildResult(session([
    objective('asked', 'java', 'DEMONSTRATED_AT_TARGET', { strengths: [' Good answer ', 'Good answer'] }),
    objective('unasked-same-skill', 'java', 'NOT_ASSESSED', { weaknesses: ['Not tested'] }),
    objective('excluded', 'docker', 'NOT_ASSESSED', { study_recommendations: ['Study Docker'] }),
    objective('stale-assessment', 'sql', 'NOT_DEMONSTRATED', { weaknesses: ['Other session'] }),
  ], [turn('t1', 'asked')], { study_recommendations: ['Study Docker'] }));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount, skill.objectives.length])),
    [['java', 'strong', 1, 1]]);
  assert.deepEqual(plain(data.strengths), ['Good answer']);
  assert.deepEqual(plain(data.weaknesses), []);
  assert.deepEqual(plain(data.recommendations), []);
  assert.equal(data.assessedCount, 1);
  assert.equal(data.achievedCount, 1);
});

test('counts distinct checked and passed essential criteria; old reports retain their summary', () => {
  const labels = ['DEMONSTRATED_AT_TARGET','DEMONSTRATED_ABOVE_TARGET','INSUFFICIENT_EVIDENCE','NOT_ASSESSED','NOT_ASSESSED'];
  const criteria = labels.map((assessment, i) => ({ criterion_id: String(i), assessment, essential: true }));
  criteria.push({ criterion_id: 'optional', assessment: 'DEMONSTRATED_AT_TARGET', essential: false });
  const turns = [turn('a', 'o'), turn('b', 'o')];
  const data = buildResult(session([objective('o', 'sql', 'INSUFFICIENT_EVIDENCE', { criteria })], turns));
  assert.deepEqual(plain(data.coverage), { total: 5, checked: 3, passed: 2 });
  assert.equal(buildResult(session([objective('o', 'sql')], turns)).coverage, null);
});

test('retains asked skills without a verdict and keeps questions even when an objective report is missing', () => {
  const data = buildResult(session([
    objective('asked', 'java'),
    objective('partial', 'sql', 'INSUFFICIENT_EVIDENCE'),
  ], [turn('t1', 'asked'), turn('t2', 'partial'), turn('t3', 'not-in-report')]));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount])),
    [['java', 'partial', 1], ['sql', 'partial', 1]]);
  assert.equal(data.questions.length, 3);
  assert.equal(data.questions[2].skillId, '');
  assert.equal(data.assessedCount, 0);
  assert.equal(percent(data.assessedCount ? data.achievedCount / data.assessedCount : null), null);
});

test('uses evidence links to retain skills assessed through a question about another objective', () => {
  const evidence = { turn_id: 't1', performance: 'BELOW' };
  const data = buildResult(session([
    objective('primary', 'java', 'DEMONSTRATED_AT_TARGET'),
    objective('linked-by-evidence', 'git', 'DEMONSTRATED_BELOW_TARGET', {
      evidence: [evidence], weaknesses: ['Needs indexing'], study_recommendations: ['Practice indexing'],
    }),
    objective('stale', 'docker', 'DEMONSTRATED_AT_TARGET', { evidence: [{ turn_id: 'other-turn', performance: 'AT_TARGET' }] }),
  ], [turn('t1', 'primary')]));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount])),
    [['java', 'strong', 1], ['git', 'weak', 1]]);
  assert.deepEqual(plain(data.recommendations), ['Practice indexing']);
  assert.deepEqual(plain(data.weaknesses), ['Needs indexing']);
  assert.equal(data.questions[0].status, 'weak');
  assert.equal(data.assessedCount, 2);
  assert.equal(percent(data.achievedCount / data.assessedCount), 50);
});

test('does not let an unasked objective change an interviewed skill verdict', () => {
  const data = buildResult(session([
    objective('strong', 'java', 'DEMONSTRATED_ABOVE_TARGET'),
    objective('weak', 'java', 'NOT_DEMONSTRATED'),
    objective('unasked', 'java'),
  ], [turn('t1', 'strong'), turn('t2', 'weak'), turn('t3', 'weak')]));
  assert.equal(data.skills.length, 1);
  assert.equal(data.skills[0].status, 'weak');
  assert.equal(data.skills[0].questionCount, 3);
  assert.equal(data.skills[0].objectives.length, 2);
});

test('ignores a pending question and stale observations in a completed objective', () => {
  const input = session([
    objective('asked', 'java', 'DEMONSTRATED_AT_TARGET', { evidence: [
      { turn_id: 'stale', performance: 'BELOW' }, { turn_id: 't1', performance: 'AT_TARGET' },
    ] }),
    objective('pending', 'docker'),
  ], [turn('t1', 'asked')]);
  input.pending_turn = turn('t2', 'pending');
  const data = buildResult(input);
  assert.equal(data.skills.length, 1);
  assert.equal(data.questions.length, 1);
  assert.equal(data.questions[0].status, 'strong');
  assert.equal(data.questions[0].evidence.length, 1);
  assert.deepEqual(plain(buildResult(session(input.report.objectives, [])).skills), []);
});

test('marks intermediate turns clarified later and detects raw code snippets cleanly', () => {
  const data = buildResult(session([
    objective('ai', 'ai_tools_usage', 'INSUFFICIENT_EVIDENCE', {
      evidence: [{ turn_id: 't2', performance: 'AT_TARGET' }],
    }),
    objective('git', 'git', 'DEMONSTRATED_AT_TARGET', {
      evidence: [{ turn_id: 't3', performance: 'AT_TARGET' }],
    }),
  ], [turn('t1', 'ai'), turn('t2', 'ai'), turn('t3', 'git')]));
  assert.equal(data.questions[0].clarifiedLater, true);
  assert.equal(data.questions[1].clarifiedLater, false);
  assert.equal(data.strongSkillCount, 1);
  assert.equal(data.partialSkillCount, 1);
  assert.equal(isBoilerplateClaim('Đánh giá kiến thức thực hành ai_tools_usage', 'ai_tools_usage'), true);
  assert.equal(isBoilerplateClaim('Thiết kế chỉ mục cho truy vấn chậm', 'sql'), false);
  assert.equal(
    cleanStudyRecommendation('ai_tools_usage (Đánh giá kiến thức thực hành ai_tools_usage): Ưu tiên ôn luyện'),
    'Ưu tiên ôn luyện',
  );
  assert.equal(looksLikeRawCode('{\n  "success": false\n}', 'DESIGN'), true);
  assert.equal(looksLikeRawCode('function sum(a, b) {\n  return a + b;\n}', 'CODING'), true);
  assert.equal(looksLikeRawCode('Nếu danh sách rỗng thì gặp lỗi chia cho 0.', 'DEBUGGING'), false);
  assert.equal(looksLikeRawCode('```js\nconst x = 1;\n```', 'CODING'), false);
});

test('distinguishes diagnostic, target and extension question badges and normalizes session coaching', () => {
  const data = buildResult(session([
    objective('sql-obj', 'sql', 'DEMONSTRATED_ABOVE_TARGET', {
      evidence: [
        { turn_id: 't-diag', criterion_id: 'c1', performance: 'AT_TARGET', depth_role: 'DIAGNOSTIC', observation: 'SUPPORTS', rationale: 'Hiểu khái niệm cơ bản' },
        { turn_id: 't-target', criterion_id: 'c1', performance: 'AT_TARGET', depth_role: 'TARGET', observation: 'SUPPORTS', rationale: 'Áp dụng đúng index' },
        { turn_id: 't-ext', criterion_id: 'c1', performance: 'ABOVE', depth_role: 'EXTENSION', observation: 'SUPPORTS', rationale: 'Phân tích trade-off write amplification' },
      ],
    }),
  ], [
    turn('t-diag', 'sql-obj'),
    turn('t-target', 'sql-obj'),
    turn('t-ext', 'sql-obj'),
  ], {
    coaching: {
      overall_summary: '  Bạn nắm rất chắc tối ưu hóa truy vấn và đánh đổi chỉ mục. ',
      top_strengths: ['Phân tích execution plan rõ ràng', 'Phân tích execution plan rõ ràng'],
      priority_gaps: [],
      actionable_study_steps: ['sql (Tune queries): Luyện thêm partitioning'],
    },
  }));

  assert.equal(data.questions[0].depthRole, 'DIAGNOSTIC');
  assert.equal(data.questions[0].badge.key, 'diagnostic');
  assert.equal(data.questions[0].badge.label, 'Đạt nền tảng (chẩn đoán)');

  assert.equal(data.questions[1].depthRole, 'TARGET');
  assert.equal(data.questions[1].badge.key, 'strong');
  assert.equal(data.questions[1].badge.label, 'Đạt yêu cầu');

  assert.equal(data.questions[2].depthRole, 'EXTENSION');
  assert.equal(data.questions[2].badge.key, 'extension');
  assert.equal(data.questions[2].badge.label, 'Vượt yêu cầu (mở rộng)');

  assert.equal(data.coaching?.overall_summary, 'Bạn nắm rất chắc tối ưu hóa truy vấn và đánh đổi chỉ mục.');
  assert.deepEqual(plain(data.coaching?.top_strengths), ['Phân tích execution plan rõ ràng']);
  assert.deepEqual(plain(data.coaching?.actionable_study_steps), ['Luyện thêm partitioning']);
});

test('computes weighted readiness giving Core objectives double weight over non-core objectives', () => {
  const data = buildResult(session([
    objective('core-java', 'java', 'DEMONSTRATED_BELOW_TARGET', {
      is_core: true,
      importance_weight: 0.9,
      target_depth: 3,
    }),
    objective('aux-git', 'git', 'DEMONSTRATED_AT_TARGET', {
      is_core: false,
      importance_weight: 0.4,
      target_depth: 2,
    }),
  ], [
    turn('t1', 'core-java'),
    turn('t2', 'aux-git'),
  ]));

  // Core weight = 2 (failed), aux weight = 1 (passed) => 1 / 3 = 33%, NOT inflated 50%
  assert.equal(data.weightedReadiness.hasCoreWeight, true);
  assert.equal(data.weightedReadiness.coreTotal, 1);
  assert.equal(data.weightedReadiness.coreMet, 0);
  assert.equal(data.weightedReadiness.conclusiveCount, 2);
  assert.equal(data.weightedReadiness.inconclusiveCount, 0);
  assert.equal(data.weightedReadiness.percent, 33);
});

test('does not penalize INSUFFICIENT_EVIDENCE objectives as zero in weightedReadiness', () => {
  const data = buildResult(session([
    objective('core-java', 'java', 'DEMONSTRATED_AT_TARGET', {
      is_core: true,
      importance_weight: 0.9,
      target_depth: 2,
    }),
    objective('core-sql-unfinished', 'sql', 'INSUFFICIENT_EVIDENCE', {
      is_core: true,
      importance_weight: 0.85,
      target_depth: 3,
    }),
  ], [
    turn('t1', 'core-java'),
    turn('t2', 'core-sql-unfinished'),
  ]));

  assert.equal(data.weightedReadiness.conclusiveCount, 1);
  assert.equal(data.weightedReadiness.inconclusiveCount, 1);
  assert.equal(data.weightedReadiness.coreTotal, 1);
  assert.equal(data.weightedReadiness.coreMet, 1);
  assert.equal(data.weightedReadiness.percent, 100);
  assert.equal(data.weightedReadiness.inconclusiveWithRiskCount, 0);
  assert.equal(data.weightedReadiness.provisionalPercent, 100);
  assert.equal(data.hiringSignal.key, 'BORDERLINE'); // 50% coverage (< 70%) avoids premature HIRE
});

test('flags observed risk inside INSUFFICIENT_EVIDENCE objectives to prevent false 100% readiness illusion', () => {
  const data = buildResult(session([
    objective('core-java', 'java', 'DEMONSTRATED_AT_TARGET', {
      is_core: true,
      importance_weight: 0.9,
      target_depth: 2,
      evidence: [{ turn_id: 't1', performance: 'AT_TARGET', observation: 'SUPPORTS' }],
    }),
    objective('core-sql-risk', 'sql', 'INSUFFICIENT_EVIDENCE', {
      is_core: true,
      importance_weight: 0.85,
      target_depth: 3,
      weaknesses: ['Trả lời sai cơ chế composite index'],
      evidence: [{ turn_id: 't2', performance: 'BELOW', observation: 'CONTRADICTS' }],
    }),
  ], [
    turn('t1', 'core-java'),
    turn('t2', 'core-sql-risk'),
  ]));

  assert.equal(data.weightedReadiness.percent, 100); // concluded-only metric preserved
  assert.equal(data.weightedReadiness.inconclusiveWithRiskCount, 1);
  assert.equal(data.weightedReadiness.coreRiskCount, 1);
  assert.equal(data.weightedReadiness.provisionalPercent, 50); // conservative readiness catches the observed failure
  assert.equal(data.hiringSignal.key, 'NEEDS_PREP');
});

test('tracks hint-assisted passes distinctly and distinguishes STRONG_HIRE vs BORDERLINE signals', () => {
  const hintedSession = buildResult(session([
    objective('core-py', 'python', 'DEMONSTRATED_AT_TARGET', {
      is_core: true,
      importance_weight: 0.9,
      hinted: true,
      evidence: [{ turn_id: 't1', performance: 'AT_TARGET', observation: 'SUPPORTS' }],
      criteria: [{ criterion_id: 'c1', description: 'Viết hàm lọc trùng', essential: true, hinted: true, assessment: 'DEMONSTRATED_AT_TARGET' }],
    }),
  ], [
    { turn_id: 't1', objective_id: 'core-py', clarifications: [{ kind: 'HINT', question: '', answer: 'Gợi ý dùng dict.' }] },
  ]));
  assert.equal(hintedSession.skills[0].hinted, true);
  assert.equal(hintedSession.questions[0].usedHint, true);
  assert.equal(hintedSession.questions[0].badge.label, 'Đạt yêu cầu (có gợi ý)');
  assert.equal(hintedSession.weightedReadiness.hintedStrongCount, 1);
  assert.equal(hintedSession.hiringSignal.key, 'BORDERLINE');

  const strongSession = buildResult(session([
    objective('core-arch', 'architecture', 'DEMONSTRATED_ABOVE_TARGET', {
      is_core: true,
      importance_weight: 0.95,
      evidence: [{ turn_id: 't1', performance: 'ABOVE', depth_role: 'EXTENSION', observation: 'SUPPORTS' }],
    }),
  ], [turn('t1', 'core-arch')]));
  assert.equal(strongSession.hiringSignal.key, 'STRONG_HIRE');
});

test('computes per-mode performance breakdown for answered turns', () => {
  const data = buildResult(session([
    objective('o-code', 'python', 'DEMONSTRATED_BELOW_TARGET', {
      evidence: [
        { turn_id: 't1', performance: 'BELOW', observation: 'CONTRADICTS' },
        { turn_id: 't2', performance: 'AT_TARGET', observation: 'SUPPORTS' },
      ],
    }),
    objective('o-design', 'architecture', 'DEMONSTRATED_AT_TARGET', {
      evidence: [{ turn_id: 't3', performance: 'AT_TARGET', observation: 'SUPPORTS' }],
    }),
  ], [
    { turn_id: 't1', objective_id: 'o-code', mode: 'CODING' },
    { turn_id: 't2', objective_id: 'o-code', mode: 'CODING' },
    { turn_id: 't3', objective_id: 'o-design', mode: 'DESIGN' },
  ]));

  assert.deepEqual(plain(data.modeBreakdown), [
    { mode: 'CODING', label: 'Lập trình', total: 2, strong: 1, weak: 1, partial: 0, passRate: 50 },
    { mode: 'DESIGN', label: 'Thiết kế hệ thống', total: 1, strong: 1, weak: 0, partial: 0, passRate: 100 },
  ]);
});

test('shows the coached retry separately and credits a later independent transfer', () => {
  const data = buildResult(session([objective('o', 'sql', 'DEMONSTRATED_AT_TARGET', {
    hinted: true, criteria: [{ criterion_id: 'c', hinted: true, transfer_verified: true, essential: true,
      assessment: 'DEMONSTRATED_AT_TARGET' }],
    evidence: [{ turn_id: 'fresh', observation: 'SUPPORTS', performance: 'AT_TARGET', depth_role: 'TARGET' }],
  })], [
    { ...turn('first', 'o'), clarifications: [{ kind: 'HINT' }] },
    { ...turn('again', 'o'), practice_step: 'RETRY' },
    { ...turn('fresh', 'o'), practice_step: 'TRANSFER' },
  ]));
  assert.equal(data.questions[1].badge.key, 'retry');
  assert.equal(data.questions[2].badge.key, 'strong');
  assert.equal(data.weightedReadiness.hintedStrongCount, 0);
  assert.equal(data.skills[0].hinted, false);
});
