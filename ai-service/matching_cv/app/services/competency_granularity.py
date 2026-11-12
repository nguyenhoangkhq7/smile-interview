"""Ontology-free competency granularity classification and overlap analysis service (Pre-GNN Phase 2C)."""
from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

CompetencyGranularity = Literal[
    "atomic_skill",
    "compound_competency",
    "contextual_activity_or_product",
    "domain_knowledge",
    "ambiguous_candidate",
]

# Common functional/architectural head nouns indicating a compound competency or scoped role
ROLE_HEAD_NOUNS_PATTERN = re.compile(
    r"\b(backends?|frontends?|architectures?|pipelines?|systems?|infrastructure|tooling|services?)\b",
    re.IGNORECASE,
)

# Common product/project context patterns indicating project tasks, features, or internal tools
CONTEXT_PRODUCT_PATTERN = re.compile(
    r"\b(internal\s+tools?|admin\s+dashboards?|dashboards?|modules?|features?|workflows?|portals?|platforms?\s+development)\b",
    re.IGNORECASE,
)

# Technical engineering workflow patterns representing transferable engineering practices
ENGINEERING_WORKFLOW_PATTERN = re.compile(
    r"\b(container(?:ized)?|ci[\s/-]?cd|devops|build|deployment|gitops|iac|infrastructure[\s/-]as[\s/-]code|automated\s+test(?:ing)?)\s+(?:deployment\s+)?workflows?\b",
    re.IGNORECASE,
)

# Architectural concept patterns representing transferable paradigms rather than project components
ARCHITECTURAL_CONCEPT_PATTERN = re.compile(
    r"^(?:microservices?(?:\s+architectures?)?|message[\s/-]driven\s+architectures?|event[\s/-]driven\s+(?:architectures?|integrations?)|service[\s/-]oriented\s+architectures?|soa|distributed\s+systems?(?:\s+architectures?)?|rest(?:ful)?\s+api\s+development|restful\s+microservices|hexagonal\s+architectures?|clean\s+architecture|domain[\s/-]driven\s+design|database\s+optimization|relational\s+database\s+design)$",
    re.IGNORECASE,
)

# Named project artifact patterns (specific microservices, modules, components)
NAMED_PROJECT_ARTIFACT_PATTERN = re.compile(
    r"^(?:order[\s/-]management|user[\s/-]management|auth|billing|checkout|inventory|payment|shipping|notification|customer|search)[\s/-]+(?:microservices?|services?|modules?|pipelines?|dashboards?|systems?)$",
    re.IGNORECASE,
)

# Runtime environment and infrastructure context patterns
ENVIRONMENT_CONTEXT_PATTERN = re.compile(
    r"^(?:production|staging|testing|local|development)[\s/-]+(?:environments?|services?|clusters?|servers?)$",
    re.IGNORECASE,
)

# Operational metrics and performance condition patterns
METRIC_CONDITION_PATTERN = re.compile(
    r"\b(throughput|latency|uptime|orders/day|requests/sec|qps|sla|high[\s/-]write)\b",
    re.IGNORECASE,
)

# Evidence pattern indicating assignment to a specific named component/module
PROJECT_ASSIGNMENT_EVIDENCE_PATTERN = re.compile(
    r"\b(?:assigned\s+to(?:\s+the)?|responsible\s+for\s+(?:the\s+bug|tickets\s+in|fixing|maintaining\s+the)|own(?:ed)?\s+the)\s+[a-z0-9_-]+\s+(?:microservices?|services?|modules?)\b",
    re.IGNORECASE,
)


@dataclass
class CompetencyRetentionDecision:
    """Standardized auditable competency retention decision for Stage 5 graph ingestion."""

    should_retain: bool
    reason_code: str
    decision_source: str
    granularity: CompetencyGranularity
    detail: Optional[str] = None


