"""
Stage C Skill Clustering Service.

Non-destructive near-duplicate explicit skill clustering using deterministic rules:
- R1 Normalization: case, plural, hyphen/space, development/design suffix variants.
- R2 Tool + Generic Suffix Containment: "Redis caching" -> member of "Redis" (generic noun list).
- R3 Known Alias Table: explicit mapping (e.g. Apache Kafka ~ Kafka, JUnit 5 ~ JUnit, Postgres ~ PostgreSQL).
- Hard Blockers Denylist: strict domain barriers that must never merge (Java/JS, Docker/K8s, SQL/NoSQL, etc.).
- Candidate Topic Groups: reports abstract concepts grouped by topic without merging them.
- Certification Hints: reports generic vs specific certification pairs without merging them.
"""
from dataclasses import dataclass
import re
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from matching_cv.app.schemas.skill_extraction import (
    CertificationHintPair,
    Evidence,
    ExtractedSkill,
    SkillCluster,
    TopicGroupHint,
)


# -----------------------------------------------------------------------------
# R2: Generic Tool Suffixes List
# -----------------------------------------------------------------------------
GENERIC_TOOL_SUFFIXES: List[str] = [
    "caching",
    "cache",
    "pipeline",
    "pipelines",
    "auth",
    "authentication",
    "authorization",
    "tests",
    "testing",
    "test",
    "script",
    "scripts",
    "scripting",
    "cluster",
    "clusters",
    "clustering",
    "server",
    "servers",
    "service",
    "services",
    "integration",
    "integrations",
    "management",
    "configuration",
    "deploy",
    "deployment",
    "deployments",
    "monitoring",
    "queries",
    "query",
    "database",
    "db",
    "automation",
    "container",
    "containers",
    "engine",
    "framework",
    "library",
    "tool",
    "tools",
    "workflow",
    "workflows",
    "broker",
    "queue",
    "api",
    "apis",
]

GENERIC_TOOL_SUFFIXES_SET: Set[str] = set(GENERIC_TOOL_SUFFIXES)


# -----------------------------------------------------------------------------
# R3: Known Alias Table
# -----------------------------------------------------------------------------
KNOWN_ALIAS_TABLE: List[Dict[str, Any]] = [
    {
        "canonical_id": "kafka",
        "canonical_label": "Apache Kafka",
        "aliases": ["kafka", "apache kafka", "apache-kafka"],
    },
    {
        "canonical_id": "postgresql",
        "canonical_label": "PostgreSQL",
        "aliases": ["postgres", "postgresql", "postgre sql", "psql"],
    },
    {
        "canonical_id": "junit",
        "canonical_label": "JUnit",
        "aliases": ["junit", "junit 5", "junit5", "junit 4", "junit4"],
    },
    {
        "canonical_id": "nodejs",
        "canonical_label": "Node.js",
        "aliases": ["nodejs", "node.js", "node js", "node"],
    },
    {
        "canonical_id": "golang",
        "canonical_label": "Go",
        "aliases": ["go", "golang", "go programming", "go language"],
    },
    {
        "canonical_id": "k8s",
        "canonical_label": "Kubernetes",
        "aliases": ["kubernetes", "k8s"],
    },
    {
        "canonical_id": "aws",
        "canonical_label": "Amazon Web Services (AWS)",
        "aliases": ["aws", "amazon web services", "amazon web service"],
    },
    {
        "canonical_id": "gcp",
        "canonical_label": "Google Cloud Platform (GCP)",
        "aliases": ["gcp", "google cloud platform", "google cloud"],
    },
    {
        "canonical_id": "github-actions",
        "canonical_label": "GitHub Actions",
        "aliases": ["github actions", "github action", "gh actions"],
    },
    {
        "canonical_id": "fastapi",
        "canonical_label": "FastAPI",
        "aliases": ["fastapi", "fast api"],
    },
    {
        "canonical_id": "react",
        "canonical_label": "React",
        "aliases": ["react", "react.js", "reactjs", "react js"],
    },
    {
        "canonical_id": "docker",
        "canonical_label": "Docker",
        "aliases": ["docker", "docker compose", "docker-compose"],
    },
    {
        "canonical_id": "system-design",
        "canonical_label": "System Design",
        "aliases": [
            "system design",
            "system architecture",
            "full-stack architecture",
            "full stack architecture",
            "software architecture",
        ],
    },
]


