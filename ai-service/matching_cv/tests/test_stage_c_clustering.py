"""
Stage C Unit Tests: Deterministic Skill Clustering & Evidence Preservation.

Verifies:
1. Must-merge pairs (at least 8 non-Northbridge technology stacks).
2. Must-NOT-merge pairs (all prompt denylist entries + 5 custom domain blockers + cert pairs).
3. Evidence preservation: sum of member evidences == cluster evidences.
4. skills output is byte-identical with clustering on vs off.
"""
import copy
import json
import pytest

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill, RawExtraction
from matching_cv.app.services.skill_clustering_service import (
    GENERIC_TOOL_SUFFIXES,
    KNOWN_ALIAS_TABLE,
    skill_clustering_service,
)
from matching_cv.app.services.skill_postprocessor import skill_postprocessor


def _make_skill(skill_id: str, label: str, category: str = "Technology/Tool", num_evidences: int = 1, kind: str = "skill") -> ExtractedSkill:
    """Helper to create dummy ExtractedSkill with num_evidences."""
    evidences = [
        Evidence(
            sentence=f"Demonstrated proficiency in {label} within production environment #{i}.",
            start=i * 200,
            end=i * 200 + 150,
            section="experience",
            verbatim_ok=True,
            mention_start=i * 200 + 25,
            mention_end=i * 200 + 25 + len(label),
        )
        for i in range(num_evidences)
    ]
    return ExtractedSkill(
        skill_id=skill_id,
        surface_forms=[label],
        category=category,
        category_raw=category,
        kind=kind,
        evidences=evidences,
    )


# -----------------------------------------------------------------------------
# 1. Must-Merge Pairs Test
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "label_a, id_a, label_b, id_b, expected_rule",
    [
        ("Node.js", "nodejs", "NodeJS", "nodejs-alt", "R3_known_alias"),
        ("GraphQL APIs", "graphql-apis", "GraphQL", "graphql", "R2_tool_generic_suffix"),
        ("Terraform scripts", "terraform-scripts", "Terraform", "terraform", "R2_tool_generic_suffix"),
        ("Postgres", "postgres", "PostgreSQL", "postgresql", "R3_known_alias"),
        ("FastAPI", "fastapi", "Fast API", "fast-api", "R3_known_alias"),
        ("Kubernetes", "kubernetes", "K8s", "k8s", "R3_known_alias"),
        ("Microservice architecture", "microservice-architecture", "Microservices architecture", "microservices-architecture", "R1_normalization"),
        ("Ansible automation", "ansible-automation", "Ansible", "ansible", "R2_tool_generic_suffix"),
        ("Docker containers", "docker-containers", "Docker", "docker", "R2_tool_generic_suffix"),
        ("React.js", "react-js", "React", "react", "R3_known_alias"),
        ("Redis caching", "redis-caching", "Redis", "redis", "R2_tool_generic_suffix"),
        ("REST APIs", "rest-apis", "REST API development", "rest-api-development", "R1_normalization"),
    ],
)
def test_must_merge_pairs(label_a, id_a, label_b, id_b, expected_rule):
    s_a = _make_skill(id_a, label_a)
    s_b = _make_skill(id_b, label_b)

    res = skill_clustering_service.cluster_skills([s_a, s_b])
    assert len(res.clusters) == 1, f"Expected 1 cluster for {label_a} and {label_b}, got {len(res.clusters)}"
    cluster = res.clusters[0]
    assert set(cluster.member_skill_ids) == {id_a, id_b}
    assert cluster.merge_rule in ("R1_normalization", "R2_tool_generic_suffix", "R3_known_alias")


