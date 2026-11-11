import copy
import hashlib
import io
import json
import os
import re
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from matching_cv.app.main import app
from matching_cv.app.schemas.skill_extraction import (
    Evidence,
    ExtractedSkill,
    ExtractionResult,
    ExtractionStats,
    RawExtraction,
    RawSkillMention,
)
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.prompt_templates import (
    EXPLICIT_SKILL_SYSTEM_PROMPT,
    EXPLICIT_SKILL_SYSTEM_PROMPT_V2A,
    EXPLICIT_SKILL_SYSTEM_PROMPT_V2B,
    EXPLICIT_SKILL_SYSTEM_PROMPT_C1,
    EXPLICIT_SKILL_SYSTEM_PROMPT_C2,
    EXPLICIT_SKILL_SYSTEM_PROMPT_C3,
    IMPLICIT_SKILL_SYSTEM_PROMPT,
    IMPLICIT_SKILL_SYSTEM_PROMPT_V2,
    VERIFIER_PROMPT_V1,
    VERIFIER_PROMPT_V2,
)
from matching_cv.app.services.section_tagger import SectionSpan, find_section_spans, section_at
from matching_cv.app.services.text_locator import locate_sentence


@pytest.fixture
def client():
    """Test client fixture bypassing heavy model loads."""
    with patch("matching_cv.app.core.model_loader.model_loader.load_model"):
        with TestClient(app) as test_client:
            yield test_client


















# -----------------------------------------------------------------------------
# Unit Tests for Pydantic Schema Invariants
# -----------------------------------------------------------------------------

def test_schema_invariants_valid():
    """Verify that a valid ExtractionResult satisfies all invariants."""
    res = ExtractionResult(
        filename="test_doc.pdf",
        stats=ExtractionStats(
            total_mentions=2,
            unique_skills=1,
            unresolved_evidences=0,
            kind_conflicts=0,
            non_verbatim_mentions=0,
            header_evidences=0,
            unresolved_mentions=0,
            ambiguous_mentions=0,
        ),
        skills=[
            ExtractedSkill(
                skill_id="kafka",
                surface_forms=["Kafka"],
                category="Technology/Tool",
                kind="skill",
                type="explicit",
                confidence=0.95,
                sections=["skills"],
                evidences=[
                    Evidence(
                        surface_form="Kafka",
                        kind="skill",
                        kind_source="inferred",
                        sentence="Experience with Kafka.",
                        start=0,
                        end=22,
                        mention_start=16,
                        mention_end=21,
                        mention_ambiguous=False,
                        modifier_text="strong",
                        section="skills",
                    ),
                    Evidence(
                        surface_form="Kafka",
                        kind="skill",
                        kind_source="inferred",
                        sentence="Built Kafka pipeline.",
                        start=30,
                        end=51,
                        mention_start=36,
                        mention_end=41,
                        mention_ambiguous=False,
                        modifier_text=None,
                        section="skills",
                    ),
                ],
            )
        ],
    )
    assert res.stats.total_mentions == 2
    assert res.stats.unique_skills == 1
    assert res.stats.kind_conflicts == 0
    assert res.stats.non_verbatim_mentions == 0
    assert res.stats.header_evidences == 0
    assert res.stats.unresolved_mentions == 0
    assert res.stats.ambiguous_mentions == 0
    assert res.skills[0].surface_forms == ["Kafka"]
    assert res.skills[0].kind == "skill"
    assert res.skills[0].sections == ["skills"]
    assert res.skills[0].evidences[0].section == "skills"
    assert res.skills[0].evidences[0].surface_form == "Kafka"
    assert res.skills[0].evidences[0].verbatim_ok is True
    assert res.skills[0].evidences[0].mention_start == 16
    assert res.skills[0].evidences[0].mention_end == 21
    assert res.skills[0].evidences[0].mention_ambiguous is False


def test_schema_invariants_duplicate_skill_id():
    """Verify that duplicate skill_id violates invariant 1."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            filename="test_doc.pdf",
            stats=ExtractionStats(total_mentions=2, unique_skills=2),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    kind="skill",
                    evidences=[Evidence(surface_form="Kafka", sentence="Kafka 1", start=0, end=7)],
                ),
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Apache Kafka"],
                    kind="skill",
                    evidences=[Evidence(surface_form="Kafka", sentence="Kafka 2", start=10, end=17)],
                ),
            ],
        )
    assert "duplicate skill_id found" in str(exc_info.value)


def test_schema_invariants_mismatched_total_mentions():
    """Verify that stats.total_mentions != sum(len(evidences)) violates invariant 2."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            filename="test_doc.pdf",
            stats=ExtractionStats(total_mentions=5, unique_skills=1),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    kind="skill",
                    evidences=[Evidence(surface_form="Kafka", sentence="Kafka 1", start=0, end=7)],
                ),
            ],
        )
    assert "stats.total_mentions (5) != sum(len(evidences)) (1)" in str(exc_info.value)


def test_schema_invariants_mismatched_unique_skills():
    """Verify that stats.unique_skills != len(skills) violates invariant 3."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            filename="test_doc.pdf",
            stats=ExtractionStats(total_mentions=1, unique_skills=3),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    kind="skill",
                    evidences=[Evidence(surface_form="Kafka", sentence="Kafka 1", start=0, end=7)],
                ),
            ],
        )
    assert "stats.unique_skills (3) != len(skills) (1)" in str(exc_info.value)


def test_evidence_invalid_offsets():
    """Verify that start >= end in Evidence raises ValidationError and start >= 0 is enforced."""
    with pytest.raises(ValidationError) as exc_info:
        Evidence(sentence="Test sentence", start=50, end=10)
    assert "strictly less than end offset" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Evidence(sentence="Test sentence", start=10, end=10)
    assert "strictly less than end offset" in str(exc_info.value)

    with pytest.raises(ValidationError):
        Evidence(sentence="Test sentence", start=-1, end=10)


def test_evidence_nullable_offsets_when_unresolved():
    """Verify Evidence can have None offsets with offset_resolved=False."""
    ev = Evidence(sentence="Unfound sentence", start=None, end=None)
    assert ev.start is None
    assert ev.end is None
    assert ev.offset_resolved is False

    # Partial offsets should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Evidence(sentence="Partial", start=0, end=None)
    assert "Both start and end must be provided if either is present" in str(exc_info.value)


def test_schema_invariants_mismatched_unresolved_evidences():
    """Verify that stats.unresolved_evidences != actual unresolved count violates invariant 4."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            filename="test_doc.pdf",
            document_type="CV",
            stats=ExtractionStats(total_mentions=1, unique_skills=1, unresolved_evidences=5),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    kind="skill",
                    evidences=[Evidence(surface_form="Kafka", sentence="Kafka 1", start=0, end=7)],
                ),
            ],
        )
    assert "stats.unresolved_evidences (5) != actual unresolved count (0)" in str(exc_info.value)


