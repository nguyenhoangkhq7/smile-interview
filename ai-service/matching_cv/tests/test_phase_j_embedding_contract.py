"""Tests for Unified Embedding Contract (Phase J)."""
import pytest
from matching_cv.research.paper_aligned_gnn.unified_embedding_contract import (
    canonical_id_to_display_name,
    get_unified_embedding_input,
    unified_embedding_contract,
    EMBEDDING_CONTRACT_VERSION,
    STAGE3_MODEL_NAME,
    STAGE3_EMBEDDING_DIM,
)


def test_01_canonical_id_to_display_name_standard_tokens():
    assert canonical_id_to_display_name("java") == "Java"
    assert canonical_id_to_display_name("python") == "Python"
    assert canonical_id_to_display_name("machine-learning") == "Machine Learning"
    assert canonical_id_to_display_name("deep-learning") == "Deep Learning"


def test_02_canonical_id_to_display_name_acronyms_and_brands():
    assert canonical_id_to_display_name("sql") == "SQL"
    assert canonical_id_to_display_name("postgresql") == "PostgreSQL"
    assert canonical_id_to_display_name("mysql") == "MySQL"
    assert canonical_id_to_display_name("ci-cd") == "CI/CD"
    assert canonical_id_to_display_name("rest-api") == "REST API"
    assert canonical_id_to_display_name("junit-5") == "JUnit 5"
    assert canonical_id_to_display_name("nodejs") == "Node.js"
    assert canonical_id_to_display_name("k8s") == "Kubernetes"


def test_03_canonical_id_to_display_name_explicit_overrides():
    assert canonical_id_to_display_name("java-spring-boot-stack") == "Java / Spring Boot Stack"
    assert canonical_id_to_display_name("restful-microservices") == "RESTful Microservices"
    assert canonical_id_to_display_name("unit-and-integration-tests") == "Unit and Integration Testing"
    assert canonical_id_to_display_name("relational-databases") == "Relational Databases"
    assert canonical_id_to_display_name("html-css") == "HTML / CSS"


def test_04_get_unified_embedding_input_determinism_and_hashing():
    t1, h1 = get_unified_embedding_input("java-spring-boot-stack", "Java/Spring Boot stack")
    t2, h2 = get_unified_embedding_input("java-spring-boot-stack", "arbitrary surface text")
    assert t1 == "Java / Spring Boot Stack"
    assert t1 == t2
    assert h1 == h2
    assert len(h1) == 64


def test_05_unified_embedding_input_fallback_when_empty_slug():
    t, h = get_unified_embedding_input("", "React Developer")
    assert t == "React Developer"
    assert len(h) == 64


def test_06_training_inference_input_equivalence():
    """Verify that training input construction and inference input construction yield 100% identical strings."""
    # Training item representation
    train_slug = "distributed-system-design"
    train_text, train_hash = get_unified_embedding_input(train_slug)

    # Inference item representation
    infer_slug = "distributed-system-design"
    infer_surface = "Distributed System Design"
    infer_text, infer_hash = get_unified_embedding_input(infer_slug, infer_surface)

    assert train_text == infer_text
    assert train_hash == infer_hash
    assert train_text == "Distributed System Design"


def test_07_contract_metadata_invariants():
    meta = unified_embedding_contract.get_contract_metadata()
    assert meta["contract_version"] == EMBEDDING_CONTRACT_VERSION
    assert meta["representation_type"] == "canonical_display_name"
    assert meta["model_name"] == STAGE3_MODEL_NAME
    assert meta["embedding_dim"] == STAGE3_EMBEDDING_DIM
    assert meta["deterministic"] is True
    assert meta["l2_normalized"] is True
