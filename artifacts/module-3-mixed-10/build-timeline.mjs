import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const run = path.join(root, 'run');
const read = (file) => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const write = (name, obj) => fs.writeFileSync(path.join(run, name), `${JSON.stringify(obj, null, 2)}\n`);
const http = path.join(run, 'http');
const steps = fs.readdirSync(http).filter((name) => name.endsWith('.json')).map((name) => read(path.join(http, name)))
  .sort((left, right) => left.started_at_utc.localeCompare(right.started_at_utc));
const events = fs.readFileSync(path.join(run, 'components.jsonl'), 'utf8').trimEnd().split('\n').map(JSON.parse);
const byStep = new Map(steps.map((row) => [row.step, row]));
const bySeq = new Map(events.map((item) => [item.seq, item]));
const successes = steps.filter((row) => row.response.status === 200);
const snapshot = (row) => row?.response.body.snapshot;
const final = successes.at(-1);
const finalSnapshot = snapshot(final);
const labels = new Map(Object.entries(finalSnapshot.objectives).map(([id, state]) => [id, state.objective.skill_id]));

const rows = steps.map((row) => {
  const before = row.request.body.snapshot;
  const after = snapshot(row);
  const pending = after?.pending_turn;
  const route = row.request.path.split('/').at(-1);
  const answered = route === 'respond' && after?.turns.length > before?.turns.length ? after.turns.at(-1) : null;
  const observed = events.filter((item) => item.step === row.step);
  return {
    step: row.step, http_file: `http/${row.step}.json`, result_status: row.response.status,
    started_at_utc: row.started_at_utc, elapsed_seconds: row.elapsed_seconds, operation: route,
    scenario: row.scenario, snapshot_source_step: row.snapshot_source_step,
    action: row.request.body.action ?? null,
    version_before: before?.state_version ?? null, version_after: after?.state_version ?? null,
    phase_before: before?.conversation?.phase ?? null, phase_after: after?.conversation?.phase ?? null,
    queue_before: before?.queue ?? null, queue_after: after?.queue ?? null,
    progress_before: before?.turns.length ?? null, progress_after: after?.turns.length ?? null,
    error: after ? null : row.response.body,
    attempted_turn: route === 'respond' ? before.pending_turn : null,
    submitted_candidate_response: row.request.body.candidate_response ?? null,
    committed_turn: answered,
    uncommitted_assessments: after ? [] : observed.filter((item) => item.event === 'return' &&
      item.component === 'workflow.apply_judgment').map((item) => ({ seq: item.seq, call_id: item.call_id,
        judgment: bySeq.get(item.call_id).input.turn.judgment, state: status(item.mutated_arguments.state) })),
    next_turn: pending ?? null, next_probe_reason: pending ? after.objectives[pending.objective_id].probe_reason : null,
    termination_reason: after?.termination_reason ?? null,
    generated_message: after?.conversation?.message.message_id !== before?.conversation?.message.message_id
      ? after?.conversation?.message : null,
    objectives_changed: after ? Object.keys(after.objectives).flatMap((id) => {
      const previous = before?.objectives[id];
      const current = after.objectives[id];
      return JSON.stringify(previous) === JSON.stringify(current) ? [] : [{
        objective_id: id, skill_id: labels.get(id), selected_mode: current.selected_mode,
        before: previous ? status(previous) : null, after: status(current),
      }];
    }) : [],
    routing: observed.filter((item) => item.event === 'return' &&
      ['workflow.next_action', 'EvidenceWorkflow._should_yield', 'EvidenceWorkflow._reallocate'].includes(item.component)).map((item) => ({
      seq: item.seq, call_id: item.call_id, component: item.component, output: item.output,
      skill_id: bySeq.get(item.call_id).input.state?.objective.skill_id ?? null,
      selected_criterion_id: item.mutated_arguments?.state?.active_criterion_id ?? null,
      probe_reason: item.mutated_arguments?.state?.probe_reason ?? null,
    })),
    model_and_validation: observed.filter((item) => item.event !== 'call' &&
      (item.component?.startsWith('DSPyAssessmentProvider.') || item.component?.endsWith('validate_judgment') ||
       item.component === 'EvidenceWorkflow._question_attempt' ||
       (item.component === 'workflow.standalone_inability' && item.output))).map((item) => ({
      seq: item.seq, call_id: item.call_id, component: item.component, event: item.event,
      output: item.output, error: item.error,
    })),
    warnings: observed.filter((item) => item.event === 'log' && item.level === 'WARNING').map(({ seq, message }) => ({ seq, message })),
    trace_seq: [observed[0]?.seq ?? null, observed.at(-1)?.seq ?? null],
  };
});