def test_schema_invariants_mismatched_kind_conflicts():
    """Verify that stats.kind_conflicts != actual conflicting count violates invariant 6."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=2,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=5,
                non_verbatim_mentions=0,
                header_evidences=0,
            ),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    evidences=[
                        Evidence(surface_form="Kafka", kind="skill", sentence="Kafka 1", start=0, end=7),
                        Evidence(surface_form="Kafka", kind="context", sentence="Kafka 2", start=10, end=17),
                    ],
                ),
            ],
        )
    assert "stats.kind_conflicts (5) != actual conflicting skills count (1)" in str(exc_info.value)


def test_schema_invariants_mismatched_non_verbatim_mentions():
    """Verify that stats.non_verbatim_mentions != actual count violates invariant 5."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=0,
                non_verbatim_mentions=4,
                header_evidences=0,
            ),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    evidences=[
                        Evidence(surface_form="Kafka", sentence="Unrelated sentence without mention", verbatim_ok=False, start=0, end=7),
                    ],
                ),
            ],
        )
    assert "stats.non_verbatim_mentions (4) != actual non-verbatim count (1)" in str(exc_info.value)


def test_schema_invariants_mismatched_header_evidences():
    """Verify that stats.header_evidences != actual count violates invariant 7."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=0,
                non_verbatim_mentions=0,
                header_evidences=3,
            ),
            skills=[
                ExtractedSkill(
                    skill_id="kafka",
                    surface_forms=["Kafka"],
                    evidences=[
                        Evidence(surface_form="Kafka", sentence="Kafka 1", section="header", start=0, end=7),
                    ],
                ),
            ],
        )
    assert "stats.header_evidences (3) != actual header evidences count (1)" in str(exc_info.value)


def test_skill_postprocessor_unresolved_sentence_offset():
    """Verify skill_postprocessor sets start/end to None and offset_resolved=False when sentence is missing."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    raw_data = {
        "skills": [
            {
                "surface_form": "Docker",
                "category": "Technology/Tool",
                "sentence": "This sentence does not exist in the document text at all.",
            }
        ]
    }
    result = skill_postprocessor.process_extraction(
        raw_result=raw_data,
        text="Sample document text without the mentioned sentence.",
        filename=None,
        document_type="CV",
    )

    assert result.stats.total_mentions == 1
    assert result.stats.unique_skills == 1
    assert result.stats.unresolved_evidences == 1
    ev = result.skills[0].evidences[0]
    assert ev.start is None
    assert ev.end is None
    assert ev.offset_resolved is False


def test_wrapped_sentence_offset_resolution():
    """
    Validates whitespace-tolerant locate: cleaned text has wrapped line ('reduced p95 API\\nlatency by 38%')
    while LLM extracted sentence is single-line ('reduced p95 API latency by 38%').
    With locate_sentence, offsets resolve successfully and satisfy the norm-equality invariant.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    text = "Work experience: optimized backend services and reduced p95 API\nlatency by 38% across all endpoints."
    raw_data = {
        "skills": [
            {
                "surface_form": "API latency",
                "category": "Technical Concept",
                "sentence": "reduced p95 API latency by 38%",
            }
        ]
    }

    result = skill_postprocessor.process_extraction(
        raw_result=raw_data,
        text=text,
        filename=None,
        document_type="CV",
    )

    ev = result.skills[0].evidences[0]
    assert ev.offset_resolved is True, "Offset should resolve despite line wrap in document text"
    assert ev.start is not None
    assert ev.end is not None
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    assert norm(text[ev.start:ev.end]) == norm(ev.sentence)


# -----------------------------------------------------------------------------
# Unit Tests for text_locator.locate_sentence
# -----------------------------------------------------------------------------

def test_locate_sentence_single_line():
    """Locate exact sentence on a single line."""
    text = "Full stack engineer with Python experience in backend."
    span = locate_sentence(text, "Python experience")
    assert span is not None
    assert text[span[0]:span[1]] == "Python experience"


def test_locate_sentence_wrapped_by_one_newline():
    """Locate sentence broken by a single newline."""
    text = "optimized backend services and reduced p95 API\nlatency by 38% across endpoints."
    sentence = "reduced p95 API latency by 38%"
    span = locate_sentence(text, sentence)
    assert span is not None
    assert text[span[0]:span[1]] == "reduced p95 API\nlatency by 38%"
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    assert norm(text[span[0]:span[1]]) == norm(sentence)


def test_locate_sentence_wrapped_by_two_breaks():
    """Locate sentence broken by two line breaks (paragraph break)."""
    text = "first paragraph header\n\ncontinuation of the sentence across double newline."
    sentence = "first paragraph header continuation of the sentence"
    span = locate_sentence(text, sentence)
    assert span is not None
    assert text[span[0]:span[1]] == "first paragraph header\n\ncontinuation of the sentence"
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    assert norm(text[span[0]:span[1]]) == norm(sentence)


def test_locate_sentence_starting_with_bullet():
    """Locate sentence starting with a bullet character."""
    text = "Skills list:\n• Java (primary), SQL, Python for tooling\n• Docker"
    sentence = "• Java (primary), SQL, Python for tooling"
    span = locate_sentence(text, sentence)
    assert span is not None
    assert text[span[0]:span[1]] == "• Java (primary), SQL, Python for tooling"


def test_locate_sentence_not_found():
    """Return None when sentence is not found."""
    text = "Software engineer building scalable systems."
    span = locate_sentence(text, "Completely absent sentence from text")
    assert span is None


def test_locate_sentence_case_mismatch_no_fuzzy():
    """Return None on case mismatch, proving strict exact matching with no fuzzy logic."""
    text = "Solid understanding of PostgreSQL and MySQL."
    span = locate_sentence(text, "solid understanding of postgresql and mysql.")
    assert span is None


def test_locate_sentence_middle_of_longer_line():
    """Locate sentence sitting in the middle of a longer line."""
    text = "Prefix words before target mention sentence and suffix words after target."
    sentence = "target mention sentence"
    span = locate_sentence(text, sentence)
    assert span is not None
    assert text[span[0]:span[1]] == "target mention sentence"


# -----------------------------------------------------------------------------
# Golden Test with Real Documents (01_Backend_CV.pdf, 01_Backend_JD.pdf)
# -----------------------------------------------------------------------------

def test_golden_01_backend_cv_and_jd_extraction():
    """
    Phase C golden test: validates whitespace-tolerant sentence location on real PDF documents
    (01_Backend_CV.pdf and 01_Backend_JD.pdf) using frozen LLM raw extractions (01_Backend_llm_raw.json).
    Asserts unresolved_evidences == 0 and norm(cleaned_text[start:end]) == norm(sentence) for all evidences.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        jd_cleaned = document_parser_service.clean_extracted_text(jd_raw)

    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    # Process CV
    cv_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["cv"],
        text=cv_cleaned,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    assert cv_result.stats.total_mentions == 51
    assert cv_result.stats.unresolved_evidences == 0
    assert cv_result.stats.unique_skills == 44
    assert cv_result.stats.header_evidences == 0
    assert cv_result.stats.kind_conflicts == 0
    assert cv_result.stats.non_verbatim_mentions == 0

    # Process JD
    jd_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["jd"],
        text=jd_cleaned,
        filename="01_Backend_JD.pdf",
        document_type="JD",
    )
    assert jd_result.stats.total_mentions == 46
    assert jd_result.stats.unresolved_evidences == 0
    assert jd_result.stats.unique_skills == 42
    assert jd_result.stats.header_evidences == 0
    assert jd_result.stats.kind_conflicts == 0
    assert jd_result.stats.non_verbatim_mentions == 1

    # Verify norm-equality invariant for all evidences
    norm = lambda s: re.sub(r"\s+", " ", s).strip()

    cv_checked = 0
    for s in cv_result.skills:
        for ev in s.evidences:
            assert ev.offset_resolved is True
            assert norm(cv_cleaned[ev.start:ev.end]) == norm(ev.sentence)
            cv_checked += 1
    assert cv_checked == 51

    jd_checked = 0
    for s in jd_result.skills:
        for ev in s.evidences:
            assert ev.offset_resolved is True
            assert norm(jd_cleaned[ev.start:ev.end]) == norm(ev.sentence)
            jd_checked += 1
    assert jd_checked == 46

    # Assert text_sha256 matches exact cleaned text sha256
    assert cv_result.text_sha256 == hashlib.sha256(cv_cleaned.encode("utf-8")).hexdigest()
    assert jd_result.text_sha256 == hashlib.sha256(jd_cleaned.encode("utf-8")).hexdigest()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Frozen JD fixture contains non-verbatim mention ('unit tests' in coordinated phrase 'unit and integration tests')",
)
def test_golden_surface_form_verbatim():
    """
    Assert verbatim_ok is True and stats.non_verbatim_mentions == 0 for all evidences
    in frozen real-document extractions (01_Backend_CV.pdf and 01_Backend_JD.pdf).
    Marked xfail(strict=True, raises=AssertionError) due to non-verbatim mention 'unit tests'
    in 01_Backend_JD.pdf.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        jd_cleaned = document_parser_service.clean_extracted_text(jd_raw)

    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    cv_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["cv"],
        text=cv_cleaned,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    jd_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["jd"],
        text=jd_cleaned,
        filename="01_Backend_JD.pdf",
        document_type="JD",
    )

    # CV has 0 non-verbatim mentions
    assert cv_result.stats.non_verbatim_mentions == 0
    for s in cv_result.skills:
        for ev in s.evidences:
            assert ev.verbatim_ok is True, f"CV evidence not verbatim: {ev.surface_form} in {ev.sentence}"

    # JD contains 1 non-verbatim mention ('unit tests'), asserting verbatim_ok raises AssertionError
    for s in jd_result.skills:
        for ev in s.evidences:
            assert ev.verbatim_ok is True, f"JD evidence not verbatim: {ev.surface_form} in {ev.sentence}"
    assert jd_result.stats.non_verbatim_mentions == 0




def test_extraction_result_text_sha256():
    """Verify ExtractionResult.text_sha256 matches hashlib.sha256(text.encode('utf-8')).hexdigest()."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    sample_text = "Senior Python Engineer with 5 years experience in FastAPI and Docker."
    expected_sha256 = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

    raw_data = {
        "skills": [
            {
                "surface_form": "Python",
                "category": "Technology/Tool",
                "sentence": "Senior Python Engineer with 5 years experience in FastAPI and Docker.",
            }
        ]
    }
    result = skill_postprocessor.process_extraction(
        raw_result=raw_data,
        text=sample_text,
        filename="sample.txt",
        document_type="CV",
    )

    assert result.text_sha256 == expected_sha256