# -----------------------------------------------------------------------------
# 2. Must-NOT-Merge Pairs Test (Denylist + Custom Blockers)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "label_a, id_a, label_b, id_b, category",
    [
        # Prompt mandatory denylist
        ("Java", "java", "JavaScript", "javascript", "Technology/Tool"),
        ("React", "react", "React Native", "react-native", "Technology/Tool"),
        ("C", "c", "C++", "cpp", "Technology/Tool"),
        ("C", "c", "C#", "c-sharp", "Technology/Tool"),
        ("C++", "cpp", "C#", "c-sharp", "Technology/Tool"),
        ("Docker", "docker", "Kubernetes", "kubernetes", "Technology/Tool"),
        ("SQL", "sql", "NoSQL", "nosql", "Technology/Tool"),
        ("MySQL", "mysql", "PostgreSQL", "postgresql", "Technology/Tool"),
        ("JUnit", "junit", "Mockito", "mockito", "Technology/Tool"),
        ("AWS", "aws", "GCP", "gcp", "Technology/Tool"),
        ("Jenkins", "jenkins", "GitHub Actions", "github-actions", "Technology/Tool"),
        ("Kafka", "kafka", "RabbitMQ", "rabbitmq", "Technology/Tool"),
        ("MySQL", "mysql", "Redis", "redis", "Technology/Tool"),
        ("AWS Certified Solutions Architect", "aws-certified-solutions-architect", "GCP Professional Cloud Architect", "gcp-professional-cloud-architect", "Certification"),
        # 5 Custom domain blockers
        ("Python", "python", "Cython", "cython", "Technology/Tool"),
        ("GraphQL", "graphql", "REST", "rest", "Technology/Tool"),
        ("Vue", "vue", "Angular", "angular", "Technology/Tool"),
        ("TCP", "tcp", "UDP", "udp", "Technology/Tool"),
        ("Swift", "swift", "Objective-C", "objective-c", "Technology/Tool"),
    ],
)
def test_must_not_merge_pairs(label_a, id_a, label_b, id_b, category):
    s_a = _make_skill(id_a, label_a, category=category, kind="certification" if category == "Certification" else "skill")
    s_b = _make_skill(id_b, label_b, category=category, kind="certification" if category == "Certification" else "skill")

    res = skill_clustering_service.cluster_skills([s_a, s_b])
    assert len(res.clusters) == 2, (
        f"Blocker failed: {label_a} and {label_b} were improperly merged into: "
        f"{[c.member_skill_ids for c in res.clusters]}"
    )
    for c in res.clusters:
        assert len(c.member_skill_ids) == 1
        assert c.merge_rule == "singleton"


def test_certifications_generic_vs_specific_hint_not_merged():
    """Vendor-generic cert vs specific role cert must NOT merge and must emit hint."""
    gen_cert = _make_skill("aws-certification", "AWS certification", category="Certification", kind="certification")
    spec_cert = _make_skill("aws-certified-developer-associate", "AWS Certified Developer – Associate", category="Certification", kind="certification")

    res = skill_clustering_service.cluster_skills([gen_cert, spec_cert])
    assert len(res.clusters) == 2, "Generic and specific certs must not merge"
    assert len(res.certification_hint_pairs) == 1
    hint = res.certification_hint_pairs[0]
    assert hint.generic_skill_id == "aws-certification"
    assert hint.specific_skill_id == "aws-certified-developer-associate"


def test_abstract_concepts_not_merged_by_topic_similarity():
    """Candidate topic groups: abstract concepts stay separate and emit topic_group_hint."""
    s1 = _make_skill("indexing", "Indexing", category="Technical Concept")
    s2 = _make_skill("query-optimization", "Query Optimization", category="Engineering Practice")
    s3 = _make_skill("relational-databases", "Relational Databases", category="Technical Concept")

    res = skill_clustering_service.cluster_skills([s1, s2, s3])
    # Must remain 3 separate clusters
    assert len(res.clusters) == 3, f"Expected 3 separate clusters, got {len(res.clusters)}"
    for c in res.clusters:
        assert len(c.member_skill_ids) == 1

    # Must emit topic_group_hint
    assert len(res.topic_group_hint) >= 1
    db_topic = next((t for t in res.topic_group_hint if t.topic == "Database & Query Performance"), None)
    assert db_topic is not None
    assert set(db_topic.member_skill_ids) == {"indexing", "query-optimization", "relational-databases"}