function status(state) {
  const { objective, ...statusFields } = state;
  return statusFields;
}

function code(text) {
  const fence = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map(([ticks]) => ticks.length + 1)));
  return `${fence}\n${text}\n${fence}`;
}

function short(id) {
  return id?.split(':').at(-1) ?? '—';
}

function queue(ids) {
  return ids?.map((id) => `\`${labels.get(id)}\``).join(' → ') || '∅';
}

function stateLabel(state) {
  if (!state) return '—';
  return [state.lifecycle, state.assessment, `${state.turns_spent} lượt`, state.stop_reason ?? state.excluded_reason].filter(Boolean).join(' / ');
}

function renderTransition(row) {
  const answerNumber = row.attempted_turn ? row.progress_before + 1 : null;
  const title = answerNumber ? `Câu ${answerNumber} · ${row.attempted_turn.skill_id}${row.result_status !== 200 ? ' · lần lỗi' : ''}`
    : ({ '01-start': 'Tạo Blueprint, lập kế hoạch và mở đầu', '02-next': 'Chuyển sang tự giới thiệu',
         '03-intro': 'Nhận tự giới thiệu và sinh câu đầu' }[row.step] ?? 'Xác nhận xem kết quả');
  const lines = [`### ${row.step} · ${title}`, '', row.scenario, '',
    `\`POST /api/v2/interview/${row.operation}\` → HTTP ${row.result_status} trong ${row.elapsed_seconds} giây. ` +
    `[Request và response](run/${row.http_file}) · [Trace](run/components.jsonl) seq ${row.trace_seq.join('–')}.`, ''];
  if (row.attempted_turn) {
    const t = row.attempted_turn;
    lines.push(`**Câu hỏi thực tế** · \`${t.mode}\` / \`${t.action}\` / L${t.question_depth} / \`${short(t.question.criterion_ids[0])}\``,
      '', code(t.question.text), '', '**Câu trả lời giả lập đã gửi**', '', code(row.submitted_candidate_response), '');
  }
  const intro = byStep.get(row.step).request.body.introduction;
  if (intro) lines.push('**Phần tự giới thiệu giả lập đã gửi**', '', code(intro), '');
  if (row.generated_message) lines.push('**Lời thoại thực tế của hệ thống**', '', code(row.generated_message.text), '');
  if (row.error) lines.push('**Phản hồi lỗi thực tế**', '', code(JSON.stringify(row.error, null, 2)), '',
    `Lần gửi sử dụng v${row.version_before}. Response lỗi không có snapshot thay thế.`, '');
  else lines.push(`**Chuyển trạng thái** · ${row.version_before === null ? 'khởi tạo' : `v${row.version_before} / ${row.phase_before}`} → v${row.version_after} / ${row.phase_after}. Tổng số câu đã ghi nhận ${row.progress_after}.`, '');
  if (row.committed_turn) {
    const j = row.committed_turn.judgment;
    lines.push(`**Judgment đã ghi nhận** · \`explicit_inability=${j.explicit_inability}\` · \`feedback_contains_hint=${j.feedback_contains_hint}\``, '');
    for (const o of j.observations) {
      const quote = (o.response_excerpt || j.inability_excerpt).trim();
      lines.push(`- \`${short(o.criterion_id)}\` · \`${o.observation} / ${o.performance}\` · ${o.rationale}`);
      if (quote) lines.push(`  - Trích dẫn${o.response_line_range ? ` dòng ${o.response_line_range.join('–')}` : ''}`, '', ...code(quote).split('\n').map((line) => `    ${line}`), '');
      if (o.unresolved_aspects.length) lines.push(`  - Nội dung còn thiếu theo Judge · ${o.unresolved_aspects.join(' · ')}`);
    }
    const publicTurn = snapshot(byStep.get(row.step)) && byStep.get(row.step).response.body.public.turns.at(-1);
    lines.push('', `Phản hồi công khai của lượt · ${publicTurn.feedback ? `“${publicTurn.feedback}”` : 'rỗng'}.`, '');
  } else if (row.attempted_turn) {
    const provisional = row.model_and_validation.filter((item) => item.component === 'DSPyAssessmentProvider.judge' && item.output);
    for (const item of provisional) {
      const judgments = item.output.observations.map((o) => `\`${o.observation} / ${o.performance}\` · ${o.rationale}`);
      lines.push(`Judgment trong lần xử lý thất bại, seq ${item.seq} · ${judgments.join(' · ')}.`, '');
    }
    for (const item of row.uncommitted_assessments) {
      const observations = item.judgment.observations.map((o) => `\`${o.observation} / ${o.performance}\``).join(' · ');
      lines.push(`Bản sao trong bộ nhớ, seq ${item.seq} · ${observations} → ${stateLabel(item.state)}. API không trả bản sao này.`, '');
    }
  }
  if (row.queue_after) lines.push(`Hàng đợi · ${queue(row.queue_before)} → ${queue(row.queue_after)}.`, '');
  for (const item of row.objectives_changed) {
    lines.push(`- \`${item.skill_id}\` · ${stateLabel(item.before)} → ${stateLabel(item.after)}.`);
    const id = row.attempted_turn?.question.criterion_ids[0];
    const progress = item.after.criterion_progress[id];
    if (row.committed_turn && item.skill_id === row.attempted_turn.skill_id && progress) {
      const target = item.after.criterion_results[id];
      const added = item.after.evidence_history.length - (item.before?.evidence_history.length ?? 0);
      lines.push(`  - \`${short(id)}\` · ${progress.turns_spent} lượt, +${added} evidence ledger, target result \`${target?.performance ?? '∅'}\`, \`stagnant_turns=${progress.stagnant_turns}\`, contradiction ${item.after.contradictions.length}.`);
      lines.push(`  - Cờ tiêu chí · \`clarification_spent=${progress.clarification_spent}\`, \`easier_spent=${progress.easier_spent}\`, \`deeper_spent=${progress.deeper_spent}\`, \`stop_reason=${progress.stop_reason ?? 'null'}\`.`);
    }
  }
  if (row.objectives_changed.length) lines.push('');
  const decision = row.routing.map((item) => {
    const output = item.component.endsWith('_reallocate') ? 'chạy phân bổ lại' : `\`${item.output ?? 'null'}\``;
    return `- \`${item.component}\` (seq ${item.seq}) · ${item.skill_id ? `\`${item.skill_id}\` · ` : ''}${output}${item.probe_reason && item.output ? ` · ${item.probe_reason}` : ''}.`;
  });
  if (decision.length) lines.push('**Các lời gọi định tuyến quan sát được**', '', ...decision, '');
  if (row.warnings.length) lines.push('**Cảnh báo từ implementation**', '', ...row.warnings.map((item) => `- Seq ${item.seq} · ${item.message}`), '');
  const verdicts = row.model_and_validation.filter((item) => item.component === 'DSPyAssessmentProvider.review_question' && item.output);
  if (verdicts.length) lines.push(`Duyệt bản câu hỏi · ${verdicts.map((item) => `\`${item.output}\` (seq ${item.seq})`).join(' → ')}.`, '');
  if (row.next_turn) {
    const t = row.next_turn;
    lines.push(`**Câu tiếp theo** · \`${t.skill_id}\` / \`${t.mode}\` / \`${t.action}\` / L${t.question_depth} / \`${short(t.question.criterion_ids[0])}\`.`, '',
      `\`probe_reason\` · ${row.next_probe_reason}.`, '', code(t.question.text), '');
  }
  if (row.termination_reason) lines.push(`Lý do kết thúc phần chuyên môn · \`${row.termination_reason}\`.`, '');
  return lines.join('\n');
}