def test_negative_control_altered_source_sentence():
    """
    Negative control test (test of the test):
    Alters a single token ('38%' -> '39%') in one source sentence of frozen CV LLM extractions.
    Asserts that unresolved_evidences equals exactly 5 (the number of mentions sharing that sentence)
    and that all other 46 mentions still resolve with valid offsets.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    # Count how many mentions share the '38%' sentence
    target_mentions = [
        s for s in frozen_data["cv"]["explicit_skills"]
        if "38%" in (s.get("sentence") or s.get("source_sentence", ""))
    ]
    expected_unresolved = len(target_mentions)
    assert expected_unresolved == 5

    # Deepcopy and alter the single token
    cv_altered = copy.deepcopy(frozen_data["cv"])
    for s in cv_altered["explicit_skills"]:
        sent = s.get("sentence") or s.get("source_sentence", "")
        if "38%" in sent:
            new_sent = sent.replace("38%", "39%")
            if "sentence" in s:
                s["sentence"] = new_sent
            if "source_sentence" in s:
                s["source_sentence"] = new_sent

    result = skill_postprocessor.process_extraction(
        raw_result=cv_altered,
        text=cv_cleaned,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )

    assert result.stats.unresolved_evidences == expected_unresolved
    resolved_count = sum(1 for s in result.skills for ev in s.evidences if ev.offset_resolved)
    unresolved_count = sum(1 for s in result.skills for ev in s.evidences if not ev.offset_resolved)
    assert unresolved_count == 5
    assert resolved_count == 46
    assert result.stats.total_mentions == 51


def test_invalid_skill_id_pattern():
    """Verify skill_id regex matching."""
    with pytest.raises(ValidationError):
        ExtractedSkill(
            skill_id="INVALID_UPPERCASE",
            surface_forms=["Python"],
            kind="skill",
            evidences=[],
        )


# -----------------------------------------------------------------------------
# Phase C Step 2: Deterministic Section Tagging Tests
# -----------------------------------------------------------------------------

def test_section_tagger_find_section_spans_unit_cases():
    """
    Unit tests for find_section_spans on small inline strings covering:
    - exact heading
    - heading with trailing colon
    - mixed case
    - unknown ALL-CAPS heading creates an 'unknown' span
    - 'GPA 3.4/4.0' is NOT a heading
    - a bullet line that merely contains a heading word is NOT a heading
    - text before the first heading is 'header'
    """
    # 1. Exact heading
    spans = find_section_spans("SKILLS\nPython\nJava", "CV")
    assert len(spans) == 1
    assert spans[0].name == "skills"
    assert spans[0].heading_text == "SKILLS"

    # 2. Heading with trailing colon
    spans = find_section_spans("Skills:\nPython\nJava", "CV")
    assert len(spans) == 1
    assert spans[0].name == "skills"
    assert spans[0].heading_text == "Skills:"

    # 3. Mixed case
    spans = find_section_spans("Work Experience\nBuilt distributed systems", "CV")
    assert len(spans) == 1
    assert spans[0].name == "experience"
    assert spans[0].heading_text == "Work Experience"

    # 4. Unknown ALL-CAPS heading creates an 'unknown' span
    spans = find_section_spans("VOLUNTEER ACTIVITIES\nOrganized community tech meetups", "CV")
    assert len(spans) == 1
    assert spans[0].name == "unknown"
    assert spans[0].heading_text == "VOLUNTEER ACTIVITIES"

    # 5. 'GPA 3.4/4.0' is NOT a heading (contains digits and dots)
    text = "EDUCATION\nBachelor of Science\nGPA 3.4/4.0"
    spans = find_section_spans(text, "CV")
    assert len(spans) == 1
    assert spans[0].name == "education"
    assert section_at(spans, text.index("GPA 3.4/4.0")) == "education"

    # 6. A bullet line that merely contains a heading word is NOT a heading
    text = "EXPERIENCE\n• Experience with Kafka and microservices\n• Skills in CI/CD"
    spans = find_section_spans(text, "CV")
    assert len(spans) == 1
    assert spans[0].name == "experience"
    assert section_at(spans, text.index("• Skills in CI/CD")) == "experience"

    # 7. Text before the first heading is 'header'
    text = "Nguyen Van A\nSenior Backend Engineer\nSUMMARY\n5 years experience"
    spans = find_section_spans(text, "CV")
    assert len(spans) == 2
    assert spans[0].name == "header"
    assert spans[0].start == 0
    assert spans[0].end == text.index("SUMMARY")
    assert spans[1].name == "summary"


def test_golden_01_backend_cv_and_jd_section_tagging():
    """
    Phase C Step 2 Golden Test:
    - Detected headings equal EXACTLY:
      CV: SUMMARY, SKILLS, EXPERIENCE, EDUCATION, CERTIFICATIONS.
      JD: ABOUT THE ROLE, KEY RESPONSIBILITIES, REQUIREMENTS, NICE TO HAVE, BENEFITS.
    - No resolved evidence in either document has section None or 'unknown'.
    - Expected sections sets:
      CV: Spring Boot == {"summary","skills","experience"};
          Redis == {"skills"}; "AWS Certified Developer – Associate" -> {"certifications"};
          "relational database design" -> {"summary"}.
      JD: Kafka == {"responsibilities","requirements"}; Kubernetes == {"nice_to_have"};
          AWS == {"nice_to_have"}; fintech == {"nice_to_have"}; Docker == {"requirements"};
          Java == {"about","requirements"}.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        jd_cleaned = document_parser_service.clean_extracted_text(jd_raw)

    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    # 1. Detected Headings Assertion
    cv_spans = find_section_spans(cv_cleaned, "CV")
    cv_detected_headings = [(s.heading_text, s.name) for s in cv_spans if s.name != "header"]
    assert cv_detected_headings == [
        ("SUMMARY", "summary"),
        ("SKILLS", "skills"),
        ("EXPERIENCE", "experience"),
        ("EDUCATION", "education"),
        ("CERTIFICATIONS", "certifications"),
    ]

    jd_spans = find_section_spans(jd_cleaned, "JD")
    jd_detected_headings = [(s.heading_text, s.name) for s in jd_spans if s.name != "header"]
    assert jd_detected_headings == [
        ("ABOUT THE ROLE", "about"),
        ("KEY RESPONSIBILITIES", "responsibilities"),
        ("REQUIREMENTS", "requirements"),
        ("NICE TO HAVE", "nice_to_have"),
        ("BENEFITS", "benefits"),
    ]

    # Process CV & JD through postprocessor
    cv_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["cv"],
        text=cv_cleaned,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    jd_result = skill_postprocessor.process_extraction(
        raw_result=frozen_data["jd"],
        text=jd_cleaned,
        filename="01_Backend_JD.pdf",
        document_type="JD",
    )

    # 2. No resolved evidence has section None or 'unknown'
    for s in cv_result.skills:
        for ev in s.evidences:
            if ev.offset_resolved:
                assert ev.section is not None, f"CV evidence has section None: {ev.sentence}"
                assert ev.section != "unknown", f"CV evidence has section 'unknown': {ev.sentence}"

    for s in jd_result.skills:
        for ev in s.evidences:
            if ev.offset_resolved:
                assert ev.section is not None, f"JD evidence has section None: {ev.sentence}"
                assert ev.section != "unknown", f"JD evidence has section 'unknown': {ev.sentence}"

    # 3. Expected sections sets
    cv_skills_by_name = {s.surface_forms[0]: set(s.sections) for s in cv_result.skills}
    assert cv_skills_by_name.get("Spring Boot") == {"summary", "skills", "experience"}
    assert cv_skills_by_name.get("Redis") == {"skills"}
    assert cv_skills_by_name.get("AWS Certified Developer – Associate") == {"certifications"}
    assert cv_skills_by_name.get("relational database design") == {"summary"}

    jd_skills_by_name = {s.surface_forms[0]: set(s.sections) for s in jd_result.skills}
    assert jd_skills_by_name.get("Kafka") == {"responsibilities", "requirements"}
    assert jd_skills_by_name.get("Kubernetes") == {"nice_to_have"}
    assert jd_skills_by_name.get("AWS") == {"nice_to_have"}
    assert jd_skills_by_name.get("fintech") == {"nice_to_have"}
    assert jd_skills_by_name.get("Docker") == {"requirements"}
    # Note: In frozen LLM extractions, Java occurs in 'about' and 'requirements'.
    # In KEY RESPONSIBILITIES, the LLM extracted RESTful microservices but omitted Java.
    assert jd_skills_by_name.get("Java") == {"about", "requirements"}