def evaluate_competency_retention(
    label: str,
    kind: Optional[str] = None,
    category: Optional[str] = None,
    evidence: Optional[str] = None,
    side: Optional[str] = None,
) -> CompetencyRetentionDecision:
    """
    Evaluate whether an extracted skill should be retained in the paper-aligned bipartite graph.
    Differentiates technical competencies (architectural concepts, engineering practices)
    from contextual project artifacts (named microservices, modules, environments).
    """
    clean_label = (label or "").strip()
    if not clean_label:
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_EMPTY_LABEL",
            decision_source="input_validation",
            granularity="ambiguous_candidate",
        )

    clean_kind = (kind or "").strip().lower()
    clean_cat = (category or "").strip()
    clean_ev = (evidence or "").strip()

    # Rule 1: Named project artifact pattern (e.g. order-management microservice, payment module)
    if NAMED_PROJECT_ARTIFACT_PATTERN.match(clean_label):
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_NAMED_PROJECT_ARTIFACT",
            decision_source="rule_named_artifact",
            granularity="contextual_activity_or_product",
            detail=f"Named project component: '{clean_label}'",
        )

    # Rule 2: Environment / infra context pattern (e.g. production environment, production services)
    if ENVIRONMENT_CONTEXT_PATTERN.match(clean_label):
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_ENVIRONMENT_OR_INFRA_CONTEXT",
            decision_source="rule_environment_context",
            granularity="contextual_activity_or_product",
            detail=f"Runtime environment context: '{clean_label}'",
        )

    # Rule 3: Operational metrics / conditions (e.g. high write throughput)
    if METRIC_CONDITION_PATTERN.search(clean_label) and clean_kind == "context":
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_DATA_CHARACTERISTIC_OR_METRIC",
            decision_source="rule_metric_characteristic",
            granularity="contextual_activity_or_product",
            detail=f"Performance/operational metric: '{clean_label}'",
        )

    # Rule 4: Specific component / system (e.g. PostgreSQL-backed services, downstream ledgers, reporting systems, Kafka-based event pipeline)
    if clean_kind == "context" and re.search(r"\b(services?|systems?|ledgers?|pipelines?)\b", clean_label, re.IGNORECASE):
        if not ARCHITECTURAL_CONCEPT_PATTERN.match(clean_label):
            return CompetencyRetentionDecision(
                should_retain=False,
                reason_code="FILTER_PROJECT_COMPONENT_OR_SYSTEM",
                decision_source="rule_project_component",
                granularity="contextual_activity_or_product",
                detail=f"Project component or subsystem: '{clean_label}'",
            )

    # Rule 5: Evidence-anchored project assignment check (Test 6: same term under different evidence)
    # Only applies to generic/ambiguous/contextual items, never to standard concrete technologies like Spring Boot or PostgreSQL.
    if clean_kind == "context" or re.search(r"^(?:microservices?|services?|modules?)$", clean_label, re.IGNORECASE):
        if clean_ev and PROJECT_ASSIGNMENT_EVIDENCE_PATTERN.search(clean_ev):
            return CompetencyRetentionDecision(
                should_retain=False,
                reason_code="FILTER_CONTEXT_ARTIFACT_EVIDENCE",
                decision_source="evidence_context_analysis",
                granularity="contextual_activity_or_product",
                detail="Evidence explicitly anchors item to a specific assigned component or bug ticket",
            )

    # Rule 6: Engineering practice workflows (Case 3: containerized deployment workflows)
    if ENGINEERING_WORKFLOW_PATTERN.search(clean_label):
        return CompetencyRetentionDecision(
            should_retain=True,
            reason_code="RETAIN_ENGINEERING_PRACTICE",
            decision_source="rule_engineering_practice",
            granularity="compound_competency",
            detail="Transferable DevOps/deployment engineering workflow",
        )

    # Rule 7: Generic workflows (Test 5: generic reporting workflow)
    if re.search(r"\bworkflows?\b", clean_label, re.IGNORECASE):
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_GENERIC_BUSINESS_WORKFLOW",
            decision_source="rule_generic_workflow",
            granularity="contextual_activity_or_product",
            detail=f"Generic/business workflow without engineering practice context: '{clean_label}'",
        )

    # Rule 8: Architectural concepts (Case 1 & 2: microservices, message-driven architectures)
    if ARCHITECTURAL_CONCEPT_PATTERN.match(clean_label):
        gran = "compound_competency" if len(clean_label.split()) > 1 else "atomic_skill"
        return CompetencyRetentionDecision(
            should_retain=True,
            reason_code="RETAIN_ARCHITECTURAL_CONCEPT",
            decision_source="rule_architectural_capability",
            granularity=gran,
            detail="Transferable architectural concept/paradigm",
        )

    # Rule 9: Domain knowledge
    if clean_kind == "domain" or clean_cat == "Domain Knowledge":
        return CompetencyRetentionDecision(
            should_retain=True,
            reason_code="RETAIN_DOMAIN_KNOWLEDGE",
            decision_source="rule_domain_knowledge",
            granularity="domain_knowledge",
        )

    # Rule 10: Certifications
    if clean_kind == "certification" or clean_cat == "Certification":
        return CompetencyRetentionDecision(
            should_retain=True,
            reason_code="RETAIN_CERTIFICATION",
            decision_source="rule_certification",
            granularity="atomic_skill",
        )

    # Rule 11: Explicit context items that didn't match any competency rule
    if clean_kind == "context":
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_EXPLICIT_CONTEXT_NON_COMPETENCY",
            decision_source="rule_explicit_context",
            granularity="contextual_activity_or_product",
        )

    # Rule 12: Contextual product/activity from label
    if CONTEXT_PRODUCT_PATTERN.search(clean_label):
        return CompetencyRetentionDecision(
            should_retain=False,
            reason_code="FILTER_CONTEXT_PRODUCT_PATTERN",
            decision_source="rule_context_product_pattern",
            granularity="contextual_activity_or_product",
        )

    # Default: Retain standard technical competencies
    has_slash = "/" in clean_label and clean_label.upper() not in ("CI/CD", "I/O", "TCP/IP")
    has_conjunction = bool(re.search(r"(?:^|\s)(?:&|and)(?:\s|$)", clean_label, re.IGNORECASE))
    has_role_head = bool(ROLE_HEAD_NOUNS_PATTERN.search(clean_label))
    gran = "compound_competency" if (has_slash or (len(clean_label.split()) >= 2 and (has_conjunction or has_role_head))) else "atomic_skill"

    return CompetencyRetentionDecision(
        should_retain=True,
        reason_code="RETAIN_STANDARD_COMPETENCY",
        decision_source="rule_standard_competency",
        granularity=gran,
    )


