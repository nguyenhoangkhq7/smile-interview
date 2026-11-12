import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/components/features/interview/result/resultData.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const sandbox = { exports: {} };
vm.runInNewContext(compiled.outputText, sandbox);
const { buildResult, percent } = sandbox.exports;
const plain = value => JSON.parse(JSON.stringify(value));

const objective = (id, skill, assessment = 'NOT_ASSESSED', extra = {}) => ({
  objective_id: id, skill_id: skill, claim: id, assessment,
  evidence: [], evidence_turn_ids: [], covered_criteria: [], missing_criteria: [],
  strengths: [], weaknesses: [], study_recommendations: [], ...extra,
});
const turn = (id, skill, objectiveId) => ({ turn_id: id, skill_id: skill, objective_id: objectiveId });
const session = (objectives, turns, extra = {}) => ({ turns, report: { objectives, ...extra } });

test('excludes unasked skills, objectives and their findings from this session result', () => {
  const data = buildResult(session([
    objective('asked', 'java', 'DEMONSTRATED_AT_TARGET', { strengths: [' Good answer ', 'Good answer'] }),
    objective('unasked-same-skill', 'java', 'NOT_ASSESSED', { weaknesses: ['Not tested'] }),
    objective('excluded', 'docker', 'NOT_ASSESSED', { study_recommendations: ['Study Docker'] }),
    objective('stale-assessment', 'sql', 'NOT_DEMONSTRATED', { weaknesses: ['Other session'] }),
  ], [turn('t1', 'java', 'asked')], { study_recommendations: ['Study Docker'] }));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount, skill.objectives.length])),
    [['java', 'strong', 1, 1]]);
  assert.deepEqual(plain(data.strengths), ['Good answer']);
  assert.deepEqual(plain(data.weaknesses), []);
  assert.deepEqual(plain(data.recommendations), []);
  assert.equal(data.assessedCount, 1);
  assert.equal(data.achievedCount, 1);
});

test('retains asked skills without a verdict, even when the objective report is missing', () => {
  const data = buildResult(session([
    objective('asked', 'java'),
    objective('partial', 'sql', 'INSUFFICIENT_EVIDENCE'),
  ], [turn('t1', 'java', 'asked'), turn('t2', 'sql', 'partial'), turn('t3', 'git', 'not-in-report')]));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount])),
    [['java', 'partial', 1], ['sql', 'partial', 1], ['git', 'partial', 1]]);
  assert.equal(data.assessedCount, 0);
  assert.equal(percent(data.assessedCount ? data.achievedCount / data.assessedCount : null), null);
});

test('uses evidence links to retain skills assessed through a question about another objective', () => {
  const evidence = { turn_id: 't1', performance: 'BELOW' };
  const data = buildResult(session([
    objective('primary', 'java', 'DEMONSTRATED_AT_TARGET'),
    objective('linked-by-ids', 'sql', 'DEMONSTRATED_BELOW_TARGET', {
      evidence_turn_ids: ['t1'], weaknesses: ['Needs indexing'], study_recommendations: ['Practice indexing'],
    }),
    objective('linked-by-evidence', 'git', 'INSUFFICIENT_EVIDENCE', { evidence: [evidence] }),
    objective('stale', 'docker', 'DEMONSTRATED_AT_TARGET', { evidence_turn_ids: ['other-turn'] }),
  ], [turn('t1', 'java', 'primary')]));
  assert.deepEqual(plain(data.skills.map(skill => [skill.id, skill.status, skill.questionCount])),
    [['java', 'strong', 1], ['sql', 'weak', 1], ['git', 'partial', 1]]);
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
  ], [turn('t1', 'java', 'strong'), turn('t2', 'java', 'weak'), turn('t3', 'java', 'weak')]));
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
  ], [turn('t1', 'java', 'asked')]);
  input.pending_turn = turn('t2', 'docker', 'pending');
  const data = buildResult(input);
  assert.equal(data.skills.length, 1);
  assert.equal(data.questions.length, 1);
  assert.equal(data.questions[0].status, 'strong');
  assert.equal(data.questions[0].evidence.length, 1);
  assert.deepEqual(plain(buildResult(session(input.report.objectives, [])).skills), []);
});