# -----------------------------------------------------------------------------
# Hard Blockers Denylist (Must NEVER merge)
# -----------------------------------------------------------------------------
HARD_BLOCKER_PAIRS: Set[FrozenSet[str]] = {
    # 1. Java / JavaScript
    frozenset({"java", "javascript"}),
    frozenset({"java", "js"}),
    # 2. React / React Native
    frozenset({"react", "react native"}),
    frozenset({"react.js", "react native"}),
    frozenset({"reactjs", "react native"}),
    # 3. C / C++ / C#
    frozenset({"c", "cpp"}),
    frozenset({"c", "c++"}),
    frozenset({"c", "c#"}),
    frozenset({"c", "c-sharp"}),
    frozenset({"c", "csharp"}),
    frozenset({"c++", "c#"}),
    frozenset({"cpp", "c#"}),
    frozenset({"cpp", "c-sharp"}),
    frozenset({"cpp", "csharp"}),
    # 4. Docker / Kubernetes
    frozenset({"docker", "kubernetes"}),
    frozenset({"docker", "k8s"}),
    # 5. SQL / NoSQL
    frozenset({"sql", "nosql"}),
    # 6. MySQL / PostgreSQL
    frozenset({"mysql", "postgresql"}),
    frozenset({"mysql", "postgres"}),
    # 7. JUnit / Mockito
    frozenset({"junit", "mockito"}),
    frozenset({"junit 5", "mockito"}),
    # 8. AWS / GCP
    frozenset({"aws", "gcp"}),
    frozenset({"amazon web services", "google cloud platform"}),
    # 9. Jenkins / GitHub Actions
    frozenset({"jenkins", "github actions"}),
    frozenset({"jenkins", "github-actions"}),
    # 10. Named message brokers
    frozenset({"kafka", "rabbitmq"}),
    frozenset({"apache kafka", "rabbitmq"}),
    # 11-15. Additional 5 custom domain blockers
    frozenset({"python", "cython"}),
    frozenset({"graphql", "rest"}),
    frozenset({"graphql api", "rest api"}),
    frozenset({"graphql apis", "rest apis"}),
    frozenset({"vue", "angular"}),
    frozenset({"tcp", "udp"}),
    frozenset({"swift", "objective-c"}),
    frozenset({"swift", "objective c"}),
}

NAMED_DATABASES: Set[str] = {
    "mysql",
    "postgresql",
    "postgres",
    "redis",
    "mongodb",
    "cassandra",
    "dynamodb",
    "elasticsearch",
    "oracle",
    "sqlite",
    "mariadb",
    "neo4j",
    "couchbase",
}

NAMED_MESSAGE_BROKERS: Set[str] = {
    "kafka",
    "apache-kafka",
    "rabbitmq",
    "activemq",
    "pulsar",
    "sqs",
    "sns",
    "nats",
}


# -----------------------------------------------------------------------------
# Candidate Topic Groups (Reported in topic_group_hint, NEVER merged)
# -----------------------------------------------------------------------------
CANDIDATE_TOPIC_GROUPS: Dict[str, List[str]] = {
    "Database & Query Performance": [
        "indexing",
        "query optimization",
        "query performance",
        "query tuning",
        "database indexing",
        "relational databases",
        "relational database",
        "data modeling",
        "sql optimization",
        "schema design",
        "database optimization",
    ],
    "Testing & Quality Assurance": [
        "unit testing",
        "integration testing",
        "test automation",
        "end-to-end testing",
        "e2e testing",
        "regression testing",
        "test coverage",
        "testing & tooling",
        "testing and tooling",
    ],
    "CI/CD & Deployment Automation": [
        "continuous integration",
        "continuous deployment",
        "ci/cd",
        "cicd",
        "pipeline automation",
        "deployment automation",
        "infrastructure as code",
        "build automation",
    ],
    "Distributed Systems & Architecture": [
        "microservices architecture",
        "microservice architecture",
        "distributed systems",
        "service mesh",
        "event-driven architecture",
        "system decoupling",
        "fault tolerance",
    ],
}


# -----------------------------------------------------------------------------
# Result Container
# -----------------------------------------------------------------------------
@dataclass
class SkillClusteringResult:
    clusters: List[SkillCluster]
    topic_group_hint: List[TopicGroupHint]
    certification_hint_pairs: List[CertificationHintPair]


