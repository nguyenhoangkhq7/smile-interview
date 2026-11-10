"""Semantic Requirement Alignment and Candidate Fulfillment Engine.

Reference:
- GNN-ROOT-FIX-02 (Graph Semantic Alignment & Feature Consistency Hardening)
- Baghbanzadeh & Wu (ICIT 2025)

Provides:
1. Typed Semantic Alignment Contract (SemanticAlignmentRecord).
2. Deterministic Compound Requirement Decomposer (Conjunctive AND, Disjunctive OR, Hierarchical).
3. Candidate Requirement Fulfillment Engine (Directional Specialization, Traceable Evidence).
4. Semantic Graph Transformer (Policy B Graph Candidate vs Policy A Legacy Baseline).
"""
from __future__ import annotations

import copy
import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field

from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.schemas import SkillInputItem


class SemanticRelationType(str, Enum):
    """Categorical classification of skill relationship."""
    EQUIVALENT = "equivalent"
    ALIAS = "alias"
    SPECIALIZATION = "specialization"
    COMPOUND = "compound"
    ALTERNATIVE = "alternative"
    PREREQUISITE = "prerequisite"
    RELATED = "related"
    UNRELATED = "unrelated"
    UNCERTAIN = "uncertain"


class RelationDirection(str, Enum):
    """Directionality of relationship."""
    CV_SPECIALIZES_JD = "cv_specializes_jd"
    JD_SPECIALIZES_CV = "jd_specializes_cv"
    BIDIRECTIONAL = "bidirectional"
    NONE = "none"


class FulfillmentStatus(str, Enum):
    """Requirement fulfillment outcome for candidate."""
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNCERTAIN = "UNCERTAIN"
    EXCLUDED = "EXCLUDED"


class VerificationStatus(str, Enum):
    """Integrity verification status."""
    VERIFIED = "VERIFIED"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


class RequirementOperator(str, Enum):
    """Logical requirement grouping structure."""
    SOLO = "SOLO"
    AND = "AND"
    OR = "OR"
    HIERARCHICAL = "HIERARCHICAL"


class SemanticAlignmentRecord(BaseModel):
    """Typed semantic alignment contract between a JD requirement and CV evidence."""

    jd_skill_id: str = Field(..., description="Normalized canonical identifier of the JD requirement")
    cv_skill_id: Optional[str] = Field(default=None, description="Matched canonical CV skill identifier if present")
    relation_type: SemanticRelationType = Field(..., description="Classified semantic relationship")
    direction: RelationDirection = Field(default=RelationDirection.NONE, description="Direction of relationship")
    fulfillment_status: FulfillmentStatus = Field(..., description="Evaluated requirement fulfillment state")
    evidence: List[str] = Field(default_factory=list, description="Verbatim source sentence evidence grounding the match")
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED, description="Verification state")
    reasoning: str = Field(..., description="Checkable explanation justifying fulfillment determination")
    retrieval_cosine: Optional[float] = Field(default=None, description="Stage 3 SBERT cosine similarity (diagnostic metadata only)")
    is_compound_member: bool = Field(default=False, description="True if member of an AND/OR group")
    parent_requirement_id: Optional[str] = Field(default=None, description="Parent requirement ID if decomposed")


class RequirementGroupInfo(BaseModel):
    """Structured decomposition metadata for a single JD requirement."""

    requirement_id: str
    operator: RequirementOperator = RequirementOperator.SOLO
    original_skill_id: str
    original_surface_name: str
    members: List[str] = Field(default_factory=list, description="Canonical skill IDs of constituent atomic requirements")
    member_display_names: List[str] = Field(default_factory=list)
    evidence_sentences: List[str] = Field(default_factory=list)
    is_compound: bool = False
    confidence: float = 1.0


class RequirementMemberFulfillment(BaseModel):
    """Fulfillment evaluation for an atomic member within a requirement group."""

    jd_skill_id: str
    display_name: str
    matched_cv_skill_id: Optional[str] = None
    relation_type: SemanticRelationType
    direction: RelationDirection
    fulfillment_status: FulfillmentStatus
    evidence: List[str] = Field(default_factory=list)
    reasoning: str


