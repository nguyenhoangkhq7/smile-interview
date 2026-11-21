"""Build 100 Fixed Paired Test Cases for Module 3 (CV Verification Ablation & Adaptive Questioning).

Reads all 100 accepted CV-JD pairs directly from `synthetic_cv_jd_dataset_v2`
(`raw/jobs.jsonl`, `raw/resumes.jsonl`, `processed/accepted_pairs.jsonl`) — the exact
same 100 pairs evaluated in Module 1 and Module 2.

For each of the 100 pairs:
1. Extracts candidate CV skills & verbatim CV spans purely from raw `cv_text` (pair-blind
   global skill lexicon, 100% `span in cv_text`, ZERO leakage of synthetic labels).
2. Extracts JD requirement skills & verbatim JD spans from raw `jd_text` (100% `span in jd_text`).
3. Selects ONE target skill requirement per pair, stratified across 3 evidence groups:
   - `PARTIAL_DETAIL`: CV mentions skill (`met_light`, `partial_years`, `partial_adjacent`)
     with verified verbatim CV spans, leaving implementation/depth details open.
   - `NO_CV_EVIDENCE`: CV lacks matching evidence (`missing` / `MISSING` alignment / empty spans).
   - `STRONG_CONTROL`: CV already provides strong evidence (`met_strong` with verbatim CV spans),
     acting as a control group to test avoiding unnecessary clarification.
4. Assigns all 100 cases evenly across 4 controlled adaptive response scenarios (25 each):
   - `SUFFICIENT` (25), `VAGUE` (25), `CONTRADICT_CV` (25, strictly from cases with verified CV
     spans), and `NO_EXPERIENCE` (25).
5. Builds and freezes ONE shared `Blueprint` per unique `(jd_id, skill_id)` using the production
   `BlueprintBuilder` so all 3 experimental conditions share identical criteria, depth, and budget.
6. Generates and freezes ONE realistic Vietnamese scripted candidate response tailored to
   criterion c1 (using an independent generator `google/gemini-2.5-flash`) for identical Turn-2
   replay across all 3 conditions.

STRICT ANTI-LEAKAGE: Synthetic `target_status` labels are used ONLY for case selection and
stratification, stored in `reference_metadata`, and NEVER injected into any prompt.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import re
import sys
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
import numpy as np
import openai

ai_service_dir = Path(__file__).resolve().parents[2]
if str(ai_service_dir) not in sys.path:
    sys.path.insert(0, str(ai_service_dir))

from adaptive_questioning.evidence.models import (
    BlueprintRequest,
    InterviewSkill,
)
from adaptive_questioning.evidence.policy_config import InterviewPolicy
from adaptive_questioning.evidence.provider import DSPyAssessmentProvider
from adaptive_questioning.evidence.workflow import EvidenceWorkflow
from adaptive_questioning.optimization.compiler import DEFAULT_COMPILED_DIR
from matching_cv.app.core.config import settings as matching_settings
from matching_cv.app.core.model_loader import ModelLoader
from matching_cv.app.services.standardized_output_builder import _classify_semantic_relation_category
from matching_cv.research.data.canonical_skill_normalizer import (
    CANONICAL_ALIASES,
    normalize_canonical_skill,
)
from matching_cv.research.paper_aligned_gnn.skill_dependency_resolver import (
    CURATED_SKILL_PREREQUISITE_DAG,
)
from skill_gap.domain.models import JobTask

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_module3_cases")


def _fallback_terms(req_text: str) -> List[str]:
    low = req_text.lower()
    if "data science" in low or "machine learning engineering" in low:
        return ["Data Science", "Machine Learning Engineering"]
    cleaned = re.sub(r"^(?:minimum of|at least)\s+\d+\+?\s+years?\s+(?:in|of)\s+(?:a\s+)?", "", req_text, flags=re.I)
    return [cleaned.strip()[:60] or "domain experience"]


def _find_verbatim_jd_span(jd_text: str, jd_quote: str, req_text: str) -> str:
    if jd_quote and jd_quote in jd_text:
        return jd_quote
    if jd_quote:
        words = [w for w in re.split(r"\s+", jd_quote.strip()) if w]
        if words:
            pat = r"\s*[\*_`]*\s*[\*_`]*".join(re.escape(w) for w in words)
            m = re.search(pat, jd_text, flags=re.IGNORECASE)
            if m and m.group(0).strip() in jd_text:
                return m.group(0).strip()
    req_tokens = set(re.findall(r"[a-z0-9\+\#\.]{2,}", (jd_quote or req_text).lower()))
    best_line, best_ov = "", -1
    for raw_line in jd_text.splitlines():
        line = raw_line.strip()
        if len(line) < 15:
            continue
        ov = len(req_tokens & set(re.findall(r"[a-z0-9\+\#\.]{2,}", line.lower())))
        if ov > best_ov:
            best_ov, best_line = ov, line
    return best_line if best_line and best_line in jd_text else jd_text.splitlines()[0].strip()


def _split_skill_list_line(line: str) -> List[str]:
    cleaned = re.sub(r"^[•\-\*\u2022]+\s*", "", line).strip()
    cleaned = re.sub(r"^\*{1,2}([^*]+)\*{1,2}\s*:\s*", "", cleaned).strip()
    cleaned = re.sub(
        r"^(?:Languages|Programming Languages|Frameworks|Libraries|Cloud|Cloud Platforms|Databases|Tools|Other|Concepts|Operating Systems|DevOps|Methodologies|Soft Skills|Backend|Frontend|Mobile|Data|ML|AI|Security|Networking|Testing|Architecture)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    out: List[str] = []
    for p in re.split(r"[,|;]", cleaned):
        p = re.sub(
            r"\s*\((?:basic|expert|advanced|proficient|beginner|intermediate|working|familiar|light exposure|\d+\+?\s*years?|years?)\)",
            "",
            p.strip(),
            flags=re.IGNORECASE,
        ).strip(".*•- ")
        if 2 <= len(p) <= 60:
            out.append(p)
    return out


def _parse_cv_skills_section(cv_text: str) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    in_sec = False
    hdr = re.compile(
        r"^(?:\*{0,2})(?:TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|SKILLS|RELEVANT\s+COURSEWORK|KEY\s+SKILLS|SKILLS\s*&\s*TOOLS|TECHNOLOGIES)(?:\*{0,2})\s*:?\s*(.*)$",
        re.IGNORECASE,
    )
    stop = re.compile(
        r"^(?:\*{0,2})(?:EDUCATION|EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|WORK\s+EXPERIENCE|PROJECTS|CERTIFICATIONS|ACTIVITIES|REFERENCES|AWARDS|PUBLICATIONS|SUMMARY|OBJECTIVE)(?:\*{0,2})\s*:?$",
        re.IGNORECASE,
    )
    for raw_line in cv_text.splitlines():
        st = raw_line.strip()
        if not st:
            in_sec = False
            continue
        m = hdr.match(st)
        if m:
            in_sec = True
            if m.group(1).strip():
                for tok in _split_skill_list_line(m.group(1).strip()):
                    results.append((tok, st))
            continue
        if stop.match(st):
            in_sec = False
            continue
        if in_sec:
            for tok in _split_skill_list_line(st):
                results.append((tok, st))
    return results


def _build_compiled_lexicon(
    jobs: Dict[str, Dict[str, Any]],
    resumes: Dict[str, Dict[str, Any]],
) -> List[Tuple[str, str, re.Pattern[str]]]:
    term_to_canon: Dict[str, str] = {}

    def _add(term: str) -> None:
        t = term.strip()
        if len(t) < 2 or t.lower() in {"and", "the", "for", "with", "from", "using", "other", "basic", "senior", "junior"}:
            return
        c = normalize_canonical_skill(t)
        if c and len(c) >= 2:
            term_to_canon.setdefault(t, c)

    for a in CANONICAL_ALIASES:
        _add(a)
        _add(a.replace("-", " "))
    for s, d in CURATED_SKILL_PREREQUISITE_DAG:
        _add(s.replace("-", " "))
        _add(d.replace("-", " "))
    for job in jobs.values():
        for req in job.get("requirements", []):
            for t in (req.get("skill_terms") or _fallback_terms(req.get("text", ""))):
                _add(t)
                base_t = re.sub(r"\s*\([^)]*\)", "", t).strip()
                if base_t and base_t != t:
                    _add(base_t)
    for res in resumes.values():
        for ph, _ in _parse_cv_skills_section(res.get("cv_text", "")):
            _add(ph)

    items = sorted(term_to_canon.items(), key=lambda kv: (-len(kv[0]), kv[0].lower()))
    return [(s, c, re.compile(r"(?<!\w)" + re.escape(s) + r"(?!\w)", re.IGNORECASE)) for s, c in items]


def _extract_cv_skills(
    cv_text: str,
    compiled_lexicon: List[Tuple[str, str, re.Pattern[str]]],
) -> Dict[str, Dict[str, Any]]:
    canon_spans: Dict[str, List[str]] = defaultdict(list)
    canon_name: Dict[str, str] = {}

    for ph, line in _parse_cv_skills_section(cv_text):
        c = normalize_canonical_skill(ph)
        if c and len(c) >= 2 and line in cv_text:
            if line not in canon_spans[c]:
                canon_spans[c].append(line)
            canon_name.setdefault(c, ph)

    for raw_line in cv_text.splitlines():
        line = raw_line.strip()
        if len(line) < 3 or line not in cv_text:
            continue
        for surf, c, pat in compiled_lexicon:
            if pat.search(line):
                if line not in canon_spans[c]:
                    canon_spans[c].append(line)
                if c not in canon_name or (len(surf) > len(canon_name[c]) and len(surf) <= 40):
                    canon_name[c] = surf

    return {
        c: {"skill_id": c, "skill_name": canon_name.get(c, c), "evidence_spans": spans}
        for c, spans in canon_spans.items()
        if spans
    }


class _SBERTCache:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.cache: Dict[str, np.ndarray] = {}

    def cosine(self, a: str, b: str) -> float:
        def _vec(s: str) -> np.ndarray:
            k = s.strip().lower()
            if k not in self.cache:
                v = np.asarray(self.model.encode(s.strip()), dtype=np.float32)
                n = float(np.linalg.norm(v))
                self.cache[k] = v / n if n > 1e-12 else v
            return self.cache[k]
        return float(np.clip(np.dot(_vec(a), _vec(b)), 0.0, 1.0))


def _prepare_pair_skill_candidates(
    pair: Dict[str, Any],
    job: Dict[str, Any],
    res: Dict[str, Any],
    compiled_lexicon: List[Tuple[str, str, re.Pattern[str]]],
    sbert: _SBERTCache,
) -> Dict[str, Dict[str, Any]]:
    """Compute leak-free Module 1 matches and candidate skill options for one pair."""
    cv_text = res["cv_text"]
    jd_text = job["jd_text"]
    cv_map = _extract_cv_skills(cv_text, compiled_lexicon)
    ts_map = pair.get("construction", {}).get("target_statuses", {})
    min_soft = float(matching_settings.SKILL_GAP_MIN_SOFT_MATCH)

    out: Dict[str, Dict[str, Any]] = {}
    seen_ids: Set[str] = set()
    for req in job["requirements"]:
        rid = req["req_id"]
        terms = req.get("skill_terms") or _fallback_terms(req.get("text", ""))
        sid = normalize_canonical_skill(terms[0])
        if sid in seen_ids:
            sid = f"{sid}_{rid}"
        seen_ids.add(sid)

        canon_terms = [normalize_canonical_skill(t) for t in terms if t.strip()]
        jd_span = _find_verbatim_jd_span(jd_text, req.get("jd_quote", ""), req.get("text", ""))
        assert jd_span in jd_text

        matched_cv_id = "none"
        soft_match = 0.0
        if cv_map:
            if sid in cv_map:
                matched_cv_id, soft_match = sid, 1.0
            else:
                sec = [c for c in canon_terms if c in cv_map]
                if sec:
                    matched_cv_id, soft_match = sec[0], 1.0
                else:
                    best_id, best_sim = "none", 0.0
                    for cid, cinfo in cv_map.items():
                        if _classify_semantic_relation_category(sid, cid, False) == "confusable_distinct_or_unrelated_guard":
                            continue
                        clabel = cinfo["skill_name"]
                        for t in terms:
                            sim = sbert.cosine(t, clabel)
                            if sim > best_sim:
                                best_sim, best_id = sim, cid
                    if best_sim >= min_soft:
                        matched_cv_id, soft_match = best_id, best_sim

        align = "MATCH" if soft_match >= 0.85 else ("PARTIAL" if soft_match >= 0.40 else "MISSING")
        cv_spans: List[str] = []
        matched_cv_name = ""
        if align != "MISSING" and matched_cv_id in cv_map:
            cv_spans = [sp for sp in cv_map[matched_cv_id]["evidence_spans"] if sp in cv_text][:4]
            matched_cv_name = cv_map[matched_cv_id]["skill_name"]

        is_crit = bool(req.get("is_critical", False))
        req_type = str(req.get("type", "mandatory")).lower()
        min_yrs = int(req.get("min_years") or 0)
        w_j = 0.85 if is_crit else (0.65 if req_type == "mandatory" else 0.35)
        if min_yrs >= 3:
            w_j = min(1.0, w_j + 0.05)
        req_prof = 4.5 if (is_crit or min_yrs >= 5) else (3.5 if (min_yrs >= 3 or req_type == "mandatory") else 2.5)

        out[sid] = {
            "skill_id": sid,
            "skill_name": ", ".join(terms),
            "req_id": rid,
            "req_type": req_type,
            "is_critical": is_crit,
            "min_years": min_yrs,
            "w_j": round(w_j, 4),
            "required_proficiency": req_prof,
            "soft_match": round(soft_match, 6),
            "semantic_alignment": align,
            "matched_cv_skill_id": matched_cv_id,
            "matched_cv_skill_name": matched_cv_name,
            "cv_evidence_spans": cv_spans,
            "jd_evidence_spans": [jd_span],
            "target_status": ts_map.get(rid, "missing"),
        }
    return out


def _select_100_cases(
    pairs: List[Dict[str, Any]],
    pair_skill_maps: List[Dict[str, Dict[str, Any]]],
) -> List[Tuple[int, str, str]]:
    """Select 1 target skill per pair balanced across PARTIAL_DETAIL (~50), NO_CV_EVIDENCE (~25), STRONG_CONTROL (~25)."""
    targets = {"PARTIAL_DETAIL": 50, "NO_CV_EVIDENCE": 25, "STRONG_CONTROL": 25}
    group_counts: Counter[str] = Counter()

    pair_options: List[Tuple[int, Dict[str, str]]] = []
    for idx, smap in enumerate(pair_skill_maps):
        opts: Dict[str, str] = {}
        # PARTIAL_DETAIL
        p_cands = [
            (v["w_j"] + (0.15 if v["target_status"] in {"partial_years", "partial_adjacent"} else 0.0), k)
            for k, v in smap.items()
            if v["target_status"] in {"met_light", "partial_years", "partial_adjacent"}
            and v["semantic_alignment"] != "MISSING" and v["cv_evidence_spans"]
        ]
        if p_cands:
            p_cands.sort(key=lambda x: (-x[0], x[1]))
            opts["PARTIAL_DETAIL"] = p_cands[0][1]

        # NO_CV_EVIDENCE
        m_cands = [
            (v["w_j"], k)
            for k, v in smap.items()
            if v["target_status"] == "missing" and (v["semantic_alignment"] == "MISSING" or not v["cv_evidence_spans"])
        ]
        if m_cands:
            m_cands.sort(key=lambda x: (-x[0], x[1]))
            opts["NO_CV_EVIDENCE"] = m_cands[0][1]

        # STRONG_CONTROL
        s_cands = [
            (v["w_j"], k)
            for k, v in smap.items()
            if v["target_status"] == "met_strong" and v["semantic_alignment"] != "MISSING" and v["cv_evidence_spans"]
        ]
        if s_cands:
            s_cands.sort(key=lambda x: (-x[0], x[1]))
            opts["STRONG_CONTROL"] = s_cands[0][1]

        pair_options.append((idx, opts))

    assigned: Dict[int, Tuple[int, str, str]] = {}
    for idx, opts in sorted(pair_options, key=lambda x: (len(x[1]), x[0])):
        if not opts:
            first_k = next(iter(pair_skill_maps[idx].keys()))
            assigned[idx] = (idx, first_k, "NO_CV_EVIDENCE")
            group_counts["NO_CV_EVIDENCE"] += 1
            continue
        best_g = max(opts.keys(), key=lambda g: (targets[g] - group_counts[g], g == "PARTIAL_DETAIL"))
        assigned[idx] = (idx, opts[best_g], best_g)
        group_counts[best_g] += 1

    logger.info(f"Stratified 100 cases by evidence group: {dict(group_counts)}")
    return [assigned[i] for i in range(len(pairs))]


def _assign_scenarios_25x4(selected: List[Tuple[int, str, str]], seed: int = 42) -> List[str]:
    rng = random.Random(seed)
    n = len(selected)
    assert n == 100
    has_cv = [i for i, (_, _, grp) in enumerate(selected) if grp in {"PARTIAL_DETAIL", "STRONG_CONTROL"}]
    no_cv = [i for i, (_, _, grp) in enumerate(selected) if grp == "NO_CV_EVIDENCE"]
    rng.shuffle(has_cv)
    rng.shuffle(no_cv)

    scenarios: List[Optional[str]] = [None] * n

    # 25 CONTRADICT_CV strictly from cases WITH verified CV spans
    p_idx = [i for i in has_cv if selected[i][2] == "PARTIAL_DETAIL"]
    s_idx = [i for i in has_cv if selected[i][2] == "STRONG_CONTROL"]
    c_pool = p_idx[:15] + s_idx[:10]
    if len(c_pool) < 25:
        c_pool.extend([i for i in has_cv if i not in c_pool][: 25 - len(c_pool)])
    for i in c_pool[:25]:
        scenarios[i] = "CONTRADICT_CV"

    # 25 NO_EXPERIENCE (mix of NO_CV_EVIDENCE and CV-present)
    rem_no_cv = [i for i in no_cv if scenarios[i] is None]
    rem_has_cv = [i for i in has_cv if scenarios[i] is None]
    ne_pool = rem_no_cv[:13] + rem_has_cv[:12]
    if len(ne_pool) < 25:
        ne_pool.extend([i for i in range(n) if scenarios[i] is None and i not in ne_pool][: 25 - len(ne_pool)])
    for i in ne_pool[:25]:
        scenarios[i] = "NO_EXPERIENCE"

    # Split remaining 50 evenly into 25 SUFFICIENT and 25 VAGUE
    rem = sorted([i for i in range(n) if scenarios[i] is None], key=lambda i: (selected[i][2], i))
    for pos, i in enumerate(rem):
        scenarios[i] = "SUFFICIENT" if pos % 2 == 0 else "VAGUE"

    counts = Counter(scenarios)
    assert all(counts[s] == 25 for s in ("SUFFICIENT", "VAGUE", "CONTRADICT_CV", "NO_EXPERIENCE")), f"Got {counts}"
    logger.info(f"Balanced 25x4 scenario counts: {dict(counts)}")
    return [str(s) for s in scenarios]


def _generate_scripted_answer(
    client: openai.OpenAI,
    model: str,
    *,
    scenario: str,
    skill_name: str,
    jd_claim: str,
    criterion: Dict[str, Any],
    cv_spans: List[str],
    target_depth: int,
) -> str:
    instructions = {
        "SUFFICIENT": (
            f"Write a concrete Vietnamese candidate answer (3-5 sentences) that COMPLETELY satisfies "
            f"`expected_evidence` and `at_target` at depth L{target_depth}. Include concrete technical mechanisms "
            f"so a strict rubric judge marks it AT_TARGET with zero unresolved gaps."
        ),
        "VAGUE": (
            "Write a short, vague Vietnamese candidate answer (1-2 sentences) using high-level buzzwords ONLY, "
            "deliberately omitting the concrete mechanism/evidence required by `expected_evidence` and `at_target` "
            "so the interviewer must ask a targeted follow-up clarification."
        ),
        "CONTRADICT_CV": (
            "Write a realistic Vietnamese candidate answer (2-3 sentences) that DIRECTLY CONTRADICTS what is claimed "
            "in the CV excerpts (e.g., stating a conflicting/wrong mechanism matching `below_target` or admitting "
            "someone else handled the claimed technical responsibility)."
        ),
        "NO_EXPERIENCE": (
            "Write a polite, natural Vietnamese candidate answer (1-2 sentences) explicitly stating they have NOT "
            "worked on this topic in practice and lack experience to answer it (do not guess a technical solution)."
        ),
    }
    prompt = (
        f"Generate ONE controlled synthetic candidate response in natural Vietnamese.\n"
        f"Scenario: {scenario}\nInstruction: {instructions[scenario]}\n\n"
        f"Target skill: {skill_name}\nJD task: {jd_claim}\n"
        f"Primary criterion (c1): description={criterion['description']} | expected_evidence={criterion['expected_evidence']} "
        f"| below_target={criterion['below_target']} | at_target={criterion['at_target']}\n"
        f"CV excerpts: {json.dumps(cv_spans, ensure_ascii=False)}\n\n"
        f"Return STRICT JSON: {{\"candidate_answer\": \"...\"}}."
    )
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                seed=42,
                max_tokens=300,
            )
            ans = str(json.loads(resp.choices[0].message.content.strip()).get("candidate_answer", "")).strip()
            if len(ans) >= 10:
                return ans
        except Exception as exc:
            logger.warning(f"Scripted answer retry {attempt + 1}/3 failed: {exc}")

    if scenario == "NO_EXPERIENCE":
        return "Phần này trước đây em chưa trực tiếp triển khai trong dự án thực tế nên hiện em chưa có kinh nghiệm xử lý ạ."
    if scenario == "VAGUE":
        return f"Ở dự án trước em có làm phần {skill_name} rồi, chủ yếu em theo chuẩn chung của nhóm và kiểm tra cơ bản là chạy ổn ạ."
    if scenario == "CONTRADICT_CV":
        return f"Dù trên CV có nhắc đến {skill_name}, nhưng phần đó thành viên khác làm chính, em chỉ dùng lại cấu hình có sẵn chứ không trực tiếp thiết kế hay xử lý."
    return f"Trong dự án trước về {skill_name}, em đã triển khai chi tiết đúng theo hướng: {criterion['at_target']}."


def build_cases(
    dataset_root: Path,
    output_path: Path,
    *,
    answer_model: str = "google/gemini-2.5-flash",
    workers: int = 6,
    seed: int = 42,
) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root.parent / ".env", override=False)
    load_dotenv(root / ".env", override=False)

    jobs = {
        j["jd_id"]: j
        for j in (json.loads(l) for l in open(dataset_root / "raw" / "jobs.jsonl", encoding="utf-8") if l.strip())
    }
    resumes = {
        r["cv_id"]: r
        for r in (json.loads(l) for l in open(dataset_root / "raw" / "resumes.jsonl", encoding="utf-8") if l.strip())
    }
    pairs = [
        json.loads(l)
        for l in open(dataset_root / "processed" / "accepted_pairs.jsonl", encoding="utf-8")
        if l.strip()
    ]
    logger.info(f"Loaded {len(jobs)} JDs, {len(resumes)} CVs, {len(pairs)} accepted pairs from {dataset_root}.")

    compiled_lexicon = _build_compiled_lexicon(jobs, resumes)
    logger.info("Loading Module 1 SBERT model for leak-free skill matching...")
    sbert = _SBERTCache(ModelLoader().load_model())

    pair_skill_maps = [
        _prepare_pair_skill_candidates(p, jobs[p["jd_id"]], resumes[p["cv_id"]], compiled_lexicon, sbert)
        for p in pairs
    ]

    selected = _select_100_cases(pairs, pair_skill_maps)
    scenarios = _assign_scenarios_25x4(selected, seed=seed)

    # Build InterviewSkill objects & unique shared JD blueprints
    provider = DSPyAssessmentProvider(compiled_dir=str(DEFAULT_COMPILED_DIR))
    workflow = EvidenceWorkflow(provider, policy=InterviewPolicy(allow_extension_probes=False))

    case_skills: List[Tuple[InterviewSkill, Dict[str, str], Dict[str, str], Dict[str, Any]]] = []
    unique_bp_inputs: Dict[str, InterviewSkill] = {}

    for idx, sid, _ in selected:
        p = pairs[idx]
        jid = p["jd_id"]
        sinfo = pair_skill_maps[idx][sid]
        jd_spans = sinfo["jd_evidence_spans"]
        cv_spans = sinfo["cv_evidence_spans"]
        req_kind = "REQUIRED" if sinfo["req_type"] == "mandatory" else "OPTIONAL"
        jtask = JobTask(
            task_id=sinfo["req_id"],
            description=jd_spans[0],
            evidence_spans=jd_spans,
            required_level=sinfo["required_proficiency"],
            requirement_kind=req_kind,
            level_basis="EXPLICIT",
        )
        isk = InterviewSkill(
            jd_skill_id=sid,
            jd_skill_name=sinfo["skill_name"][:200],
            matched_cv_skill_name=sinfo["matched_cv_skill_name"][:200],
            semantic_alignment=sinfo["semantic_alignment"],
            context_job="",
            cv_evidence_spans=cv_spans,
            required_proficiency=sinfo["required_proficiency"],
            priority=sinfo["w_j"],
            importance_weight=sinfo["w_j"],
            jd_evidence_spans=jd_spans,
            job_tasks=[jtask],
        )
        cv_src = {sp: sp for sp in cv_spans}
        jd_src = {sp: sp for sp in jd_spans}
        case_skills.append((isk, cv_src, jd_src, sinfo))

        bp_key = f"{jid}__{sid}"
        if bp_key not in unique_bp_inputs:
            # Strip CV fields so shared blueprint is 100% JD-derived and identical across pairs/conditions
            unique_bp_inputs[bp_key] = isk.model_copy(
                update={"cv_evidence_spans": [], "context_job": "", "matched_cv_skill_name": ""}
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bp_cache_file = output_path.with_suffix(".blueprints_cache.json")
    blueprints_by_key: Dict[str, Dict[str, Any]] = {}
    if bp_cache_file.exists():
        blueprints_by_key = json.loads(bp_cache_file.read_text(encoding="utf-8"))

    pending_bps = [(k, sk) for k, sk in unique_bp_inputs.items() if k not in blueprints_by_key]
    logger.info(f"Shared JD blueprints: total={len(unique_bp_inputs)}, cached={len(blueprints_by_key)}, pending={len(pending_bps)}")

    def _draft_one(k_str: str, sk: InterviewSkill) -> Tuple[str, Dict[str, Any]]:
        bp = workflow.build_blueprint(BlueprintRequest(skills=[sk]))
        return k_str, bp.model_dump(mode="json")

    if pending_bps:
        bp_lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=min(workers, 4)) as pool:
            futs = [pool.submit(_draft_one, k, sk) for k, sk in pending_bps]
            for fut in as_completed(futs):
                k_str, bp_d = fut.result()
                with bp_lock:
                    blueprints_by_key[k_str] = bp_d
                    bp_cache_file.write_text(json.dumps(blueprints_by_key, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Completed drafting all {len(blueprints_by_key)} shared JD blueprints.")

    # Generate 100 frozen criterion-grounded scripted answers with independent model
    ans_cache_file = output_path.with_suffix(".answers_cache.json")
    answers_by_pair: Dict[str, str] = {}
    if ans_cache_file.exists():
        answers_by_pair = json.loads(ans_cache_file.read_text(encoding="utf-8"))

    oa_client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        timeout=45.0,
    )
    pending_ans = []
    for (idx, sid, _), sc, (isk, _, _, _) in zip(selected, scenarios, case_skills):
        pid = pairs[idx]["pair_id"]
        if pid in answers_by_pair:
            continue
        jid = pairs[idx]["jd_id"]
        obj = blueprints_by_key[f"{jid}__{sid}"]["objectives"][0]
        pending_ans.append((pid, sc, isk.jd_skill_name or sid, obj["claim"], obj["criteria"][0], isk.cv_evidence_spans, obj["target_depth"]))

    if pending_ans:
        logger.info(f"Generating {len(pending_ans)} criterion-grounded scripted answers using {answer_model}...")
        ans_lock = threading.Lock()
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {
                pool.submit(
                    _generate_scripted_answer,
                    oa_client,
                    answer_model,
                    scenario=sc,
                    skill_name=sn,
                    jd_claim=cl,
                    criterion=c1,
                    cv_spans=cv_sp,
                    target_depth=dp,
                ): pid
                for pid, sc, sn, cl, c1, cv_sp, dp in pending_ans
            }
            for fut in as_completed(futs):
                pid = futs[fut]
                ans = fut.result()
                with ans_lock:
                    answers_by_pair[pid] = ans
                    done += 1
                    if done % 20 == 0 or done == len(pending_ans):
                        ans_cache_file.write_text(json.dumps(answers_by_pair, ensure_ascii=False, indent=2), encoding="utf-8")
                        logger.info(f"  Scripted answers progress: {done}/{len(pending_ans)}")

    cases: List[Dict[str, Any]] = []
    for pos, ((idx, sid, grp), sc, (isk, cv_src, jd_src, sinfo)) in enumerate(zip(selected, scenarios, case_skills)):
        p = pairs[idx]
        jid = p["jd_id"]
        cid = p["cv_id"]
        cases.append({
            "case_id": f"m3_case_{pos + 1:03d}",
            "pair_id": p["pair_id"],
            "jd_id": jid,
            "cv_id": cid,
            "skill_id": sid,
            "evidence_group": grp,
            "scenario": sc,
            "cv_text": resumes[cid]["cv_text"],
            "jd_text": jobs[jid]["jd_text"],
            "interview_skill": isk.model_dump(mode="json"),
            "verification_sources": {"cv": cv_src, "jd": jd_src},
            "blueprint": blueprints_by_key[f"{jid}__{sid}"],
            "scripted_answer": answers_by_pair[p["pair_id"]],
            "reference_metadata": {
                "target_status": sinfo["target_status"],
                "pair_label": p.get("label", "UNCERTAIN"),
                "label_nature": "synthetic_dataset_status_for_stratification_only_never_in_prompt",
            },
        })

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(cases),
        "unique_blueprints": len(blueprints_by_key),
        "blueprint_model": provider.lm.model,
        "scripted_answer_model": answer_model,
        "seed": seed,
        "evidence_group_counts": dict(Counter(c["evidence_group"] for c in cases)),
        "scenario_counts": dict(Counter(c["scenario"] for c in cases)),
        "cross_tab_group_x_scenario": {
            f"{g}__{s}": sum(1 for c in cases if c["evidence_group"] == g and c["scenario"] == s)
            for g in sorted({c["evidence_group"] for c in cases})
            for s in sorted({c["scenario"] for c in cases})
        },
        "criteria_count_distribution": dict(Counter(len(c["blueprint"]["objectives"][0]["criteria"]) for c in cases)),
    }

    output_path.write_text(json.dumps({"summary": summary, "cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved 100 fixed Module 3 cases to {output_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    import threading
    parser = argparse.ArgumentParser(description="Build 100 Fixed Test Cases for Module 3 Experiment.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(r"matching_cv\dataset\synthetic_cv_jd_dataset_v2-20261118T164928Z-1-001\synthetic_cv_jd_dataset_v2"),
    )
    parser.add_argument("--output", type=Path, default=Path("adaptive_questioning/optimization/results/module3_100_cases.json"))
    parser.add_argument("--answer-model", type=str, default="google/gemini-2.5-flash")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    build_cases(args.dataset_root, args.output, answer_model=args.answer_model, workers=args.workers, seed=args.seed)
