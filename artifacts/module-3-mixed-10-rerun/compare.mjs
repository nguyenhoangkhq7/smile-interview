import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const read = (file) => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const tally = (items) => Object.fromEntries(Array.from(new Set(items), (key) => [key, items.filter((item) => item === key).length]));

function stats(samples) {
  const sorted = [...samples].sort((left, right) => left - right);
  const size = sorted.length;
  return size ? { n: size, min: sorted[0], median: +((sorted[(size - 1) >> 1] + sorted[size >> 1]) / 2).toFixed(3),
    max: sorted.at(-1), samples } : { n: 0, min: null, median: null, max: null, samples: [] };
}

function compare(run) {
  const http = path.join(run, 'http');
  const requests = fs.readdirSync(http).filter((file) => file.endsWith('.json')).map((file) => read(path.join(http, file)))
    .sort((left, right) => left.started_at_utc.localeCompare(right.started_at_utc));
  const events = fs.readFileSync(path.join(run, 'components.jsonl'), 'utf8').trimEnd().split('\n').map(JSON.parse);
  const latest = requests.findLast((item) => item.response.status === 200)?.response.body.snapshot;
  const invokes = events.filter((item) => item.event === 'call' && item.component === 'dspy.execution.execute');
  const completed = events.filter((item) => item.event === 'return' && item.component?.startsWith('DSPyAssessmentProvider.'));
  const respond = requests.filter((item) => item.request.path.endsWith('/respond'));
  const successful = respond.filter((item) => item.response.status === 200);
  const operational = (component, step) => completed.filter((item) => item.step === step &&
    item.component === `DSPyAssessmentProvider.${component}`);
  const judgeRequests = completed.filter((item) => item.component === 'DSPyAssessmentProvider.judge');
  const modelCallsPerJudge = judgeRequests.map((item) => invokes.filter((invocation) => invocation.step === item.step &&
    invocation.seq > item.call_id && invocation.seq < item.seq).length);
  const sums = (steps, operations) => steps.flatMap(({ step }) => {
    const records = operations.flatMap((operation) => operational(operation, step));
    return records.length ? [+records.reduce((sum, item) => sum + item.elapsed_seconds, 0).toFixed(3)] : [];
  });
  return {
    session_id: latest?.session_id,
    transition_count: requests.length,
    states: tally(requests.map((item) => item.response.status)),
    failures: requests.filter((item) => item.response.status !== 200).map((item) => ({
      step: item.step, status: item.response.status, route: item.request.path, result: item.response.body,
    })),
    phase: latest?.conversation?.phase, state_version: latest?.state_version, total_answered: latest?.turns.length,
    termination_reason: latest?.termination_reason, question_modes: tally(latest?.turns.map((turn) => turn.mode) ?? []),
    question_actions: tally(latest?.turns.map((turn) => turn.action) ?? []),
    judge_labels: tally(latest?.turns.flatMap((turn) => turn.judgment.observations.map((o) => `${o.observation}/${o.performance}`)) ?? []),
    objectives: Object.values(latest?.objectives ?? {}).map((state) => ({ skill: state.objective.skill_id,
      assessment: state.assessment, stop_reason: state.stop_reason, excluded_reason: state.excluded_reason, turns: state.turns_spent })),
    start_seconds: requests.find((item) => item.request.path.endsWith('/start'))?.elapsed_seconds,
    start_model_calls: invokes.filter((item) => item.step === '01-start').length,
    first_question_seconds: requests.find((item) => item.request.body.action === 'SUBMIT_INTRODUCTION' &&
      item.response.status === 200)?.elapsed_seconds ?? null,
    total_model_calls: invokes.length,
    judge_attempts: judgeRequests.length,
    model_calls_per_judge: tally(modelCallsPerJudge),
    review_verdicts: tally(completed.filter((item) => item.component === 'DSPyAssessmentProvider.review_question').map((item) => item.output)),
    respond_count: respond.length,
    successful_respond_seconds: stats(successful.map((item) => item.elapsed_seconds)),
    successful_respond_judge_seconds: stats(sums(successful, ['judge'])),
    successful_respond_question_and_review_seconds: stats(sums(successful, ['question', 'review_question'])),
    all_respond_judge_seconds: stats(sums(respond, ['judge'])),
    all_respond_question_and_review_seconds: stats(sums(respond, ['question', 'review_question'])),
    coding_checks: events.filter((item) => item.event === 'return' && item.component === 'workflow.check_coding_answer' &&
      item.output).map(({ step, seq, output }) => ({ step, seq, output })),
  };
}

const summaries = { baseline: compare(path.join(root, '..', 'module-3-mixed-10', 'run')), rerun: [] };
for (const run of ['run', 'attempt-b/run', 'attempt-c/run']) {
  if (fs.existsSync(path.join(root, run, 'http'))) summaries.rerun.push({ run, ...compare(path.join(root, run)) });
}
fs.writeFileSync(path.join(root, 'comparison.json'), JSON.stringify(summaries, null, 2) + '\n');
console.log(JSON.stringify([summaries.baseline, ...summaries.rerun].map((data) => ({
  session: data.session_id, phase: data.phase, answered: data.total_answered, termination: data.termination_reason,
  status: data.states, start_seconds: data.start_seconds, start_model_calls: data.start_model_calls,
  first_question_seconds: data.first_question_seconds, judge_calls: data.model_calls_per_judge,
  judge: data.successful_respond_judge_seconds.median, next_question: data.successful_respond_question_and_review_seconds.median,
  respond: data.successful_respond_seconds.median, judge_in_respond_attempts: data.all_respond_judge_seconds.median,
  review: data.review_verdicts, coding: data.coding_checks,
})), null, 2));
