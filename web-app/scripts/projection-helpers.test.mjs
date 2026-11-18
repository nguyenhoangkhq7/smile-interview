import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const src = path.resolve(import.meta.dirname, '../src');

function loadTs(relativePath) {
  const file = path.join(src, relativePath);
  const compiled = ts.transpileModule(readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = { exports: {} };
  const localRequire = name => (name === 'axios' || name === '@/lib/axiosClient' ? { default: {} } : {});
  vm.runInNewContext(`(function(require, module, exports) { ${compiled}\n})`, { URL })(localRequire, mod, mod.exports);
  return mod.exports;
}

const {
  competencySummary, competencyLastAssessment, skillLastChecked, skillCriteriaCounts,
} = loadTs('services/applicationProfiles.ts');
const { isCriterionRecommended } = loadTs('services/studyPlans.ts');
const { turnSkillId } = loadTs('services/evidenceInterview.ts');

const source = (attemptNumber, sessionId = `s${attemptNumber}`) => ({
  sessionId, attemptNumber, assessedAt: `2026-11-0${attemptNumber}T10:00:00`,
});

test('computes competency summary, latest sources and criteria counts from skill trees', () => {
  const skills = [
    {
      skillId: 'sql', baselineAlignment: 'MATCH', assessment: 'DEMONSTRATED_AT_TARGET',
      objectives: [{
        id: 'o1', claim: 'SQL', assessment: 'DEMONSTRATED_AT_TARGET',
        lastChecked: source(3), lastAssessment: source(1), explanation: '',
        criteria: [
          { id: 'c1', description: 'C1', essential: true, assessment: 'DEMONSTRATED_AT_TARGET', lastAssessment: source(2), evidence: [{ turnId: 't1' }] },
          { id: 'c2', description: 'C2', essential: false, assessment: 'NOT_ASSESSED', lastAssessment: null, evidence: [] },
        ],
      }],
    },
    {
      skillId: 'java', baselineAlignment: 'PARTIAL', assessment: 'NEEDS_VERIFICATION',
      objectives: [{
        id: 'o2', claim: 'Java', assessment: 'NEEDS_VERIFICATION',
        lastChecked: source(4), lastAssessment: source(4), explanation: '',
        criteria: [{ id: 'c3', description: 'C3', essential: true, assessment: 'NEEDS_VERIFICATION', lastAssessment: source(4), evidence: [{ turnId: 't2' }] }],
      }],
    },
    { skillId: 'docker', baselineAlignment: 'MISSING', assessment: 'NOT_ASSESSED', objectives: [] },
  ];

  assert.deepEqual(JSON.parse(JSON.stringify(competencySummary(skills))), {
    totalSkills: 3, meetingTarget: 1, belowTarget: 0, needsVerification: 1, incomplete: 0, notAssessed: 1,
  });
  assert.equal(competencyLastAssessment(skills)?.attemptNumber, 4);
  assert.equal(skillLastChecked(skills[0])?.attemptNumber, 3);
  assert.equal(skillLastChecked(skills[2]), null);
  assert.deepEqual(JSON.parse(JSON.stringify(skillCriteriaCounts(skills[0]))), { evidenced: 1, total: 2 });
});

test('derives recommended study criteria from kind and resolves turn skill from report objectives', () => {
  assert.equal(isCriterionRecommended({ kind: 'REVIEW' }), true);
  assert.equal(isCriterionRecommended({ kind: 'VERIFY' }), true);
  assert.equal(isCriterionRecommended({ kind: 'REINFORCE' }), false);
  assert.equal(isCriterionRecommended({ kind: 'MET' }), false);
  assert.equal(isCriterionRecommended({ kind: 'UNASSESSED' }), false);

  const session = {
    report: {
      termination_reason: null,
      objectives: [{ objective_id: 'obj-1', skill_id: 'postgresql' }],
    },
  };
  assert.equal(turnSkillId(session, { objective_id: 'obj-1' }), 'postgresql');
  assert.equal(turnSkillId(session, { objective_id: 'missing' }), '');
});
