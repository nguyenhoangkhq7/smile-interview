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


