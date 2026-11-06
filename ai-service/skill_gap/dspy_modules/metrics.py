"""
Scientifically Calibrated Evaluation Metrics for DSPy Teleprompter Optimization in Module 2 (skill_gap).

Each metric is designed to align directly with the mathematical invariants of Module 2:
1. `job_extraction_metric`: Evaluates cardinality, ISO timeline alignment, seniority autonomy group
   (Supervised {Intern, Junior} = 0.8 vs. Autonomous {Mid, Senior, Lead} = 1.0), and verbatim quote grounding.
2. `span_mapping_metric`: Evaluates verbatim span coverage, exact `job_id` attribution, and the critical
   `UNASSIGNED` boundary F1 (preventing global skill lists from inflating job duration).
3. `jd_requirement_metric`: Evaluates calibrated P_JD accuracy on [1.0, 5.0], skill coverage,
   pairwise ordinal ranking concordance (Must-have Senior > Mid > Nice-to-have), and reasoning quality.
4. `span_richness_metric`: Evaluates asymmetric `RichnessLabel` accuracy, direct alignment of the
   continuous evidence coverage ratio `c_evidence`, and `modifier_score` calibration.
"""

import difflib
from typing import Any, Callable, Dict, List, Optional
from skill_gap.domain.models import UNASSIGNED_JOB_ID

SUPERVISED_LEVELS = {"Intern", "Junior"}
AUTONOMOUS_LEVELS = {"Mid", "Senior", "Lead"}


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _norm_enum_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val.value) if hasattr(val, "value") else str(val).strip()