class SkillClusteringService:
    """Service implementing Stage C deterministic skill clustering."""

    @staticmethod
    def normalize_r1(label: str) -> str:
        """
        R1 Normalization:
        - Lowercase
        - Punctuation to space (hyphens, dots, underscores, slashes)
        - Strip 'development', 'design', 'designing', 'dev' suffix variants
        - Normalize simple token plurals (apis -> api, pipelines -> pipeline)
        """
        s = label.strip().casefold()
        s = re.sub(r"[\-_\.\/]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()

        # Strip suffix variants if length allows (keep 'design' unless preceded by 'api')
        for suffix in [" development", " designing", " dev"]:
            if s.endswith(suffix) and len(s) > len(suffix) + 2:
                s = s[: -len(suffix)].strip()
                break
        if s.endswith(" api design") or s == "api design":
            s = s[: -len(" design")].strip()

        # Token plural normalization
        tokens = s.split()
        norm_tokens = []
        keep_s_words = {
            "postgres",
            "kubernetes",
            "redis",
            "express",
            "aws",
            "gcp",
            "nodejs",
            "jenkins",
            "rails",
            "pandas",
            "c++",
            "c#",
        }
        for t in tokens:
            if t in keep_s_words:
                norm_tokens.append(t)
            elif t.endswith("ies") and len(t) > 4:
                norm_tokens.append(t[:-3] + "y")
            elif (t.endswith("sses") or t.endswith("xes") or t.endswith("shes") or t.endswith("ches")) and len(t) > 4:
                norm_tokens.append(t[:-2])
            elif t.endswith("s") and len(t) > 3 and not t.endswith("ss") and t not in keep_s_words:
                norm_tokens.append(t[:-1])
            else:
                norm_tokens.append(t)

        return " ".join(norm_tokens)

    @classmethod
    def check_r3_alias(
        cls, skill_a: ExtractedSkill, skill_b: ExtractedSkill
    ) -> Optional[Tuple[str, str, str]]:
        """
        Check if both skills match known aliases of the same canonical entity.
        Returns (canonical_id, canonical_label, rule) or None.
        """
        slug_a = skill_a.skill_id.casefold()
        slug_b = skill_b.skill_id.casefold()
        lbl_a = skill_a.label.casefold()
        lbl_b = skill_b.label.casefold()

        for entry in KNOWN_ALIAS_TABLE:
            aliases = [a.casefold() for a in entry["aliases"]]
            match_a = any(slug_a == a or lbl_a == a or cls.normalize_r1(skill_a.label) == cls.normalize_r1(a) for a in aliases)
            match_b = any(slug_b == a or lbl_b == a or cls.normalize_r1(skill_b.label) == cls.normalize_r1(a) for a in aliases)
            if match_a and match_b:
                return (entry["canonical_id"], entry["canonical_label"], "R3_known_alias")

        return None

    @classmethod
    def check_r2_containment(
        cls, skill_a: ExtractedSkill, skill_b: ExtractedSkill
    ) -> Optional[Tuple[ExtractedSkill, ExtractedSkill]]:
        """
        Check R2 tool + generic suffix containment:
        Returns (canonical_shorter_skill, member_longer_skill) if one is the shorter
        tool and the other is the shorter tool plus generic noun suffix(es).
        """
        norm_a = cls.normalize_r1(skill_a.label)
        norm_b = cls.normalize_r1(skill_b.label)

        if norm_a == norm_b:
            return None

        def _is_valid_suffix_token(w: str) -> bool:
            return w in GENERIC_TOOL_SUFFIXES_SET or bool(re.match(r"^v?\d+(?:\.\d+)*$", w))

        # Check if B is A + generic/version suffix
        if norm_b.startswith(norm_a + " "):
            remainder = norm_b[len(norm_a) :].strip().split()
            if remainder and all(_is_valid_suffix_token(w) for w in remainder):
                return (skill_a, skill_b)

        # Check if A is B + generic/version suffix
        if norm_a.startswith(norm_b + " "):
            remainder = norm_a[len(norm_b) :].strip().split()
            if remainder and all(_is_valid_suffix_token(w) for w in remainder):
                return (skill_b, skill_a)

        return None

    @classmethod
    def is_blocked_merge(cls, skill_a: ExtractedSkill, skill_b: ExtractedSkill) -> bool:
        """
        Check whether merging skill_a and skill_b is strictly prohibited by domain denylists.
        """
        norm_a = cls.normalize_r1(skill_a.label)
        norm_b = cls.normalize_r1(skill_b.label)
        slug_a = skill_a.skill_id.casefold()
        slug_b = skill_b.skill_id.casefold()

        # 1. Direct pair in HARD_BLOCKER_PAIRS
        if frozenset({norm_a, norm_b}) in HARD_BLOCKER_PAIRS:
            return True
        if frozenset({slug_a, slug_b}) in HARD_BLOCKER_PAIRS:
            return True
        if frozenset({skill_a.label.casefold(), skill_b.label.casefold()}) in HARD_BLOCKER_PAIRS:
            return True

        # Check token sets for exact language / tool clash
        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())
        for blocked_pair in HARD_BLOCKER_PAIRS:
            pair_list = list(blocked_pair)
            if len(pair_list) == 2:
                p1, p2 = pair_list[0], pair_list[1]
                if (p1 in tokens_a and p2 in tokens_b) or (p2 in tokens_a and p1 in tokens_b):
                    return True

        # 2. Named databases clash (unless they are the same database or known aliases)
        db_a = {db for db in NAMED_DATABASES if db in tokens_a or db == slug_a}
        db_b = {db for db in NAMED_DATABASES if db in tokens_b or db == slug_b}
        if db_a and db_b and db_a != db_b:
            alias_match = cls.check_r3_alias(skill_a, skill_b)
            if not alias_match:
                return True

        # 3. Named message brokers clash (unless they are the same broker or known aliases)
        mb_a = {mb for mb in NAMED_MESSAGE_BROKERS if mb in tokens_a or mb == slug_a}
        mb_b = {mb for mb in NAMED_MESSAGE_BROKERS if mb in tokens_b or mb == slug_b}
        if mb_a and mb_b and mb_a != mb_b:
            alias_match = cls.check_r3_alias(skill_a, skill_b)
            if not alias_match:
                return True

        # 4. Certifications: any two different certifications must NEVER merge
        is_cert_a = (skill_a.category == "Certification") or (getattr(skill_a, "kind", None) == "certification") or ("certif" in norm_a)
        is_cert_b = (skill_b.category == "Certification") or (getattr(skill_b, "kind", None) == "certification") or ("certif" in norm_b)
        if is_cert_a and is_cert_b:
            if norm_a != norm_b:
                return True

        # 5. Certification generic vs specific
        if is_cert_a or is_cert_b:
            vendors = ["aws", "gcp", "azure", "kubernetes", "oracle", "cisco", "java"]
            for v in vendors:
                is_gen_a = bool(re.search(rf"\b{v}\s+(certification|certified)\b", norm_a))
                is_gen_b = bool(re.search(rf"\b{v}\s+(certification|certified)\b", norm_b))
                if (is_gen_a and not is_gen_b and v in norm_b) or (is_gen_b and not is_gen_a and v in norm_a):
                    return True

        return False

    @classmethod
    def detect_topic_group_hints(cls, skills: List[ExtractedSkill]) -> List[TopicGroupHint]:
        """
        Detect candidate topic groups among extracted skills without merging them.
        """
        hints: List[TopicGroupHint] = []

        for topic_name, terms in CANDIDATE_TOPIC_GROUPS.items():
            member_ids = []
            member_lbls = []
            term_norms = {cls.normalize_r1(t) for t in terms}

            for s in skills:
                norm_lbl = cls.normalize_r1(s.label)
                slug = s.skill_id.casefold().replace("-", " ")
                if norm_lbl in term_norms or slug in term_norms or any(t == norm_lbl for t in term_norms):
                    if s.skill_id not in member_ids:
                        member_ids.append(s.skill_id)
                        member_lbls.append(s.label)

            if len(member_ids) > 1:
                hints.append(
                    TopicGroupHint(
                        topic=topic_name,
                        member_skill_ids=member_ids,
                        member_labels=member_lbls,
                    )
                )

        return hints

    @classmethod
    def detect_certification_hints(cls, skills: List[ExtractedSkill]) -> List[CertificationHintPair]:
        """
        Detect generic vs specific certification co-occurrences without merging them.
        """
        pairs: List[CertificationHintPair] = []
        vendors = ["aws", "gcp", "azure", "kubernetes", "oracle", "cisco", "java"]

        for v in vendors:
            generic_skill = None
            specific_skills = []

            for s in skills:
                norm = cls.normalize_r1(s.label)
                is_cert = (s.category == "Certification") or (getattr(s, "kind", None) == "certification") or ("certif" in norm)
                if not is_cert:
                    continue

                if re.search(rf"^{v}\s+(certification|certified)$", norm):
                    generic_skill = s
                elif v in norm:
                    specific_skills.append(s)

            if generic_skill and specific_skills:
                for spec in specific_skills:
                    pairs.append(
                        CertificationHintPair(
                            generic_skill_id=generic_skill.skill_id,
                            generic_label=generic_skill.label,
                            specific_skill_id=spec.skill_id,
                            specific_label=spec.label,
                            hint=f"Vendor-generic certification '{generic_skill.label}' co-occurs with specific credential '{spec.label}'",
                        )
                    )

        return pairs

    @classmethod
    def cluster_skills(cls, skills: List[ExtractedSkill]) -> SkillClusteringResult:
        """
        Main entrypoint: Cluster explicit skills deterministically without deleting any skill or evidence.
        """
        n = len(skills)
        if n == 0:
            return SkillClusteringResult(clusters=[], topic_group_hint=[], certification_hint_pairs=[])

        # Disjoint-set data structure
        parent = list(range(n))
        rule_map: Dict[Tuple[int, int], str] = {}
        canonical_override: Dict[int, Tuple[str, str]] = {}

        def find(i: int) -> int:
            path = []
            while parent[i] != i:
                path.append(i)
                i = parent[i]
            for node in path:
                parent[node] = i
            return i

        def union(i: int, j: int, rule: str) -> None:
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_j] = root_i
                rule_map[(min(root_i, root_j), max(root_i, root_j))] = rule

        # Pairwise comparison
        for i in range(n):
            for j in range(i + 1, n):
                s_i = skills[i]
                s_j = skills[j]

                # 1. Denylist check
                if cls.is_blocked_merge(s_i, s_j):
                    continue

                # 2. R3 Known Alias check
                alias_match = cls.check_r3_alias(s_i, s_j)
                if alias_match:
                    canon_id, canon_label, rule = alias_match
                    root = find(i)
                    canonical_override[root] = (canon_id, canon_label)
                    union(i, j, rule)
                    continue

                # 3. R1 Normalization check
                norm_i = cls.normalize_r1(s_i.label)
                norm_j = cls.normalize_r1(s_j.label)
                if norm_i == norm_j:
                    union(i, j, "R1_normalization")
                    continue

                # 4. R2 Tool + Generic Suffix containment
                r2_match = cls.check_r2_containment(s_i, s_j)
                if r2_match:
                    canon_s, member_s = r2_match
                    union(i, j, "R2_tool_generic_suffix")
                    root = find(i)
                    canonical_override[root] = (canon_s.skill_id, canon_s.label)
                    continue

        # Group skills into components
        components: Dict[int, List[int]] = {}
        for i in range(n):
            root = find(i)
            components.setdefault(root, []).append(i)

        clusters: List[SkillCluster] = []

        for root, member_indices in components.items():
            members = [skills[idx] for idx in member_indices]

            # Merge rule determination
            if len(members) == 1:
                merge_rule = "singleton"
                canonical_skill = members[0]
                canon_id = canonical_skill.skill_id
                canon_label = canonical_skill.label
            else:
                # Find the applied rule
                merge_rule = "R1_normalization"
                for i_idx in member_indices:
                    for j_idx in member_indices:
                        if (min(i_idx, j_idx), max(i_idx, j_idx)) in rule_map:
                            merge_rule = rule_map[(min(i_idx, j_idx), max(i_idx, j_idx))]
                            break

                # Canonical selection
                if root in canonical_override:
                    canon_id, canon_label = canonical_override[root]
                else:
                    # Prefer shorter / title-case label
                    sorted_by_pref = sorted(members, key=lambda s: (len(s.label), s.skill_id))
                    canonical_skill = sorted_by_pref[0]
                    canon_id = canonical_skill.skill_id
                    canon_label = canonical_skill.label

            # Collect member IDs and surface forms
            member_skill_ids = sorted(list({s.skill_id for s in members}))
            surface_forms = set()
            for s in members:
                if getattr(s, "surface_forms", None):
                    surface_forms.update(s.surface_forms)
                else:
                    surface_forms.add(s.label)
            member_surface_forms = sorted(list(surface_forms))

            # Concatenate / preserve all evidences
            all_evidences: List[Evidence] = []
            for s in members:
                if s.evidences:
                    all_evidences.extend(s.evidences)

            clusters.append(
                SkillCluster(
                    cluster_id=f"cluster-{canon_id}",
                    canonical_skill_id=canon_id,
                    canonical_label=canon_label,
                    member_skill_ids=member_skill_ids,
                    member_surface_forms=member_surface_forms,
                    merge_rule=merge_rule,
                    evidences=all_evidences,
                )
            )

        # Deterministic sort by cluster_id
        clusters.sort(key=lambda c: c.cluster_id)

        topic_hints = cls.detect_topic_group_hints(skills)
        cert_hints = cls.detect_certification_hints(skills)

        return SkillClusteringResult(
            clusters=clusters,
            topic_group_hint=topic_hints,
            certification_hint_pairs=cert_hints,
        )


skill_clustering_service = SkillClusteringService()
