"""Tests for implicit skill extraction schemas, postprocessor, API endpoints,
invariants, coverage function, and frozen fixtures.
"""
import io
import json
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app
from matching_cv.app.schemas.implicit_skill_extraction import (
    CandidateVerification,
    ExtractionMeta,
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
    RawImplicitExtraction,
    RawImplicitExtractionV2,
    RawImplicitSkillMention,
    RawImplicitSkillMentionV2,
)
from matching_cv.app.services.document_parser import document_parser_service
from matching_cv.app.services.implicit_skill_postprocessor import (
    PorterStemmer,
    aggregate_runs,
    build_explicit_list,
    coverage_vs_explicit,
    implicit_skill_postprocessor,
    postprocess_verification,
    token_jaccard,
    tokenize_and_stem,
    verify_candidates,
)
from matching_cv.app.services.llm_service import LLMService, ProvenanceMismatchError, llm_service
from matching_cv.app.services.prompt_templates import (
    IMPLICIT_SKILL_SYSTEM_PROMPT,
    IMPLICIT_SKILL_SYSTEM_PROMPT_V2,
    VERIFIER_PROMPT_V1,
    VERIFIER_PROMPT_V2,
)
from matching_cv.tests.helpers import run_single_implicit_extraction


@pytest.fixture
def client():
    """Test client fixture bypassing heavy model loads."""
    with patch("matching_cv.app.core.model_loader.model_loader.load_model"):
        with TestClient(app) as test_client:
            yield test_client


def test_implicit_postprocessor_dedup_and_invariants():
    """Test that postprocessor aggregates evidences by skill_id and computes correct stats."""
    raw = RawImplicitExtraction(
        implicit_skills=[
            RawImplicitSkillMention(
                skill_label="System Design",
                category="Technical Concept",
                inferred_from="Designed event-driven microservices using Kafka.",
                reasoning="Requires distributed system knowledge.",
                confidence=0.92,
            ),
            RawImplicitSkillMention(
                skill_label="System Design",
                category="Technical Concept",
                inferred_from="Architected scalable API serving 1M daily requests.",
                reasoning="High-scale API needs robust architectural design.",
                confidence=0.88,
            ),
            RawImplicitSkillMention(
                skill_label="Leadership",
                category="Soft Skill",
                inferred_from="Mentored 4 junior engineers.",
                reasoning="Mentorship implies leadership and knowledge sharing.",
                confidence=0.90,
            ),
        ]
    )
    text = (
        "Designed event-driven microservices using Kafka. "
        "Architected scalable API serving 1M daily requests. "
        "Mentored 4 junior engineers."
    )
    result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw,
        text=text,
        filename="test_cv.pdf",
        document_type="CV",
    )

    assert isinstance(result, ImplicitExtractionResult)
    assert result.stats.total_inferences == 3
    assert result.stats.unique_skills == 2
    assert len(result.skills) == 2
    assert result.stats.non_verbatim_evidences == 0
    assert result.stats.multi_fragment_evidences == 0
    assert result.stats.multi_section_evidences == 0

    # Verify deduplication for System Design
    sys_design = next((s for s in result.skills if s.skill_id == "system-design"), None)
    assert sys_design is not None
    assert sys_design.label == "System Design"
    assert sys_design.category == "Technical Concept"
    assert sys_design.confidence is None
    assert len(sys_design.evidences) == 2
    for ev in sys_design.evidences:
        assert len(ev.snippets) == 1
        assert ev.snippets[0].verbatim_ok is True
        assert ev.snippets[0].start is not None


def test_implicit_evidence_snippets_and_fragments():
    """Test splitting on ellipses ('...' and '…'), verbatim checks, and non-verbatim handling."""
    text = (
        "EXPERIENCE\n"
        "Built asynchronous broker with RabbitMQ. Deployed on Kubernetes cluster.\n"
        "EDUCATION\n"
        "B.S. in Computer Science."
    )

    raw = RawImplicitExtraction(
        implicit_skills=[
            RawImplicitSkillMention(
                skill_label="Distributed Systems",
                category="Technical Concept",
                # Contains both '...' and non-verbatim fragment
                inferred_from="Built asynchronous broker with RabbitMQ... non-existent text here… Deployed on Kubernetes cluster.",
                reasoning="Multi-fragment inference with one invalid part.",
                confidence=0.85,
            )
        ]
    )

    result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw,
        text=text,
        filename="test.pdf",
        document_type="CV",
    )

    assert len(result.skills) == 1
    skill = result.skills[0]
    assert len(skill.evidences) == 1
    ev = skill.evidences[0]

    # Inferred from raw is preserved without modification
    assert ev.inferred_from_raw == "Built asynchronous broker with RabbitMQ... non-existent text here… Deployed on Kubernetes cluster."
    # Fragments split into 3 snippets
    assert len(ev.snippets) == 3
    assert ev.snippets[0].text == "Built asynchronous broker with RabbitMQ"
    assert ev.snippets[0].verbatim_ok is True
    assert ev.snippets[0].start is not None

    assert ev.snippets[1].text == "non-existent text here"
    assert ev.snippets[1].verbatim_ok is False
    assert ev.snippets[1].start is None
    assert ev.snippets[1].end is None
    assert ev.snippets[1].section is None

    assert ev.snippets[2].text == "Deployed on Kubernetes cluster."
    assert ev.snippets[2].verbatim_ok is True
    assert ev.snippets[2].start is not None

    # Stats reflect non-verbatim and multi-fragment
    assert result.stats.non_verbatim_evidences == 1
    assert result.stats.multi_fragment_evidences == 1


