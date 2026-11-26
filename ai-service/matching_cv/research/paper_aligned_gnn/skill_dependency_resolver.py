"""Skill Dependency Resolver for Dependency-Aware Heterogeneous GNN.

Resolves directed `(skill, prerequisite_to, skill)` edges among active graph skill nodes
by combining:
1. Stage 4 LLM Semantic Reasoning outputs (`relationship == "prerequisite"` with verified direction).
2. A curated, cycle-free technical skill prerequisite taxonomy (DAG) covering software engineering,
   cloud/DevOps, data/ML, QA, security, and product engineering competencies.

Each resolved dependency edge is weighted by the SBERT cosine similarity between the two skill
nodes' embeddings (clamped to [0.1, 1.0]), directly coupling Sentence-BERT semantic similarity
with GNN intra-skill dependency message passing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Set, Tuple
import numpy as np

from matching_cv.app.schemas.semantic_reasoning import SkillPairReasoningResult
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.schemas import PaperAlignedSkillNode
from matching_cv.research.paper_aligned_gnn.shared_skill_matcher import compute_vector_cosine

DependencyScope = Literal["jd_bidirectional", "jd_anchored", "jd_only", "all_skills"]
DirectedRelationKind = Literal["cv_supersedes_jd", "cv_is_prerequisite_only", "none"]

# Alias normalization specifically for prerequisite lookup (preserves distinct node identities
# in the graph while allowing slightly qualified surface slugs like 'javascript-es6+' to match
# their base foundational skill in the prerequisite DAG).
_PREREQ_LOOKUP_ALIASES: Dict[str, str] = {
    "javascript-es6+": "javascript",
    "javascript-es6": "javascript",
    "es6": "javascript",
    "es6+": "javascript",
    "js": "javascript",
    "ts": "typescript",
    "restful-apis": "rest-api",
    "restful-api": "rest-api",
    "rest-apis": "rest-api",
    "gitlab-ci-cd": "gitlab-ci",
    "github-actions-ci-cd": "github-actions",
    "cloud-platforms": "cloud",
    "cloud-computing": "cloud",
    "google-cloud": "gcp",
    "amazon-web-services": "aws",
    "http-s": "http",
    "https": "http",
    "command-line": "cli",
    "relational-database": "relational-databases",
    "rdbms": "relational-databases",
    "postgres": "postgresql",
    "data-warehouse": "data-warehousing",
    "streaming-data": "streaming-technologies",
    "event-driven-architecture": "event-streaming",
    "messaging-queues": "messaging-systems",
    "message-queues": "messaging-systems",
    "automated-testing": "test-automation",
    "end-to-end-testing": "e2e-testing",
    "ml": "machine-learning",
    "spark": "apache-spark",
    "kafka": "kafka",
    "apache-kafka": "kafka",
    "react-js": "react",
    "reactjs": "react",
    "nextjs": "next.js",
    "vue-js": "vue",
    "vuejs": "vue",
    "node-js": "nodejs",
    "spring-framework": "spring-boot",
    "spring": "spring-boot",
    "k8s": "kubernetes",
    "docker-compose": "docker",
    "go": "golang",
}

# Verified Directed Acyclic Graph (DAG) of foundational -> dependent technical skill prerequisites.
# Direction: (prerequisite_skill, dependent_skill) meaning `prerequisite_skill` is foundational for
# or enables `dependent_skill`.
CURATED_SKILL_PREREQUISITE_DAG: Tuple[Tuple[str, str], ...] = (
    # --- Core Programming Languages -> Frameworks & Ecosystems ---
    ("java", "spring-boot"),
    ("java", "backend-development"),
    ("spring-boot", "backend-development"),
    ("spring-boot", "microservices"),
    ("python", "django"),
    ("python", "fastapi"),
    ("python", "flask"),
    ("python", "backend-development"),
    ("python", "full-stack-development"),
    ("python", "data-pipelines"),
    ("python", "data-manipulation"),
    ("python", "data-engineering"),
    ("python", "automation"),
    ("python", "scikit-learn"),
    ("python", "tensorflow"),
    ("python", "pytorch"),
    ("python", "pandas"),
    ("python", "numpy"),
    ("python", "pytest"),
    ("javascript", "typescript"),
    ("javascript", "react"),
    ("javascript", "vue"),
    ("javascript", "angular"),
    ("javascript", "nodejs"),
    ("javascript", "frontend-development"),
    ("javascript", "full-stack-development"),
    ("javascript", "cypress"),
    ("typescript", "angular"),
    ("typescript", "nestjs"),
    ("typescript", "frontend-development"),
    ("typescript", "cypress"),
    ("nodejs", "express"),
    ("nodejs", "nestjs"),
    ("nodejs", "backend-development"),
    ("golang", "backend-development"),
    ("golang", "microservices"),
    ("c#", ".net"),
    ("ruby", "ruby-on-rails"),
    ("swift", "ios-development"),
    ("kotlin", "android-development"),

    # --- Frontend & Web Architecture ---
    ("html", "css"),
    ("html", "responsive-design"),
    ("html", "frontend-development"),
    ("css", "responsive-design"),
    ("css", "tailwind-css"),
    ("css", "bootstrap"),
    ("css", "frontend-development"),
    ("react", "redux"),
    ("react", "redux-toolkit"),
    ("react", "mobx"),
    ("react", "next.js"),
    ("react", "react-query"),
    ("react", "react-router"),
    ("react", "react-native"),
    ("react", "frontend-development"),
    ("react", "full-stack-development"),
    ("state-management", "redux"),
    ("state-management", "mobx"),
    ("redux", "redux-toolkit"),
    ("rest-api", "api-integration"),
    ("rest-api", "graphql"),
    ("rest-api", "api-testing"),

    # --- Mobile Engineering ---
    ("architectural-patterns", "mvvm"),
    ("architectural-patterns", "mvi"),
    ("clean-code", "testable-code"),
    ("ios-development", "fastlane"),
    ("android-development", "fastlane"),
    ("ci-cd", "fastlane"),
    ("ci-cd", "bitrise"),
    ("hl7", "fhir"),

    # --- Backend, Distributed Systems & Messaging ---
    ("system-design", "distributed-systems"),
    ("distributed-systems", "microservices"),
    ("distributed-systems", "event-streaming"),
    ("event-streaming", "kafka"),
    ("messaging-systems", "kafka"),
    ("messaging-systems", "rabbitmq"),
    ("streaming-technologies", "kafka"),
    ("streaming-technologies", "kinesis"),
    ("real-time-data", "streaming-technologies"),

    # --- Databases & Data Engineering ---
    ("sql", "relational-databases"),
    ("sql", "postgresql"),
    ("sql", "mysql"),
    ("sql", "sqlite"),
    ("sql", "query-optimization"),
    ("sql", "data-warehousing"),
    ("sql", "database-testing"),
    ("relational-databases", "postgresql"),
    ("relational-databases", "mysql"),
    ("postgresql", "query-optimization"),
    ("data-manipulation", "data-pipelines"),
    ("data-pipelines", "data-engineering"),
    ("etl", "data-warehousing"),
    ("elt", "data-warehousing"),
    ("data-warehousing", "redshift"),
    ("data-warehousing", "snowflake"),
    ("big-data", "apache-spark"),
    ("big-data", "hadoop"),
    ("hadoop", "apache-spark"),

    # --- Cloud, DevOps & Containers ---
    ("version-control", "git"),
    ("git", "ci-cd"),
    ("git", "github"),
    ("git", "gitlab"),
    ("git", "github-actions"),
    ("git", "gitlab-ci"),
    ("ci-cd", "gitlab-ci"),
    ("ci-cd", "github-actions"),
    ("ci-cd", "jenkins"),
    ("linux", "cli"),
    ("linux", "bash"),
    ("linux", "docker"),
    ("cli", "bash"),
    ("bash", "automation"),
    ("containerization", "docker"),
    ("docker", "kubernetes"),
    ("kubernetes", "helm"),
    ("iac", "terraform"),
    ("cloud", "aws"),
    ("cloud", "azure"),
    ("cloud", "gcp"),
    ("aws", "ec2"),
    ("aws", "s3"),
    ("aws", "lambda"),
    ("aws", "rds"),
    ("aws", "redshift"),
    ("aws", "kinesis"),
    ("aws", "aws-security"),
    ("aws", "cloud-monitoring"),
    ("observability", "prometheus"),
    ("observability", "datadog"),
    ("observability", "grafana"),
    ("prometheus", "grafana"),

    # --- Data Science, Machine Learning & MLOps ---
    ("mathematics", "statistics"),
    ("mathematics", "machine-learning"),
    ("statistics", "statistical-modeling"),
    ("statistical-modeling", "machine-learning"),
    ("machine-learning", "scikit-learn"),
    ("machine-learning", "tensorflow"),
    ("machine-learning", "pytorch"),
    ("machine-learning", "ml-deployment"),
    ("ml-deployment", "production-ml"),
    ("production-ml", "mlops"),
    ("mlops", "model-versioning"),
    ("mlops", "deployment-pipelines"),
    ("financial-services", "banking"),
    ("financial-services", "financial-regulations"),
    ("banking", "credit-risk"),
    ("banking", "fraud-detection"),

    # --- QA & Test Automation ---
    ("test-automation", "e2e-testing"),
    ("test-automation", "api-testing"),
    ("test-automation", "performance-testing"),
    ("test-automation", "contract-testing"),
    ("e2e-testing", "cypress"),
    ("e2e-testing", "playwright"),
    ("e2e-testing", "selenium"),
    ("api-testing", "postman"),
    ("performance-testing", "k6"),
    ("contract-testing", "pact"),
    ("microservices", "contract-testing"),

    # --- Networking & Cybersecurity ---
    ("network-protocols", "tcp-ip"),
    ("network-protocols", "dns"),
    ("network-protocols", "http"),
    ("tcp-ip", "dns"),
    ("tcp-ip", "http"),
    ("log-analysis", "siem"),
    ("siem", "splunk"),
    ("alert-triage", "incident-escalation"),
    ("compliance", "hipaa"),
    ("data-security-best-practices", "healthcare-security"),
    ("data-security-best-practices", "endpoint-security"),
    ("data-security-best-practices", "aws-security"),
    ("documentation", "technical-writing"),

    # --- Product Management, Agile & Leadership ---
    ("sdlc", "agile"),
    ("agile", "scrum"),
    ("agile", "user-stories"),
    ("scrum", "cspo"),
    ("project-management-tools", "jira"),
    ("agile", "jira"),
    ("requirements-gathering", "user-stories"),
    ("requirements-gathering", "technical-specifications"),
    ("business-analyst", "cbap"),
    ("business-analyst", "requirements-gathering"),
    ("edtech", "lms"),
    ("online-course-platforms", "lms"),
    ("communication", "collaboration"),
    ("communication", "mentoring"),
    ("communication", "client-interaction"),
    ("technical-leadership", "project-leadership"),
    ("technical-leadership", "mentoring"),
)


@dataclass(frozen=True)
class ResolvedDependencyEdge:
    """Validated directed prerequisite edge (source_node_id -> target_node_id)."""

    source_node_id: str
    target_node_id: str
    source_canonical_id: str
    target_canonical_id: str
    weight: float
    dependency_source: str  # 'stage4_llm_reasoning' | 'curated_skill_dag'
    cosine_similarity: Optional[float]


def _lookup_key(canonical_id: str) -> str:
    canon = normalize_canonical_skill(canonical_id)
    return _PREREQ_LOOKUP_ALIASES.get(canon, canon)


def _compute_dependency_weight(
    src_node: PaperAlignedSkillNode,
    dst_node: PaperAlignedSkillNode,
    min_weight: float = 0.1,
    fallback_weight: float = 0.75,
) -> Tuple[float, Optional[float]]:
    """Compute bounded SBERT cosine edge weight in [min_weight, 1.0]."""
    cos = compute_vector_cosine(src_node.embedding_vector, dst_node.embedding_vector)
    if cos is None:
        return round(float(fallback_weight), 6), None
    clamped = max(min_weight, min(1.0, float(cos)))
    return round(clamped, 6), round(float(cos), 6)


def _edge_in_scope(
    src_node: PaperAlignedSkillNode,
    dst_node: PaperAlignedSkillNode,
    scope: DependencyScope,
) -> bool:
    if scope == "all_skills":
        return True
    if scope == "jd_only":
        return src_node.membership in ("job_only", "shared") and dst_node.membership in ("job_only", "shared")
    if scope == "jd_bidirectional":
        # Anchored to JD in EITHER direction:
        # - dst in JD: CV foundational skill -> JD advanced skill (e.g., CV=docker -> JD=kubernetes)
        # - src in JD: JD foundational skill -> CV advanced skill (e.g., JD=docker -> CV=kubernetes,
        #   allowing reverse prerequisite_of edge kubernetes -> docker to inform the job node)
        return (
            dst_node.membership in ("job_only", "shared")
            or src_node.membership in ("job_only", "shared")
        )
    # 'jd_anchored': dependent/target skill MUST be required by JD;
    # prerequisite skill may be in JD (intra-JD dependency) or CV (foundational bridge).
    return dst_node.membership in ("job_only", "shared")


_DAG_FORWARD_ADJ: Optional[Dict[str, Set[str]]] = None


def _get_curated_dag_adjacency() -> Dict[str, Set[str]]:
    global _DAG_FORWARD_ADJ
    if _DAG_FORWARD_ADJ is None:
        adj: Dict[str, Set[str]] = {}
        for raw_u, raw_v in CURATED_SKILL_PREREQUISITE_DAG:
            u = _lookup_key(raw_u)
            v = _lookup_key(raw_v)
            if u and v and u != v:
                adj.setdefault(u, set()).add(v)
        _DAG_FORWARD_ADJ = adj
    return _DAG_FORWARD_ADJ


def _shortest_dag_hops(src_key: str, dst_key: str, max_hops: int = 2) -> int:
    """Return shortest directed path length from src_key to dst_key in the prerequisite DAG, or 0 if unreachable."""
    if not src_key or not dst_key or src_key == dst_key or max_hops < 1:
        return 0
    adj = _get_curated_dag_adjacency()
    frontier: Set[str] = {src_key}
    visited: Set[str] = {src_key}
    for depth in range(1, max_hops + 1):
        next_frontier: Set[str] = set()
        for node in frontier:
            neighbors = adj.get(node)
            if not neighbors:
                continue
            if dst_key in neighbors:
                return depth
            for nb in neighbors:
                if nb not in visited:
                    visited.add(nb)
                    next_frontier.add(nb)
        if not next_frontier:
            break
        frontier = next_frontier
    return 0


def resolve_directed_skill_relation(
    jd_skill_id: str,
    cv_skill_id: str,
    reasoning_results: Optional[Sequence[SkillPairReasoningResult]] = None,
    max_hops: int = 2,
) -> Tuple[DirectedRelationKind, int]:
    """
    Determine directed hierarchical/prerequisite relation between a JD skill and a CV skill:
    - ('cv_supersedes_jd', hops): JD skill is a prerequisite/parent of CV skill
      (e.g., JD='docker', CV='kubernetes' -> candidate holds the more advanced/dependent skill).
    - ('cv_is_prerequisite_only', hops): CV skill is only a prerequisite/foundation of JD skill
      (e.g., JD='kubernetes', CV='docker' -> candidate only holds the foundational skill).
    - ('none', 0): No verified directed hierarchy relation found.
    """
    jd_key = _lookup_key(jd_skill_id)
    cv_key = _lookup_key(cv_skill_id)
    if not jd_key or not cv_key or jd_key == cv_key:
        return "none", 0

    # 1. Stage 4 LLM verified directional reasoning (prerequisite / specialization)
    if reasoning_results:
        for res in reasoning_results:
            if res.graph_relation_status != "eligible" or res.contradiction_detected:
                continue
            if res.identity in ("equivalent", "uncertain"):
                continue
            if res.relationship not in ("prerequisite", "specialization"):
                continue

            key_a = _lookup_key(res.skill_a.skill_id or res.skill_a.name)
            key_b = _lookup_key(res.skill_b.skill_id or res.skill_b.name)
            if {key_a, key_b} != {jd_key, cv_key}:
                continue

            direction = (res.direction or "a_to_b").strip().lower()
            if res.relationship == "prerequisite":
                # prerequisite direction: prereq -> dependent
                prereq_key, dep_key = (key_b, key_a) if direction == "b_to_a" else (key_a, key_b)
                if prereq_key == jd_key and dep_key == cv_key:
                    return "cv_supersedes_jd", 1
                if prereq_key == cv_key and dep_key == jd_key:
                    return "cv_is_prerequisite_only", 1
            elif res.relationship == "specialization":
                # specialization direction: narrow/specialized -> broader parent (a_to_b means A is a specialization of B)
                spec_key, parent_key = (key_b, key_a) if direction == "b_to_a" else (key_a, key_b)
                if spec_key == cv_key and parent_key == jd_key:
                    return "cv_supersedes_jd", 1
                if spec_key == jd_key and parent_key == cv_key:
                    return "cv_is_prerequisite_only", 1

    # 2. Curated Technical Skill Prerequisite DAG (direct or transitive up to max_hops)
    hops_jd_to_cv = _shortest_dag_hops(jd_key, cv_key, max_hops=max_hops)
    if hops_jd_to_cv > 0:
        return "cv_supersedes_jd", hops_jd_to_cv

    hops_cv_to_jd = _shortest_dag_hops(cv_key, jd_key, max_hops=max_hops)
    if hops_cv_to_jd > 0:
        return "cv_is_prerequisite_only", hops_cv_to_jd

    return "none", 0


def _would_create_cycle(
    adjacency: Dict[str, Set[str]],
    src: str,
    dst: str,
) -> bool:
    """Return True if adding directed edge src -> dst creates a cycle."""
    if src == dst:
        return True
    # Check if src is reachable from dst via existing directed edges
    visited: Set[str] = set()
    stack = [dst]
    while stack:
        curr = stack.pop()
        if curr == src:
            return True
        if curr in visited:
            continue
        visited.add(curr)
        stack.extend(adjacency.get(curr, ()))
    return False


def detect_directed_cycles(edges: Sequence[Tuple[str, str]]) -> List[List[str]]:
    """Detect any directed cycles in a list of (src, dst) edges using DFS."""
    adj: Dict[str, List[str]] = {}
    nodes: Set[str] = set()
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        nodes.add(u)
        nodes.add(v)

    state: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=done
    path: List[str] = []
    cycles: List[List[str]] = []

    def dfs(u: str) -> None:
        state[u] = 1
        path.append(u)
        for v in adj.get(u, ()):
            st = state.get(v, 0)
            if st == 1:
                idx = path.index(v)
                cycles.append(path[idx:] + [v])
            elif st == 0:
                dfs(v)
        path.pop()
        state[u] = 2

    for n in sorted(nodes):
        if state.get(n, 0) == 0:
            dfs(n)
    return cycles


def resolve_skill_dependency_edges(
    skill_nodes: Dict[str, PaperAlignedSkillNode],
    reasoning_results: Optional[Sequence[SkillPairReasoningResult]] = None,
    *,
    scope: DependencyScope = "jd_bidirectional",
    use_curated_dag: bool = True,
    use_stage4_reasoning: bool = True,
) -> Tuple[List[ResolvedDependencyEdge], Dict[str, object]]:
    """
    Resolve verified, cycle-free directed `prerequisite_to` edges among active skill nodes.

    Priority order:
    1. Stage 4 LLM reasoning (`relationship == "prerequisite"`, eligible, non-contradicted).
    2. Curated technical skill prerequisite DAG (`CURATED_SKILL_PREREQUISITE_DAG`).

    Guarantees:
    - No self-loops (`src != dst`).
    - No duplicate `(src, dst)` pairs.
    - Strictly acyclic (DAG) via incremental reachability check.
    - Deterministic output ordering.
    """
    if len(skill_nodes) < 2:
        return [], {
            "enabled": True,
            "scope": scope,
            "total_edges": 0,
            "from_stage4_llm": 0,
            "from_curated_dag": 0,
            "cycles_blocked": 0,
            "edges": [],
        }

    # Index nodes by canonical ID, lookup alias key, and occurrence IDs
    nodes_by_lookup: Dict[str, List[PaperAlignedSkillNode]] = {}
    node_by_occ: Dict[str, PaperAlignedSkillNode] = {}
    for node_id in sorted(skill_nodes.keys()):
        node = skill_nodes[node_id]
        keys = {_lookup_key(node.canonical_skill_id)}
        if node.cv_canonical_id:
            keys.add(_lookup_key(node.cv_canonical_id))
        if node.jd_canonical_id:
            keys.add(_lookup_key(node.jd_canonical_id))
        for k in keys:
            if k:
                nodes_by_lookup.setdefault(k, []).append(node)
        for occ in node.cv_occurrence_ids:
            node_by_occ[occ] = node
        for occ in node.jd_occurrence_ids:
            node_by_occ[occ] = node

    resolved: List[ResolvedDependencyEdge] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    adjacency: Dict[str, Set[str]] = {}
    from_stage4 = 0
    from_dag = 0
    cycles_blocked = 0

    def _try_add(
        src_node: PaperAlignedSkillNode,
        dst_node: PaperAlignedSkillNode,
        source_tag: str,
    ) -> bool:
        nonlocal from_stage4, from_dag, cycles_blocked
        if src_node.node_id == dst_node.node_id:
            return False
        if not _edge_in_scope(src_node, dst_node, scope):
            return False
        pair_key = (src_node.node_id, dst_node.node_id)
        if pair_key in seen_pairs:
            return False
        if _would_create_cycle(adjacency, src_node.node_id, dst_node.node_id):
            cycles_blocked += 1
            return False

        weight, cos = _compute_dependency_weight(src_node, dst_node)
        seen_pairs.add(pair_key)
        adjacency.setdefault(src_node.node_id, set()).add(dst_node.node_id)
        resolved.append(
            ResolvedDependencyEdge(
                source_node_id=src_node.node_id,
                target_node_id=dst_node.node_id,
                source_canonical_id=src_node.canonical_skill_id,
                target_canonical_id=dst_node.canonical_skill_id,
                weight=weight,
                dependency_source=source_tag,
                cosine_similarity=cos,
            )
        )
        if source_tag == "stage4_llm_reasoning":
            from_stage4 += 1
        else:
            from_dag += 1
        return True

    # 1. Stage 4 LLM Reasoning prerequisite relations
    if use_stage4_reasoning and reasoning_results:
        for res in reasoning_results:
            if res.relationship != "prerequisite":
                continue
            if res.graph_relation_status != "eligible" or res.contradiction_detected:
                continue
            if res.identity in ("equivalent", "uncertain"):
                continue

            # Resolve endpoints via occurrence IDs first, then canonical lookup
            node_a: Optional[PaperAlignedSkillNode] = None
            node_b: Optional[PaperAlignedSkillNode] = None
            if res.source_occurrence_ids and len(res.source_occurrence_ids) >= 2:
                node_a = node_by_occ.get(res.source_occurrence_ids[0])
                node_b = node_by_occ.get(res.source_occurrence_ids[1])

            if node_a is None:
                key_a = _lookup_key(res.skill_a.skill_id or res.skill_a.name)
                cands_a = nodes_by_lookup.get(key_a, [])
                node_a = cands_a[0] if cands_a else None
            if node_b is None:
                key_b = _lookup_key(res.skill_b.skill_id or res.skill_b.name)
                cands_b = nodes_by_lookup.get(key_b, [])
                node_b = cands_b[0] if cands_b else None

            if node_a is None or node_b is None:
                continue

            direction = (res.direction or "a_to_b").strip().lower()
            if direction == "b_to_a":
                _try_add(node_b, node_a, "stage4_llm_reasoning")
            else:
                _try_add(node_a, node_b, "stage4_llm_reasoning")

    # 2. Curated Technical Skill Prerequisite DAG
    if use_curated_dag:
        for raw_prereq, raw_target in CURATED_SKILL_PREREQUISITE_DAG:
            pk = _lookup_key(raw_prereq)
            tk = _lookup_key(raw_target)
            src_nodes = nodes_by_lookup.get(pk)
            dst_nodes = nodes_by_lookup.get(tk)
            if not src_nodes or not dst_nodes:
                continue
            for sn in src_nodes:
                for dn in dst_nodes:
                    _try_add(sn, dn, "curated_skill_dag")

    # Deterministic ordering
    resolved.sort(key=lambda e: (e.source_node_id, e.target_node_id))

    audit = {
        "enabled": True,
        "scope": scope,
        "total_edges": len(resolved),
        "from_stage4_llm": from_stage4,
        "from_curated_dag": from_dag,
        "cycles_blocked": cycles_blocked,
        "edges": [
            {
                "source_node_id": e.source_node_id,
                "target_node_id": e.target_node_id,
                "source_canonical_id": e.source_canonical_id,
                "target_canonical_id": e.target_canonical_id,
                "weight": e.weight,
                "cosine_similarity": e.cosine_similarity,
                "dependency_source": e.dependency_source,
            }
            for e in resolved
        ],
    }
    return resolved, audit
