"""DSPy explicit extraction contract and precision-focused metric tests."""

import dspy
import pytest
from pydantic import TypeAdapter, ValidationError

from matching_cv.dspy_modules.dataset import get_gold_examples, get_train_val_split
from matching_cv.dspy_modules.compiler import compile_labeled_few_shot
from matching_cv.dspy_modules.metrics import explicit_skill_metric
from matching_cv.dspy_modules.schemas import ExplicitSkillMention, ExplicitSkillMentionList
from matching_cv.app.services.dspy_explicit_skill_service import DSPyExplicitSkillService
from matching_cv.app.services.cached_extraction_service import CachedExtractionService
from matching_cv.app.services.skill_postprocessor import skill_postprocessor
from matching_cv.app.core.config import settings


def _candidate(mention: str, sentence: str, kind: str = "skill") -> ExplicitSkillMention:
    return ExplicitSkillMention(
        mention=mention,
        kind=kind,
        category="Technology/Tool",
        source_sentence=sentence,
    )


def test_gold_set_covers_education_false_positive_and_real_skills():
    examples = get_gold_examples()
    education_case = next(example for example in examples if "Khoa học máy tính" in example.document_text)

    assert [item.mention for item in education_case.explicit_skills] == ["Python", "REST API"]
    assert len(get_train_val_split()[1]) == 4


def test_labeled_few_shot_compiles_without_live_llm_calls():
    module = compile_labeled_few_shot(k=3)

    assert len(module.extract.demos) == 3


def test_compiled_runtime_artifact_contains_demos():
    service = DSPyExplicitSkillService()

    assert service._compiled_path.is_file()
    assert len(service._load_module().extract.demos) > 0


def test_metric_penalizes_academic_field_false_positive():
    example = dspy.Example(
        document_type="JD",
        document_text="Yêu cầu tốt nghiệp chuyên ngành Khoa học máy tính.",
        explicit_skills=[],
    )
    prediction = dspy.Prediction(
        explicit_skills=[
            _candidate(
                "Khoa học máy tính",
                "Yêu cầu tốt nghiệp chuyên ngành Khoa học máy tính.",
                kind="domain",
            )
        ]
    )

    assert explicit_skill_metric(example, prediction) == 0.0


def test_metric_rewards_exact_grounded_skill_extraction():
    sentence = "Yêu cầu Python và REST API."
    candidates = [
        _candidate("Python", sentence),
        _candidate("REST API", sentence),
    ]
    example = dspy.Example(
        document_type="JD",
        document_text=sentence,
        explicit_skills=candidates,
    )
    prediction = dspy.Prediction(explicit_skills=candidates)

    assert explicit_skill_metric(example, prediction) == 1.0


def test_metric_penalizes_wrong_evidence_sentence():
    example = dspy.Example(
        document_type="JD",
        document_text="Ứng viên cần Python.",
        explicit_skills=[_candidate("Python", "Ứng viên cần Python.")],
    )
    prediction = dspy.Prediction(
        explicit_skills=[_candidate("Python", "Ưu tiên biết Java.")]
    )

    assert explicit_skill_metric(example, prediction) == 0.0


def test_runtime_adapter_rejects_unverifiable_mention(tmp_path):
    service = DSPyExplicitSkillService(tmp_path / "missing.json")
    candidate = _candidate("Khoa học máy tính", "Yêu cầu tốt nghiệp ngành Công nghệ thông tin.")

    assert service._validated_candidate(
        candidate,
        "Yêu cầu tốt nghiệp ngành Công nghệ thông tin.",
    ) is None


def test_cache_requires_current_extractor_metadata_when_dspy_is_enabled(monkeypatch):
    monkeypatch.setattr(settings, "MATCHING_CV_DSPY_EXPLICIT_ENABLED", True)

    assert not CachedExtractionService._cache_version_is_usable({"extracted_skills": []})
    assert CachedExtractionService._cache_version_is_usable(
        {"extractor_version": "explicit_dspy_v1"}
    )
    assert CachedExtractionService._cache_version_is_usable(
        {
            "cv": {"explicit": {"extraction_meta": {"schema_version": "explicit_dspy_v1"}}},
            "jd": {"explicit": {"extraction_meta": {"schema_version": "explicit_dspy_v1"}}},
        }
    )