def test_implicit_invariants_enforcement():
    """Test that violating any of the 7 invariants raises ValueError."""
    snip1 = ImplicitEvidenceSnippet(
        text="Sample text",
        start=0,
        end=11,
        section="summary",
        verbatim_ok=True,
    )
    ev1 = ImplicitEvidence(
        inferred_from_raw="Sample text",
        snippets=[snip1],
        reasoning="Test reasoning",
        llm_confidence_raw=0.9,
    )
    skill1 = ImplicitExtractedSkill(
        skill_id="test-skill-1",
        label="Test Skill 1",
        category="Technical Concept",
        category_raw="Technical Concept",
        type="implicit",
        confidence=None,
        evidences=[ev1],
    )
    skill2 = ImplicitExtractedSkill(
        skill_id="test-skill-2",
        label="Test Skill 2",
        category="Technical Concept",
        category_raw="Technical Concept",
        type="implicit",
        confidence=None,
        evidences=[ev1],
    )

    # 1. Duplicate skill_id
    with pytest.raises(ValueError, match="duplicate skill_id"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=2,
                unique_skills=2,
                non_verbatim_evidences=0,
                multi_fragment_evidences=0,
                multi_section_evidences=0,
            ),
            skills=[skill1, skill1],
        )

    # 2. Invariant unique_skills mismatch
    with pytest.raises(ValueError, match="stats.unique_skills"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=2,
                unique_skills=1,  # wrong (2 actual skills)
                non_verbatim_evidences=0,
                multi_fragment_evidences=0,
                multi_section_evidences=0,
            ),
            skills=[skill1, skill2],
        )

    # 3. Invariant total_inferences mismatch
    with pytest.raises(ValueError, match="stats.total_inferences"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=2,  # wrong
                unique_skills=1,
                non_verbatim_evidences=0,
                multi_fragment_evidences=0,
                multi_section_evidences=0,
            ),
            skills=[skill1],
        )

    # 4. Invariant non_verbatim_evidences mismatch
    with pytest.raises(ValueError, match="stats.non_verbatim_evidences"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=1,
                unique_skills=1,
                non_verbatim_evidences=1,  # wrong (0 actual)
                multi_fragment_evidences=0,
                multi_section_evidences=0,
            ),
            skills=[skill1],
        )

    # 5. Invariant multi_fragment_evidences mismatch
    with pytest.raises(ValueError, match="stats.multi_fragment_evidences"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=1,
                unique_skills=1,
                non_verbatim_evidences=0,
                multi_fragment_evidences=1,  # wrong (0 actual)
                multi_section_evidences=0,
            ),
            skills=[skill1],
        )

    # 6. Invariant multi_section_evidences mismatch
    ev_same_sec = ImplicitEvidence(
        inferred_from_raw="Part 1... Part 2",
        snippets=[
            ImplicitEvidenceSnippet(text="Part 1", start=0, end=6, section="summary", verbatim_ok=True),
            ImplicitEvidenceSnippet(text="Part 2", start=7, end=13, section="summary", verbatim_ok=True),
        ],
        reasoning="Test",
        llm_confidence_raw=0.9,
    )
    skill_same_sec = ImplicitExtractedSkill(
        skill_id="test-skill-same-sec",
        label="Test Skill Same Sec",
        category="Technical Concept",
        category_raw="Technical Concept",
        type="implicit",
        confidence=None,
        evidences=[ev_same_sec],
    )
    with pytest.raises(ValueError, match="stats.multi_section_evidences"):
        ImplicitExtractionResult(
            stats=ImplicitExtractionStats(
                total_inferences=1,
                unique_skills=1,
                non_verbatim_evidences=0,
                multi_fragment_evidences=1,
                multi_section_evidences=1,  # wrong (0 actual multi-section evidences)
            ),
            skills=[skill_same_sec],
        )


def test_extraction_meta_typing_and_confidence():
    """Test typed ExtractionMeta, calibrated confidence flag, and stats."""
    meta = ExtractionMeta(
        prompt_sha256="1761372bbd812868b09c329782b3892586a66d9440920fd8fd4088f7b4ce66e4",
        prompt_variant="default",
        model_configured="google/gemini-2.5-flash",
        temperature=0.0,
        schema_version="1.0.0",
        extracted_at="2026-10-24T00:00:00Z",
        confidence_calibrated=False,
    )
    assert meta.confidence_calibrated is False
    assert meta.prompt_variant == "default"

    raw = RawImplicitExtraction(
        implicit_skills=[
            RawImplicitSkillMention(
                skill_label="Scalability",
                category="Technical Concept",
                inferred_from="Scaled service to 10M requests.",
                reasoning="High volume needs scalability.",
                confidence=0.88,
            )
        ]
    )
    result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw,
        text="Scaled service to 10M requests.",
        filename="test.pdf",
        document_type="CV",
        extraction_meta=meta,
    )

    assert result.extraction_meta is not None
    assert result.extraction_meta.confidence_calibrated is False
    assert result.skills[0].confidence is None
    assert result.skills[0].evidences[0].llm_confidence_raw == 0.88
    # Assert low_confidence_count is NOT in stats fields
    assert not hasattr(result.stats, "low_confidence_count")


def test_coverage_vs_explicit_pure_function():
    """Test coverage_vs_explicit logic: top-3 matches, token Jaccard >= 0.34 threshold, immutability."""
    # Build a mock implicit extraction
    imp_skill_1 = ImplicitExtractedSkill(
        skill_id="event-driven-architecture-design",
        label="Event-Driven Architecture Design",
        type="implicit",
        evidences=[],
    )
    imp_skill_2 = ImplicitExtractedSkill(
        skill_id="financial-domain-knowledge",
        label="Financial Domain Knowledge",
        type="implicit",
        evidences=[],
    )
    implicit_res = {"skills": [imp_skill_1, imp_skill_2]}

    # Build a mock explicit extraction
    explicit_res = {
        "processed_result": {
            "skills": [
                {"surface_forms": ["message-driven architectures", "Kafka"]},
                {"surface_forms": ["Docker", "Kubernetes"]},
            ]
        }
    }

    coverage = coverage_vs_explicit(implicit_res, explicit_res)
    assert len(coverage) == 2

    # Item 1: 'Event-Driven Architecture Design' vs 'message-driven architectures'
    # stemmed imp: {architectur, design, driven, event}
    # stemmed exp: {architectur, driven, messag}
    # intersection: {architectur, driven} (2)
    # union: {architectur, design, driven, event, messag} (5)
    # Jaccard = 2 / 5 = 0.40 >= 0.34 -> possibly_covered = True
    c1 = next(c for c in coverage if c["skill_id"] == "event-driven-architecture-design")
    assert c1["possibly_covered"] is True
    assert c1["top_matches"][0]["mention"] == "message-driven architectures"
    assert abs(c1["top_matches"][0]["jaccard"] - 0.40) < 1e-4

    # Item 2: 'Financial Domain Knowledge' vs mentions
    c2 = next(c for c in coverage if c["skill_id"] == "financial-domain-knowledge")
    assert c2["possibly_covered"] is False
    assert c2["top_matches"][0]["jaccard"] < 0.34

    # Verify original objects were not mutated
    assert len(implicit_res["skills"]) == 2