const finalReport = final.response.body.public.report;
write('timeline.json', { session_id: finalSnapshot.session_id, steps: rows });
write('final-report.json', finalReport);
const blueprintEvent = events.find((item) => item.component === 'BlueprintBuilder.build' && item.event === 'return');
if (blueprintEvent) write('blueprint.json', blueprintEvent.output);

if (finalSnapshot.conversation.phase === 'FINISHED') {
  const checked = [];
  function check(label, validate) {
    validate();
    checked.push(label);
  }
  check('MIXED thành công đủ 10 câu, đủ 5 dạng, kết thúc bằng QUESTION_BUDGET', () => {
    assert.equal(finalSnapshot.config.mode, 'MIXED');
    assert.equal(finalSnapshot.config.max_questions, 10);
    assert.equal(finalSnapshot.turns.length, 10);
    assert.equal(new Set(finalSnapshot.turns.map((t) => t.turn_id)).size, 10);
    assert.equal(new Set(finalSnapshot.turns.map((t) => t.mode)).size, 5);
    assert.equal(finalSnapshot.termination_reason, 'QUESTION_BUDGET');
    assert.equal(finalSnapshot.is_finished, true);
    assert.equal(finalSnapshot.pending_turn, null);
    assert.deepEqual(finalSnapshot.queue, []);
  });
  check('Mọi request chuyển trạng thái lấy snapshot nguyên vẹn và tăng đúng một version khi thành công', () => {
    for (const row of steps.filter((item) => item.snapshot_source_step)) {
      assert.deepEqual(row.request.body.snapshot, snapshot(byStep.get(row.snapshot_source_step)));
      assert.equal(row.request.body.expected_state_version, row.request.body.snapshot.state_version);
      if (row.response.status === 200) assert.equal(snapshot(row).state_version, row.request.body.expected_state_version + 1);
    }
  });
  check('Mỗi 503 đã được phục hồi bằng request nguyên văn và lưu đúng một turn', () => {
    for (const row of steps.filter((item) => item.response.status === 503)) {
      assert.equal(snapshot(row), undefined);
      const retry = steps.find((candidate) => candidate.started_at_utc > row.started_at_utc && candidate.response.status === 200 &&
        candidate.request.body.turn_id === row.request.body.turn_id);
      assert.ok(retry);
      assert.deepEqual(row.request.body, retry.request.body);
      assert.equal(finalSnapshot.turns.filter((t) => t.turn_id === row.request.body.turn_id).length, 1);
    }
  });
  check('Ledger liên kết được với turn, trích dẫn lưu là chuỗi con có trong câu trả lời tương ứng', () => {
    for (const state of Object.values(finalSnapshot.objectives)) {
      for (const evidence of state.evidence_history) {
        const turn = finalSnapshot.turns.find((t) => t.turn_id === evidence.turn_id);
        assert.ok(turn);
        assert.ok(turn.answer.includes(evidence.response_excerpt));
        assert.ok(turn.question.criterion_ids.includes(evidence.criterion_id));
      }
    }
  });
  check('JSONL có seq liên tục, mỗi call có chính xác một return hoặc error', () => {
    const open = new Set();
    events.forEach((item, index) => {
      assert.equal(item.seq, index + 1);
      if (item.event === 'call') open.add(item.seq);
      if (item.event === 'return' || item.event === 'error') assert.ok(open.delete(item.call_id));
    });
    assert.equal(open.size, 0);
    assert.ok(events.some((item) => item.component === 'dspy.execution.execute' && item.event === 'return' &&
      item.output.responses.length > 0 && item.output.cache_hit === false));
  });
  check('Timeline theo thứ tự request thực thi và khớp thứ tự trace', () => {
    rows.slice(1).forEach((row, index) => assert.ok(rows[index].trace_seq[1] < row.trace_seq[0]));
  });
  check('Snapshot cuối giữ nguyên báo cáo đã chốt ở CLOSING', () => {
    assert.equal(snapshot(successes.at(-2)).conversation.phase, 'CLOSING');
    assert.deepEqual(finalReport, successes.at(-2).response.body.public.report);
  });
  const live = path.join(run, 'live-final-transition.json');
  if (fs.existsSync(live)) check('POST trực tiếp đến cổng 8000 trả cùng kết quả FINISHED', () => {
    const comparison = read(live);
    assert.equal(comparison.response.status, 200);
    assert.deepEqual(comparison.request.body, final.request.body);
    assert.deepEqual(comparison.response.body, final.response.body);
  });
  write('verification.json', { result: 'PASS', verified_at_utc: new Date().toISOString(), checks: checked });
}
console.log(rows.map(renderTransition).join('\n'));