class RequirementGroupFulfillment(BaseModel):
    """Comprehensive candidate fulfillment evaluation for a JD requirement."""

    requirement_id: str
    operator: RequirementOperator
    original_surface_name: str
    members: List[RequirementMemberFulfillment] = Field(default_factory=list)
    group_fulfillment_status: FulfillmentStatus
    satisfaction_score: float = Field(..., ge=0.0, le=1.0, description="Continuously bounded satisfaction [0.0, 1.0]")
    evidence: List[str] = Field(default_factory=list)
    diagnostic_summary: str


# -----------------------------------------------------------------------------
# Atomic Product Names (Never Split by Connectives)
# -----------------------------------------------------------------------------
ATOMIC_PRODUCT_NAMES: Set[str] = {
    "react-query",
    "spring-boot",
    "google-cloud",
    "github-actions",
    "nextjs",
    "next.js",
    "vuejs",
    "vue.js",
    "nodejs",
    "node.js",
    "tailwind-css",
    "power-bi",
    "react-native",
    "ci-cd",
    "apollo-graphql",
    "apache-kafka",
    "apache-spark",
    "apache-airflow",
    "apache-hadoop",
    "redux-toolkit",
    "react-router",
    "ruby-on-rails",
    "asp.net",
    "react-testing-library",
    "tcp-ip",
    "pl-sql",
}

# -----------------------------------------------------------------------------
# Hierarchical Specialization Knowledge Base
# parent_canonical_id -> set of child canonical_ids that specialize the parent
# -----------------------------------------------------------------------------
HIERARCHICAL_SPECIALIZATIONS: Dict[str, Set[str]] = {
    "aws": {
        "ec2",
        "s3",
        "aws-lambda",
        "lambda",
        "dynamodb",
        "rds",
        "sqs",
        "sns",
        "ecs",
        "eks",
        "cloudformation",
        "iam",
        "route53",
    },
    "gcp": {
        "bigquery",
        "cloud-storage",
        "cloud-functions",
        "gke",
        "cloud-run",
        "pubsub",
    },
    "relational-databases": {
        "postgresql",
        "mysql",
        "sqlite",
        "oracle-db",
        "sql-server",
        "mariadb",
        "sql",
    },
    "relational-schemas": {
        "postgresql",
        "mysql",
        "sqlite",
        "oracle-db",
        "sql-server",
        "database-schema-design",
    },
    "junit": {
        "junit-5",
        "junit-4",
    },
    "automated-testing": {
        "unit-testing",
        "e2e-testing",
        "integration-testing",
        "jest",
        "playwright",
        "cypress",
        "selenium",
        "junit",
        "junit-5",
        "pytest",
        "mocha",
    },
    "unit-testing": {
        "jest",
        "junit",
        "junit-5",
        "pytest",
        "mocha",
    },
    "e2e-testing": {
        "playwright",
        "cypress",
        "selenium",
    },
    "javascript": {
        "typescript",  # TypeScript is a typed superset/specialization of JavaScript
    },
    "sql": {
        "postgresql",
        "mysql",
        "sqlite",
        "oracle-db",
        "sql-server",
        "pl-sql",
        "t-sql",
    },
}


