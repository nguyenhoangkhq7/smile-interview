"""Tests for numeric skill filtering, technical token preservation, and cache invalidation."""
import pytest
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, ExtractionResult, ExtractionStats
from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult
from matching_cv.app.services.dataset_preprocessor import VersionedCacheKeyManager
from matching_cv.app.services.extraction_adapter import ExtractionDataAdapter


def create_dummy_doc_with_skills(skill_ids: list[str]) -> DocumentUnifiedResult:
    """Helper to create a DocumentUnifiedResult with specific explicit skill IDs."""
    skills = [
        ExtractedSkill(
            skill_id=s_id,
            surface_forms=[s_id.replace("-", " ")],
            category="Technology/Tool",
            type="explicit",
            evidences=[
                Evidence(
                    surface_form=s_id.replace("-", " "),
                    sentence=f"Experienced in {s_id.replace('-', ' ')} daily.",
                )
            ],
        )
        for s_id in skill_ids
    ]
    explicit = ExtractionResult(
        document_type="CV",
        skills=skills,
        text_sha256="dummy_sha256",
        stats=ExtractionStats(
            total_mentions=len(skills),
            unique_skills=len(skills),
            unresolved_evidences=len(skills),
            unresolved_mentions=len(skills),
            invalid_kind_mentions=len(skills),
        ),
    )
    return DocumentUnifiedResult(
        document_type="CV",
        text_sha256="dummy_sha256",
        explicit=explicit,
    )


def test_pure_numeric_tokens_excluded():
    """Verify that standalone pure numeric tokens are filtered from active skills."""
    anomalous_tokens = ["2000", "2007", "2010", "2013", "1999", "100", "42"]
    doc = create_dummy_doc_with_skills(anomalous_tokens)
    res = ExtractionDataAdapter.extract_active_skills(doc)
    active_ids = [s.skill_id for s in res.active_skills]
    for token in anomalous_tokens:
        assert token not in active_ids, f"Pure numeric token {token} was not excluded!"
    assert len(res.active_skills) == 0


def test_legitimate_versioned_and_symbol_skills_preserved():
    """Verify that legitimate technical competencies with numbers/symbols are strictly preserved."""
    legitimate_skills = [
        "windows-server-2019",
        "python-3-12",
        "iso-27001",
        "802-11ax",
        "c-sharp",
        "c-plus-plus",
        "dot-net",
        "3d-modeling",
        "h-264",
        "mp3",
        "b2b",
        "w3c",
        "k8s",
        "x86",
        "windows-98",
    ]
    doc = create_dummy_doc_with_skills(legitimate_skills)
    res = ExtractionDataAdapter.extract_active_skills(doc)
    active_ids = [s.skill_id for s in res.active_skills]
    for skill in legitimate_skills:
        assert skill in active_ids, f"Legitimate skill {skill} was mistakenly excluded!"
    assert len(res.active_skills) == len(legitimate_skills)


def test_mixed_domain_skill_filtering():
    """Verify mixed domain list correctly filters only purely numeric tokens."""
    mixed_input = [
        "python-3-12",       # Keep
        "2007",              # Exclude
        "iso-27001",         # Keep
        "2010",              # Exclude
        "c-plus-plus",       # Keep
        "2000",              # Exclude
        "windows-98",        # Keep
    ]
    doc = create_dummy_doc_with_skills(mixed_input)
    res = ExtractionDataAdapter.extract_active_skills(doc)
    active_ids = [s.skill_id for s in res.active_skills]
    expected_kept = ["python-3-12", "iso-27001", "c-plus-plus", "windows-98"]
    assert set(active_ids) == set(expected_kept)


def test_cache_key_invalidation_on_policy_and_version_changes():
    """Verify cache keys change when extractor version, policy, or builder version changes."""
    text_hash = "abc123hash"

    # 1. Extraction key invalidation
    k1 = VersionedCacheKeyManager.get_document_extraction_key(text_hash, extractor_version="v1.0")
    k2 = VersionedCacheKeyManager.get_document_extraction_key(text_hash, extractor_version="v2.0")
    k3 = VersionedCacheKeyManager.get_document_extraction_key(text_hash, eligibility_policy="grounded_v1")
    k4 = VersionedCacheKeyManager.get_document_extraction_key(text_hash, eligibility_policy="grounded_v2")
    assert k1 != k2, "Extractor version bump did not invalidate extraction cache key!"
    assert k3 != k4, "Policy change did not invalidate extraction cache key!"

    # 2. Graph key invalidation
    g1 = VersionedCacheKeyManager.get_graph_key("cv_h", "jd_h", "art_v1", graph_builder_version="gb_1.0")
    g2 = VersionedCacheKeyManager.get_graph_key("cv_h", "jd_h", "art_v1", graph_builder_version="gb_2.0")
    g3 = VersionedCacheKeyManager.get_graph_key("cv_h", "jd_h", "art_v2", graph_builder_version="gb_1.0")
    assert g1 != g2, "Graph builder version bump did not invalidate graph cache key!"
    assert g1 != g3, "Upstream artifact version change did not invalidate graph cache key!"
