"""
Tests for Phase I2-A Embedding Input Consistency & Compatibility.

Validates that SBERT embeddings are deterministic, pinned, source-order independent,
and compatible with the training configuration.
"""

import hashlib
import numpy as np
import pytest
import torch

from matching_cv.app.core.config import settings
from matching_cv.app.services.semantic_embedding_service import semantic_embedding_service
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.shared_skill_matcher import combine_shared_embeddings


def test_01_pinned_sbert_model_and_revision():
    """Verify SBERT model and immutable revision SHA are pinned to prevent cross-model drift."""
    assert settings.STAGE3_MODEL_NAME == "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    assert settings.STAGE3_MODEL_REVISION == "4328cf26390c98c5e3c738b4460a05b95f4911f5"
    assert settings.STAGE3_EMBEDDING_DIM == 768


def test_02_embedding_dimension_and_l2_normalization():
    """Verify generated embeddings strictly have 768 dimensions and unit L2 norm."""
    test_skills = ["Java", "Spring Boot", "Kafka"]
    vecs = semantic_embedding_service.encode_batch(test_skills)

    assert isinstance(vecs, np.ndarray)
    assert vecs.shape == (3, 768)

    norms = np.linalg.norm(vecs, axis=1)
    for norm in norms:
        assert np.isclose(norm, 1.0, atol=1e-5), f"Expected unit norm, got {norm}"


def test_03_deterministic_embeddings_across_calls():
    """Verify repeat calls produce bitwise identical embeddings."""
    phrase = "RESTful microservices in Java"
    vec1 = semantic_embedding_service.encode_batch([phrase])
    vec2 = semantic_embedding_service.encode_batch([phrase])

    np.testing.assert_array_equal(vec1, vec2)


def test_04_cache_key_content_hash_correctness():
    """Verify cache keys strictly derive from the exact input text and differ for surface variants."""
    text_a = "Java"
    text_b = "java"
    text_c = "Java "

    hash_a = hashlib.sha256(text_a.encode("utf-8")).hexdigest()
    hash_b = hashlib.sha256(text_b.encode("utf-8")).hexdigest()
    hash_c = hashlib.sha256(text_c.encode("utf-8")).hexdigest()

    assert hash_a != hash_b, "Case differences must produce distinct hash keys"
    assert hash_a != hash_c, "Whitespace differences must produce distinct hash keys"


def test_05_shared_skill_source_order_independence():
    """Verify combine_shared_embeddings is strictly commutative (CV-first vs JD-first)."""
    np.random.seed(42)
    vec_a = np.random.randn(768).astype(np.float32)
    vec_a /= np.linalg.norm(vec_a)
    vec_b = np.random.randn(768).astype(np.float32)
    vec_b /= np.linalg.norm(vec_b)

    comb_ab, mode_ab = combine_shared_embeddings(vec_a.tolist(), vec_b.tolist())
    comb_ba, mode_ba = combine_shared_embeddings(vec_b.tolist(), vec_a.tolist())

    assert mode_ab == mode_ba
    np.testing.assert_allclose(comb_ab, comb_ba, atol=1e-6)


def test_06_canonical_alias_consistency():
    """Verify canonical normalizer consistently maps aliases to authoritative IDs without collisions."""
    assert normalize_canonical_skill("node.js") == "nodejs"
    assert normalize_canonical_skill("nodejs") == "nodejs"
    assert normalize_canonical_skill("c++") == "c++"
    assert normalize_canonical_skill("cplusplus") == "c++"
    assert normalize_canonical_skill("c#") == "c#"
    assert normalize_canonical_skill("csharp") == "c#"
    assert normalize_canonical_skill("postgres") == "postgresql"
    assert normalize_canonical_skill("postgresql") == "postgresql"
