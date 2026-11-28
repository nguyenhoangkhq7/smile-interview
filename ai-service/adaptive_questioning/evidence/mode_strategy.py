"""Mode-specific questioning strategies, pacing defaults, and adaptive routing helpers."""
from __future__ import annotations

from .models import Action, Mode

_DEFAULT_SECONDS_BY_MODE: dict[Mode, int] = {
    Mode.CODING: 240,
    Mode.DESIGN: 240,
    Mode.DEBUGGING: 180,
    Mode.BEHAVIORAL: 150,
    Mode.TECHNICAL_EXPLANATION: 120,
}


def supports_easier_drop(mode: Mode) -> bool:
    """Behavioral STAR stories should be probed on missing STAR elements, not dropped to L1 theory."""
    return mode != Mode.BEHAVIORAL


def default_estimated_seconds(mode: Mode) -> int:
    """Realistic default objective duration by question mode."""
    return _DEFAULT_SECONDS_BY_MODE.get(mode, 120)


def question_guidance_for(
    *,
    mode: Mode,
    action: Action,
    interaction_mode: str,
    depth: int,
    has_history: bool,
    prior_coding_partial_failure: bool = False,
    prior_coding_zero_pass: bool = False,
) -> list[str]:
    """Return focused, mode-appropriate guidance instructions for question generation."""
    parts: list[str] = []
    if action == Action.EASIER:
        parts.append(
            "Simplify one decision from the preceding question. Keep its technical subject and make the "
            "prerequisite observable with a small new case. Do not substitute a generic definition, "
            "an unrelated task, or a question about why the candidate could not answer."
        )
    if mode == Mode.CODING:
        parts.extend(_coding_guidance(
            action, interaction_mode, has_history, prior_coding_partial_failure, prior_coding_zero_pass,
        ))
    elif mode == Mode.DEBUGGING:
        parts.extend(_debugging_guidance(action, has_history, prior_coding_partial_failure, prior_coding_zero_pass))
    elif mode == Mode.DESIGN:
        parts.extend(_design_guidance(action, has_history, interaction_mode))
    elif mode == Mode.BEHAVIORAL:
        parts.extend(_behavioral_guidance(action, has_history))
    elif mode == Mode.TECHNICAL_EXPLANATION:
        parts.extend(_technical_guidance(action, depth))
    return parts


def _coding_guidance(
    action: Action,
    interaction_mode: str,
    has_history: bool,
    prior_coding_partial_failure: bool,
    prior_coding_zero_pass: bool = False,
) -> list[str]:
    parts: list[str] = []
    if action == Action.DEEPER:
        parts.append(
            "Build on the prior coding problem/solution in history by changing one harder technical constraint "
            "(e.g. large or streaming input, bounded memory, concurrency, or time/space limit) and ask ONE "
            "focused question about adapting the algorithm/data structure or evaluating trade-offs for above_target. "
            "Do not ask the candidate to rewrite the basic function from scratch or split into separate deliverables."
        )
        return parts
    if action == Action.CLARIFY and (prior_coding_partial_failure or prior_coding_zero_pass):
        if prior_coding_partial_failure:
            parts.append(
                "The candidate's previous code passed some automated tests but failed an edge or logic case. "
                "Keep the exact same problem and ask the candidate to inspect and fix their submitted code for the "
                "failing behavior/edge case without revealing the fix or hidden test inputs."
            )
        else:
            parts.append(
                "The candidate's previous code failed automated tests (syntax/runtime error or incorrect return value). "
                "Keep the exact same problem and ask the candidate to trace and fix their submitted code without "
                "revealing the solution or hidden test inputs."
            )
        return parts
    if not has_history and action in {Action.INITIAL, Action.FOLLOW_UP}:
        if interaction_mode == "TEXT":
            parts.append(
                "State exact function signature/table columns and expected behavior concisely in natural Vietnamese. "
                "When asking for executable Python, JavaScript, or SQL code, populate `coding_spec` (language, "
                "entry_point or setup_sql, starter_code declaring the exact entry_point, 1–2 sample_tests, "
                "1–3 hidden_tests, and a concise verified `reference_solution`) so the sandbox can verify every "
                "test case before delivery. Never paste raw '-- Setup', '-- Entry Point', INSERT test rows, "
                "or 'Expected Output:' blocks into `question.text`—keep those strictly inside `coding_spec`."
            )
        else:
            parts.append(
                "For VOICE coding, when the task runs deterministically in Python, JavaScript, or SQL, you may "
                "populate `coding_spec` (including a concise `reference_solution`) so the candidate can type and "
                "dry-run code while explaining aloud; otherwise keep the task concise for oral walkthrough or typed pseudocode."
            )
    return parts