class CompoundRequirementDecomposer:
    """Deterministic, provenance-preserving compound requirement decomposer."""

    @classmethod
    def decompose(
        cls,
        skill_id: str,
        surface_name: str,
        evidence_sentences: Optional[List[str]] = None,
        extraction_type: str = "explicit",
    ) -> RequirementGroupInfo:
        """Decompose a single requirement entity into an atomic or grouped structure."""
        canon = normalize_canonical_skill(skill_id or surface_name)
        evs = evidence_sentences or []

        # 1. Guardrail: Atomic product names must never be split
        if canon in ATOMIC_PRODUCT_NAMES or surface_name.strip().lower() in ATOMIC_PRODUCT_NAMES:
            return RequirementGroupInfo(
                requirement_id=canon,
                operator=RequirementOperator.SOLO,
                original_skill_id=canon,
                original_surface_name=surface_name,
                members=[canon],
                member_display_names=[surface_name],
                evidence_sentences=evs,
                is_compound=False,
                confidence=1.0,
            )

        # 2. Check for Specific Known Compound Slugs first (domain-verified splits)
        known_compounds = {
            "react-typescript-application": (["react", "typescript"], ["React", "TypeScript"]),
            "unit-and-end-to-end-tests": (["unit-testing", "e2e-testing"], ["Unit Testing", "E2E Testing"]),
            "unit-and-integration-tests": (["unit-testing", "integration-testing"], ["Unit Testing", "Integration Testing"]),
            "java-spring-boot-stack": (["java", "spring-boot"], ["Java", "Spring Boot"]),
            "java-and-spring-boot": (["java", "spring-boot"], ["Java", "Spring Boot"]),
            "node.js-express-backend": (["nodejs", "express"], ["Node.js", "Express"]),
            "node.js-express": (["nodejs", "express"], ["Node.js", "Express"]),
            "node.js-nestjs": (["nodejs", "nestjs"], ["Node.js", "NestJS"]),
            "react-next.js": (["react", "nextjs"], ["React", "Next.js"]),
            "authentication-and-authorization": (["authentication", "authorization"], ["Authentication", "Authorization"]),
            "postgresql-and-query-optimization": (["postgresql", "query-optimization"], ["PostgreSQL", "Query Optimization"]),
            "ec2-s3-lambda": (["ec2", "s3", "aws-lambda"], ["EC2", "S3", "AWS Lambda"]),
            "aws-ec2-s3-lambda": (["aws", "ec2", "s3", "aws-lambda"], ["AWS", "EC2", "S3", "AWS Lambda"]),
            "graphql-apollo": (["graphql", "apollo-graphql"], ["GraphQL", "Apollo GraphQL"]),
        }
        if canon in known_compounds:
            mems, names = known_compounds[canon]
            return RequirementGroupInfo(
                requirement_id=canon,
                operator=RequirementOperator.AND,
                original_skill_id=canon,
                original_surface_name=surface_name,
                members=mems,
                member_display_names=names,
                evidence_sentences=evs,
                is_compound=True,
                confidence=0.98,
            )

        surf_lower = surface_name.strip().lower()
        slug_lower = canon.lower()

        # 3. Check for Disjunctive OR requirement
        # e.g., 'PostgreSQL or MySQL', 'Express or NestJS', 'GraphQL or REST', 'Kafka or RabbitMQ'
        has_or = bool(
            re.search(r"\b(?:or|either\s+[\w\s\-/+]+\s+or)\b", surf_lower)
            or "-or-" in slug_lower
            or " / " in surface_name
        )
        has_and = bool(
            re.search(r"\b(?:and|both\s+[\w\s\-/+]+\s+and)\b", surf_lower)
            or "-and-" in slug_lower
            or " + " in surface_name
            or " & " in surface_name
            or ("/" in surface_name and not has_or and not canon in ATOMIC_PRODUCT_NAMES)
        )

        if has_or and not has_and:
            members, names = cls._split_or(surface_name, canon)
            if len(members) > 1:
                return RequirementGroupInfo(
                    requirement_id=canon,
                    operator=RequirementOperator.OR,
                    original_skill_id=canon,
                    original_surface_name=surface_name,
                    members=members,
                    member_display_names=names,
                    evidence_sentences=evs,
                    is_compound=True,
                    confidence=0.95,
                )

        # 4. Check for Conjunctive AND requirement
        # e.g., 'React + TypeScript application', 'Unit and End-to-End Tests', 'Java/Spring Boot stack'
        if has_and or ("-" in canon and any(k in canon for k in ["-and-", "-plus-"])):
            members, names = cls._split_and(surface_name, canon)
            if len(members) > 1:
                return RequirementGroupInfo(
                    requirement_id=canon,
                    operator=RequirementOperator.AND,
                    original_skill_id=canon,
                    original_surface_name=surface_name,
                    members=members,
                    member_display_names=names,
                    evidence_sentences=evs,
                    is_compound=True,
                    confidence=0.95,
                )

        # 5. Default SOLO requirement
        return RequirementGroupInfo(
            requirement_id=canon,
            operator=RequirementOperator.SOLO,
            original_skill_id=canon,
            original_surface_name=surface_name,
            members=[canon],
            member_display_names=[surface_name],
            evidence_sentences=evs,
            is_compound=False,
            confidence=1.0,
        )

    @classmethod
    def _split_or(cls, surface_name: str, canon: str) -> Tuple[List[str], List[str]]:
        """Split a disjunctive OR clause."""
        parts = re.split(r"\s+or\s+|\s*/\s*|\s*\|\s*", surface_name, flags=re.IGNORECASE)
        members, names = [], []
        for p in parts:
            clean_p = p.strip().strip(".,;:()")
            if not clean_p:
                continue
            norm = normalize_canonical_skill(clean_p)
            if norm and norm not in members:
                members.append(norm)
                names.append(clean_p)
        return members, names

    @classmethod
    def _split_and(cls, surface_name: str, canon: str) -> Tuple[List[str], List[str]]:
        """Split a conjunctive AND clause."""
        # Clean out common non-competency suffix words before splitting
        cleaned_surf = re.sub(r"\b(?:applications?|stacks?|development|codebases?|systems?)\b", "", surface_name, flags=re.IGNORECASE).strip()
        parts = re.split(r"\s+and\s+|\s*\+\s*|\s*&\s*|\s*/\s*", cleaned_surf, flags=re.IGNORECASE)
        members, names = [], []
        for p in parts:
            clean_p = p.strip().strip(".,;:()")
            if not clean_p or len(clean_p) < 2:
                continue
            norm = normalize_canonical_skill(clean_p)
            if norm and norm not in members:
                members.append(norm)
                names.append(clean_p)
        return members, names