def test_golden_jd_section_deletion_negative_control():
    """
    Negative control test:
    Delete the 'REQUIREMENTS' heading line from a copy of JD text and verify
    that Docker and JUnit evidences become section 'responsibilities' (falling into the previous span).
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        jd_cleaned = document_parser_service.clean_extracted_text(jd_raw)

    with open("tests/fixtures/01_Backend_llm_raw.json", "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    # Delete 'REQUIREMENTS' heading line from copy of JD text
    assert "\nREQUIREMENTS\n" in jd_cleaned or "REQUIREMENTS" in jd_cleaned
    jd_no_req = jd_cleaned.replace("REQUIREMENTS\n", "")

    result_no_req = skill_postprocessor.process_extraction(
        raw_result=frozen_data["jd"],
        text=jd_no_req,
        filename="01_Backend_JD.pdf",
        document_type="JD",
    )

    jd_skills = {s.surface_forms[0]: s for s in result_no_req.skills}
    docker_skill = jd_skills["Docker"]
    junit_skill = jd_skills["JUnit"]

    # Docker and JUnit evidences fall into the previous span ('responsibilities')
    assert "responsibilities" in docker_skill.sections
    assert "requirements" not in docker_skill.sections
    assert docker_skill.evidences[0].section == "responsibilities"

    assert "responsibilities" in junit_skill.sections
    assert "requirements" not in junit_skill.sections
    assert junit_skill.evidences[0].section == "responsibilities"


def test_locator_repeated_sentence_risk_limitation():
    """
    Document repeated-sentence risk limitation:
    When the exact SAME sentence appears under two different headings in the document,
    locate_sentence deterministically returns the first match in text.
    Therefore, the second occurrence's evidence is attributed to the first heading's section.
    This test documents and enforces this explicit known limitation.
    """
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    repeated_text = (
        "SUMMARY\n"
        "Solid experience with Python and FastAPI in backend microservices.\n\n"
        "EXPERIENCE\n"
        "Solid experience with Python and FastAPI in backend microservices.\n"
    )

    raw_data = {
        "skills": [
            {
                "surface_form": "Python",
                "category": "Technology/Tool",
                "sentence": "Solid experience with Python and FastAPI in backend microservices.",
            }
        ]
    }

    result = skill_postprocessor.process_extraction(
        raw_result=raw_data,
        text=repeated_text,
        filename="test_repeated.txt",
        document_type="CV",
    )

    # Both locator and section tagger resolve to the first occurrence (under 'summary')
    ev = result.skills[0].evidences[0]
    assert ev.offset_resolved is True
    assert ev.section == "summary"
    assert result.skills[0].sections == ["summary"]


# -----------------------------------------------------------------------------
# Phase D1: Mention-Level Schema, Kind, Verbatim Guard, and Header Guard Tests
# -----------------------------------------------------------------------------

def test_kind_from_llm_wins_over_category_inferred():
    """Verify explicit kind from LLM takes precedence over category inference, setting kind_source='llm'."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    raw_data = {
        "skills": [
            {
                "mention": "order-management microservice",
                "kind": "context",
                "category": "Technology/Tool",  # Category says Technology/Tool, but LLM says context
                "sentence": "Developed an order-management microservice in Go.",
            },
            {
                "mention": "Fintech",
                "category": "Domain Knowledge",  # No kind provided, should infer 'domain'
                "sentence": "Extensive experience in Fintech domain.",
            },
            {
                "mention": "Go",
                "category": "Technology/Tool",  # No kind provided, should infer 'skill'
                "sentence": "Developed an order-management microservice in Go.",
            },
        ]
    }
    text = "Developed an order-management microservice in Go. Extensive experience in Fintech domain."
    result = skill_postprocessor.process_extraction(raw_data, text=text, document_type="CV")

    skills_dict = {s.skill_id: s for s in result.skills}

    # 1. LLM kind="context" wins
    order_skill = skills_dict["order-management-microservice"]
    assert order_skill.kind == "context"
    assert order_skill.evidences[0].kind == "context"
    assert order_skill.evidences[0].kind_source == "llm"

    # 2. Inferred "domain" from category
    fintech_skill = skills_dict["fintech"]
    assert fintech_skill.kind == "domain"
    assert fintech_skill.evidences[0].kind == "domain"
    assert fintech_skill.evidences[0].kind_source == "inferred"

    # 3. Inferred "skill" from default
    go_skill = skills_dict["go"]
    assert go_skill.kind == "skill"
    assert go_skill.evidences[0].kind == "skill"
    assert go_skill.evidences[0].kind_source == "inferred"


