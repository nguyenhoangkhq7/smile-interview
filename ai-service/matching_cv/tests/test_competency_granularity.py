"""Unit and integration tests for Competency Granularity and Context Segregation (Pre-GNN Phase 2C Fix 2)."""
import pytest

from matching_cv.app.services.competency_granularity import (
    analyze_constituent_overlaps,
    classify_competency_granularity,
    normalize_inflectional_slug,
)
from matching_cv.app.services.extraction_adapter import AdaptedSkillItem, ExtractionDataAdapter
from matching_cv.app.services.skill_postprocessor import SkillPostprocessor


def test_classify_competency_granularity_atomic():
    """Verify standard atomic skills are correctly identified across IT and non-IT domains."""
    assert classify_competency_granularity("Node.js", kind="skill") == "atomic_skill"
    assert classify_competency_granularity("Express", kind="skill") == "atomic_skill"
    assert classify_competency_granularity("PostgreSQL", kind="skill") == "atomic_skill"
    assert classify_competency_granularity("React", kind="skill") == "atomic_skill"
    assert classify_competency_granularity("Surgical Suturing", kind="skill") == "atomic_skill"
    assert classify_competency_granularity("Bookkeeping", kind="skill") == "atomic_skill"


def test_classify_competency_granularity_compound():
    """Verify compound competencies combining multiple technologies or role head nouns."""
    assert classify_competency_granularity("Node.js/Express backends", kind="skill") == "compound_competency"
    assert classify_competency_granularity("React frontends", kind="skill") == "compound_competency"
    assert classify_competency_granularity("React frontend", kind="skill") == "compound_competency"
    assert classify_competency_granularity("CI/CD pipeline automation", kind="skill") == "compound_competency"
    assert classify_competency_granularity("Financial Accounting & Reconciliation", kind="skill") == "compound_competency"
    assert classify_competency_granularity("Distributed database architecture", kind="skill") == "compound_competency"


def test_classify_competency_granularity_context():
    """Verify project activities, features, and internal products are segregated as contextual artifacts."""
    assert classify_competency_granularity("internal tools", kind="context") == "contextual_activity_or_product"
    assert classify_competency_granularity("admin dashboard", kind="context") == "contextual_activity_or_product"
    assert classify_competency_granularity("route-planning module", kind="context") == "contextual_activity_or_product"
    assert classify_competency_granularity("real-time shipment-tracking feature", kind="context") == "contextual_activity_or_product"
    # Even if kind was not populated, feature/dashboard phrasing is detected
    assert classify_competency_granularity("admin dashboard") == "contextual_activity_or_product"
    assert classify_competency_granularity("route-planning module") == "contextual_activity_or_product"


def test_classify_competency_granularity_domain():
    """Verify domain knowledge items are categorized as domain_knowledge."""
    assert classify_competency_granularity("Healthcare", kind="domain") == "domain_knowledge"
    assert classify_competency_granularity("Supply Chain & Logistics", category="Domain Knowledge") == "domain_knowledge"


def test_inflectional_slug_consolidation():
    """Verify inflectional variants resolve to the same canonical slug while preserving surface forms."""
    slug_plural = normalize_inflectional_slug("React frontends")
    slug_singular = normalize_inflectional_slug("React frontend")
    assert slug_plural == slug_singular == "react-frontend"

    postprocessor = SkillPostprocessor()
    assert postprocessor.slugify_skill("React frontends") == postprocessor.slugify_skill("React frontend")
    assert postprocessor.slugify_skill("Node.js backends") == postprocessor.slugify_skill("Node.js backend")


def test_analyze_constituent_overlaps():
    """
    Verify that composite competencies are linked with constituent atomic skills without deleting either.
    E.g., Node.js/Express backends contains Node.js and Express.
    """
    skills = [
        {"skill_id": "node.js-express-backend", "display_name": "Node.js/Express backends", "kind": "skill"},
        {"skill_id": "node.js", "display_name": "Node.js", "kind": "skill"},
        {"skill_id": "express", "display_name": "Express", "kind": "skill"},
        {"skill_id": "postgresql", "display_name": "PostgreSQL", "kind": "skill"},
        {"skill_id": "admin-dashboard", "display_name": "admin dashboard", "kind": "context"},
    ]

    overlaps = analyze_constituent_overlaps(skills)

    # Compound skill has both constituents
    compound_info = overlaps["node.js-express-backend"]
    assert compound_info["granularity"] == "compound_competency"
    assert "node.js" in compound_info["constituent_skill_ids"]
    assert "express" in compound_info["constituent_skill_ids"]
    assert "postgresql" not in compound_info["constituent_skill_ids"]

    # Atomic skills have the parent compound
    node_info = overlaps["node.js"]
    assert node_info["granularity"] == "atomic_skill"
    assert "node.js-express-backend" in node_info["parent_compound_skill_ids"]

    express_info = overlaps["express"]
    assert express_info["granularity"] == "atomic_skill"
    assert "node.js-express-backend" in express_info["parent_compound_skill_ids"]

    # Contextual artifact is segregated
    context_info = overlaps["admin-dashboard"]
    assert context_info["granularity"] == "contextual_activity_or_product"


def test_adapted_skill_item_granularity_metadata():
    """Verify AdaptedSkillItem carries granularity and is_competency flags."""
    item_atomic = AdaptedSkillItem(
        occurrence_id="occ_1",
        skill_id="react",
        display_name="React",
        extraction_type="explicit",
        kind="skill",
    )
    assert item_atomic.granularity == "atomic_skill"
    assert item_atomic.metadata.get("is_competency", True) is True

    item_context = AdaptedSkillItem(
        occurrence_id="occ_2",
        skill_id="internal-tools",
        display_name="internal tools",
        extraction_type="explicit",
        kind="context",
    )
    assert item_context.granularity == "contextual_activity_or_product"
    assert item_context.metadata.get("is_competency") is False
