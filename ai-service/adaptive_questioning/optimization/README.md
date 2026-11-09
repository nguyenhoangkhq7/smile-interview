# DSPy optimization for evidence V2

This package preserves all 20 question cases and 20 candidate answers from the
original dataset, with its 14 train / 6 dev ordering. `examples.json` includes the
original questions, responses, source contexts, reasoning and source Git revision.
Tests pin SHA-256 digests of the original question/answer lists to guard against
silently replacing the recovered corpus.

`dataset.py` exposes `dspy.Example(context=..., question=Question(...))` and
`dspy.Example(context=..., judgment=Judgment(...))` matching the production V2
signatures. Source metadata is retained for audit, never supplied as extra model
output labels. Question demonstrations are shortened to one task. Historical CV
context is kept separately; only CV quotes enter `cv_evidence`. Depth is assigned
from the task, independently of the original JD proficiency score.

The old probability outputs, update labels and corresponding metrics are removed.
Judgment labels now distinguish supported/contradictory evidence from incomplete
or absent evidence; admitting no experience does not itself become a failed score.
These are curated demonstrations, not an independently validated benchmark, and
the split is **not disjoint by technology/domain**. No accuracy claim follows from
compiling or from examples passing their own labels.

One old positive Kubernetes annotation was corrected while retaining the answer:
memory request at 80% of limit does not establish Guaranteed QoS. The relevant
CPU/memory requests and limits must match; see the
[official Kubernetes requirements](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/).
This correction is recorded on the source case in `examples.json`.

## Compile offline

From `ai-service`:

```powershell
python -m adaptive_questioning.optimization.compiler
```

This uses `LabeledFewShot` on the **train** split and makes no LLM calls. It writes
`question_generator.json`, `reflective_judge.json` and `manifest.json` under
`adaptive_questioning/compiled_modules/`. The manifest records the current
signature/schema fingerprint and artifact hashes. Changed contracts or modified
artifacts require recompilation; legacy artifacts are not loaded.

## Use the compiled modules

```python
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider

provider = DSPyAssessmentProvider(
    compiled_dir="adaptive_questioning/compiled_modules",
)
```

The provider's blueprint generator is unchanged. Loading demos is **opt-in**;
normal production construction without `compiled_dir` continues to use source
signatures. Checked-in artifacts are seeded labeled examples, not evidence of an
improvement in model quality. Evaluate with the intended model before enabling.

## Online optimization and held-out evaluation

These operations invoke the configured LM and can incur costs:

```powershell
python -m adaptive_questioning.optimization.compiler --bootstrap --evaluate
```

Use `compile_with_bootstrap_few_shot(lm=student, judge_lm=teacher)` in Python to
choose a separate semantic evaluator. Without it the CLI uses the same LM in a
separate evaluator role. Bootstrap uses train only, with an explicit default
acceptance threshold of 0.8. Evaluation uses dev/val only and reports failed
module executions as zero scores.

Question metrics first enforce the production metadata, one-task and voice-length
contracts. The offline lexical proxy has a ceiling of 0.7 and cannot certify depth;
online evaluation checks relevance, one intent and appropriate depth with an LM.
Judgment metrics validate excerpts and criterion IDs, compare observation/performance
labels and missing-evidence status, and optionally audit supporting rationale and
feedback for hints using the evaluator. These checks do not make subjective labels
objective ground truth or replace an expert review of the corpus.

## Tests

```powershell
python -m pytest tests_adaptive_questioning/test_dspy_optimization.py -q
```

Tests use local examples and `DummyLM`: no real API calls. They cover preservation,
train/dev separation, runtime contracts, bad evidence/metadata, semantic evaluator
gates, compilation, artifact compatibility and actual provider calls after loading.