class RequirementFulfillmentEngine:
    """Semantic requirement fulfillment engine evaluating candidate evidence against JD requirements."""

    def __init__(self) -> None:
        self.decomposer = CompoundRequirementDecomposer()

    def evaluate_fulfillment(
        self,
        cv_items: Sequence[Any],
        jd_items: Sequence[Any],
        verified_relations: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate end-to-end requirement fulfillment for candidate.

        Args:
            cv_items: List of CV skill items (SkillInputItem or dicts)
            jd_items: List of JD skill items (SkillInputItem or dicts)
            verified_relations: Optional list of verified relations

        Returns:
            Structured fulfillment dictionary with detailed records, grouped evaluations, and summary metrics.
        """
        # 1. Normalize CV skills into an indexed competency lookup
        cv_competencies: Dict[str, Dict[str, Any]] = {}
        for item in cv_items:
            if isinstance(item, dict):
                c_id = item.get("canonical_skill_id") or item.get("skill_id") or item.get("name") or ""
                disp = item.get("surface_name") or item.get("display_name") or c_id
                evs = item.get("evidence_sentences") or item.get("evidence") or []
                prof = item.get("modifier_text") or item.get("proficiency")
            else:
                c_id = getattr(item, "canonical_skill_id", "")
                disp = getattr(item, "surface_name", c_id)
                evs = getattr(item, "evidence_sentences", [])
                prof = getattr(item, "modifier_text", None)

            canon = normalize_canonical_skill(c_id)
            if not canon:
                continue
            if canon not in cv_competencies:
                cv_competencies[canon] = {
                    "canonical_id": canon,
                    "raw_id": c_id,
                    "display_name": disp,
                    "evidence": list(evs),
                    "proficiency": prof,
                }
            else:
                for e in evs:
                    if e and e not in cv_competencies[canon]["evidence"]:
                        cv_competencies[canon]["evidence"].append(e)

        # 2. Decompose and evaluate each JD requirement
        alignment_records: List[SemanticAlignmentRecord] = []
        grouped_evals: List[RequirementGroupFulfillment] = []

        satisfied_count = 0
        partially_satisfied_count = 0
        not_satisfied_count = 0

        for item in jd_items:
            if isinstance(item, dict):
                jd_id = item.get("canonical_skill_id") or item.get("skill_id") or item.get("name") or ""
                jd_disp = item.get("surface_name") or item.get("display_name") or jd_id
                jd_evs = item.get("evidence_sentences") or item.get("evidence") or []
            else:
                jd_id = getattr(item, "canonical_skill_id", "")
                jd_disp = getattr(item, "surface_name", jd_id)
                jd_evs = getattr(item, "evidence_sentences", [])

            canon_jd = normalize_canonical_skill(jd_id)
            if not canon_jd:
                continue

            # Decompose requirement into atomic/group structure
            req_info = self.decomposer.decompose(canon_jd, jd_disp, jd_evs)

            # Evaluate each member requirement
            member_evals: List[RequirementMemberFulfillment] = []
            for mem_id, mem_name in zip(req_info.members, req_info.member_display_names):
                mem_eval = self._evaluate_atomic_member(mem_id, mem_name, cv_competencies, jd_evs)
                member_evals.append(mem_eval)

                # Record typed alignment record
                alignment_records.append(
                    SemanticAlignmentRecord(
                        jd_skill_id=mem_id,
                        cv_skill_id=mem_eval.matched_cv_skill_id,
                        relation_type=mem_eval.relation_type,
                        direction=mem_eval.direction,
                        fulfillment_status=mem_eval.fulfillment_status,
                        evidence=mem_eval.evidence,
                        verification_status=VerificationStatus.VERIFIED,
                        reasoning=mem_eval.reasoning,
                        is_compound_member=req_info.is_compound,
                        parent_requirement_id=req_info.requirement_id if req_info.is_compound else None,
                    )
                )

            # Synthesize group fulfillment based on logical operator
            group_status, score, diag = self._synthesize_group_status(req_info, member_evals)

            if group_status == FulfillmentStatus.SATISFIED:
                satisfied_count += 1
            elif group_status == FulfillmentStatus.PARTIALLY_SATISFIED:
                partially_satisfied_count += 1
            else:
                not_satisfied_count += 1

            all_group_evs = list(dict.fromkeys(jd_evs + [e for m in member_evals for e in m.evidence]))

            grouped_evals.append(
                RequirementGroupFulfillment(
                    requirement_id=req_info.requirement_id,
                    operator=req_info.operator,
                    original_surface_name=req_info.original_surface_name,
                    members=member_evals,
                    group_fulfillment_status=group_status,
                    satisfaction_score=round(score, 4),
                    evidence=all_group_evs,
                    diagnostic_summary=diag,
                )
            )

        total_reqs = len(grouped_evals)
        eff_coverage = float(
            sum(g.satisfaction_score for g in grouped_evals) / total_reqs
        ) if total_reqs > 0 else 0.0

        return {
            "evaluation_id": "SEMANTIC-REQUIREMENT-FULFILLMENT-V1",
            "summary": {
                "total_jd_requirements": total_reqs,
                "satisfied_count": satisfied_count,
                "partially_satisfied_count": partially_satisfied_count,
                "not_satisfied_count": not_satisfied_count,
                "effective_coverage_ratio": round(eff_coverage, 4),
                "unsupported_match_count": 0,
            },
            "alignment_records": [r.model_dump() for r in alignment_records],
            "grouped_evaluations": [g.model_dump() for g in grouped_evals],
        }

    def _evaluate_atomic_member(
        self,
        jd_id: str,
        jd_disp: str,
        cv_competencies: Dict[str, Dict[str, Any]],
        jd_evs: List[str],
    ) -> RequirementMemberFulfillment:
        """Evaluate a single atomic JD requirement against candidate CV competencies."""
        # Level 1: Exact Identity or Verified Alias Match
        if jd_id in cv_competencies:
            cv_match = cv_competencies[jd_id]
            raw_cv = str(cv_match.get("raw_id", "") or cv_match.get("display_name", "")).strip().lower()
            raw_jd = str(jd_disp or jd_id).strip().lower()
            norm_raw_cv = raw_cv.replace("-", "").replace(".", "").replace(" ", "").replace("_", "")
            norm_raw_jd = raw_jd.replace("-", "").replace(".", "").replace(" ", "").replace("_", "")
            is_alias = (norm_raw_cv != norm_raw_jd) and (raw_cv != jd_id)
            rel_type = SemanticRelationType.ALIAS if is_alias else SemanticRelationType.EQUIVALENT
            reasoning = (
                f"Verified canonical alias match ('{raw_cv}' <-> '{raw_jd}' mapped to '{jd_id}')."
                if is_alias
                else f"Exact canonical skill match ('{jd_id}'). Candidate directly demonstrates this competency."
            )
            return RequirementMemberFulfillment(
                jd_skill_id=jd_id,
                display_name=jd_disp,
                matched_cv_skill_id=jd_id,
                relation_type=rel_type,
                direction=RelationDirection.BIDIRECTIONAL,
                fulfillment_status=FulfillmentStatus.SATISFIED,
                evidence=cv_match["evidence"] + jd_evs,
                reasoning=reasoning,
            )

        # Level 2: Directional Specialization (CV specializes generic JD requirement)
        # e.g., JD requires 'relational-databases', CV demonstrates 'postgresql'
        # or JD requires 'junit', CV demonstrates 'junit-5'
        # or JD requires 'aws', CV demonstrates 'ec2', 's3', 'aws-lambda'
        for cv_id, cv_match in cv_competencies.items():
            # Check if cv_id specializes jd_id
            children = HIERARCHICAL_SPECIALIZATIONS.get(jd_id, set())
            if cv_id in children:
                return RequirementMemberFulfillment(
                    jd_skill_id=jd_id,
                    display_name=jd_disp,
                    matched_cv_skill_id=cv_id,
                    relation_type=SemanticRelationType.SPECIALIZATION,
                    direction=RelationDirection.CV_SPECIALIZES_JD,
                    fulfillment_status=FulfillmentStatus.SATISFIED,
                    evidence=cv_match["evidence"] + jd_evs,
                    reasoning=(
                        f"Directional specialization verified: candidate demonstrates specific competency "
                        f"'{cv_id}' which fulfills broader requirement '{jd_id}'."
                    ),
                )

        # Level 3: Reverse Specialization (Candidate has generic category, JD requires specific framework)
        # e.g., JD requires 'postgresql', CV only demonstrates broad 'relational-databases'
        for parent_id, children in HIERARCHICAL_SPECIALIZATIONS.items():
            if jd_id in children and parent_id in cv_competencies:
                cv_match = cv_competencies[parent_id]
                return RequirementMemberFulfillment(
                    jd_skill_id=jd_id,
                    display_name=jd_disp,
                    matched_cv_skill_id=parent_id,
                    relation_type=SemanticRelationType.SPECIALIZATION,
                    direction=RelationDirection.JD_SPECIALIZES_CV,
                    fulfillment_status=FulfillmentStatus.PARTIALLY_SATISFIED,
                    evidence=cv_match["evidence"] + jd_evs,
                    reasoning=(
                        f"Partial fulfillment: candidate demonstrates general domain '{parent_id}', "
                        f"but JD requests specific specialization '{jd_id}' without verified hands-on evidence."
                    ),
                )

        # Level 4: Not Satisfied
        return RequirementMemberFulfillment(
            jd_skill_id=jd_id,
            display_name=jd_disp,
            matched_cv_skill_id=None,
            relation_type=SemanticRelationType.UNRELATED,
            direction=RelationDirection.NONE,
            fulfillment_status=FulfillmentStatus.NOT_SATISFIED,
            evidence=jd_evs,
            reasoning=f"No matching or specializing competency found in candidate CV for '{jd_id}'.",
        )

    def _synthesize_group_status(
        self,
        req_info: RequirementGroupInfo,
        member_evals: List[RequirementMemberFulfillment],
    ) -> Tuple[FulfillmentStatus, float, str]:
        """Synthesize group fulfillment status and satisfaction score."""
        if not member_evals:
            return FulfillmentStatus.NOT_SATISFIED, 0.0, "Empty requirement group."

        n_members = len(member_evals)
        n_sat = sum(1 for m in member_evals if m.fulfillment_status == FulfillmentStatus.SATISFIED)
        n_part = sum(1 for m in member_evals if m.fulfillment_status == FulfillmentStatus.PARTIALLY_SATISFIED)

        if req_info.operator == RequirementOperator.SOLO:
            status = member_evals[0].fulfillment_status
            score = 1.0 if status == FulfillmentStatus.SATISFIED else (0.4 if status == FulfillmentStatus.PARTIALLY_SATISFIED else 0.0)
            return status, score, member_evals[0].reasoning

        elif req_info.operator == RequirementOperator.AND:
            # Conjunctive requirement: candidate must satisfy ALL members for complete satisfaction
            if n_sat == n_members:
                diag = f"All {n_members} constituent competencies satisfied ({', '.join(req_info.members)})."
                return FulfillmentStatus.SATISFIED, 1.0, diag
            elif n_sat > 0 or n_part > 0:
                score = (n_sat * 1.0 + n_part * 0.4) / n_members
                diag = f"Partially satisfied: candidate fulfills {n_sat}/{n_members} required competencies in AND group."
                return FulfillmentStatus.PARTIALLY_SATISFIED, score, diag
            else:
                diag = f"None of the {n_members} constituent competencies satisfied in AND group."
                return FulfillmentStatus.NOT_SATISFIED, 0.0, diag

        elif req_info.operator == RequirementOperator.OR:
            # Disjunctive requirement: candidate satisfies if ANY member is fulfilled
            if n_sat > 0:
                sat_members = [m.jd_skill_id for m in member_evals if m.fulfillment_status == FulfillmentStatus.SATISFIED]
                diag = f"Alternative satisfied: candidate fulfills '{sat_members[0]}' out of choices ({', '.join(req_info.members)})."
                return FulfillmentStatus.SATISFIED, 1.0, diag
            elif n_part > 0:
                diag = f"Alternative partially satisfied: candidate partially satisfies choice in OR group."
                return FulfillmentStatus.PARTIALLY_SATISFIED, 0.4, diag
            else:
                diag = f"None of the alternative choices satisfied ({', '.join(req_info.members)})."
                return FulfillmentStatus.NOT_SATISFIED, 0.0, diag

        else:
            # Hierarchical
            if n_sat > 0:
                return FulfillmentStatus.SATISFIED, 1.0, "Hierarchical requirement fulfilled by specific competencies."
            return FulfillmentStatus.NOT_SATISFIED, 0.0, "Hierarchical requirement unfulfilled."


class SemanticGraphTransformer:
    """Transforms input skill items under Policy B (Semantic-Aligned Candidate) for PaperAlignedGraphBuilder."""

    def __init__(self) -> None:
        self.decomposer = CompoundRequirementDecomposer()

    def transform_policy_b(
        self,
        cv_items: List[SkillInputItem],
        jd_items: List[SkillInputItem],
        sbert_encoder: Optional[Any] = None,
    ) -> Tuple[List[SkillInputItem], List[SkillInputItem], Dict[str, Any]]:
        """
        Transform CV and JD items under Policy B:
        1. Resolve verified aliases.
        2. Decompose compound JD requirements into constituent atomic skills.
        3. Prune redundant composite JD nodes when constituent atomic skills exist.
        4. For satisfied OR groups, represent the fulfilled alternative without inflating denominator.
        5. Return prepared items and audit trace.
        """
        # 1. First-pass alias normalization
        transformed_cv = [self._normalize_item_alias(it) for it in cv_items]
        transformed_jd = [self._normalize_item_alias(it) for it in jd_items]

        # 2. Decompose compound JD items
        decomposed_jd: List[SkillInputItem] = []
        decomposition_audit: List[Dict[str, Any]] = []
        all_atomic_jd_slugs: Set[str] = set()

        for jd_it in transformed_jd:
            canon = jd_it.canonical_skill_id
            req_info = self.decomposer.decompose(canon, jd_it.surface_name, jd_it.evidence_sentences)

            if not req_info.is_compound or req_info.operator == RequirementOperator.SOLO:
                decomposed_jd.append(jd_it)
                all_atomic_jd_slugs.add(canon)
            elif req_info.operator == RequirementOperator.AND:
                # Decompose into constituent atomic skill items
                audit_entry = {
                    "original_id": canon,
                    "operator": "AND",
                    "decomposed_members": req_info.members,
                }
                decomposition_audit.append(audit_entry)
                for mem_id, mem_name in zip(req_info.members, req_info.member_display_names):
                    new_item = SkillInputItem(
                        occurrence_id=f"decomp_{jd_it.occurrence_id}_{mem_id}",
                        canonical_skill_id=mem_id,
                        surface_name=mem_name,
                        source_document="JD",
                        extraction_type=jd_it.extraction_type,
                        evidence_sentences=list(jd_it.evidence_sentences),
                        evidence_offsets=list(jd_it.evidence_offsets),
                        modifier_text=jd_it.modifier_text,
                        proficiency_override=jd_it.proficiency_override,
                        embedding_vector=None,  # will encode if missing
                    )
                    decomposed_jd.append(new_item)
                    all_atomic_jd_slugs.add(mem_id)
            elif req_info.operator == RequirementOperator.OR:
                # Disjunctive OR: check if candidate already satisfies one of the OR choices
                cv_slugs = {it.canonical_skill_id for it in transformed_cv}
                satisfied_choices = [m for m in req_info.members if m in cv_slugs]
                audit_entry = {
                    "original_id": canon,
                    "operator": "OR",
                    "choices": req_info.members,
                    "satisfied_by_cv": satisfied_choices,
                }
                decomposition_audit.append(audit_entry)

                if satisfied_choices:
                    # Represent the satisfied choice as 1 requirement slot (avoiding denominator inflation)
                    chosen_id = satisfied_choices[0]
                    chosen_name = req_info.member_display_names[req_info.members.index(chosen_id)]
                    new_item = SkillInputItem(
                        occurrence_id=f"or_sat_{jd_it.occurrence_id}_{chosen_id}",
                        canonical_skill_id=chosen_id,
                        surface_name=chosen_name,
                        source_document="JD",
                        extraction_type=jd_it.extraction_type,
                        evidence_sentences=list(jd_it.evidence_sentences),
                        evidence_offsets=list(jd_it.evidence_offsets),
                        modifier_text=jd_it.modifier_text,
                        proficiency_override=jd_it.proficiency_override,
                        embedding_vector=None,
                    )
                    decomposed_jd.append(new_item)
                    all_atomic_jd_slugs.add(chosen_id)
                else:
                    # Candidate has none of the choices: preserve first alternative as requirement
                    fallback_id = req_info.members[0]
                    fallback_name = req_info.member_display_names[0]
                    new_item = SkillInputItem(
                        occurrence_id=f"or_unsat_{jd_it.occurrence_id}_{fallback_id}",
                        canonical_skill_id=fallback_id,
                        surface_name=fallback_name,
                        source_document="JD",
                        extraction_type=jd_it.extraction_type,
                        evidence_sentences=list(jd_it.evidence_sentences),
                        evidence_offsets=list(jd_it.evidence_offsets),
                        modifier_text=jd_it.modifier_text,
                        proficiency_override=jd_it.proficiency_override,
                        embedding_vector=None,
                    )
                    decomposed_jd.append(new_item)
                    all_atomic_jd_slugs.add(fallback_id)

        # 3. Deduplicate JD items to eliminate redundant composite/atomic double counting
        pruned_jd: List[SkillInputItem] = []
        seen_jd_slugs: Set[str] = set()
        for it in decomposed_jd:
            if it.canonical_skill_id not in seen_jd_slugs:
                seen_jd_slugs.add(it.canonical_skill_id)
                pruned_jd.append(it)

        # 4. Deduplicate CV items
        pruned_cv: List[SkillInputItem] = []
        seen_cv_slugs: Set[str] = set()
        for it in transformed_cv:
            if it.canonical_skill_id not in seen_cv_slugs:
                seen_cv_slugs.add(it.canonical_skill_id)
                pruned_cv.append(it)

        # 5. Encode missing vectors via SBERT if encoder provided
        all_items = pruned_cv + pruned_jd
        missing = [it for it in all_items if it.embedding_vector is None]
        if missing and sbert_encoder is not None:
            texts = [it.surface_name for it in missing]
            vecs = sbert_encoder.encode(texts, normalize_embeddings=True)
            for it, v in zip(missing, vecs):
                it.embedding_vector = v.tolist()

        audit_meta = {
            "policy": "POLICY_B_SEMANTIC",
            "cv_input_count": len(cv_items),
            "cv_transformed_count": len(pruned_cv),
            "jd_input_count": len(jd_items),
            "jd_transformed_count": len(pruned_jd),
            "decomposition_audit": decomposition_audit,
        }

        return pruned_cv, pruned_jd, audit_meta

    def _normalize_item_alias(self, item: SkillInputItem) -> SkillInputItem:
        """Normalize canonical alias on a skill input item."""
        canon = normalize_canonical_skill(item.canonical_skill_id or item.surface_name)
        if canon == item.canonical_skill_id:
            return item
        cloned = item.model_copy(deep=True)
        cloned.canonical_skill_id = canon
        return cloned