def test_frozen_fixture_implicit_dev_run1():
    """Verify frozen fixture tests/fixtures/implicit_dev_run1.json against Item 6 specs:
    - total evidences 15 (CV 9, JD 6)
    - whole-string verbatim 6/15
    - all fragments verbatim 14/15
    - the one non-verbatim fragment is in JD skill 'production-incident-management'
      ('participate in on-call rotation for production services')
    - multi-fragment evidences 3/15, of which 2 span different sections
    """
    fixture_path = "tests/fixtures/implicit_dev_run1.json"
    assert os.path.exists(fixture_path), f"Missing fixture file: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Load cleaned text from dev PDFs
    cv_pdf_path = "tests/fixtures/01_Backend_CV.pdf"
    jd_pdf_path = "tests/fixtures/01_Backend_JD.pdf"
    assert os.path.exists(cv_pdf_path), f"Missing {cv_pdf_path}"
    assert os.path.exists(jd_pdf_path), f"Missing {jd_pdf_path}"

    with open(cv_pdf_path, "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
    cv_text = document_parser_service.clean_extracted_text(cv_raw)

    with open(jd_pdf_path, "rb") as f:
        jd_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
    jd_text = document_parser_service.clean_extracted_text(jd_raw)

    # Process CV & JD independently with code
    cv_res = implicit_skill_postprocessor.process_extraction(
        raw_result=data["cv"],
        text=cv_text,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    jd_res = implicit_skill_postprocessor.process_extraction(
        raw_result=data["jd"],
        text=jd_text,
        filename="01_Backend_JD.pdf",
        document_type="JD",
    )

    from matching_cv.app.services.text_locator import locate_sentence

    cv_evidences = sum(len(s.evidences) for s in cv_res.skills)
    jd_evidences = sum(len(s.evidences) for s in jd_res.skills)
    total_evidences = cv_evidences + jd_evidences

    assert cv_evidences == 9, f"Expected 9 CV evidences, got {cv_evidences}"
    assert jd_evidences == 6, f"Expected 6 JD evidences, got {jd_evidences}"
    assert total_evidences == 15, f"Expected 15 total evidences, got {total_evidences}"

    whole_string_verbatim = 0
    all_fragments_verbatim = 0
    unresolved_fragments = []
    multi_fragment_count = 0
    multi_section_count = 0

    pairs = [("CV", cv_res, cv_text), ("JD", jd_res, jd_text)]
    for doc_name, res, text in pairs:
        for s in res.skills:
            for ev in s.evidences:
                # Whole string verbatim check
                if locate_sentence(text, ev.inferred_from_raw) is not None:
                    whole_string_verbatim += 1

                # All fragments verbatim check
                if all(snip.verbatim_ok for snip in ev.snippets):
                    all_fragments_verbatim += 1
                else:
                    for snip in ev.snippets:
                        if not snip.verbatim_ok:
                            unresolved_fragments.append((doc_name, s.skill_id, snip.text))

                if len(ev.snippets) > 1:
                    multi_fragment_count += 1

                distinct_secs = {snip.section for snip in ev.snippets if snip.section is not None}
                if len(distinct_secs) > 1:
                    multi_section_count += 1

    # Exact numbers assertion from Item 6:
    assert whole_string_verbatim == 6, f"Expected 6/15 whole-string verbatim, got {whole_string_verbatim}"
    assert all_fragments_verbatim == 14, f"Expected 14/15 all-fragments verbatim, got {all_fragments_verbatim}"

    # The one non-verbatim fragment is in JD skill 'production-incident-management'
    assert len(unresolved_fragments) == 1
    doc_type, skill_id, frag_text = unresolved_fragments[0]
    assert doc_type == "JD"
    assert skill_id == "production-incident-management"
    assert frag_text == "participate in on-call rotation for production services"

    # Multi-fragment evidences 3/15, of which 2 span different sections
    assert multi_fragment_count == 3, f"Expected 3/15 multi-fragment, got {multi_fragment_count}"
    assert multi_section_count == 2, f"Expected 2/15 multi-section, got {multi_section_count}"


def test_run_implicit_runner_persistence_and_outcomes():
    """Test experiments/run_implicit.py persistence before validation and outcomes."""
    import asyncio

    async def _runner():
        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Successful extraction -> outcome: ok
            async def mock_extract_ok(text, doc_type, system_prompt=None):
                return {
                    "implicit_skills": [
                        {
                            "skill_label": "System Design",
                            "category": "Technical Concept",
                            "inferred_from": "Built microservices using Kafka.",
                            "reasoning": "Implies distributed architecture.",
                            "confidence": 0.9,
                        }
                    ]
                }

            res_ok = await run_single_implicit_extraction(
                cleaned_text="Built microservices using Kafka.",
                doc_id="mock_doc",
                doc_type="CV",
                run_idx=1,
                out_dir=temp_dir,
                extract_fn=mock_extract_ok,
            )
            assert res_ok["outcome"] == "ok"
            file_path_1 = os.path.join(temp_dir, "mock_doc_run1.json")
            assert os.path.exists(file_path_1)
            with open(file_path_1, "r", encoding="utf-8") as f:
                saved_1 = json.load(f)
            assert saved_1["outcome"] == "ok"
            assert saved_1["raw_llm"] is not None
            assert saved_1["processed_result"] is not None

            # 2. Schema invalid extraction -> outcome: schema_invalid (persisted BEFORE validation)
            async def mock_extract_invalid(text, doc_type, system_prompt=None):
                return {
                    # missing required fields
                    "implicit_skills": [{"not_a_valid_field": 123}]
                }

            res_invalid = await run_single_implicit_extraction(
                cleaned_text="Some text",
                doc_id="mock_doc",
                doc_type="CV",
                run_idx=2,
                out_dir=temp_dir,
                extract_fn=mock_extract_invalid,
            )
            assert res_invalid["outcome"] == "schema_invalid"
            file_path_2 = os.path.join(temp_dir, "mock_doc_run2.json")
            assert os.path.exists(file_path_2)
            with open(file_path_2, "r", encoding="utf-8") as f:
                saved_2 = json.load(f)
            assert saved_2["outcome"] == "schema_invalid"
            assert saved_2["raw_llm"] == {"implicit_skills": [{"not_a_valid_field": 123}]}
            assert saved_2["processed_result"] is None

            # 3. API error extraction -> outcome: api_error
            async def mock_extract_error(text, doc_type, system_prompt=None):
                raise ConnectionError("OpenRouter timeout")

            res_err = await run_single_implicit_extraction(
                cleaned_text="Some text",
                doc_id="mock_doc",
                doc_type="CV",
                run_idx=3,
                out_dir=temp_dir,
                extract_fn=mock_extract_error,
            )
            assert res_err["outcome"] == "api_error"
            file_path_3 = os.path.join(temp_dir, "mock_doc_run3.json")
            assert os.path.exists(file_path_3)
            with open(file_path_3, "r", encoding="utf-8") as f:
                saved_3 = json.load(f)
            assert saved_3["outcome"] == "api_error"
            assert "ConnectionError" in saved_3["metadata"]["raw_validation_error"]

        finally:
            shutil.rmtree(temp_dir)

    asyncio.run(_runner())






# =============================================================================
# GATE I2a Tests: Default unchanged, V2 prompt, Schema, Verifier, Consensus, Stemmer
# =============================================================================

@pytest.mark.anyio
async def test_extract_implicit_skills_default_sends_current_prompt():
    """Verify that the default implicit extraction sends IMPLICIT_SKILL_SYSTEM_PROMPT
    (sha256 56e25ca7d7076a498924d8a6e411642d3068e8ae49a4cb63dc9f1b368f560959)
    without an ALREADY EXPLICIT section in the user message, and extraction_meta
    records the exact prompt sha256 and temperature 0.0."""
    import hashlib

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"implicit_skills": []})
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        service = LLMService()
        doc_text = "Experienced software engineer with deep backend expertise."
        result = await service.extract_implicit_skills(doc_text, "CV")

        assert mock_create.called
        call_kwargs = mock_create.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        user_msg = next(m for m in messages if m["role"] == "user")

        # 1. System prompt sha256 must match current implicit prompt
        sent_prompt = system_msg["content"]
        sent_sha256 = hashlib.sha256(sent_prompt.encode("utf-8")).hexdigest()
        assert sent_sha256 == "56e25ca7d7076a498924d8a6e411642d3068e8ae49a4cb63dc9f1b368f560959"
        assert sent_prompt == IMPLICIT_SKILL_SYSTEM_PROMPT

        # 2. User message must reproduce byte-for-byte today's format (no ALREADY EXPLICIT)
        assert user_msg["content"] == f"Document Type: CV\n\nText:\n{doc_text}"
        assert "ALREADY EXPLICIT" not in user_msg["content"]

        # 3. ExtractionMeta in response dict
        assert "extraction_meta" in result
        meta = result["extraction_meta"]
        assert meta["prompt_sha256"] == "56e25ca7d7076a498924d8a6e411642d3068e8ae49a4cb63dc9f1b368f560959"
        assert meta["prompt_variant"] == "default"
        assert meta["temperature"] == 0.0


