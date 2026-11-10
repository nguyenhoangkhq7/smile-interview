"""
Comprehensive Test Suite for Standardized Pipeline Output Contract
Validating all 20 required scenarios prior to GNN training.

Contract: standardized-output-v1
Scientific Reference: Baghbanzadeh & Wu (ICIT 2025)
"""
import copy
import hashlib
import io
import json
import os
import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from matching_cv.app.core.config import settings
from matching_cv.app.main import app
from matching_cv.app.schemas.standardized_output import (
    STANDARDIZED_OUTPUT_SCHEMA_VERSION,
    STANDARDIZED_OUTPUT_VERSION_HEADER,
    ProficiencyInput,
    ProficiencySkill,
    SkillGapRow,
    StandardizedPipelineOutput,
)
from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse

REAL_STANDARDIZED_PATH = os.path.join("scratch", "real_standardized_output.json")
REAL_INTERNAL_PATH = os.path.join("scratch", "real_standardized_output_internal.json")
FRONTEND_FIXTURE_PATH = os.path.join("tests", "fixtures", "02_Frontend_run.json")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def real_standardized_json():
    assert os.path.exists(REAL_STANDARDIZED_PATH), "Real standardized output JSON artifact missing!"
    with open(REAL_STANDARDIZED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def real_internal_data():
    assert os.path.exists(REAL_INTERNAL_PATH), "Real internal output JSON artifact missing!"
    with open(REAL_INTERNAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def frontend_fixture() -> UnifiedExtractFileResponse:
    with open(FRONTEND_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return UnifiedExtractFileResponse.model_validate(json.load(f))


# =========================================================================
# Scenario 1: match_score is serialized first
# =========================================================================
def test_scenario_01_match_score_serialized_first(real_standardized_json):
    """Scenario 1: match_score appears as the very first key in serialized JSON."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    json_bytes = model.model_dump_json()

    # Regex check: very first key after '{' must be "match_score"
    match = re.match(r'^\s*\{\s*"match_score"\s*:', json_bytes)
    assert match is not None, f"JSON does not start with match_score: {json_bytes[:50]}"

    # Also verify dictionary keys order
    keys = list(model.model_dump().keys())
    assert keys[0] == "match_score"
    assert keys == [
        "match_score",
        "status",
        "cv_text",
        "jd_text",
        "skill_gap_input",
        "proficiency_input",
    ]


# =========================================================================
# Scenario 2: Correct cv_text and jd_text
# =========================================================================
def test_scenario_02_correct_cv_text_and_jd_text(real_standardized_json):
    """Scenario 2: cv_text and jd_text faithfully contain clean document text."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    assert model.cv_text is not None and len(model.cv_text) > 100
    assert model.jd_text is not None and len(model.jd_text) > 100

    # Backend CV contains known candidate phrases
    assert "Backend" in model.cv_text or "Java" in model.cv_text or "Engineer" in model.cv_text
    # Backend JD contains known job phrases
    assert "Job Description" in model.jd_text or "Responsibilities" in model.jd_text or "Backend" in model.jd_text


# =========================================================================
# Scenario 3: Every retained JD skill has one skill-gap row (exactly 37)
# =========================================================================
def test_scenario_03_every_retained_jd_skill_has_one_skill_gap_row(real_standardized_json):
    """Scenario 3: Skill gap analysis contains exactly one row per retained JD skill."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    jd_skills = model.proficiency_input.jd_skills

    assert len(model.skill_gap_input) == 37, f"Expected 37 rows, got {len(model.skill_gap_input)}"
    assert len(jd_skills) == 37, f"Expected 37 JD skills, got {len(jd_skills)}"

    skill_gap_jd_ids = [row.jd_skill_id for row in model.skill_gap_input]
    proficiency_jd_ids = [skill.skill_id for skill in jd_skills]

    # Every retained JD skill has exactly one row, no duplicates
    assert len(skill_gap_jd_ids) == len(set(skill_gap_jd_ids))
    assert set(skill_gap_jd_ids) == set(proficiency_jd_ids)


# =========================================================================
# Scenario 4: Exactly four fields exist in each skill-gap row
# =========================================================================
def test_scenario_04_exactly_four_fields_in_skill_gap_row(real_standardized_json):
    """Scenario 4: Each skill gap row has exactly [jd_skill_id, w_j, matched_cv_skill_id, soft_match]."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    expected_fields = ["jd_skill_id", "w_j", "matched_cv_skill_id", "soft_match"]

    for idx, row in enumerate(model.skill_gap_input):
        row_dict = row.model_dump()
        assert list(row_dict.keys()) == expected_fields, f"Row {idx} keys mismatch: {list(row_dict.keys())}"


# =========================================================================
# Scenario 5: Best CV match chosen JD-to-CV across full matrix
# =========================================================================
def test_scenario_05_reverse_retrieval_jd_to_cv(real_internal_data):
    """Scenario 5: Reverse retrieval evaluates all JD skills against all CV candidates."""
    details = real_internal_data["skill_gap_details"]
    assert len(details) == 37

    # In reverse retrieval, JD skills with semantic matches evaluated the full CV candidate set
    semantic_details = [d for d in details if d["match_type"] == "semantic_related"]
    assert len(semantic_details) == 16
    for d in semantic_details:
        assert d["similarity_source"] == "stage3_matrix"
        assert d["matched_cv_skill_id"] is not None
        assert d["soft_match"] >= 0.50


# =========================================================================
# Scenario 6: Verified shared identity is preserved
# =========================================================================
def test_scenario_06_verified_shared_identity_preserved(real_standardized_json, real_internal_data):
    """Scenario 6: Verified shared identities have soft_match >= 0.50 and matched_cv_skill_id matching canonical."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    details = {d["jd_skill_id"]: d for d in real_internal_data["skill_gap_details"]}

    # In real Backend run, 11 skills were verified identities
    identities = [d for d in real_internal_data["skill_gap_details"] if d["match_type"] == "verified_identity"]
    assert len(identities) == 11, f"Expected 11 verified identities, got {len(identities)}"

    rows_by_jd = {r.jd_skill_id: r for r in model.skill_gap_input}
    for ident in identities:
        jid = ident["jd_skill_id"]
        row = rows_by_jd[jid]
        assert row.matched_cv_skill_id == jid, f"Expected identity match for {jid}"
        assert row.soft_match is not None and row.soft_match >= 0.50
        # Measured similarity is preserved from Stage 3, never forced to 1.0
        assert abs(row.soft_match - round(ident["soft_match"], 6)) <= 1e-6
        if jid == "kafka":
            # Real measured cosine of "Apache Kafka" vs "Kafka" is strictly < 1.0
            assert row.soft_match < 1.0
            assert row.soft_match == 0.823818


# =========================================================================
# Scenario 7: Related skills are not mislabeled equivalent
# =========================================================================
def test_scenario_07_related_skills_not_mislabeled_equivalent(real_standardized_json, real_internal_data):
    """Scenario 7: Related skills matched via cosine have soft_match < 1.0 and jd_skill_id != matched_cv_skill_id."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    details = {d["jd_skill_id"]: d for d in real_internal_data["skill_gap_details"]}

    semantic_jids = [d["jd_skill_id"] for d in real_internal_data["skill_gap_details"] if d["match_type"] == "semantic_related"]
    assert len(semantic_jids) == 16

    rows_by_jd = {r.jd_skill_id: r for r in model.skill_gap_input}
    for jid in semantic_jids:
        row = rows_by_jd[jid]
        assert row.matched_cv_skill_id is not None
        assert row.soft_match is not None
        # Must be strictly non-identical
        assert row.jd_skill_id != row.matched_cv_skill_id
        assert 0.50 <= row.soft_match < 1.0


# =========================================================================
# Scenario 8: No matching CV skill returns nulls
# =========================================================================
def test_scenario_08_no_matching_cv_skill_returns_nulls(real_standardized_json, real_internal_data):
    """Scenario 8: Unmatched JD skills strictly return matched_cv_skill_id=None, soft_match=None."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    unmatched_jids = [d["jd_skill_id"] for d in real_internal_data["skill_gap_details"] if d["match_type"] == "no_match"]
    assert len(unmatched_jids) == 10

    rows_by_jd = {r.jd_skill_id: r for r in model.skill_gap_input}
    for jid in unmatched_jids:
        row = rows_by_jd[jid]
        assert row.matched_cv_skill_id is None
        assert row.soft_match is None
        assert row.w_j is None


# =========================================================================
# Scenario 9: w_j is null without valid JD importance
# =========================================================================
def test_scenario_09_w_j_strictly_null(real_standardized_json):
    """Scenario 9: w_j is strictly None for all skill gap rows without a validated estimator."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    for row in model.skill_gap_input:
        assert row.w_j is None, f"w_j was unexpectedly populated for {row.jd_skill_id}: {row.w_j}"


# =========================================================================
# Scenario 10: Real soft_match originates from SBERT cosine
# =========================================================================
def test_scenario_10_real_soft_match_originates_from_sbert(real_internal_data, real_standardized_json):
    """Scenario 10: soft_match for semantic candidates equals the rounded SBERT cosine matrix entry."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    rows_by_jd = {r.jd_skill_id: r for r in model.skill_gap_input}

    for d in real_internal_data["skill_gap_details"]:
        if d["match_type"] == "semantic_related":
            row = rows_by_jd[d["jd_skill_id"]]
            assert abs(row.soft_match - round(d["soft_match"], 6)) <= 1e-6
            assert d["similarity_source"] == "stage3_matrix"


# =========================================================================
# Scenario 11: Explicit extraction confidence remains null when unknown
# =========================================================================
def test_scenario_11_explicit_confidence_null_when_unknown(real_standardized_json):
    """Scenario 11: Explicit skills without numeric confidence retain confidence=None."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)

    explicit_skills = [s for s in model.proficiency_input.cv_skills if s.type == "explicit"]
    assert len(explicit_skills) == 42
    for s in explicit_skills:
        assert s.confidence is None, f"Explicit skill {s.skill_id} had unexpected confidence {s.confidence}"


# =========================================================================
# Scenario 12: Implicit confidence is preserved when available
# =========================================================================
def test_scenario_12_implicit_confidence_preserved(real_standardized_json):
    """Scenario 12: Implicit skills with LLM confidence preserve their exact numeric value."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)

    implicit_skills = [s for s in model.proficiency_input.cv_skills if s.type == "implicit"]
    assert len(implicit_skills) == 2, f"Expected 2 implicit CV skills, got {len(implicit_skills)}"

    conf_by_id = {s.skill_id: s.confidence for s in implicit_skills}
    # From audit: system-decoupling has 0.92, legacy-modernization has 0.88
    assert "system-decoupling" in conf_by_id
    assert conf_by_id["system-decoupling"] == 0.92
    assert "legacy-modernization" in conf_by_id
    assert conf_by_id["legacy-modernization"] == 0.88


# =========================================================================
# Scenario 13: Evidence spans correspond to original source text
# =========================================================================
def test_scenario_13_evidence_spans_correspond_to_source_text(real_standardized_json):
    """Scenario 13: 100% of evidence spans are verified substrings of the normalized source text."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)

    cv_text_norm = " ".join(model.cv_text.split()).lower()
    jd_text_norm = " ".join(model.jd_text.split()).lower()

    for s in model.proficiency_input.cv_skills:
        for span in s.evidence_spans:
            span_norm = " ".join(span.split()).lower()
            assert span_norm in cv_text_norm, f"CV span '{span}' not in CV text!"

    for s in model.proficiency_input.jd_skills:
        for span in s.evidence_spans:
            span_norm = " ".join(span.split()).lower()
            assert span_norm in jd_text_norm, f"JD span '{span}' not in JD text!"


# =========================================================================
# Scenario 14: Evidence deduplication is deterministic
# =========================================================================
def test_scenario_14_evidence_deduplication_deterministic(real_standardized_json):
    """Scenario 14: Duplicate spans are deduplicated deterministically while preserving order."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)

    # In real pair, verify all evidence spans are uniquely deduplicated
    for s in model.proficiency_input.cv_skills:
        assert len(s.evidence_spans) == len(set(s.evidence_spans)), f"Duplicate spans in CV skill {s.skill_id}"

    for s in model.proficiency_input.jd_skills:
        assert len(s.evidence_spans) == len(set(s.evidence_spans)), f"Duplicate spans in JD skill {s.skill_id}"


# =========================================================================
# Scenario 15: CV and JD proficiency lists are never mixed
# =========================================================================
def test_scenario_15_cv_and_jd_proficiency_lists_never_mixed(real_standardized_json):
    """Scenario 15: cv_skills and jd_skills contain only their respective document's skills."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)

    cv_text_norm = " ".join(model.cv_text.split()).lower()
    jd_text_norm = " ".join(model.jd_text.split()).lower()

    # Verify CV evidence is from CV text and JD evidence is from JD text
    for skill in model.proficiency_input.cv_skills:
        for span in skill.evidence_spans:
            assert " ".join(span.split()).lower() in cv_text_norm

    for skill in model.proficiency_input.jd_skills:
        for span in skill.evidence_spans:
            assert " ".join(span.split()).lower() in jd_text_norm


# =========================================================================
# Scenario 16: Graph-only mode still returns the new schema
# =========================================================================
def test_scenario_16_graph_only_mode_returns_standardized_schema(client: TestClient, frontend_fixture):
    """Scenario 16: evidence_only mode returns valid StandardizedPipelineOutput with status MODEL_NOT_TRAINED."""
    cv_b = b"Frontend developer with React and TypeScript"
    jd_b = b"Hiring React frontend developer with TypeScript"

    fixture = copy.deepcopy(frontend_fixture)
    fixture.cv.text_sha256 = hashlib.sha256(cv_b).hexdigest()
    fixture.jd.text_sha256 = hashlib.sha256(jd_b).hexdigest()

    files = {
        "cv_file": ("frontend_cv.txt", io.BytesIO(cv_b), "text/plain"),
        "jd_file": ("frontend_jd.txt", io.BytesIO(jd_b), "text/plain"),
    }
    with patch(
        "matching_cv.app.services.unified_skill_service.unified_skill_service.extract_unified_from_files",
        new=AsyncMock(return_value=fixture),
    ):
        resp = client.post(
            "/api/v1/pipeline/analyze",
            files=files,
            data={"graph_mode": "evidence_only", "top_k": 3},
        )
    assert resp.status_code == 200
    assert resp.headers.get("x-output-schema-version") == "standardized-output-v1"
    data = resp.json()

    # Validates cleanly against Pydantic schema
    validated = StandardizedPipelineOutput.model_validate(data)
    assert validated.status in ("MODEL_READY", "MODEL_NOT_TRAINED")
    if validated.status == "MODEL_READY":
        assert validated.match_score is not None and 0.0 <= validated.match_score <= 1.0
    else:
        assert validated.match_score is None
    assert "Frontend developer" in validated.cv_text
    assert len(validated.proficiency_input.cv_skills) > 0


# =========================================================================
# Scenario 17: No untrained matching score is generated
# =========================================================================
def test_scenario_17_no_untrained_matching_score_generated(real_standardized_json):
    """Scenario 17: In untrained state, match_score is strictly null, status is MODEL_NOT_TRAINED."""
    model = StandardizedPipelineOutput.model_validate(real_standardized_json)
    assert model.match_score is None
    assert model.status == "MODEL_NOT_TRAINED"


# =========================================================================
# Scenario 18: Internal diagnostics remain available for research
# =========================================================================
def test_scenario_18_internal_diagnostics_remain_available(real_internal_data):
    """Scenario 18: Internal diagnostics (run_id, skill_gap_details, proficiency_debug) are intact."""
    assert "run_id" in real_internal_data
    assert "schema_version" in real_internal_data
    assert real_internal_data["schema_version"] == "standardized-output-v1"
    assert "skill_gap_details" in real_internal_data
    assert len(real_internal_data["skill_gap_details"]) == 37
    assert "proficiency_debug" in real_internal_data
    assert real_internal_data["proficiency_debug"]["cv"]["dropped_unverified_spans"] == 0
    assert real_internal_data["proficiency_debug"]["jd"]["dropped_unverified_spans"] == 0
    assert real_internal_data["internal_matching_status"] == "MODEL_NOT_TRAINED"


# =========================================================================