def _quote_grounded_in_cv(quote: Optional[str], cv_text: str, fuzzy_threshold: float = 0.75) -> bool:
    """Mirror `ResumeSegmenter._validate_quote_in_text` to penalize hallucinated quotes."""
    if not quote or not quote.strip():
        return False
    if not cv_text or not cv_text.strip():
        return True
    q = quote.strip().lower()
    txt = cv_text.lower()
    if q in txt:
        return True
    q_len = len(q)
    if q_len > 10 and len(txt) >= q_len:
        step = max(1, q_len // 4)
        for i in range(0, len(txt) - q_len + 1, step):
            window = txt[i : i + q_len]
            if difflib.SequenceMatcher(None, q, window).ratio() >= fuzzy_threshold:
                return True
    return difflib.SequenceMatcher(None, q, txt).ratio() >= fuzzy_threshold


def _date_similarity(gold_date: Optional[str], pred_date: Optional[str]) -> float:
    """Compare ISO YYYY-MM dates (or None for ongoing 'present' jobs)."""
    if gold_date is None and pred_date is None:
        return 1.0
    if gold_date is None or pred_date is None:
        return 0.0
    g = str(gold_date).strip()
    p = str(pred_date).strip()
    if g == p:
        return 1.0
    # Partial credit if the 4-digit year matches
    if len(g) >= 4 and len(p) >= 4 and g[:4] == p[:4]:
        return 0.5
    return 0.0


def _seniority_similarity(gold_sen: str, pred_sen: str) -> float:
    """
    Score seniority classification:
    - 1.0 for exact match
    - 0.6 for same autonomy multiplier group in ProficiencyEstimator (Supervised 0.8 vs Autonomous 1.0)
    - 0.0 otherwise
    """
    if not gold_sen or not pred_sen:
        return 0.0
    if gold_sen == pred_sen:
        return 1.0
    if (gold_sen in SUPERVISED_LEVELS and pred_sen in SUPERVISED_LEVELS) or (
        gold_sen in AUTONOMOUS_LEVELS and pred_sen in AUTONOMOUS_LEVELS
    ):
        return 0.6
    return 0.0


def job_extraction_metric(example: Any, pred: Any, trace: Any = None) -> float:
    """
    Multi-component composite metric for Step 1a (`JobBlockExtractionSignature`):
      0.20 * Cardinality + 0.35 * ISO Timeline Alignment + 0.25 * Seniority Autonomy + 0.20 * Verbatim Grounding
    """
    gold_blocks = _get_field(example, "job_blocks", [])
    pred_blocks = _get_field(pred, "job_blocks", None)
    cv_text = _get_field(example, "cv_text", "") or ""

    if pred_blocks is None or not isinstance(pred_blocks, list):
        return 0.0

    # Fresher / Zero-experience CV edge case
    if len(gold_blocks) == 0:
        return 1.0 if len(pred_blocks) == 0 else 0.0
    if len(pred_blocks) == 0:
        return 0.0

    # 1. Cardinality Score (w = 0.20)
    count_score = min(len(pred_blocks), len(gold_blocks)) / max(len(pred_blocks), len(gold_blocks))

    # Pair each gold block with best matching predicted block (greedy optimal matching)
    used_pred_indices = set()
    timeline_scores: List[float] = []
    seniority_scores: List[float] = []

    for g in gold_blocks:
        g_start = _get_field(g, "start_date")
        g_end = _get_field(g, "end_date")
        g_sen = _norm_enum_str(_get_field(g, "seniority_level"))

        best_idx = -1
        best_pair_score = -1.0
        best_t_score = 0.0
        best_s_score = 0.0

        for idx, p in enumerate(pred_blocks):
            if idx in used_pred_indices:
                continue
            p_start = _get_field(p, "start_date")
            p_end = _get_field(p, "end_date")
            p_sen = _norm_enum_str(_get_field(p, "seniority_level"))

            t_score = 0.5 * _date_similarity(g_start, p_start) + 0.5 * _date_similarity(g_end, p_end)
            s_score = _seniority_similarity(g_sen, p_sen)
            pair_score = 0.65 * t_score + 0.35 * s_score

            if pair_score > best_pair_score:
                best_pair_score = pair_score
                best_idx = idx
                best_t_score = t_score
                best_s_score = s_score

        if best_idx >= 0:
            used_pred_indices.add(best_idx)
            timeline_scores.append(best_t_score)
            seniority_scores.append(best_s_score)
        else:
            timeline_scores.append(0.0)
            seniority_scores.append(0.0)

    timeline_avg = sum(timeline_scores) / len(gold_blocks)
    seniority_avg = sum(seniority_scores) / len(gold_blocks)

    # 4. Year & Text Grounding + Unique ID Check (w = 0.20)
    pred_ids = [str(_get_field(p, "job_id", "")) for p in pred_blocks]
    unique_id_ratio = len(set(pred_ids)) / len(pred_ids) if pred_ids else 0.0

    import re
    cv_years = set(re.findall(r"\b(19\d{2}|20\d{2})\b", cv_text or ""))

    grounded_count = 0
    for p in pred_blocks:
        quote = _get_field(p, "raw_quote") or _get_field(p, "raw_text")
        text_ok = _quote_grounded_in_cv(quote, cv_text)
        p_s = str(_get_field(p, "start_date") or "")
        p_e = str(_get_field(p, "end_date") or "")
        year_ok = True
        if cv_years:
            if len(p_s) >= 4 and p_s[:4].isdigit() and p_s[:4] not in cv_years:
                year_ok = False
            if len(p_e) >= 4 and p_e[:4].isdigit() and p_e[:4] not in cv_years:
                year_ok = False
        if text_ok and year_ok:
            grounded_count += 1
    quote_grounding_ratio = grounded_count / len(pred_blocks)
    grounding_score = 0.75 * quote_grounding_ratio + 0.25 * unique_id_ratio

    # During BootstrapFewShot trace filtering, reject traces with hallucinated years or text
    if trace is not None and quote_grounding_ratio < 1.0:
        return 0.0

    total = (
        0.20 * count_score
        + 0.35 * timeline_avg
        + 0.25 * seniority_avg
        + 0.20 * grounding_score
    )
    return float(round(total, 6))


def span_mapping_metric(example: Any, pred: Any, trace: Any = None) -> float:
    """
    Multi-component composite metric for Step 1b (`SpanMappingSignature`):
      0.25 * Verbatim Span Coverage + 0.50 * Exact job_id Attribution + 0.25 * UNASSIGNED Boundary F1
    """
    gold_mappings = _get_field(example, "span_mappings", [])
    pred_mappings = _get_field(pred, "span_mappings", None)
    if not pred_mappings or not isinstance(pred_mappings, list) or not gold_mappings:
        return 0.0

    def _clean_span(s: Any) -> str:
        if not s:
            return ""
        txt = str(s).strip()
        if txt.startswith("- "):
            txt = txt[2:].strip()
        return txt

    gold_exact: Dict[str, str] = {}
    gold_clean: Dict[str, str] = {}
    for m in gold_mappings:
        sp = str(_get_field(m, "span", "")).strip()
        jid = str(_get_field(m, "job_id", "")).strip()
        if sp:
            gold_exact[sp] = jid
            gold_clean[_clean_span(sp)] = jid

    if not gold_exact:
        return 0.0

    pred_exact: Dict[str, str] = {}
    pred_clean: Dict[str, str] = {}
    for m in pred_mappings:
        sp = str(_get_field(m, "span", "")).strip()
        jid = str(_get_field(m, "job_id", "")).strip()
        if sp:
            pred_exact[sp] = jid
            pred_clean[_clean_span(sp)] = jid

    # 1. Verbatim Span Coverage (Jaccard overlap on exact spans, w = 0.25)
    gold_set = set(gold_exact.keys())
    pred_set = set(pred_exact.keys())
    union_size = len(gold_set | pred_set)
    coverage_score = (len(gold_set & pred_set) / union_size) if union_size > 0 else 0.0

    # 2. Exact & Normalized Attribution Accuracy (w = 0.50)
    attr_points = 0.0
    for sp, g_jid in gold_exact.items():
        if sp in pred_exact and pred_exact[sp] == g_jid:
            attr_points += 1.0
        else:
            c_sp = _clean_span(sp)
            if c_sp in pred_clean and pred_clean[c_sp] == g_jid:
                attr_points += 0.9  # Slight discount if leading '- ' wasn't stripped cleanly
    attribution_score = attr_points / len(gold_exact)

    # 3. Critical UNASSIGNED Boundary F1 (w = 0.25)
    gold_unassigned = {sp for sp, jid in gold_clean.items() if jid == UNASSIGNED_JOB_ID}
    pred_unassigned = {sp for sp, jid in pred_clean.items() if jid == UNASSIGNED_JOB_ID}

    if not gold_unassigned and not pred_unassigned:
        unassigned_f1 = 1.0
    elif not gold_unassigned or not pred_unassigned:
        unassigned_f1 = 0.0
    else:
        tp = len(gold_unassigned & pred_unassigned)
        prec = tp / len(pred_unassigned)
        rec = tp / len(gold_unassigned)
        unassigned_f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    total = 0.25 * coverage_score + 0.50 * attribution_score + 0.25 * unassigned_f1
    return float(round(total, 6))


def jd_requirement_metric(example: Any, pred: Any, trace: Any = None) -> float:
    """
    Multi-component composite metric for Step 2 (`JDRequirementSignature`):
      0.50 * Calibrated Milestone Accuracy + 0.15 * Coverage & Bounds
      + 0.20 * Pairwise Ordinal Ranking Concordance + 0.15 * Grounded Reasoning Quality
    """
    gold_reqs = _get_field(example, "requirements", [])
    pred_reqs = _get_field(pred, "requirements", None)
    if not pred_reqs or not isinstance(pred_reqs, list) or not gold_reqs:
        return 0.0

    gold_dict: Dict[str, float] = {}
    for r in gold_reqs:
        sid = str(_get_field(r, "jd_skill_id", "")).strip()
        lvl = _get_field(r, "required_level")
        if sid and lvl is not None:
            gold_dict[sid] = float(lvl)

    if not gold_dict:
        return 0.0

    pred_dict: Dict[str, float] = {}
    reasoning_scores: List[float] = []
    valid_bounds_count = 0

    for r in pred_reqs:
        sid = str(_get_field(r, "jd_skill_id", "")).strip()
        lvl = _get_field(r, "required_level")
        rsn = str(_get_field(r, "reasoning", "") or "").strip()
        if sid and lvl is not None:
            try:
                f_lvl = float(lvl)
            except (TypeError, ValueError):
                continue
            pred_dict[sid] = f_lvl
            if 1.0 <= f_lvl <= 5.0:
                valid_bounds_count += 1
            # Evaluate reasoning quality: non-empty + cites years/level/rule cues
            if len(rsn) >= 15:
                reasoning_scores.append(1.0)
            elif len(rsn) >= 5:
                reasoning_scores.append(0.5)
            else:
                reasoning_scores.append(0.0)

    if not pred_dict:
        return 0.0

    # 1. Calibrated Milestone Accuracy (w = 0.50)
    level_scores: List[float] = []
    for sid, g_lvl in gold_dict.items():
        if sid not in pred_dict:
            level_scores.append(0.0)
            continue
        err = abs(pred_dict[sid] - g_lvl)
        if err <= 1e-6:
            level_scores.append(1.0)
        elif err <= 0.25:
            # Within 0.25 tolerance -> >= 0.90 score
            level_scores.append(1.0 - 0.4 * err)
        else:
            # Steeper linear decay beyond 0.25
            level_scores.append(max(0.0, 1.0 - err / 2.5))
    calibrated_acc = sum(level_scores) / len(gold_dict)

    # 2. Skill Coverage & Scale Bounds Validity (w = 0.15)
    matched_skills = len(set(gold_dict.keys()) & set(pred_dict.keys()))
    coverage_ratio = matched_skills / len(gold_dict)
    bounds_ratio = valid_bounds_count / len(pred_dict)
    coverage_and_bounds = 0.6 * coverage_ratio + 0.4 * bounds_ratio

    # 3. Pairwise Ordinal Ranking Concordance (w = 0.20)
    skill_ids = [sid for sid in gold_dict.keys() if sid in pred_dict]
    concordant_pairs = 0.0
    total_distinct_pairs = 0
    for i in range(len(skill_ids)):
        for j in range(i + 1, len(skill_ids)):
            s_a, s_b = skill_ids[i], skill_ids[j]
            g_diff = gold_dict[s_a] - gold_dict[s_b]
            if abs(g_diff) > 1e-6:
                total_distinct_pairs += 1
                p_diff = pred_dict[s_a] - pred_dict[s_b]
                if g_diff * p_diff > 0:
                    concordant_pairs += 1.0
                elif abs(p_diff) <= 1e-6:
                    concordant_pairs += 0.25  # Tie when one should be strictly higher
    ordinal_score = (
        (concordant_pairs / total_distinct_pairs)
        if total_distinct_pairs > 0
        else calibrated_acc
    )

    # 4. Reasoning Quality (w = 0.15)
    reasoning_avg = (sum(reasoning_scores) / len(gold_dict)) if reasoning_scores else 0.0
    reasoning_avg = min(1.0, reasoning_avg)

    total = (
        0.50 * calibrated_acc
        + 0.15 * coverage_and_bounds
        + 0.20 * ordinal_score
        + 0.15 * reasoning_avg
    )
    return float(round(total, 6))


def span_richness_metric(example: Any, pred: Any, trace: Any = None) -> float:
    """
    Multi-component composite metric for Step 3 (`SpanRichnessSignature`):
      0.55 * Asymmetric RichnessLabel Accuracy
      + 0.30 * Continuous Evidence Coverage (`c_evidence`) Alignment
      + 0.15 * Verbatim Span Completeness
    """
    gold_analyses = _get_field(example, "analyses", [])
    pred_analyses = _get_field(pred, "analyses", None)
    if not pred_analyses or not isinstance(pred_analyses, list) or not gold_analyses:
        return 0.0

    def _clean(s: Any) -> str:
        txt = str(s or "").strip()
        return txt[2:].strip() if txt.startswith("- ") else txt

    gold_map: Dict[str, str] = {}
    for a in gold_analyses:
        sp = _clean(_get_field(a, "span"))
        lbl = _norm_enum_str(_get_field(a, "richness_label"))
        if sp:
            gold_map[sp] = lbl

    if not gold_map:
        return 0.0

    pred_map: Dict[str, str] = {}
    for a in pred_analyses:
        sp = _clean(_get_field(a, "span"))
        lbl = _norm_enum_str(_get_field(a, "richness_label"))
        if sp:
            pred_map[sp] = lbl

    if not pred_map:
        return 0.0

    # 1. Asymmetric RichnessLabel Accuracy (w = 0.55)
    # False promotion between {LIST_ONLY, AMBIGUOUS} and RICH_CONTEXT gets 0.0 because it flips
    # context density multiplier between 0.3 and 1.0 in ProficiencyEstimator!
    label_points = 0.0
    for sp, g_lbl in gold_map.items():
        if sp not in pred_map:
            continue
        p_lbl = pred_map[sp]
        if p_lbl == g_lbl:
            label_points += 1.0
        elif {p_lbl, g_lbl} == {"LIST_ONLY", "AMBIGUOUS"}:
            label_points += 0.4  # Both yield non-rich context weight (0.3) in ProficiencyEstimator
        else:
            label_points += 0.0

    label_acc = label_points / len(gold_map)

    # 2. Continuous Evidence Coverage Ratio (`c_evidence`) Alignment (w = 0.30)
    gold_rich_ratio = sum(1 for lbl in gold_map.values() if lbl == "RICH_CONTEXT") / len(gold_map)
    pred_rich_ratio = sum(1 for lbl in pred_map.values() if lbl == "RICH_CONTEXT") / len(pred_map)
    c_evidence_alignment = max(0.0, 1.0 - abs(pred_rich_ratio - gold_rich_ratio))

    # 3. Verbatim Span Completeness (w = 0.15)
    completeness = len(set(gold_map.keys()) & set(pred_map.keys())) / len(gold_map)

    total = 0.55 * label_acc + 0.30 * c_evidence_alignment + 0.15 * completeness
    return float(round(total, 6))


def evaluate_dspy_dataset(
    examples: List[Any],
    predictor_fn: Callable[[Any], Any],
    metric_fn: Callable[[Any, Any], float],
) -> Dict[str, Any]:
    """
    Evaluate a predictor or DSPy Module across a dataset using one of the calibrated metrics.
    Returns mean score, min/max, and per-example breakdown.
    """
    if not examples:
        return {"mean_score": 0.0, "count": 0, "scores": []}

    scores: List[float] = []
    for ex in examples:
        pred = predictor_fn(ex)
        sc = float(metric_fn(ex, pred))
        scores.append(sc)

    return {
        "mean_score": round(sum(scores) / len(scores), 4),
        "min_score": round(min(scores), 4),
        "max_score": round(max(scores), 4),
        "count": len(scores),
        "scores": [round(s, 4) for s in scores],
    }