def _debugging_guidance(
    action: Action,
    has_history: bool,
    prior_coding_partial_failure: bool,
    prior_coding_zero_pass: bool = False,
) -> list[str]:
    parts: list[str] = []
    if action == Action.CLARIFY and (prior_coding_partial_failure or prior_coding_zero_pass):
        parts.append(
            "The candidate's previous fix still fails automated checks on this bug scenario. "
            "Ask them to trace and adjust their fix on the same scenario without giving away the answer."
        )
    elif not has_history and action in {Action.INITIAL, Action.FOLLOW_UP}:
        parts.append(
            "Provide the concrete buggy snippet, query, or log symptom AND the explicit intended behavior inline "
            "so the bug is unambiguously diagnosable. When asking for an executable Python, JavaScript, or SQL "
            "fix, optionally populate `coding_spec` with starter_code containing the buggy function/query, "
            "deterministic sample/hidden tests, and a concise verified `reference_solution`."
        )
    return parts


def _design_guidance(action: Action, has_history: bool, interaction_mode: str = "TEXT") -> list[str]:
    text_budget = (
        " In TEXT mode, up to ~110 Vietnamese words of prose is acceptable when needed to specify concrete "
        "scale, latency, or consistency constraints cleanly."
        if interaction_mode == "TEXT"
        else ""
    )
    if not has_history and action in {Action.INITIAL, Action.FOLLOW_UP}:
        return [
            "Frame a realistic, bounded system/component design scenario grounded in the JD domain with explicit "
            "key constraints (scale, latency, or consistency target) and ask for ONE core architectural decision "
            f"with its rationale.{text_budget}"
        ]
    if action in {Action.FOLLOW_UP, Action.DEEPER}:
        return [
            "Maintain continuity with the system architecture already discussed in history. Introduce ONE concrete "
            "scaling, failure-mode, consistency, or cost constraint and ask how the candidate adapts the design "
            f"and evaluates the resulting trade-off.{text_budget}"
        ]
    return []


def _behavioral_guidance(action: Action, has_history: bool) -> list[str]:
    if not has_history and action == Action.INITIAL:
        return [
            "Ask for one concrete past experience (work, internship, school, or personal project) relevant to the "
            "role so the candidate can demonstrate Situation/Task, their personal Action, and measurable Result."
        ]
    if action in {Action.CLARIFY, Action.FOLLOW_UP}:
        return [
            "Stay grounded in the candidate's own story from history and probe ONE missing STAR element "
            "(their specific personal decision/Action, measurable Result/impact, or concrete lesson learned) "
            "rather than switching to abstract definitions."
        ]
    if action == Action.DEEPER:
        return [
            "Build on the candidate's story from history to probe root-cause reflection, systemic prevention, "
            "or measurable team-level impact matching above_target."
        ]
    return []


def _technical_guidance(action: Action, depth: int) -> list[str]:
    if depth >= 2 and action in {Action.INITIAL, Action.FOLLOW_UP}:
        return [
            "Ground the technical question in a concrete practical scenario or failure/choice from the JD/CV "
            "rather than asking for a textbook definition."
        ]
    return []


def judge_guidance_for(
    mode: Mode,
    *,
    coding_passed: int | None = None,
    coding_total: int | None = None,
) -> str:
    """Return concise mode-specific evaluation axes for the Judge without altering signature fingerprints."""
    if mode == Mode.CODING:
        if coding_total is not None and coding_total > 0 and coding_passed is not None:
            if coding_passed < coding_total:
                return (
                    "CODING with failed automated tests: acknowledge valid algorithmic approach/complexity fairly, "
                    "and pinpoint the exact failing logic or boundary defect in rationale and unresolved_aspects "
                    "without leaking hidden test inputs."
                )
            return (
                "CODING with all automated tests passing: tests verify outputs only—explicitly verify time/space "
                "complexity, boundary handling, and code clarity against at_target."
            )
        return (
            "CODING semantic evaluation: trace the candidate's code or algorithm step-by-step on normal and edge "
            "cases (empty, duplicates, null/boundaries) and verify time/space complexity against at_target."
        )
    if mode == Mode.BEHAVIORAL:
        return (
            "BEHAVIORAL STAR evaluation: check Situation/Task, candidate's personal Action (not just team effort), "
            "and measurable Result or lesson. Quote ONE verbatim passage showing the clearest Action/Result and "
            "name any missing STAR component in unresolved_aspects."
        )
    if mode == Mode.DESIGN:
        return (
            "DESIGN evaluation axes: assess (1) stated assumptions/constraints, (2) architectural choices and data "
            "flow, and (3) bottlenecks, failure modes, and technical trade-offs. Name any missing axis in unresolved_aspects."
        )
    if mode == Mode.DEBUGGING:
        return (
            "DEBUGGING evaluation axes: distinguish accurate root-cause diagnosis from a safe fix and verification "
            "plan; confirm whether the candidate's explanation accounts for the observed symptom."
        )
    return (
        "TECHNICAL_EXPLANATION evaluation: verify accurate underlying mechanism and practical implications or "
        "trade-offs matching question_depth rather than surface-level buzzwords."
    )