@pytest.mark.anyio
async def test_extract_implicit_skills_v2_user_message_already_explicit_and_meta():
    """Verify that when explicit_mentions are provided, the user message carries
    the ALREADY EXPLICIT section listing unique surface forms, and extraction_meta
    records the V2 sha256 and configured temperature."""
    import hashlib

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"implicit_skills": []})
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        service = LLMService()
        doc_text = "Trained five new analysts and wrote the onboarding handbook."
        explicit = ["onboarding handbook", "analyst", "onboarding handbook"]  # with duplicate
        result = await service.extract_implicit_skills(
            text=doc_text,
            document_type="CV",
            explicit_mentions=explicit,
            system_prompt=IMPLICIT_SKILL_SYSTEM_PROMPT_V2,
            temperature=0.2,
        )

        assert mock_create.called
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.2
        messages = call_kwargs["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        user_msg = next(m for m in messages if m["role"] == "user")

        # 1. System prompt sha256 matches V2
        v2_sha256 = hashlib.sha256(IMPLICIT_SKILL_SYSTEM_PROMPT_V2.encode("utf-8")).hexdigest()
        sent_sha256 = hashlib.sha256(system_msg["content"].encode("utf-8")).hexdigest()
        assert sent_sha256 == v2_sha256

        # 2. User message carries ALREADY EXPLICIT with unique mentions
        assert "ALREADY EXPLICIT:" in user_msg["content"]
        assert '["onboarding handbook", "analyst"]' in user_msg["content"]
        assert f"Text:\n{doc_text}" in user_msg["content"]

        # 3. ExtractionMeta records temperature and V2 variant
        meta = result["extraction_meta"]
        assert meta["prompt_sha256"] == v2_sha256
        assert meta["prompt_variant"] == "v2"
        assert meta["temperature"] == 0.2


def test_v2_postprocessing_tolerance_and_invariants():
    """Test V2 postprocessing with per-item tolerance:
    - Unknown basis -> basis None + basis_raw, counted in stats.invalid_basis.
    - Missing label or empty evidence list -> quarantined.
    - Snippets resolved directly with locator without splitting.
    - Snippets containing '...' or '…' are KEPT, flagged ellipsis_in_snippet, and counted in stats.
    - Invariants validate cleanly.
    """
    text = (
        "Cut warehouse picking errors from 4% to 1% by redesigning the shelf layout. "
        "Mentored junior engineers and led technical workshops across teams... "
        "Built internal documentation handbook for team onboarding."
    )

    raw_v2 = {
        "implicit_skills": [
            # 1. Valid V2 item (basis="activity")
            {
                "label": "Process Improvement",
                "basis": "activity",
                "evidence": ["Cut warehouse picking errors from 4% to 1% by redesigning the shelf layout."],
            },
            # 2. Unknown basis -> basis None + basis_raw, counted in stats.invalid_basis
            # Also contains '...' in snippet -> ellipsis_in_snippet=True, counted in stats.ellipsis_snippets
            {
                "label": "Technical Mentoring",
                "basis": "unknown_custom_basis",
                "evidence": ["Mentored junior engineers and led technical workshops across teams..."],
            },
            # 3. Structural error: missing label -> quarantined
            {
                "basis": "role",
                "evidence": ["Built internal documentation handbook for team onboarding."],
            },
            # 4. Structural error: empty evidence list -> quarantined
            {
                "label": "Knowledge Transfer",
                "basis": "role",
                "evidence": [],
            },
        ]
    }

    result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw_v2,
        text=text,
        filename="resume.txt",
        document_type="CV",
    )

    assert isinstance(result, ImplicitExtractionResult)
    assert result.stats.unique_skills == 2
    assert result.stats.total_inferences == 2
    assert result.stats.quarantined_mentions == 2
    assert len(result.quarantined) == 2
    assert result.stats.invalid_basis == 1
    assert result.stats.ellipsis_snippets == 1

    # Skill 1: Process Improvement
    s1 = next(s for s in result.skills if s.skill_id == "process-improvement")
    assert s1.label == "Process Improvement"
    assert s1.basis == "activity"
    assert s1.basis_raw == "activity"
    assert len(s1.evidences) == 1
    assert len(s1.evidences[0].snippets) == 1
    assert s1.evidences[0].snippets[0].verbatim_ok is True
    assert s1.evidences[0].snippets[0].ellipsis_in_snippet is False

    # Skill 2: Technical Mentoring (invalid basis + ellipsis snippet)
    s2 = next(s for s in result.skills if s.skill_id == "technical-mentoring")
    assert s2.label == "Technical Mentoring"
    assert s2.basis is None
    assert s2.basis_raw == "unknown_custom_basis"
    assert len(s2.evidences[0].snippets) == 1
    assert s2.evidences[0].snippets[0].verbatim_ok is True
    assert s2.evidences[0].snippets[0].ellipsis_in_snippet is True


