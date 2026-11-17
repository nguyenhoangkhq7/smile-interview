"""DSPy explicit extraction contract and precision-focused metric tests."""

import dspy

from matching_cv.dspy_modules.dataset import get_gold_examples, get_train_val_split
from matching_cv.dspy_modules.compiler import compile_labeled_few_shot
from matching_cv.dspy_modules.metrics import explicit_skill_metric
from matching_cv.dspy_modules.schemas import ExplicitSkillMention
from matching_cv.app.services.dspy_explicit_skill_service import DSPyExplicitSkillService
from matching_cv.app.services.cached_extraction_service import CachedExtractionService
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