# -----------------------------------------------------------------------------
# 3. Evidence Preservation Test
# -----------------------------------------------------------------------------
def test_evidence_preservation():
    """Sum of member evidences == cluster evidences."""
    s1 = _make_skill("redis", "Redis", num_evidences=3)
    s2 = _make_skill("redis-caching", "Redis caching", num_evidences=2)
    s3 = _make_skill("terraform", "Terraform", num_evidences=1)
    s4 = _make_skill("terraform-scripts", "Terraform scripts", num_evidences=4)

    skills = [s1, s2, s3, s4]
    total_evidences_input = sum(len(s.evidences) for s in skills)

    res = skill_clustering_service.cluster_skills(skills)
    assert len(res.clusters) == 2

    redis_cluster = next(c for c in res.clusters if "redis" in c.canonical_skill_id)
    tf_cluster = next(c for c in res.clusters if "terraform" in c.canonical_skill_id)

    # Check member evidence count sum == cluster evidence count
    assert len(redis_cluster.evidences) == len(s1.evidences) + len(s2.evidences)
    assert len(redis_cluster.evidences) == 5

    assert len(tf_cluster.evidences) == len(s3.evidences) + len(s4.evidences)
    assert len(tf_cluster.evidences) == 5

    total_cluster_evidences = sum(len(c.evidences) for c in res.clusters)
    assert total_cluster_evidences == total_evidences_input == 10

    # Ensure no evidence was mutated or dropped
    redis_ev_sentences = [e.sentence for e in redis_cluster.evidences]
    for e in s1.evidences + s2.evidences:
        assert e.sentence in redis_ev_sentences


# -----------------------------------------------------------------------------
# 4. Byte-Identical skills Output Test (Clustering On vs Off)
# -----------------------------------------------------------------------------
def test_skills_byte_identical_clustering_on_vs_off(monkeypatch):
    """Verify that skills output is 100% byte-identical whether clustering is enabled or disabled."""
    raw_input = {
        "skills": [
            {"surface_form": "Redis", "category": "Technology/Tool", "sentence": "Used Redis for state caching."},
            {"surface_form": "Redis caching", "category": "Technology/Tool", "sentence": "Used Redis caching in API."},
            {"surface_form": "PostgreSQL", "category": "Technology/Tool", "sentence": "PostgreSQL relational DB."},
            {"surface_form": "Postgres", "category": "Technology/Tool", "sentence": "Queried Postgres database."},
        ]
    }
    doc_text = "Used Redis for state caching. Used Redis caching in API. PostgreSQL relational DB. Queried Postgres database."

    # Run with clustering disabled (default)
    monkeypatch.setattr(settings, "SKILL_CLUSTERING_ENABLED", False)
    res_disabled = skill_postprocessor.process_extraction(
        raw_result=raw_input,
        text=doc_text,
        filename="test.txt",
        document_type="CV",
    )

    # Run with clustering enabled
    monkeypatch.setattr(settings, "SKILL_CLUSTERING_ENABLED", True)
    res_enabled = skill_postprocessor.process_extraction(
        raw_result=raw_input,
        text=doc_text,
        filename="test.txt",
        document_type="CV",
    )

    # skills field comparison
    skills_dump_disabled = [s.model_dump() for s in res_disabled.skills]
    skills_dump_enabled = [s.model_dump() for s in res_enabled.skills]

    assert skills_dump_disabled == skills_dump_enabled, "skills output modified when clustering enabled!"
    json_disabled = json.dumps(skills_dump_disabled, sort_keys=True)
    json_enabled = json.dumps(skills_dump_enabled, sort_keys=True)
    assert json_disabled == json_enabled, "skills JSON serialization is not byte-identical!"

    # Clusters comparison
    assert res_disabled.skill_clusters == []
    assert len(res_enabled.skill_clusters) == 2
    cluster_canons = {c.canonical_skill_id for c in res_enabled.skill_clusters}
    assert "redis" in cluster_canons
    assert "postgresql" in cluster_canons