@pytest.mark.anyio
async def test_verifier_candidates_mocked():
    """Verify that verify_candidates passes ONLY document text, candidate label,
    snippets, and explicit list (NOT generator note) to the LLM, and correctly
    processes entailed, plausible, unsupported, covered_by, and invalid verdicts."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "verifications": [
            {
                "label": "Process Improvement",
                "verdict": "entailed",
                "covered_by": None,
                "note": "Directly evidenced by the shelf redesign error drop.",
            },
            {
                "label": "Technical Mentoring",
                "verdict": "plausible",
                "covered_by": None,
                "note": "Workshops and mentorship indicate strong mentoring capability.",
            },
            {
                "label": "Cloud Architecture",
                "verdict": "unsupported",
                "covered_by": None,
                "note": "No cloud infrastructure is mentioned in the evidence.",
            },
            {
                "label": "Onboarding Coordination",
                "verdict": "entailed",
                "covered_by": "onboarding handbook",
                "note": "Covered by explicit mention 'onboarding handbook'.",
            },
            {
                "label": "Team Leadership",
                "verdict": "somewhat_likely",  # invalid verdict -> becomes 'invalid'
                "covered_by": None,
                "note": "Uncalibrated verdict format.",
            },
        ]
    })
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    candidates = [
        {
            "label": "Process Improvement",
            "snippets": ["Cut warehouse picking errors from 4% to 1% by redesigning the shelf layout."],
            "note": "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK",
        },
        {
            "label": "Technical Mentoring",
            "snippets": ["Mentored junior engineers."],
            "note": "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK",
        },
        {
            "label": "Cloud Architecture",
            "snippets": ["Wrote Terraform modules."],
            "note": "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK",
        },
        {
            "label": "Onboarding Coordination",
            "snippets": ["Wrote onboarding handbook."],
            "note": "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK",
        },
        {
            "label": "Team Leadership",
            "snippets": ["Led 5 engineers."],
            "note": "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK",
        },
    ]

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        verifications = await verify_candidates(
            text="Document text goes here.",
            candidates=candidates,
            explicit_mentions=["onboarding handbook"],
        )

        # 1. Verify sent prompt sees ONLY label, snippets, text, explicit list (NO generator notes)
        call_kwargs = mock_create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "GENERATOR_PRIVATE_NOTE_MUST_NOT_LEAK" not in user_msg["content"]
        assert "Process Improvement" in user_msg["content"]
        assert "onboarding handbook" in user_msg["content"]

        # 2. Check verdicts
        assert len(verifications) == 5
        assert verifications[0].verdict == "entailed"
        assert verifications[0].covered_by is None
        assert verifications[1].verdict == "plausible"
        assert verifications[2].verdict == "unsupported"
        assert verifications[3].verdict == "entailed"
        assert verifications[3].covered_by == "onboarding handbook"
        # Tolerance: 'somewhat_likely' -> 'invalid'
        assert verifications[4].verdict == "invalid"
        assert verifications[4]["verdict"] == "invalid"


def test_consensus_aggregate_runs_synthetic():
    """Test pure function aggregate_runs with hand-computable synthetic runs:
    - K = 2 runs.
    - Jaccard >= 0.5 clusters without shared evidence.
    - Near-threshold cases:
      - 0.50 threshold: 2 shared stems out of 4 total -> Jaccard = 0.50 (matches).
      - Below 0.50 without shared snippet: 2 shared stems out of 6 -> Jaccard = 0.333 < 0.50 (no match).
      - With shared snippet: Jaccard = 0.333 >= 0.25 -> clusters!
      - Near-threshold 0.25: 1 shared stem out of 4 -> Jaccard = 0.25 with shared snippet (matches).
      - Below 0.25: 1 shared stem out of 5 -> Jaccard = 0.20 with shared snippet (no match).
    """
    # Case 1: Exact label match across 2 runs -> agreement = 2/2 = 1.0
    run1 = [{"label": "Process Improvement", "evidence": ["Cut picking errors."]}]
    run2 = [{"label": "Process Improvement", "evidence": ["Redesigned shelf layout."]}]
    clusters = aggregate_runs([run1, run2])
    assert len(clusters) == 1
    assert clusters[0]["agreement"] == 1.0
    assert clusters[0]["member_labels"] == ["Process Improvement", "Process Improvement"]

    # Case 2: 0.50 threshold without shared snippet
    # Label 1: "Continuous Process Improvement" -> stems: continu, process, improv (3)
    # Label 2: "Process Improvement Plan" -> stems: process, improv, plan (3)
    # Intersection: process, improv (2). Union: continu, process, improv, plan (4).
    # Jaccard = 2/4 = 0.50 >= 0.50 -> clusters!
    run_a = [{"label": "Continuous Process Improvement", "evidence": ["Snippet A"]}]
    run_b = [{"label": "Process Improvement Plan", "evidence": ["Snippet B"]}]
    clusters_thresh_05 = aggregate_runs([run_a, run_b])
    assert len(clusters_thresh_05) == 1
    assert clusters_thresh_05[0]["agreement"] == 1.0

    # Case 3: 0.333 without shared snippet -> fails 0.50 threshold -> 2 separate clusters
    # Label 1: "Fast System Performance Tuning" -> stems: fast, system, perform, tune (4)
    # Label 2: "System Performance Monitoring Tool" -> stems: system, perform, monitor, tool (4)
    # Intersection: system, perform (2). Union: 6 stems. Jaccard = 2/6 = 0.333.
    run_c1 = [{"label": "Fast System Performance Tuning", "evidence": ["Evidence 1"]}]
    run_c2 = [{"label": "System Performance Monitoring Tool", "evidence": ["Evidence 2"]}]
    clusters_no_shared = aggregate_runs([run_c1, run_c2])
    assert len(clusters_no_shared) == 2
    assert clusters_no_shared[0]["agreement"] == 0.5
    assert clusters_no_shared[1]["agreement"] == 0.5

    # Case 4: Same labels (Jaccard = 0.333) WITH shared snippet -> >= 0.25 threshold -> clusters!
    run_d1 = [{"label": "Fast System Performance Tuning", "evidence": ["Optimized SQL query performance."]}]
    run_d2 = [{"label": "System Performance Monitoring Tool", "evidence": ["Optimized SQL query performance."]}]
    clusters_with_shared = aggregate_runs([run_d1, run_d2])
    assert len(clusters_with_shared) == 1
    assert clusters_with_shared[0]["agreement"] == 1.0

    # Case 5: Near-threshold 0.25 with shared snippet
    # 1 shared stem out of 4 total: Jaccard = 1/4 = 0.25
    # Label 1: "Data Pipeline" (data, pipelin) -> 2 stems
    # Label 2: "Pipeline Security Audit" (pipelin, secur, audit) -> 3 stems
    # Intersection: pipelin (1). Union: data, pipelin, secur, audit (4). Jaccard = 1/4 = 0.25.
    run_e1 = [{"label": "Data Pipeline", "evidence": ["Shared infrastructure snippet."]}]
    run_e2 = [{"label": "Pipeline Security Audit", "evidence": ["Shared infrastructure snippet."]}]
    clusters_thresh_025 = aggregate_runs([run_e1, run_e2])
    assert len(clusters_thresh_025) == 1
    assert clusters_thresh_025[0]["agreement"] == 1.0

    # Case 6: Below 0.25 with shared snippet: 1 shared stem out of 5 total -> Jaccard = 1/5 = 0.20 < 0.25 -> no match
    # Label 1: "Data Pipeline" (data, pipelin) -> 2 stems
    # Label 2: "Pipeline Security Compliance Audit" (pipelin, secur, complianc, audit) -> 4 stems
    # Intersection: pipelin (1). Union: 5 stems. Jaccard = 1/5 = 0.20.
    run_f1 = [{"label": "Data Pipeline", "evidence": ["Shared infrastructure snippet."]}]
    run_f2 = [{"label": "Pipeline Security Compliance Audit", "evidence": ["Shared infrastructure snippet."]}]
    clusters_below_025 = aggregate_runs([run_f1, run_f2])
    assert len(clusters_below_025) == 2
    assert clusters_below_025[0]["agreement"] == 0.5
    assert clusters_below_025[1]["agreement"] == 0.5


def test_porter_stemmer_known_pairs():
    """Verify PorterStemmer against at least 10 known (word, stem) pairs."""
    stemmer = PorterStemmer()
    known_pairs = [
        ("connecting", "connect"),
        ("connection", "connect"),
        ("connections", "connect"),
        ("relational", "relat"),
        ("conditional", "condit"),
        ("rational", "ration"),
        ("controller", "control"),
        ("rollouts", "rollout"),
        ("architectures", "architectur"),
        ("provisioning", "provis"),
        ("meetings", "meet"),
    ]
    assert len(known_pairs) >= 10
    for word, expected_stem in known_pairs:
        actual_stem = stemmer.stem(word)
        assert actual_stem == expected_stem, f"Stem mismatch for '{word}': got '{actual_stem}', expected '{expected_stem}'"


def test_build_explicit_list_kinds_and_deduplication():
    """Verify build_explicit_list:
    - Extracts surface forms whose Evidence.kind is in kinds.
    - Excludes 'context' and invalid/None kinds by default.
    - Performs case-insensitive de-duplication with stable order of first occurrence (no sorting).
    - Supports custom kinds filtering.
    """
    from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult

    mock_result = ExtractionResult.model_construct(
        skills=[
            ExtractedSkill(
                skill_id="java",
                label="Java",
                evidences=[
                    Evidence(surface_form="Java", kind="skill", sentence="Built backend services using Java."),
                    Evidence(surface_form="java", kind="skill", sentence="Mentored junior engineers on java."),
                ],
            ),
            ExtractedSkill(
                skill_id="spring-boot",
                label="Spring Boot",
                evidences=[
                    Evidence(surface_form="Spring Boot", kind="skill", sentence="Developed REST APIs using Spring Boot."),
                ],
            ),
            ExtractedSkill(
                skill_id="order-service",
                label="Order Management",
                evidences=[
                    Evidence(surface_form="order-management microservice", kind="context", sentence="Scaled order-management microservice."),
                ],
            ),
            ExtractedSkill(
                skill_id="fintech",
                label="Fintech",
                evidences=[
                    Evidence(surface_form="Fintech", kind="domain", sentence="Experienced in Fintech domain."),
                    Evidence(surface_form="FINTECH", kind="domain", sentence="Consulted for FINTECH companies."),
                ],
            ),
            ExtractedSkill(
                skill_id="aws-cert",
                label="AWS Certified",
                evidences=[
                    Evidence(surface_form="AWS Certified Developer", kind="certification", sentence="Holds AWS Certified Developer."),
                ],
            ),
            ExtractedSkill(
                skill_id="unknown-kind",
                label="Unknown",
                evidences=[
                    Evidence(surface_form="Some Invalid Mention", kind=None, sentence="Has invalid kind mention."),
                ],
            ),
        ]
    )

    # 1. Default kinds ("skill", "domain", "certification")
    explicit_list = build_explicit_list(mock_result)
    assert explicit_list == [
        "Java",
        "Spring Boot",
        "Fintech",
        "AWS Certified Developer",
    ]
    # Check "order-management microservice" (context) is excluded
    assert "order-management microservice" not in explicit_list
    # Check invalid/None kind is excluded
    assert "Some Invalid Mention" not in explicit_list
    # Check case-insensitive deduplication preserved first occurrence order
    assert len(explicit_list) == 4

    # 2. Custom kinds filter
    skills_only = build_explicit_list(mock_result, kinds=("skill",))
    assert skills_only == ["Java", "Spring Boot"]

    domain_only = build_explicit_list(mock_result, kinds=("domain",))
    assert domain_only == ["Fintech"]


@pytest.mark.anyio
async def test_llm_service_temperature_mocked_client():
    """Verify mocked-client temperature assertions:
    - Default call sends temperature 0.0.
    - Explicit temperature argument is passed through unchanged.
    - Tests both extract_implicit_skills and verify_candidates.
    """
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"implicit_skills": [], "verifications": []})
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        service = LLMService()

        # 1. extract_implicit_skills default call -> temperature=0.0
        await service.extract_implicit_skills("Some CV text", "CV")
        assert mock_create.called
        assert mock_create.call_args.kwargs["temperature"] == 0.0

        # 2. extract_implicit_skills explicit call -> temperature=0.75
        mock_create.reset_mock()
        await service.extract_implicit_skills("Some CV text", "CV", temperature=0.75)
        assert mock_create.called
        assert mock_create.call_args.kwargs["temperature"] == 0.75

        # 3. verify_candidates default call -> temperature=0.0
        mock_create.reset_mock()
        await service.verify_candidates("Doc text", [{"label": "Skill", "snippets": ["Doc text"]}])
        assert mock_create.called
        assert mock_create.call_args.kwargs["temperature"] == 0.0

        # 4. verify_candidates explicit call -> temperature=0.35
        mock_create.reset_mock()
        await service.verify_candidates("Doc text", [{"label": "Skill", "snippets": ["Doc text"]}], temperature=0.35)
        assert mock_create.called
        assert mock_create.call_args.kwargs["temperature"] == 0.35


def test_basis_invalid_for_cv_flagged_and_counted():
    """Verify that basis 'jd_role_context' on a CV document is flagged
    (basis_invalid_for_cv = True) and counted in stats.basis_invalid_for_cv,
    while on a JD document it is valid (basis_invalid_for_cv = False, count 0).
    """
    cv_text = "Designed and maintained distributed microservices architecture."
    jd_text = "Experienced backend engineer needed to manage distributed services."

    # Raw item with basis="jd_role_context"
    raw_cv = {
        "implicit_skills": [
            {
                "label": "Distributed Systems Architecture",
                "basis": "jd_role_context",
                "evidence": ["Designed and maintained distributed microservices architecture."],
            },
            {
                "label": "Service Design",
                "basis": "activity",
                "evidence": ["Designed and maintained distributed microservices architecture."],
            },
        ]
    }

    # 1. Process as CV -> jd_role_context must be flagged basis_invalid_for_cv=True
    cv_result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw_cv,
        text=cv_text,
        filename="resume.txt",
        document_type="CV",
    )
    assert cv_result.stats.basis_invalid_for_cv == 1
    s_invalid = next(s for s in cv_result.skills if s.label == "Distributed Systems Architecture")
    assert s_invalid.basis == "jd_role_context"
    assert s_invalid.basis_invalid_for_cv is True
    assert s_invalid.evidences[0].basis_invalid_for_cv is True

    s_valid = next(s for s in cv_result.skills if s.label == "Service Design")
    assert s_valid.basis == "activity"
    assert s_valid.basis_invalid_for_cv is False
    assert s_valid.evidences[0].basis_invalid_for_cv is False

    # 2. Process as JD -> jd_role_context is valid (basis_invalid_for_cv=False, count=0)
    raw_jd = {
        "implicit_skills": [
            {
                "label": "Distributed Systems Architecture",
                "basis": "jd_role_context",
                "evidence": ["Experienced backend engineer needed to manage distributed services."],
            }
        ]
    }
    jd_result = implicit_skill_postprocessor.process_extraction(
        raw_result=raw_jd,
        text=jd_text,
        filename="job.txt",
        document_type="JD",
    )
    assert jd_result.stats.basis_invalid_for_cv == 0
    s_jd = jd_result.skills[0]
    assert s_jd.basis == "jd_role_context"
    assert s_jd.basis_invalid_for_cv is False
    assert s_jd.evidences[0].basis_invalid_for_cv is False




@pytest.mark.anyio
async def test_provenance_guard_positive_and_explicit_source(client):
    """Verify provenance guard accepts matching text_sha256 and records explicit_source
    as 'extraction_result', while plain list of strings records 'caller_list'."""
    import hashlib
    from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats

    doc_text = "Backend engineer building Java Spring Boot microservices."
    doc_sha = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "implicit_skills": [
            {
                "label": "System Architecture",
                "basis": "activity",
                "evidence": ["Backend engineer building Java Spring Boot microservices."],
            }
        ]
    })
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    ev = Evidence(
        evidence_id="ev-1",
        surface_form="Java",
        start_offset=26,
        end_offset=30,
        unit_text=doc_text,
        sentence=doc_text,
        kind="skill",
    )
    matching_explicit = ExtractionResult.model_construct(
        text_sha256=doc_sha,
        stats=ExtractionStats(total_mentions=1, unique_skills=1, by_kind={"skill": 1}),
        skills=[
            ExtractedSkill(
                skill_id="java",
                canonical_name="Java",
                category="Technology/Tool",
                evidences=[ev],
            )
        ],
    )

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        # 1. Calling with matching explicit_result -> succeeds and sets explicit_source = "extraction_result"
        raw_res1 = await llm_service.extract_implicit_skills(
            text=doc_text,
            document_type="CV",
            explicit_result=matching_explicit,
        )
        assert raw_res1["extraction_meta"]["explicit_source"] == "extraction_result"
        post_res1 = implicit_skill_postprocessor.process_extraction(raw_res1, doc_text, document_type="CV")
        assert post_res1.extraction_meta.explicit_source == "extraction_result"

        # 2. Calling with explicit_mentions (caller_list) -> sets explicit_source = "caller_list"
        raw_res2 = await llm_service.extract_implicit_skills(
            text=doc_text,
            document_type="CV",
            explicit_mentions=["Java", "Spring Boot"],
        )
        assert raw_res2["extraction_meta"]["explicit_source"] == "caller_list"
        post_res2 = implicit_skill_postprocessor.process_extraction(raw_res2, doc_text, document_type="CV")
        assert post_res2.extraction_meta.explicit_source == "caller_list"

        # 3. Calling with neither -> explicit_source is None
        raw_res3 = await llm_service.extract_implicit_skills(
            text=doc_text,
            document_type="CV",
        )
        assert raw_res3["extraction_meta"]["explicit_source"] is None
        post_res3 = implicit_skill_postprocessor.process_extraction(raw_res3, doc_text, document_type="CV")
        assert post_res3.extraction_meta.explicit_source is None


@pytest.mark.anyio
async def test_verifier_v2_basis_handling_mocked():
    """Verify VERIFIER_PROMPT_V2 passes basis for each candidate and handles
    normal_for_role, possible, entailed, plausible, unsupported verdicts."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "verifications": [
            {
                "label": "Payment Processing",
                "verdict": "normal_for_role",
                "covered_by": None,
                "note": "A hiring manager would consider payment processing normal for this role.",
            },
            {
                "label": "Microservices Design",
                "verdict": "entailed",
                "covered_by": None,
                "note": "Directly evidenced by the described service decomposition.",
            },
        ]
    })
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    candidates = [
        {
            "label": "Payment Processing",
            "basis": "jd_role_context",
            "snippets": ["Platform processing millions of transactions daily."],
        },
        {
            "label": "Microservices Design",
            "basis": "activity",
            "snippets": ["Migrated monolith payment module to standalone service."],
        },
    ]

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        verifications = await verify_candidates(
            text="Document text here.",
            candidates=candidates,
            explicit_mentions=["monolith"],
        )

        # Verify sent payload included basis
        call_kwargs = mock_create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert '"basis": "jd_role_context"' in user_msg["content"]
        assert '"basis": "activity"' in user_msg["content"]

        # Verify default prompt is VERIFIER_PROMPT_V2
        sys_msg = next(m for m in messages if m["role"] == "system")
        assert sys_msg["content"] == VERIFIER_PROMPT_V2

        assert len(verifications) == 2
        assert verifications[0].verdict == "normal_for_role"
        assert verifications[0].basis == "jd_role_context"
        assert verifications[1].verdict == "entailed"
        assert verifications[1].basis == "activity"