def test_kind_conflicts_increments_stat_and_satisfies_invariant():
    """Verify conflicting kinds for the same skill_id increments stats.kind_conflicts."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    raw_data = {
        "skills": [
            {
                "mention": "Payment Gateway",
                "kind": "domain",
                "category": "Domain Knowledge",
                "sentence": "Integrated international Payment Gateway services.",
            },
            {
                "mention": "payment gateway",
                "kind": "context",
                "category": "Technology/Tool",
                "sentence": "Maintained payment gateway microservice cluster.",
            },
        ]
    }
    text = "Integrated international Payment Gateway services. Maintained payment gateway microservice cluster."
    result = skill_postprocessor.process_extraction(raw_data, text=text, document_type="CV")

    assert result.stats.unique_skills == 1
    assert result.stats.total_mentions == 2
    assert result.stats.kind_conflicts == 1
    skill = result.skills[0]
    assert skill.skill_id == "payment-gateway"
    assert skill.surface_forms == ["Payment Gateway", "payment gateway"]
    # First evidence kind is kept for the canonical skill
    assert skill.kind == "domain"
    assert skill.evidences[0].kind == "domain"
    assert skill.evidences[1].kind == "context"


def test_non_verbatim_mention_flagged_and_counted():
    """Verify non-verbatim mentions are retained (not dropped), flagged verbatim_ok=False, and counted in stats."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    raw_data = {
        "skills": [
            {
                "mention": "unit tests",
                "category": "Engineering Practice",
                "sentence": "Write unit and integration tests for all services.",
            },
            {
                "mention": "backend microservices",
                "category": "Technology/Tool",
                "sentence": "Write unit and integration tests for all services.",
            },
            {
                "mention": "integration tests",
                "category": "Engineering Practice",
                "sentence": "Write unit and integration tests for all services.",
            },
        ]
    }
    text = "Write unit and integration tests for all services."
    result = skill_postprocessor.process_extraction(raw_data, text=text, document_type="JD")

    assert result.stats.total_mentions == 3
    assert result.stats.unique_skills == 3
    assert result.stats.non_verbatim_mentions == 2

    # Mentions are NOT dropped; verbatim_ok correctly reflects verbatim check
    skills_by_id = {s.skill_id: s for s in result.skills}
    assert skills_by_id["unit-tests"].evidences[0].verbatim_ok is False
    assert skills_by_id["backend-microservices"].evidences[0].verbatim_ok is False
    assert skills_by_id["integration-tests"].evidences[0].verbatim_ok is True


