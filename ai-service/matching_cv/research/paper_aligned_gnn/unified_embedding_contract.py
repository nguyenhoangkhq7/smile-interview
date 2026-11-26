"""Unified Embedding Contract for Phase J Retraining and Inference Alignment.

Ensures training and production inference share an identical, deterministic SBERT
embedding representation, resolving the canonical slug vs surface form divergence.

Reference:
- Baghbanzadeh & Wu (2025), ICIT 2025
- Phase I2-B Findings & Phase J Mandate
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Authoritative Contract Specification
EMBEDDING_CONTRACT_VERSION = "phase_j_v1_canonical_display"
STAGE3_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
STAGE3_MODEL_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"
STAGE3_EMBEDDING_DIM = 768

# Curated Acronym and Brand Capitalization Dictionary
ACRONYM_MAP: Dict[str, str] = {
    "sql": "SQL",
    "nosql": "NoSQL",
    "rdbms": "RDBMS",
    "dbms": "DBMS",
    "aws": "AWS",
    "gcp": "GCP",
    "ci": "CI",
    "cd": "CD",
    "ci-cd": "CI/CD",
    "api": "API",
    "apis": "APIs",
    "rest": "REST",
    "restful": "RESTful",
    "html": "HTML",
    "css": "CSS",
    "ui": "UI",
    "ux": "UX",
    "etl": "ETL",
    "elt": "ELT",
    "bi": "BI",
    "ai": "AI",
    "ml": "ML",
    "nlp": "NLP",
    "orm": "ORM",
    "jpa": "JPA",
    "sre": "SRE",
    "devops": "DevOps",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react": "React",
    "vuejs": "Vue.js",
    "angularjs": "AngularJS",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "rabbitmq": "RabbitMQ",
    "kafka": "Apache Kafka",
    "docker": "Docker",
    "spring-boot": "Spring Boot",
    "spring-framework": "Spring Framework",
    "junit-5": "JUnit 5",
    "junit": "JUnit",
    "mockito": "Mockito",
    "microservices": "Microservices",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
}

# Specific Canonical Display Name Overrides for Multi-word Compound Competencies
EXPLICIT_DISPLAY_NAMES: Dict[str, str] = {
    "java-spring-boot-stack": "Java / Spring Boot Stack",
    "unit-and-integration-tests": "Unit and Integration Testing",
    "relational-databases": "Relational Databases",
    "restful-microservices": "RESTful Microservices",
    "containerized-deployment-workflows": "Containerized Deployment Workflows",
    "ci-cd-pipelines": "CI/CD Pipelines",
    "html-css": "HTML / CSS",
    "react-redux": "React / Redux",
    "etl-elt-pipelines": "ETL / ELT Pipelines",
    "microsoft-office-suite": "Microsoft Office Suite",
    "relational-database-design": "Relational Database Design",
    "distributed-system-design": "Distributed System Design",
    "legacy-system-migration": "Legacy System Migration",
    "system-decoupling": "System Decoupling",
    "test-strategy": "Test Strategy",
    "coverage-analysis": "Code Coverage Analysis",
    "requirements-translation": "Requirements Translation",
}


def canonical_id_to_display_name(canonical_id: str) -> str:
    """
    Deterministically transforms a canonical skill slug (e.g. 'java-spring-boot-stack')
    into its authoritative natural language canonical display name (e.g. 'Java / Spring Boot Stack').
    """
    if not canonical_id or not isinstance(canonical_id, str):
        return ""

    slug = canonical_id.strip().lower()
    if not slug:
        return ""

    # Check explicit compound override
    if slug in EXPLICIT_DISPLAY_NAMES:
        return EXPLICIT_DISPLAY_NAMES[slug]

    # Check direct acronym/brand override
    if slug in ACRONYM_MAP:
        return ACRONYM_MAP[slug]

    # Handle hyphenated and underscored terms
    tokens = re.split(r"[-_]+", slug)
    formatted_tokens = []
    for token in tokens:
        if not token:
            continue
        if token in ACRONYM_MAP:
            formatted_tokens.append(ACRONYM_MAP[token])
        else:
            formatted_tokens.append(token.capitalize())

    return " ".join(formatted_tokens)


def get_unified_embedding_input(
    canonical_id: str,
    surface_name: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Authoritative single-source function generating embedding input text across both
    training and production inference pipelines.

    Returns:
        (text_to_encode, text_sha256)
    """
    # Deterministic Canonical Display Name is the chosen Phase J standard
    text_to_encode = canonical_id_to_display_name(canonical_id)
    if not text_to_encode:
        # Fallback to sanitized surface name if canonical is blank
        text_to_encode = (surface_name or "").strip()

    text_sha256 = hashlib.sha256(text_to_encode.encode("utf-8")).hexdigest()
    return text_to_encode, text_sha256


class UnifiedEmbeddingContract:
    """Encapsulates contract verification, metadata, and deterministic batch encoding."""

    def __init__(self) -> None:
        self.version = EMBEDDING_CONTRACT_VERSION
        self.model_name = STAGE3_MODEL_NAME
        self.model_revision = STAGE3_MODEL_REVISION
        self.embedding_dim = STAGE3_EMBEDDING_DIM

    def get_contract_metadata(self) -> Dict[str, Any]:
        return {
            "contract_version": self.version,
            "representation_type": "canonical_display_name",
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "embedding_dim": self.embedding_dim,
            "l2_normalized": True,
            "deterministic": True,
        }

    def prepare_embedding_text(self, canonical_id: str, surface_name: Optional[str] = None) -> str:
        text, _ = get_unified_embedding_input(canonical_id, surface_name)
        return text

    def prepare_batch_texts(
        self,
        skill_items: List[Tuple[str, Optional[str]]],
    ) -> Tuple[List[str], List[str]]:
        """
        Prepares a batch of skills for SBERT encoding.
        Input: list of (canonical_id, surface_name) tuples.
        Returns: (texts_to_encode, text_hashes).
        """
        texts = []
        hashes = []
        for canon, surf in skill_items:
            t, h = get_unified_embedding_input(canon, surf)
            texts.append(t)
            hashes.append(h)
        return texts, hashes


unified_embedding_contract = UnifiedEmbeddingContract()