def test_aggregate_runs_use_snippet_rule_difference_and_return_fields():
    """Verify that aggregate_runs:
    1. Returns member_labels, run_indices, and cluster_size per cluster.
    2. Gives different clusterings when use_snippet_rule is True vs False on two different
       skills quoted from the same sentence where 0.25 <= jaccard < 0.5.
    """
    sentence = "Reduced p95 API latency by 38% through query indexing and Redis caching."
    # Skill A: "Database Optimization" -> stems: {"databas", "optim"} (2 stems)
    # Skill B: "Query Optimization" -> stems: {"queri", "optim"} (2 stems)
    # Intersection = {"optim"} (1), Union = {"databas", "queri", "optim"} (3) -> Jaccard = 1/3 = 0.333
    run1 = [{"label": "Database Optimization", "evidence": [sentence]}]
    run2 = [{"label": "Query Optimization", "evidence": [sentence]}]

    # When use_snippet_rule=True: Jaccard >= 0.25 and shared snippet -> clustered together into 1 cluster
    clusters_with_rule = aggregate_runs([run1, run2], use_snippet_rule=True)
    assert len(clusters_with_rule) == 1
    c_true = clusters_with_rule[0]
    assert c_true["cluster_size"] == 2
    assert c_true["member_labels"] == ["Database Optimization", "Query Optimization"]
    assert c_true["run_indices"] == [0, 1]
    assert c_true["agreement"] == 1.0

    # When use_snippet_rule=False: Jaccard 0.333 < 0.5 -> NOT clustered together, yields 2 separate clusters
    clusters_without_rule = aggregate_runs([run1, run2], use_snippet_rule=False)
    assert len(clusters_without_rule) == 2
    c0 = clusters_without_rule[0]
    c1 = clusters_without_rule[1]
    assert c0["cluster_size"] == 1
    assert c0["member_labels"] == ["Database Optimization"]
    assert c0["run_indices"] == [0]
    assert c0["agreement"] == 0.5

    assert c1["cluster_size"] == 1
    assert c1["member_labels"] == ["Query Optimization"]
    assert c1["run_indices"] == [1]
    assert c1["agreement"] == 0.5