def test_header_evidences_stat_and_invariant():
    """Verify evidences occurring before the first section heading are tagged section='header' and counted in header_evidences."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    text = (
        "John Doe - Senior Software Engineer specializing in Python\n\n"
        "SUMMARY\n"
        "Experienced software developer building backend systems with FastAPI.\n"
    )
    raw_data = {
        "skills": [
            {
                "mention": "Python",
                "category": "Technology/Tool",
                "sentence": "John Doe - Senior Software Engineer specializing in Python",
            },
            {
                "mention": "FastAPI",
                "category": "Technology/Tool",
                "sentence": "Experienced software developer building backend systems with FastAPI.",
            },
        ]
    }
    result = skill_postprocessor.process_extraction(raw_data, text=text, document_type="CV")

    assert result.stats.total_mentions == 2
    assert result.stats.header_evidences == 1
    python_skill = next(s for s in result.skills if s.skill_id == "python")
    assert python_skill.evidences[0].section == "header"
    fastapi_skill = next(s for s in result.skills if s.skill_id == "fastapi")
    assert fastapi_skill.evidences[0].section == "summary"






def test_postprocessor_quarantine_structural_errors():
    """Verify that missing surface_form or sentence are quarantined and stats.quarantined_mentions counted."""
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    raw_result = {
        "skills": [
            {
                "mention": "Python",
                "kind": "skill",
                "sentence": "Experience with Python.",
            },
            {
                # Missing mention
                "kind": "skill",
                "sentence": "Sentence without mention.",
            },
            {
                # Non-string sentence
                "mention": "Java",
                "kind": "skill",
                "sentence": 12345,
            },
            {
                # Empty whitespace mention
                "mention": "   ",
                "kind": "skill",
                "sentence": "Some valid sentence.",
            },
        ]
    }
    text = "Experience with Python and Java."
    res = skill_postprocessor.process_extraction(raw_result, text=text)
    assert res.stats.total_mentions == 1
    assert res.stats.quarantined_mentions == 3
    assert len(res.quarantined) == 3
    assert res.quarantined[0]["raw_item"]["sentence"] == "Sentence without mention."
    assert any("surface_form" in err for err in res.quarantined[0]["errors"])
    assert any("sentence" in err for err in res.quarantined[1]["errors"])
    assert any("surface_form" in err for err in res.quarantined[2]["errors"])


def test_prompt_template_contents_and_sha256():
    """Verify that EXPLICIT_SKILL_SYSTEM_PROMPT includes all required rules, definitions, and few-shot examples."""
    from matching_cv.app.services.prompt_templates import EXPLICIT_SKILL_SYSTEM_PROMPT

    required_phrases = [
        "reusable technology, tool, language, framework, technique or technical practice",
        "transferable business domain",
        "project- or company-specific system, or a generic environment phrase",
        "credential name or a certification requirement",
        "functional and regression tests",
        "Build and operate batch data pipelines in Python (Airflow) that support billing and revenue reporting.",
        "Applicants need a PMP or Scrum certification and experience writing functional and regression tests.",
        "Supervised retail operations with inventory forecasting and trained hospital staff on post-operative patient care.",
        "KHÔNG SUY DIỄN",
        "ĐẶC BIỆT CHÚ Ý TỚI DOMAIN & OPERATION",
        "KHÔNG TRÍCH XUẤT TỪ TITLE BLOCK ĐẦU TRANG",
        "title block",
        "inventory forecasting",
        "post-operative patient care",
    ]
    for phrase in required_phrases:
        assert phrase in EXPLICIT_SKILL_SYSTEM_PROMPT, f"Missing phrase in prompt: '{phrase}'"

    prompt_sha256 = hashlib.sha256(EXPLICIT_SKILL_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert prompt_sha256 == "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"


def test_prompt_rule_10_precision_and_non_skill_entities_excluded():
    """Verify that rule 10 key phrases and precision few-shot example are in EXPLICIT_SKILL_SYSTEM_PROMPT."""
    from matching_cv.app.services.prompt_templates import EXPLICIT_SKILL_SYSTEM_PROMPT

    rule_10_phrases = [
        "Do NOT extract: numbers, metrics or results",
        "38%, 120k orders/day, GPA",
        "years of experience",
        "company names",
        "job titles, including those in experience-entry headings",
        "schools and degrees",
        "locations",
        "dates",
        "benefits",
        "abstract qualities that are not skills",
        "fast, correct, and auditable",
        "Senior Data Analyst at Acme Corp (2019-2023): cut report turnaround by 40% using SQL.",
    ]
    for phrase in rule_10_phrases:
        assert phrase in EXPLICIT_SKILL_SYSTEM_PROMPT, f"Missing rule 10 phrase in prompt: '{phrase}'"


def test_production_prompt_sha256_constant():
    """Verify that EXPLICIT_SKILL_SYSTEM_PROMPT has byte-identical sha256 digest."""
    import hashlib
    from matching_cv.app.services.prompt_templates import EXPLICIT_SKILL_SYSTEM_PROMPT

    prompt_sha256 = hashlib.sha256(EXPLICIT_SKILL_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert prompt_sha256 == "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"


def test_prompt_examples_do_not_leak_eval_text():
    """Verify that no few-shot source_sentence in any variant appears (whitespace-tolerant, casefold)
    in tests/fixtures/, in the unit texts of the annotation gold files, or in the cleaned fixture PDFs."""
    import json
    from matching_cv.app.services.prompt_templates import (
        EXPLICIT_SKILL_SYSTEM_PROMPT,
        EXPLICIT_SKILL_SYSTEM_PROMPT_V2A,
        EXPLICIT_SKILL_SYSTEM_PROMPT_V2B,
    )
    from matching_cv.app.services.document_parser import document_parser_service

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()

    fixtures_dir = "tests/fixtures"
    fixture_texts = []
    for fname in os.listdir(fixtures_dir):
        fpath = os.path.join(fixtures_dir, fname)
        if not os.path.isfile(fpath):
            continue

        if fname.lower().endswith(".pdf"):
            with open(fpath, "rb") as f:
                raw_text, _ = document_parser_service.extract_text_from_pdf(f.read())
            cleaned_text = document_parser_service.clean_extracted_text(raw_text)
            fixture_texts.append((fname, norm(cleaned_text)))
        else:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            fixture_texts.append((fname, norm(content)))

    gold_dir = "annotation/gold"
    gold_unit_texts = []
    if os.path.isdir(gold_dir):
        for fname in os.listdir(gold_dir):
            if fname.endswith(".gold.json"):
                with open(os.path.join(gold_dir, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for unit in data.get("units", []):
                        gold_unit_texts.append((f"{fname}:{unit.get('id')}", norm(unit.get("text", ""))))

    variants = {
        "V1": (EXPLICIT_SKILL_SYSTEM_PROMPT, 4),
        "V2A": (EXPLICIT_SKILL_SYSTEM_PROMPT_V2A, 6),
        "V2B": (EXPLICIT_SKILL_SYSTEM_PROMPT_V2B, 8),
        "C1": (EXPLICIT_SKILL_SYSTEM_PROMPT_C1, 4),
        "C2": (EXPLICIT_SKILL_SYSTEM_PROMPT_C2, 6),
        "C3": (EXPLICIT_SKILL_SYSTEM_PROMPT_C3, 8),
    }

    for variant_name, (prompt, expected_cnt) in variants.items():
        few_shot_section = prompt.split("FEW-SHOT EXAMPLES:")[1]
        few_shot_sentences = set(re.findall(r'"source_sentence":\s*"([^"]+)"', few_shot_section))
        assert len(few_shot_sentences) == expected_cnt, (
            f"Variant {variant_name}: expected {expected_cnt} distinct few-shot sentences, found {len(few_shot_sentences)}"
        )

        for s in few_shot_sentences:
            norm_s = norm(s)
            for fname, norm_content in fixture_texts:
                assert norm_s not in norm_content, (
                    f"Variant {variant_name}: few-shot sentence '{s}' leaked into fixture file '{fname}'"
                )
            for unit_id, norm_text in gold_unit_texts:
                assert norm_s not in norm_text, (
                    f"Variant {variant_name}: few-shot sentence '{s}' leaked into gold unit text '{unit_id}'"
                )


PROMPT_VARIANTS = {
    "V1": EXPLICIT_SKILL_SYSTEM_PROMPT,
    "V2A": EXPLICIT_SKILL_SYSTEM_PROMPT_V2A,
    "V2B": EXPLICIT_SKILL_SYSTEM_PROMPT_V2B,
    "C1": EXPLICIT_SKILL_SYSTEM_PROMPT_C1,
    "C2": EXPLICIT_SKILL_SYSTEM_PROMPT_C2,
    "C3": EXPLICIT_SKILL_SYSTEM_PROMPT_C3,
    "IMPLICIT_DEFAULT": IMPLICIT_SKILL_SYSTEM_PROMPT,
    "IMPLICIT_V2": IMPLICIT_SKILL_SYSTEM_PROMPT_V2,
    "VERIFIER_V1": VERIFIER_PROMPT_V1,
    "VERIFIER_V2": VERIFIER_PROMPT_V2,
}


@pytest.mark.parametrize(
    "variant_name",
    [
        pytest.param(
            "V1",
            marks=pytest.mark.xfail(strict=True, reason="Contamination from development documents"),
        ),
        pytest.param(
            "V2A",
            marks=pytest.mark.xfail(strict=True, reason="Contamination from development documents"),
        ),
        pytest.param(
            "V2B",
            marks=pytest.mark.xfail(strict=True, reason="Contamination from development documents"),
        ),
        pytest.param("C1"),
        pytest.param("C2"),
        pytest.param("C3"),
        pytest.param(
            "IMPLICIT_DEFAULT",
            marks=pytest.mark.xfail(
                strict=True,
                reason="Default implicit prompt contains 9 known offending strings: "
                "Kafka, Kafka-based event pipeline, Python, REST APIs, caching, "
                "code review, mentored, microservices, query optimization",
            ),
        ),
        pytest.param("IMPLICIT_V2"),
        pytest.param("VERIFIER_V1"),
        pytest.param("VERIFIER_V2"),
    ],
)
def test_prompt_contamination_eval_text(variant_name):
    """Assert that for every prompt variant, none of the development document strings occurs
    anywhere in the prompt text (casefold, whitespace-tolerant; substring match for strings
    of 4+ characters, whole-word boundary matching only for shorter strings):
    - every surface_form in both gold files (all kinds),
    - every gold unit text and every known_non_skills text,
    - '38%', '120k', '3.4/4.0', 'fast, correct, and auditable'.
    """
    import json
    import re

    prompt_text = PROMPT_VARIANTS[variant_name]

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()

    forbidden_strings = set()
    for gold_path in ["annotation/gold/01_Backend_CV.gold.json", "annotation/gold/01_Backend_JD.gold.json"]:
        if os.path.exists(gold_path):
            with open(gold_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for unit in data.get("units", []):
                if unit.get("text"):
                    forbidden_strings.add(unit["text"])
                for m in unit.get("mentions", []):
                    if m.get("surface_form"):
                        forbidden_strings.add(m["surface_form"])
            for kns in data.get("known_non_skills", []):
                if kns.get("text"):
                    forbidden_strings.add(kns["text"])

    for s in ["38%", "120k", "3.4/4.0", "fast, correct, and auditable"]:
        forbidden_strings.add(s)

    norm_prompt = norm(prompt_text)
    violations = []
    for s in sorted(forbidden_strings):
        ns = norm(s)
        if not ns:
            continue
        if len(ns) < 4:
            pattern = r"(?<![a-z0-9])" + re.escape(ns) + r"(?![a-z0-9])"
            if re.search(pattern, norm_prompt):
                violations.append(s)
        else:
            if ns in norm_prompt:
                violations.append(s)

    assert not violations, (
        f"Variant {variant_name} has {len(violations)} contaminated strings: {violations}"
    )


def test_header_evidences_unsectioned_document_fallback():
    """Verify that for documents without recognized headings, the entire text falls into
    a single fallback 'header' span, so stats.header_evidences counts all resolved mentions."""
    from matching_cv.app.services.section_tagger import find_section_spans
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    unsectioned_text = "Software engineer skilled in Python and Docker with extensive experience in cloud platforms."
    spans = find_section_spans(unsectioned_text, document_type="CV")

    # 1. Spans contain only one fallback 'header' span covering the full text length
    assert len(spans) == 1
    assert spans[0].name == "header"
    assert spans[0].heading_text == ""
    assert spans[0].start == 0
    assert spans[0].end == len(unsectioned_text)

    # 2. Process extraction on unsectioned text
    raw_data = {
        "explicit_skills": [
            {
                "mention": "Python",
                "kind": "skill",
                "category": "Technology/Tool",
                "source_sentence": unsectioned_text,
            },
            {
                "mention": "Docker",
                "kind": "skill",
                "category": "Technology/Tool",
                "source_sentence": unsectioned_text,
            },
        ]
    }
    result = skill_postprocessor.process_extraction(
        raw_result=raw_data,
        text=unsectioned_text,
        document_type="CV",
    )

    # In an unsectioned document, header_evidences equals total_mentions
    assert result.stats.total_mentions == 2
    assert result.stats.header_evidences == 2
    for skill in result.skills:
        assert skill.sections == ["header"]
        for ev in skill.evidences:
            assert ev.section == "header"


# -----------------------------------------------------------------------------
# GATE D3: Mention-level Offsets Unit & Golden Tests
# -----------------------------------------------------------------------------

def test_locate_mention_in_sentence_unit_tests():
    """
    GATE D3 Unit Tests for locate_mention_in_sentence:
    - Single occurrence
    - Repeated word in one sentence (CV checkout bullet)
    - Hyphenated ('Kafka-based')
    - Slash list ('Java/Spring Boot')
    - Not found
    """
    from matching_cv.app.services.text_locator import locate_mention_in_sentence, norm_casefold

    # 1. Single occurrence
    sent1 = "Experience building microservices in Python."
    s1, e1, ambig1 = locate_mention_in_sentence(sent1, "Python")
    assert s1 is not None and e1 is not None
    assert ambig1 is False
    assert sent1[s1:e1] == "Python"
    assert norm_casefold(sent1[s1:e1]) == norm_casefold("Python")

    # 2. Repeated word in one sentence: the CV bullet contains "checkout" twice
    cv_bullet = (
        "Designed and rolled out a Kafka-based event pipeline to decouple inventory "
        "updates from checkout, cutting checkout failures during flash sales by roughly 60%."
    )
    s2, e2, ambig2 = locate_mention_in_sentence(cv_bullet, "checkout")
    assert s2 is not None and e2 is not None
    assert ambig2 is True, "First occurrence wins and mention_ambiguous must be True"
    assert cv_bullet[s2:e2] == "checkout"
    assert norm_casefold(cv_bullet[s2:e2]) == norm_casefold("checkout")
    # Verify it points to the FIRST occurrence
    second_idx = cv_bullet.index("checkout", e2)
    assert s2 < second_idx

    # 3. Hyphenated: "Kafka-based"
    sent3 = "Engineered a Kafka-based event pipeline for transaction logs."
    # Mention is "Kafka-based"
    s3a, e3a, ambig3a = locate_mention_in_sentence(sent3, "Kafka-based")
    assert s3a is not None and e3a is not None
    assert ambig3a is False
    assert sent3[s3a:e3a] == "Kafka-based"
    # Mention is "Kafka" inside "Kafka-based"
    s3b, e3b, ambig3b = locate_mention_in_sentence(sent3, "Kafka")
    assert s3b is not None and e3b is not None
    assert ambig3b is False
    assert sent3[s3b:e3b] == "Kafka"

    # 4. Slash list: "Java/Spring Boot"
    sent4 = "Stack includes Java/Spring Boot microservices and PostgreSQL."
    # Mention "Java"
    s4a, e4a, ambig4a = locate_mention_in_sentence(sent4, "Java")
    assert s4a is not None and e4a is not None
    assert ambig4a is False
    assert sent4[s4a:e4a] == "Java"
    # Mention "Spring Boot"
    s4b, e4b, ambig4b = locate_mention_in_sentence(sent4, "Spring Boot")
    assert s4b is not None and e4b is not None
    assert ambig4b is False
    assert sent4[s4b:e4b] == "Spring Boot"
    # Mention "Java/Spring Boot"
    s4c, e4c, ambig4c = locate_mention_in_sentence(sent4, "Java/Spring Boot")
    assert s4c is not None and e4c is not None
    assert ambig4c is False
    assert sent4[s4c:e4c] == "Java/Spring Boot"

    # 5. Not found
    sent5 = "Proficient in Python and FastAPI."
    s5, e5, ambig5 = locate_mention_in_sentence(sent5, "Kubernetes")
    assert s5 is None and e5 is None
    assert ambig5 is False


def test_evidence_invalid_mention_offsets():
    """Verify that Evidence validates mention_start and mention_end bounds and invariants."""
    # mention_start >= mention_end
    with pytest.raises(ValidationError) as exc_info:
        Evidence(
            surface_form="Python",
            sentence="Python developer",
            start=0,
            end=16,
            mention_start=6,
            mention_end=6,
        )
    assert "strictly less than mention_end offset" in str(exc_info.value)

    # mention_start < start
    with pytest.raises(ValidationError) as exc_info:
        Evidence(
            surface_form="Python",
            sentence="Python developer",
            start=10,
            end=26,
            mention_start=5,
            mention_end=15,
        )
    assert "must be inside evidence span" in str(exc_info.value)

    # mention_end > end
    with pytest.raises(ValidationError) as exc_info:
        Evidence(
            surface_form="Python",
            sentence="Python developer",
            start=10,
            end=26,
            mention_start=12,
            mention_end=30,
        )
    assert "must be inside evidence span" in str(exc_info.value)

    # Partial mention offsets
    with pytest.raises(ValidationError) as exc_info:
        Evidence(
            surface_form="Python",
            sentence="Python developer",
            start=0,
            end=16,
            mention_start=0,
            mention_end=None,
        )
    assert "Both mention_start and mention_end must be provided if either is present" in str(exc_info.value)

    # Mention offsets present when start/end is None
    with pytest.raises(ValidationError) as exc_info:
        Evidence(
            surface_form="Python",
            sentence="Python developer",
            start=None,
            end=None,
            mention_start=0,
            mention_end=6,
        )
    assert "Mention offsets cannot be present when evidence offsets" in str(exc_info.value)


def test_schema_invariants_mismatched_mention_stats():
    """Verify ExtractionResult enforces unresolved_mentions and ambiguous_mentions invariants."""
    # Invariant 8: mismatched unresolved_mentions
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=0,
                non_verbatim_mentions=0,
                header_evidences=0,
                unresolved_mentions=5,  # actual is 0
                ambiguous_mentions=0,
            ),
            skills=[
                ExtractedSkill(
                    skill_id="python",
                    surface_forms=["Python"],
                    evidences=[
                        Evidence(
                            surface_form="Python",
                            sentence="Python dev",
                            start=0,
                            end=10,
                            mention_start=0,
                            mention_end=6,
                            mention_ambiguous=False,
                        )
                    ],
                )
            ],
        )
    assert "stats.unresolved_mentions (5) != actual unresolved mentions count (0)" in str(exc_info.value)

    # Invariant 9: mismatched ambiguous_mentions
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=0,
                non_verbatim_mentions=0,
                header_evidences=0,
                unresolved_mentions=0,
                ambiguous_mentions=3,  # actual is 1
            ),
            skills=[
                ExtractedSkill(
                    skill_id="checkout",
                    surface_forms=["checkout"],
                    evidences=[
                        Evidence(
                            surface_form="checkout",
                            sentence="checkout and checkout",
                            start=0,
                            end=21,
                            mention_start=0,
                            mention_end=8,
                            mention_ambiguous=True,
                        )
                    ],
                )
            ],
        )
    assert "stats.ambiguous_mentions (3) != actual ambiguous mentions count (1)" in str(exc_info.value)

    # Invariant 10: mismatched unknown_category_mentions
    with pytest.raises(ValidationError) as exc_info:
        ExtractionResult(
            stats=ExtractionStats(
                total_mentions=1,
                unique_skills=1,
                unresolved_evidences=0,
                kind_conflicts=0,
                non_verbatim_mentions=0,
                header_evidences=0,
                unresolved_mentions=0,
                ambiguous_mentions=0,
                unknown_category_mentions=2,  # actual is 1
            ),
            skills=[
                ExtractedSkill(
                    skill_id="communication",
                    surface_forms=["Communication"],
                    category=None,
                    category_raw="Soft Skill",
                    evidences=[
                        Evidence(
                            surface_form="Communication",
                            sentence="Great communication skills",
                            start=0,
                            end=26,
                            mention_start=6,
                            mention_end=19,
                            mention_ambiguous=False,
                            category=None,
                            category_raw="Soft Skill",
                        )
                    ],
                )
            ],
        )
    assert "stats.unknown_category_mentions (2) != actual unknown category mentions count (1)" in str(exc_info.value)


def test_stored_runs_mention_offsets_and_invariants():
    """
    GATE D3 Golden Test on real fixtures using the 10 stored run files in experiments/runs/.
    - Asserts all invariants hold.
    - Asserts every resolved mention span is inside evidence span: ev.start <= ev.mention_start < ev.mention_end <= ev.end.
    - Asserts norm_casefold(cleaned_text[mention_start:mention_end]) == norm_casefold(surface_form).
    - Asserts the CV bullet containing 'checkout' twice has mention_ambiguous == True.
    - Measures and asserts ambiguous, unresolved, and unknown_category mentions per run.
    """
    import glob
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor
    from matching_cv.app.services.text_locator import norm_casefold

    with open("tests/fixtures/01_Backend_CV.pdf", "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        cv_cleaned = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_JD.pdf", "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
        jd_cleaned = document_parser_service.clean_extracted_text(jd_raw)

    run_files = sorted(glob.glob("tests/fixtures/stored_runs/*.json"))
    assert len(run_files) == 10, f"Expected 10 stored runs, found {len(run_files)}"

    for rf in run_files:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        fname = os.path.basename(rf)
        doc_type = "CV" if "CV" in fname else "JD"
        cleaned_text = cv_cleaned if doc_type == "CV" else jd_cleaned

        # Process directly from raw_llm without manual sanitization
        res = skill_postprocessor.process_extraction(
            raw_result=data["raw_llm"],
            text=cleaned_text,
            filename=fname,
            document_type=doc_type,
        )

        # Invariants on every mention
        for s in res.skills:
            for ev in s.evidences:
                if ev.mention_start is not None and ev.mention_end is not None:
                    assert ev.start is not None and ev.end is not None
                    assert ev.start <= ev.mention_start < ev.mention_end <= ev.end
                    mention_text = cleaned_text[ev.mention_start:ev.mention_end]
                    assert norm_casefold(mention_text) == norm_casefold(ev.surface_form)

        # Verified counts: all 10 runs have 0 unresolved mentions
        assert res.stats.unresolved_mentions == 0

        # Verified counts for unknown_category_mentions
        if doc_type == "CV":
            if "run1" in fname:
                assert res.stats.unknown_category_mentions == 3
            elif "run2" in fname or "run5" in fname:
                assert res.stats.unknown_category_mentions == 2
            else:
                assert res.stats.unknown_category_mentions == 0

            # Exactly 1 ambiguous mention: "checkout" in the inventory updates bullet
            assert res.stats.ambiguous_mentions == 1
            # Check the checkout bullet specifically
            checkout_evs = [
                ev for s in res.skills for ev in s.evidences
                if norm_casefold(ev.surface_form) == "checkout" and "inventory updates" in ev.sentence.lower()
            ]
            assert len(checkout_evs) >= 1
            for ev in checkout_evs:
                assert ev.mention_ambiguous is True
        else:
            # JD has 0 ambiguous mentions and 0 unknown_category_mentions
            assert res.stats.ambiguous_mentions == 0
            assert res.stats.unknown_category_mentions == 0


def test_extracted_skill_confidence_none_and_meta():
    """Verify confidence defaults to None (uncalibrated) and extraction_meta is supported."""
    from matching_cv.app.schemas.skill_extraction import ExtractedSkill, ExtractionMeta, ExtractionResult, ExtractionStats
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    # 1. Direct instantiation defaults confidence to None
    skill = ExtractedSkill(
        skill_id="python",
        surface_forms=["Python"],
    )
    assert skill.confidence is None

    # 2. Postprocessor produces confidence = None
    raw = {
        "explicit_skills": [
            {
                "mention": "Python",
                "kind": "skill",
                "category": "Technology/Tool",
                "source_sentence": "We need Python developers.",
            }
        ]
    }
    result = skill_postprocessor.process_extraction(
        raw_result=raw,
        text="We need Python developers.",
        filename="test.pdf",
        document_type="JD",
    )
    assert len(result.skills) == 1
    assert result.skills[0].confidence is None

    # 3. ExtractionMeta propagates to ExtractionResult
    meta = ExtractionMeta(
        prompt_sha256="0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce",
        prompt_variant="default",
        model_configured="qwen/qwen3.7-flash",
        temperature=0.0,
        schema_version="1.0.0",
        extracted_at="2026-10-19T00:00:00Z",
    )
    result_with_meta = skill_postprocessor.process_extraction(
        raw_result=raw,
        text="We need Python developers.",
        filename="test.pdf",
        document_type="JD",
        extraction_meta=meta,
    )
    assert result_with_meta.extraction_meta is not None
    assert result_with_meta.extraction_meta.prompt_sha256 == "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"
    assert result_with_meta.extraction_meta.prompt_variant == "default"