def test_schema_enforces_valid_categories_and_extended_kinds():
    with pytest.raises(ValidationError):
        ExplicitSkillMention(
            mention="Python",
            kind="skill",
            category="InvalidCategory",  # type: ignore[arg-type]
            source_sentence="Uses Python.",
        )

    for non_skill_kind in ("education", "industry", "experience_years", "job_title", "context"):
        item = ExplicitSkillMention(
            mention="Test",
            kind=non_skill_kind,  # type: ignore[arg-type]
            category="Domain Knowledge",
            source_sentence="Test sentence.",
        )
        assert item.kind == non_skill_kind


def test_single_item_validation_failure_drops_only_invalid_item(tmp_path):
    raw_list = [
        {
            "mention": "Python",
            "kind": "skill",
            "category": "Technology/Tool",
            "source_sentence": "Ứng viên thành thạo Python và Docker.",
        },
        {
            "mention": "BadCategoryItem",
            "kind": "skill",
            "category": "NotAValidCategory",
            "source_sentence": "Ứng viên thành thạo Python và Docker.",
        },
        {
            "mention": "Docker",
            "kind": "skill",
            "category": "Technology/Tool",
            "source_sentence": "Ứng viên thành thạo Python và Docker.",
        },
    ]
    validated = TypeAdapter(ExplicitSkillMentionList).validate_python(raw_list)
    assert [m.mention for m in validated] == ["Python", "Docker"]

    service = DSPyExplicitSkillService(tmp_path / "missing.json")
    doc_text = "Ứng viên thành thạo Python và Docker."
    assert service._validated_candidate(raw_list[1], doc_text) is None
    assert service._validated_candidate(raw_list[0], doc_text) is not None


def test_postprocessor_routing_and_deterministic_guard():
    doc_text = (
        "Lĩnh vực: IT - Phần mềm. "
        "Yêu cầu tốt nghiệp Khoa học máy tính và có 3 năm kinh nghiệm làm việc trong môi trường sản xuất (production environment). "
        "Thành thạo Python, phối hợp với product managers, xử lý production issues cho production services. "
        "Ưu tiên có chứng chỉ AWS Certified Solutions Architect hoặc có chứng chỉ liên quan."
    )
    raw_extraction = {
        "explicit_skills": [
            {"mention": "Python", "kind": "skill", "category": "Technology/Tool", "source_sentence": doc_text},
            {"mention": "AWS Certified Solutions Architect", "kind": "certification", "category": "Certification", "source_sentence": doc_text},
            # Bare certification words without proper name -> routed to non_skill_entities
            {"mention": "chứng chỉ", "kind": "certification", "category": "Certification", "source_sentence": doc_text},
            # LLM mistakenly labels years of experience and stoplist items as "skill" -> guard overrides & routes to non_skill_entities
            {"mention": "3 năm kinh nghiệm", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "môi trường sản xuất", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "production environment", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "product managers", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "production issues", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "production services", "kind": "skill", "category": "Engineering Practice", "source_sentence": doc_text},
            {"mention": "IT - Phần mềm", "kind": "industry", "category": "Domain Knowledge", "source_sentence": doc_text},
            {"mention": "Khoa học máy tính", "kind": "education", "category": "Domain Knowledge", "source_sentence": doc_text},
        ]
    }

    res = skill_postprocessor.process_extraction(
        raw_result=raw_extraction,
        text=doc_text,
        filename="synthetic_vn_jd.txt",
        document_type="JD",
    )

    assert [s.surface_forms[0] for s in res.skills] == ["Python", "AWS Certified Solutions Architect"]
    assert res.stats.unique_skills == 2
    assert res.stats.non_skill_count == 9

    non_skills_by_form = {s.surface_forms[0]: s.kind for s in res.non_skill_entities}
    assert non_skills_by_form["chứng chỉ"] == "certification"
    assert non_skills_by_form["3 năm kinh nghiệm"] == "experience_years"
    assert non_skills_by_form["môi trường sản xuất"] == "context"
    assert non_skills_by_form["production environment"] == "context"
    assert non_skills_by_form["product managers"] == "job_title"
    assert non_skills_by_form["production issues"] == "context"
    assert non_skills_by_form["production services"] == "context"
    assert non_skills_by_form["IT - Phần mềm"] == "industry"
    assert non_skills_by_form["Khoa học máy tính"] == "education"

    assert res.stats.kind_counts == {
        "skill": 1,
        "certification": 2,
        "experience_years": 1,
        "context": 4,
        "job_title": 1,
        "industry": 1,
        "education": 1,
    }


