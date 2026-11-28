import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/skillLabels.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const sandbox = { exports: {} };
vm.runInNewContext(compiled.outputText, sandbox);
const { jdSkillLabel, skillLabel } = sandbox.exports;

test('restores saved Vietnamese IDs from exact JD evidence without changing the IDs', () => {
  const examples = [
    ['ph-t-tri-n-ai-coding-agent', 'Phát triển AI Coding Agent'],
    ['th-tr-ng-ch-ng-kho-n', 'Thị trường chứng khoán'],
    ['khoa-h-c-m-y-t-nh', 'Khoa học máy tính'],
  ];
  for (const [id, name] of examples) {
    assert.equal(skillLabel(id, null, [`Yêu cầu ${name}.`]), name);
    assert.equal(skillLabel(id, null, [`Kinh nghiệm: ${name}, ưu tiên ứng viên đã có dự án.`]), name);
  }
});

test('prefers explicit names, preserves technical brands and formats Unicode IDs', () => {
  assert.equal(skillLabel('ph-t-tri-n-ai-coding-agent', 'Phát triển AI Coding Agent'), 'Phát triển AI Coding Agent');
  assert.equal(skillLabel('spring-boot'), 'Spring Boot');
  assert.equal(skillLabel('spring_boot'), 'Spring Boot');
  assert.equal(skillLabel('rest-api'), 'REST API');
  assert.equal(skillLabel('ai_tools_usage'), 'Sử dụng công cụ AI');
  assert.equal(skillLabel('english_reading'), 'Đọc hiểu tiếng Anh');
  assert.equal(skillLabel('golang'), 'Golang');
  assert.equal(skillLabel('thị-trường-chứng-khoán'), 'thị trường chứng khoán');
  assert.equal(skillLabel('C++'), 'C++');
});

test('normalizes extracted JD names and their saved ID fallbacks for display', () => {
  const examples = [
    ['spring_boot', 'spring BOOT', 'Spring Boot'],
    ['restful-microservices', 'RESTful microservices', 'RESTful Microservices'],
    ['query-performance', 'query performance', 'Query Performance'],
    ['integration-tests', 'integration tests', 'Integration Tests'],
    ['indexing', 'indexing', 'Indexing'],
  ];
  for (const [id, name, expected] of examples) {
    assert.equal(jdSkillLabel({ jd_skill_id: id, jd_skill_name: name }), expected);
    assert.equal(jdSkillLabel({ jd_skill_id: id }), expected);
  }
});

test('formats extracted names and evidence without losing technical casing or Vietnamese accents', () => {
  assert.equal(skillLabel('node-js-development', 'node.js development'), 'Node.js Development');
  assert.equal(skillLabel('ci-cd', 'ci/cd'), 'CI/CD');
  assert.equal(skillLabel('ebpf-programming', 'eBPF programming'), 'eBPF Programming');
  assert.equal(skillLabel('service-design', 'restful api – microservice design'), 'RESTful API – Microservice Design');
  assert.equal(skillLabel('performance testing', 'performance testing'), 'Performance Testing');
  assert.equal(skillLabel('database-indexing', null, ['Experience with database indexing.']), 'Database Indexing');
  assert.equal(skillLabel('phan-tich-he-thong', 'phân tích hệ thống'), 'Phân tích hệ thống');
});

test('does not guess accents from an ambiguous or unrelated quote', () => {
  assert.equal(skillLabel('m-y', null, ['máy và mây']), 'm y');
  assert.equal(skillLabel('th-tr-ng-ch-ng-kho-n', null, ['Không có thông tin tương ứng.']), 'th tr ng ch ng kho n');
});