def classify_competency_granularity(
    label: str,
    kind: Optional[str] = None,
    category: Optional[str] = None,
    evidence: Optional[str] = None,
) -> CompetencyGranularity:
    """
    Domain-agnostic competency granularity classifier.

    Distinguishes:
    1. atomic_skill: Individual tools, languages, standards, or techniques.
    2. compound_competency: Composite competencies combining multiple technologies or scoped roles.
    3. contextual_activity_or_product: Activities, applications, features, or internal products.
    4. domain_knowledge: Industry or business domain concepts.
    5. ambiguous_candidate: Malformed or unresolvable candidate labels.
    """
    decision = evaluate_competency_retention(
        label=label,
        kind=kind,
        category=category,
        evidence=evidence,
    )
    return decision.granularity


def normalize_inflectional_slug(label: str) -> str:
    """
    Normalize minor grammatical inflectional variations (e.g. frontends -> frontend)
    to prevent spurious duplicate skill nodes while preserving surface forms.
    """
    slug = re.sub(r"[^\w\-\.]+|_+", "-", unicodedata.normalize("NFKC", label).lower()).strip("-.")
    # Lemmatize common plural suffixes on role head nouns
    slug = re.sub(r"-backends$", "-backend", slug)
    slug = re.sub(r"-frontends$", "-frontend", slug)
    slug = re.sub(r"-pipelines$", "-pipeline", slug)
    slug = re.sub(r"-systems$", "-system", slug)
    return slug


def analyze_constituent_overlaps(skills: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze textual containment and constituent relationships among extracted skills.
    Preserves all records while annotating compound competencies with their atomic constituents
    and atomic skills with their parent compound competencies.
    """
    result: Dict[str, Dict[str, Any]] = {}
    for s in skills:
        s_id = s.get("skill_id") or s.get("occurrence_id") or ""
        result[s_id] = {
            "constituent_skill_ids": [],
            "parent_compound_skill_ids": [],
            "granularity": s.get("granularity") or classify_competency_granularity(
                s.get("display_name") or s.get("label") or "",
                kind=s.get("kind"),
                category=s.get("category"),
            ),
        }

    # Detect containment among pairs
    for i, s1 in enumerate(skills):
        id1 = s1.get("skill_id") or s1.get("occurrence_id") or ""
        label1 = (s1.get("display_name") or s1.get("label") or "").casefold()
        gran1 = result[id1]["granularity"]

        for j, s2 in enumerate(skills):
            if i == j:
                continue
            id2 = s2.get("skill_id") or s2.get("occurrence_id") or ""
            label2 = (s2.get("display_name") or s2.get("label") or "").casefold()
            gran2 = result[id2]["granularity"]

            # If s1 is compound and s2 is atomic, check if s2 is a constituent substring of s1
            if gran1 == "compound_competency" and gran2 == "atomic_skill":
                # Ensure word-boundary or slash containment
                pat = rf"(?:^|[\s/_\-])" + re.escape(label2) + rf"(?:$|[\s/_\-])"
                if re.search(pat, label1):
                    if id2 not in result[id1]["constituent_skill_ids"]:
                        result[id1]["constituent_skill_ids"].append(id2)
                    if id1 not in result[id2]["parent_compound_skill_ids"]:
                        result[id2]["parent_compound_skill_ids"].append(id1)

    return result