def test_non_skill_entities_with_category_none_routed_not_dropped():
    """Verify that items with non-skill kinds and category=None are preserved and routed to non_skill_entities."""
    from matching_cv.dspy_modules.schemas import ExplicitSkillMention, ExplicitSkillMentionList
    from pydantic import TypeAdapter

    # 1. Pydantic validation on ExplicitSkillMention and ExplicitSkillMentionList
    items = [
        {"mention": "Computer Science", "kind": "education", "category": None, "source_sentence": "Has degree in Computer Science."},
        {"mention": "Fintech", "kind": "industry", "category": None, "source_sentence": "Working in Fintech domain."},
        {"mention": "5 years", "kind": "experience_years", "category": None, "source_sentence": "Requires 5 years of experience."},
        {"mention": "Senior Backend Engineer", "kind": "job_title", "category": None, "source_sentence": "Role is Senior Backend Engineer."},
        {"mention": "Python", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Experienced with Python."},
    ]
    adapter = TypeAdapter(ExplicitSkillMentionList)
    validated = adapter.validate_python(items)
    assert len(validated) == 5
    assert validated[0].category is None
    assert validated[0].kind == "education"

    # 2. End-to-end postprocessing routing
    doc_text = "Role is Senior Backend Engineer with degree in Computer Science and 5 years experience in Fintech. Experienced with Python."
    raw_extraction = {
        "explicit_skills": [
            {"mention": "Senior Backend Engineer", "kind": "job_title", "category": None, "source_sentence": "Role is Senior Backend Engineer with degree in Computer Science and 5 years experience in Fintech."},
            {"mention": "Computer Science", "kind": "education", "category": None, "source_sentence": "Role is Senior Backend Engineer with degree in Computer Science and 5 years experience in Fintech."},
            {"mention": "5 years", "kind": "experience_years", "category": None, "source_sentence": "Role is Senior Backend Engineer with degree in Computer Science and 5 years experience in Fintech."},
            {"mention": "Fintech", "kind": "industry", "category": None, "source_sentence": "Role is Senior Backend Engineer with degree in Computer Science and 5 years experience in Fintech."},
            {"mention": "Python", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Experienced with Python."},
        ]
    }
    res = skill_postprocessor.process_extraction(
        raw_result=raw_extraction,
        text=doc_text,
        filename="test_non_skill_cat_none.txt",
        document_type="JD",
    )
    assert [s.surface_forms[0] for s in res.skills] == ["Python"]
    assert res.stats.unique_skills == 1
    assert res.stats.non_skill_count == 4
    non_skills = {s.surface_forms[0]: (s.kind, s.category) for s in res.non_skill_entities}
    assert non_skills["Senior Backend Engineer"] == ("job_title", None)
    assert non_skills["Computer Science"] == ("education", None)
    assert non_skills["5 years"] == ("experience_years", None)
    assert non_skills["Fintech"] == ("industry", None)


def test_core_skills_filtering_and_in_document_consolidation():
    """Verify filtering of generic/buzzword/project-activity mentions, section tagging, and duplicate consolidation."""
    from matching_cv.app.services.section_tagger import find_section_spans
    from matching_cv.app.services.unified_skill_service import deduplicate_explicit_implicit
    from matching_cv.app.schemas.implicit_skill_extraction import (
        ImplicitEvidence,
        ImplicitEvidenceSnippet,
        ImplicitExtractedSkill,
        ImplicitExtractionResult,
        ImplicitExtractionStats,
    )

    cv_text = (
        "SUMMARY\n"
        "Experienced with Java, Docker, and database design.\n"
        "TECHNICAL SKILLS\n"
        "Java (Java 21), React\n"
        "PERSONAL PROJECTS\n"
        "Built app using Eisenhower Matrix, AI-assisted development, full-stack architecture, system design, "
        "interval-merging approach, rule-based auto-scheduling algorithm, JWT, Email OTP, authentication, "
        "Docker Compose, migrations, TanStack Query, client-side caching, optimistic updates, React Hook Form, Zod, "
        "form validation, AI-powered feature, third-party API integration.\n"
        "ACADEMIC PROJECTS\n"
        "Built real-time chat with Socket.io, troubleshooting, system architecture.\n"
        "ADDITIONAL INFORMATION\n"
        "The Ultimate Spring Boot Framework (Part 1 & 2) - Code with Mosh\n"
    )

    spans = find_section_spans(cv_text, "CV")
    section_names = [s.name for s in spans]
    assert "unknown" not in section_names
    assert section_names == ["summary", "skills", "projects", "projects", "other"]

    s_sum = "Experienced with Java, Docker, and database design."
    s_sk = "Java (Java 21), React"
    s_p1 = (
        "Built app using Eisenhower Matrix, AI-assisted development, full-stack architecture, system design, "
        "interval-merging approach, rule-based auto-scheduling algorithm, JWT, Email OTP, authentication, "
        "Docker Compose, migrations, TanStack Query, client-side caching, optimistic updates, React Hook Form, Zod, "
        "form validation, AI-powered feature, third-party API integration."
    )
    s_p2 = "Built real-time chat with Socket.io, troubleshooting, system architecture."
    s_oth = "The Ultimate Spring Boot Framework (Part 1 & 2) - Code with Mosh"

    raw_mentions = [
        {"mention": "Java", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_sum},
        {"mention": "Docker", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_sum},
        {"mention": "database design", "kind": "skill", "category": "Technical Concept", "source_sentence": s_sum},
        {"mention": "Java 21", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_sk},
        {"mention": "React", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_sk},
        {"mention": "full-stack architecture", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "system design", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "system architecture", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p2},
        {"mention": "Docker Compose", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_p1},
        {"mention": "JWT", "kind": "skill", "category": "Technical Standard", "source_sentence": s_p1},
        {"mention": "TanStack Query", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_p1},
        {"mention": "React Hook Form", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_p1},
        {"mention": "Zod", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_p1},
        {"mention": "Socket.io", "kind": "skill", "category": "Technology/Tool", "source_sentence": s_p2},
        # Noise / non-skills that must be routed to non_skill_entities
        {"mention": "Eisenhower Matrix", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "AI-assisted development", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "interval-merging approach", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "rule-based auto-scheduling algorithm", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "Email OTP", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "authentication", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "migrations", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "client-side caching", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "optimistic updates", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "form validation", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "AI-powered", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p1},
        {"mention": "third-party API integration", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p1},
        {"mention": "real-time chat", "kind": "skill", "category": "Technical Concept", "source_sentence": s_p2},
        {"mention": "troubleshooting", "kind": "skill", "category": "Engineering Practice", "source_sentence": s_p2},
        {"mention": "The Ultimate Spring Boot Framework (Part 1 & 2)", "kind": "certification", "category": "Certification", "source_sentence": s_oth},
    ]

    res = skill_postprocessor.process_extraction(
        raw_result={"explicit_skills": raw_mentions},
        text=cv_text,
        filename="cv.pdf",
        document_type="CV",
    )

    skill_ids = [s.skill_id for s in res.skills]
    assert skill_ids == [
        "java",
        "docker",
        "database-design",
        "react",
        "system-design",
        "jwt",
        "tanstack-query",
        "react-hook-form",
        "zod",
        "socket.io",
    ]
    skills_by_id = {s.skill_id: s for s in res.skills}
    assert skills_by_id["java"].surface_forms == ["Java", "Java 21"]
    assert len(skills_by_id["java"].evidences) == 2
    assert skills_by_id["docker"].surface_forms == ["Docker", "Docker Compose"]
    assert len(skills_by_id["docker"].evidences) == 2
    assert set(skills_by_id["system-design"].surface_forms) == {
        "system design",
        "full-stack architecture",
        "system architecture",
    }
    assert len(skills_by_id["system-design"].evidences) == 3
    assert len(res.non_skill_entities) == 15

    # Verify implicit token-subset deduplication ("Database Schema Design" vs explicit "database design")
    imp_res = ImplicitExtractionResult(
        filename="cv.pdf",
        document_type="CV",
        text_sha256=res.text_sha256,
        stats=ImplicitExtractionStats(total_inferences=1, unique_skills=1),
        skills=[
            ImplicitExtractedSkill(
                skill_id="database-schema-design",
                label="Database Schema Design",
                category="Engineering Practice",
                evidences=[
                    ImplicitEvidence(
                        inferred_from_raw=s_p2,
                        snippets=[
                            ImplicitEvidenceSnippet(
                                text=s_p2,
                                start=0,
                                end=len(s_p2),
                                section="projects",
                                verbatim_ok=True,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    val_res = deduplicate_explicit_implicit(res, imp_res, document_type="CV")
    assert len(val_res.accepted_implicit_skills) == 0
    assert len(val_res.duplicate_implicit_skills) == 1
    assert val_res.duplicate_implicit_skills[0].matched_explicit_skill_id == "database-design"


def test_slash_compound_mention_splitting_and_protected_terms():
    """Verify splitting of slash mentions like ESLint/Prettier and REST/GraphQL APIs, while protecting CI/CD."""
    # Split candidates
    assert skill_postprocessor.split_slash_skill_mention("ESLint/Prettier", "skill", "Technology/Tool", "Tooling: ESLint/Prettier") == ["ESLint", "Prettier"]
    assert skill_postprocessor.split_slash_skill_mention("REST/GraphQL APIs", "skill", "Technology/Tool", "Design REST/GraphQL APIs") == ["REST", "GraphQL"]
    assert skill_postprocessor.split_slash_skill_mention("REST/GraphQL API integration", "skill", "Technology/Tool", "Experience in REST/GraphQL API integration") == ["REST", "GraphQL"]

    # Protected candidates (atomic or domain terms)
    assert skill_postprocessor.split_slash_skill_mention("CI/CD", "skill", "Technology/Tool", "Set up CI/CD pipeline") is None
    assert skill_postprocessor.split_slash_skill_mention("TCP/IP", "skill", "Technology/Tool", "Knowledge of TCP/IP") is None
    assert skill_postprocessor.split_slash_skill_mention("PL/SQL", "skill", "Technology/Tool", "Stored procedures in PL/SQL") is None
    assert skill_postprocessor.split_slash_skill_mention("ETL/ELT", "skill", "Technology/Tool", "ETL/ELT data pipelines") is None
    assert skill_postprocessor.split_slash_skill_mention("booking/inventory systems", "domain", "Domain Knowledge", "Built booking/inventory systems") is None


def test_canonical_skill_id_normalization_and_merging():
    """Verify unconditional canonical skill ID merging (e.g. Next.js App Router -> next.js, ES6 -> JavaScript)."""
    text = (
        "SKILLS\n"
        "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs\n"
        "EXPERIENCE\n"
        "Used Next.js and GraphQL for frontend."
    )
    raw_mentions = [
        {"mention": "JavaScript (ES6+)", "kind": "skill", "category": "Programming Language", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "HTML5", "kind": "skill", "category": "Programming Language", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "CSS3", "kind": "skill", "category": "Technology/Tool", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "WCAG AA", "kind": "skill", "category": "Engineering Practice", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "Next.js (App Router)", "kind": "skill", "category": "Framework/Library", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "GraphQL APIs", "kind": "skill", "category": "Technology/Tool", "source_sentence": "JavaScript (ES6+), HTML5, CSS3, WCAG AA, Next.js (App Router), GraphQL APIs"},
        {"mention": "Next.js", "kind": "skill", "category": "Framework/Library", "source_sentence": "Used Next.js and GraphQL for frontend."},
        {"mention": "GraphQL", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Used Next.js and GraphQL for frontend."},
    ]
    res = skill_postprocessor.process_extraction(
        raw_result={"explicit_skills": raw_mentions},
        text=text,
        filename="test_canon.txt",
        document_type="CV",
    )
    skill_ids = {s.skill_id for s in res.skills}
    assert "javascript" in skill_ids
    assert "html" in skill_ids
    assert "css" in skill_ids
    assert "wcag" in skill_ids
    assert "next.js" in skill_ids
    assert "graphql" in skill_ids
    # Merged correctly: Next.js has 2 evidences, GraphQL has 2 evidences
    skills_map = {s.skill_id: s for s in res.skills}
    assert len(skills_map["next.js"].evidences) == 2
    assert len(skills_map["graphql"].evidences) == 2


def test_coordinate_ellipsis_and_standalone_acronym():
    """Verify coordinate ellipsis detection for test phrases and standalone acronym recovery."""
    service = DSPyExplicitSkillService()
    # Coordinate ellipsis mention
    s1 = "Write unit and end-to-end tests for all features."
    assert service._is_coordinate_ellipsis_mention("unit tests", s1) is True
    assert service._is_coordinate_ellipsis_mention("end-to-end tests", s1) is False
    assert service._is_coordinate_ellipsis_mention("integration tests", s1) is False

    # Standalone acronym before parentheses
    s2 = "Personal habit-tracker PWA (React, TypeScript) — 300+ GitHub stars"
    existing_skills = [
        {"mention": "React", "kind": "skill", "category": "Framework/Library", "source_sentence": s2}
    ]
    mentions_s2 = service._backfill_missing_line_occurrences(
        skills=existing_skills,
        text=s2,
    )
    pwa_found = any(m["mention"] == "PWA" for m in mentions_s2)
    assert pwa_found is True


def test_implicit_hardening_soft_skills_and_redundancy():
    """Verify rejection of Soft Skills, bare umbrella labels, and explicit tool redundancy in Implicit extraction."""
    from matching_cv.app.services.implicit_evidence_verifier import ImplicitEvidenceVerifier
    from matching_cv.app.schemas.implicit_skill_extraction import (
        ImplicitExtractedSkill,
        ImplicitEvidence,
        ImplicitEvidenceSnippet,
    )
    from matching_cv.app.schemas.skill_extraction import (
        ExtractionResult,
        ExtractedSkill,
        ExtractionStats,
    )

    text = (
        "SUMMARY\n"
        "Lead team and own products end to end with WCAG AA compliance.\n"
        "EXPERIENCE\n"
        "Collaborated with designers to translate Figma files into reusable, accessible components (WCAG AA).\n"
    )

    # 1. Soft skill category rejection
    c1 = ImplicitExtractedSkill(
        skill_id="product-ownership",
        label="Product Ownership",
        category="Soft Skill",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Lead team and own products end to end",
                snippets=[ImplicitEvidenceSnippet(text="Lead team and own products end to end", start=8, end=43)],
                reasoning="Owning products indicates product ownership.",
            )
        ],
    )
    # 2. Bare umbrella label rejection
    c2 = ImplicitExtractedSkill(
        skill_id="feature-ownership",
        label="Feature Ownership",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Lead team and own products end to end",
                snippets=[ImplicitEvidenceSnippet(text="Lead team and own products end to end", start=8, end=43)],
                reasoning="Owning products indicates feature ownership.",
            )
        ],
    )
    # 3. Explicit tool implied concept redundancy (Accessibility Implementation vs explicit wcag)
    c3 = ImplicitExtractedSkill(
        skill_id="accessibility-implementation",
        label="Accessibility Implementation",
        category="Engineering Practice",
        evidences=[
            ImplicitEvidence(
                inferred_from_raw="Collaborated with designers to translate Figma files into reusable, accessible components (WCAG AA).",
                snippets=[ImplicitEvidenceSnippet(text="accessible components (WCAG AA)", start=139, end=170)],
                reasoning="Building accessible components demonstrates accessibility implementation.",
            )
        ],
    )

    explicit_res = ExtractionResult(
        filename="test.pdf",
        document_type="CV",
        text_sha256="abc",
        stats=ExtractionStats(total_mentions=0, unique_skills=1, non_skill_count=0),
        skills=[
            ExtractedSkill(
                skill_id="wcag",
                canonical_id="wcag",
                category="Engineering Practice",
                surface_forms=["WCAG AA"],
                evidences=[],
            )
        ],
    )

    accepted, rejected, verifications = ImplicitEvidenceVerifier.verify_candidates(
        candidates=[c1, c2, c3],
        document_type="CV",
        explicit_result=explicit_res,
    )

    assert len(accepted) == 0
    assert len(rejected) == 3
    rejection_reasons = {v.original_label or v.skill_id: v.support_reason for v in verifications}
    assert any("soft skill" in reason.lower() for reason in rejection_reasons.values())
    assert any("umbrella" in reason.lower() or "generic" in reason.lower() for reason in rejection_reasons.values())
    assert any("superficial or concept-redundant" in reason.lower() for reason in rejection_reasons.values())