def test_verifier_verdict_basis_validation():
    """Verify that verify_candidates validates verdict against basis in code:
    - entailed and plausible only for activity/role
    - normal_for_role and possible only for jd_role_context
    - unsupported for all
    - invalid combinations become 'invalid_for_basis'
    - unknown verdicts become 'invalid'
    """
    raw_response = {
        "verifications": [
            {"label": "Skill 1", "basis": "activity", "verdict": "normal_for_role"},  # -> invalid_for_basis
            {"label": "Skill 2", "basis": "activity", "verdict": "possible"},         # -> invalid_for_basis
            {"label": "Skill 3", "basis": "activity", "verdict": "entailed"},         # -> entailed
            {"label": "Skill 4", "basis": "activity", "verdict": "plausible"},        # -> plausible
            {"label": "Skill 5", "basis": "activity", "verdict": "unsupported"},      # -> unsupported
            {"label": "Skill 6", "basis": "role", "verdict": "normal_for_role"},      # -> invalid_for_basis
            {"label": "Skill 7", "basis": "role", "verdict": "entailed"},             # -> entailed
            {"label": "Skill 8", "basis": "jd_role_context", "verdict": "entailed"},  # -> invalid_for_basis
            {"label": "Skill 9", "basis": "jd_role_context", "verdict": "plausible"}, # -> invalid_for_basis
            {"label": "Skill 10", "basis": "jd_role_context", "verdict": "normal_for_role"}, # -> normal_for_role
            {"label": "Skill 11", "basis": "jd_role_context", "verdict": "possible"}, # -> possible
            {"label": "Skill 12", "basis": "jd_role_context", "verdict": "unsupported"}, # -> unsupported
            {"label": "Skill 13", "basis": "activity", "verdict": "gibberish"},       # -> invalid
        ]
    }
    results = postprocess_verification(raw_response)
    expected_verdicts = [
        "invalid_for_basis",
        "invalid_for_basis",
        "entailed",
        "plausible",
        "unsupported",
        "invalid_for_basis",
        "entailed",
        "invalid_for_basis",
        "invalid_for_basis",
        "normal_for_role",
        "possible",
        "unsupported",
        "invalid",
    ]
    actual_verdicts = [r.verdict for r in results]
    assert actual_verdicts == expected_verdicts


@pytest.mark.anyio
async def test_verifier_model_env_override_and_recording():
    """Verify that if env OPENROUTER_VERIFIER_MODEL is set, the verifier uses it
    and records the model actually used in CandidateVerification.model_used."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "verifications": [
            {
                "label": "Distributed Systems",
                "verdict": "entailed",
                "covered_by": None,
                "note": "Evidenced by Kafka architecture.",
            }
        ]
    })
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.model = "meta-llama/llama-3.3-70b-instruct"
    mock_create = AsyncMock(return_value=mock_completion)

    candidates = [
        {"label": "Distributed Systems", "basis": "activity", "snippets": ["Built Kafka pipeline."]}
    ]

    with patch.dict(os.environ, {"OPENROUTER_VERIFIER_MODEL": "meta-llama/llama-3.3-70b-instruct"}), \
         patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        verifications = await verify_candidates(
            text="Document text.",
            candidates=candidates,
        )

        # Check model passed to OpenAI client
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "meta-llama/llama-3.3-70b-instruct"

        # Check recorded model_used
        assert len(verifications) == 1
        assert verifications[0].model_used == "meta-llama/llama-3.3-70b-instruct"


def test_coverage_flag_regression_real_explicit():
    """Regression test for GATE I2c Item 1:
    Verify coverage_vs_explicit flags 'Event-Driven Architecture Design' and
    'Zero-Downtime Deployment Strategies' with Jaccard 0.4 against the real CV explicit list/result.
    Both must have possibly_covered == True with threshold 0.34.
    """
    from matching_cv.app.services.implicit_skill_postprocessor import build_explicit_list, coverage_vs_explicit
    from matching_cv.app.services.skill_postprocessor import skill_postprocessor

    cv_pdf_path = "tests/fixtures/01_Backend_CV.pdf"
    with open(cv_pdf_path, "rb") as f:
        cv_raw, _ = document_parser_service.extract_text_from_pdf(f.read())
    cv_text = document_parser_service.clean_extracted_text(cv_raw)

    with open("tests/fixtures/01_Backend_CV_run1_d7.json", "r", encoding="utf-8") as f:
        run_data = json.load(f)

    processed_explicit = skill_postprocessor.process_extraction(
        raw_result=run_data["raw_llm"],
        text=cv_text,
        filename="01_Backend_CV.pdf",
        document_type="CV",
    )
    explicit_list = build_explicit_list(processed_explicit)
    assert "message-driven architectures" in explicit_list
    assert "zero-downtime cutover" in explicit_list

    # Test 1: Using processed_explicit with list-of-dict input format
    labels = [
        "Event-Driven Architecture Design",
        "Zero-Downtime Deployment Strategies",
    ]
    report_proc = coverage_vs_explicit([{"label": l} for l in labels], processed_explicit)
    assert len(report_proc) == 2
    assert report_proc[0]["possibly_covered"] is True
    assert report_proc[0]["top_matches"][0]["mention"] == "message-driven architectures"
    assert report_proc[0]["top_matches"][0]["jaccard"] == 0.4

    assert report_proc[1]["possibly_covered"] is True
    assert report_proc[1]["top_matches"][0]["mention"] == "zero-downtime cutover"
    assert report_proc[1]["top_matches"][0]["jaccard"] == 0.4

    # Test 2: Using explicit_list directly
    report_list = coverage_vs_explicit([{"label": l} for l in labels], explicit_list)
    assert len(report_list) == 2
    assert report_list[0]["possibly_covered"] is True
    assert report_list[0]["top_matches"][0]["jaccard"] == 0.4
    assert report_list[1]["possibly_covered"] is True
    assert report_list[1]["top_matches"][0]["jaccard"] == 0.4


def test_aggregate_single_candidate_passes_logic():
    """Unit test for GATE I2c single-candidate pass aggregation."""
    from matching_cv.app.services.implicit_skill_postprocessor import aggregate_single_candidate_passes

    # Case 1: Clear majority verdict, covered_by in 2/3 passes
    res1 = aggregate_single_candidate_passes([
        {"verifications": [{"verdict": "entailed", "covered_by": "Kafka"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": "Kafka"}]},
        {"verifications": [{"verdict": "plausible", "covered_by": None}]},
    ])
    assert res1["final_verdict"] == "entailed"
    assert res1["covered_by_final"] == "Kafka"
    assert res1["covered_unstable"] is False
    assert res1["pass_verdicts"] == ["entailed", "entailed", "plausible"]
    assert res1["pass_covered_by"] == ["Kafka", "Kafka", None]

    # Case 2: No majority verdict (all 3 different) -> unstable
    res2 = aggregate_single_candidate_passes([
        {"verifications": [{"verdict": "entailed", "covered_by": None}]},
        {"verifications": [{"verdict": "plausible", "covered_by": None}]},
        {"verifications": [{"verdict": "unsupported", "covered_by": None}]},
    ])
    assert res2["final_verdict"] == "unstable"
    assert res2["covered_by_final"] == None
    assert res2["covered_unstable"] is False

    # Case 3: Covered_by in exactly 1 pass -> covered_by_final = None, covered_unstable = True
    res3 = aggregate_single_candidate_passes([
        {"verifications": [{"verdict": "entailed", "covered_by": "message-driven architectures"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": None}]},
        {"verifications": [{"verdict": "entailed", "covered_by": "none"}]},
    ])
    assert res3["final_verdict"] == "entailed"
    assert res3["covered_by_final"] is None
    assert res3["covered_unstable"] is True

    # Case 4: Covered_by split across 2 different strings -> covered_by_final = None, covered_unstable = True
    res4 = aggregate_single_candidate_passes([
        {"verifications": [{"verdict": "entailed", "covered_by": "Kafka"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": "RabbitMQ"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": None}]},
    ])
    assert res4["final_verdict"] == "entailed"
    assert res4["covered_by_final"] is None
    assert res4["covered_unstable"] is True

    # Case 5: Covered_by in all 3 passes stably
    res5 = aggregate_single_candidate_passes([
        {"verifications": [{"verdict": "entailed", "covered_by": "PostgreSQL"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": "PostgreSQL"}]},
        {"verifications": [{"verdict": "entailed", "covered_by": "PostgreSQL"}]},
    ])
    assert res5["final_verdict"] == "entailed"
    assert res5["covered_by_final"] == "PostgreSQL"
    assert res5["covered_unstable"] is False



