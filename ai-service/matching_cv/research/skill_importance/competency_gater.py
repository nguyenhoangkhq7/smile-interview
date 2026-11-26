"""Competency Eligibility Gater (JSI-4 Research Module).

Distinguishes between genuine candidate competencies and non-competency contextual entities:
- ACTOR_OR_ROLE_ENTITY: Colleague roles, stakeholders, external partners ('backend engineers', 'stakeholders')
- CONTEXT_ONLY: Hardware form factors, media types ('tablet', 'web', 'mobile devices')
- NOT_A_COMPETENCY: Non-skill nouns ('ui', 'requisition', 'salary')
- VALID_TECHNOLOGY: Discrete tools, languages, frameworks ('react', 'java', 'postgresql')
- VALID_COMPETENCY: Conceptual methodologies, engineering capabilities ('query-optimization', 'relational-databases')
- VALID_DOMAIN_KNOWLEDGE: Industry verticals ('healthcare', 'payments', 'telehealth')
- COMPOSITE_COMPETENCY: Multi-technology stack phrases ('java-spring-boot-stack', 'production-web-applications')
- TASK_OR_RESPONSIBILITY: Operational duties ('incident management', 'code reviews')
- UNCERTAIN: Entities requiring human review (never silently dropped)

Strict Invariant:
Does not rely on a static closed-world ontology whitelist. Open to emerging technologies and implicit competencies.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

EligibilityCategory = Literal[
    "VALID_COMPETENCY",
    "VALID_TECHNOLOGY",
    "VALID_DOMAIN_KNOWLEDGE",
    "COMPOSITE_COMPETENCY",
    "TASK_OR_RESPONSIBILITY",
    "ACTOR_OR_ROLE_ENTITY",
    "CONTEXT_ONLY",
    "NOT_A_COMPETENCY",
    "UNCERTAIN",
]


class EligibilityAuditRecord(BaseModel):
    """Detailed audit record for entity competency eligibility."""

    canonical_skill_id: str
    skill_display_name: str
    eligibility_class: EligibilityCategory
    is_eligible_for_ranking: bool = Field(
        ...,
        description="True if entity represents a valid candidate requirement; False if non-competency context/actor",
    )
    is_standalone_competency: bool
    is_compound: bool
    is_context_only: bool
    confidence: float
    decision_reason: str
    evidence_sentence: Optional[str] = None


# Collaboration verbal cues that identify companion actors/collaborators
COLLABORATOR_VERB_PATTERNS = [
    re.compile(r"\b(?:partner\s+with|collaborate\s+with|work\s+with|work\s+closely\s+with|interface\s+with|liaise\s+with|report\s+to|support|interact\s+with|coordinate\s+with)\b", re.IGNORECASE),
    re.compile(r"\b(?:cross\-functional\s+partners|teammates|colleagues|stakeholders|peers)\b", re.IGNORECASE),
]

# Actor role noun patterns (plural occupational roles or stakeholder collective nouns)
ACTOR_NOUN_PATTERNS = [
    re.compile(r"\b(?:backend|frontend|fullstack|software|qa|devops|data|platform|systems?|infrastructure|cloud)\s+(?:engineers?|developers?|architects?|analysts?|specialists?|leads?)\b", re.IGNORECASE),
    re.compile(r"\b(?:stakeholders?|clients?|customers?|residents?|patients?|users?|vendors?|providers?|clinicians?|product\s+owners?|product\s+managers?|scrum\s+masters?|management|team\s+members?)\b", re.IGNORECASE),
]

# Form factor / platform target nouns that are context-only deployment media
FORM_FACTOR_PATTERNS = [
    re.compile(r"^(?:tablet|tablets|smartphone|smartphones|desktop|web|mobile\s+devices?|handhelds?|ui|screen|screens)$", re.IGNORECASE),
]

# Known technology keywords (open, non-exhaustive seed patterns)
TECH_STEMS = {
    "java", "python", "typescript", "javascript", "golang", "go", "c#", "c++", "ruby", "php",
    "react", "angular", "vue", "next.js", "nuxt", "svelte", "tailwind", "bootstrap", "css", "html",
    "spring", "spring-boot", "hibernate", "django", "flask", "fastapi", "express", "node", "nodejs",
    "sql", "mysql", "postgresql", "postgres", "oracle", "sqlite", "mongodb", "redis", "cassandra",
    "kafka", "rabbitmq", "activemq", "graphql", "rest", "restful", "grpc", "soap",
    "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "git", "jenkins", "gitlab", "ci/cd",
    "jest", "playwright", "cypress", "junit", "mockito", "selenium", "terraform", "ansible",
}


class CompetencyEligibilityGater:
    """Evaluates whether an extracted entity represents a genuine candidate competency."""

    def __init__(self, blocked_classes: Optional[set[str]] = None) -> None:
        self.blocked_classes = blocked_classes or {"ACTOR_OR_ROLE_ENTITY", "CONTEXT_ONLY", "NOT_A_COMPETENCY"}

    def evaluate_eligibility(
        self,
        canonical_skill_id: str,
        skill_display_name: str,
        evidence_sentences: Optional[List[str]] = None,
        extraction_type: str = "explicit",
    ) -> EligibilityAuditRecord:
        """Classify entity into EligibilityCategory with grounded justification."""
        cid = canonical_skill_id.strip().lower().replace("_", "-")
        disp = skill_display_name.strip()
        first_sent = evidence_sentences[0].strip() if evidence_sentences else ""
        lower_sent = first_sent.lower()
        lower_disp = disp.lower()

        # 1. Rule A: Check Actor / Role Entity (e.g. "backend engineers", "stakeholders")
        is_actor_noun = any(p.search(disp) for p in ACTOR_NOUN_PATTERNS)
        is_collab_context = any(p.search(first_sent) for p in COLLABORATOR_VERB_PATTERNS)

        if is_actor_noun and (is_collab_context or "partner" in lower_sent or "collaborat" in lower_sent or "work with" in lower_sent):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="ACTOR_OR_ROLE_ENTITY",
                is_eligible_for_ranking=False,
                is_standalone_competency=False,
                is_compound=False,
                is_context_only=True,
                confidence=0.98,
                decision_reason=f"Entity '{disp}' is an occupational actor/role mentioned in collaborative context ('{first_sent[:80]}...'). It represents a colleague or stakeholder, not a candidate skill.",
                evidence_sentence=first_sent,
            )

        if cid in ("backend-engineers", "frontend-engineers", "product-managers", "stakeholders", "team-members", "clients", "residents"):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="ACTOR_OR_ROLE_ENTITY",
                is_eligible_for_ranking=False,
                is_standalone_competency=False,
                is_compound=False,
                is_context_only=True,
                confidence=0.95,
                decision_reason=f"Entity '{disp}' is an occupational title or collective noun representing human agents rather than a personal skill.",
                evidence_sentence=first_sent,
            )

        # 2. Rule B: Check Context-Only / Form Factor / Generic Target
        if any(p.search(cid) for p in FORM_FACTOR_PATTERNS) or any(p.search(disp) for p in FORM_FACTOR_PATTERNS):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="CONTEXT_ONLY",
                is_eligible_for_ranking=False,
                is_standalone_competency=False,
                is_compound=False,
                is_context_only=True,
                confidence=0.92,
                decision_reason=f"Entity '{disp}' is a hardware form-factor, media target, or generic design noun ('{first_sent[:80]}...').",
                evidence_sentence=first_sent,
            )

        # 3. Rule C: Discrete Technologies
        clean_tokens = set(re.split(r"[\s\-\/\.]+", cid))
        if any(t in TECH_STEMS for t in clean_tokens) and len(clean_tokens) <= 3:
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="VALID_TECHNOLOGY",
                is_eligible_for_ranking=True,
                is_standalone_competency=True,
                is_compound=len(clean_tokens) > 1,
                is_context_only=False,
                confidence=0.95,
                decision_reason=f"Entity '{disp}' matches recognized software technology or tool stem.",
                evidence_sentence=first_sent,
            )

        # 4. Rule D: Composite Competencies / Technology Stack phrases
        if any(sep in disp for sep in ["/", "&", "+", " stack", " platform", " applications", " workflows"]):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="COMPOSITE_COMPETENCY",
                is_eligible_for_ranking=True,
                is_standalone_competency=False,
                is_compound=True,
                is_context_only=False,
                confidence=0.88,
                decision_reason=f"Entity '{disp}' represents a composite stack or broad engineering domain phrase.",
                evidence_sentence=first_sent,
            )

        # 5. Rule E: Valid Competency & Engineering Capabilities
        if any(kw in lower_disp for kw in [
            "database", "indexing", "optimization", "architecture", "design", "testing",
            "microservices", "streaming", "caching", "debugging", "modeling", "analytics",
            "collaboration", "leadership", "governance", "security", "ci/cd", "deployment"
        ]):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="VALID_COMPETENCY",
                is_eligible_for_ranking=True,
                is_standalone_competency=True,
                is_compound=False,
                is_context_only=False,
                confidence=0.90,
                decision_reason=f"Entity '{disp}' represents a conceptual engineering capability or technical methodology.",
                evidence_sentence=first_sent,
            )

        # 6. Rule F: Domain Knowledge
        if any(dom in lower_disp for dom in [
            "financial", "payment", "banking", "health", "clinical", "insurance", "telehealth",
            "accounting", "treasury", "construction", "e-commerce"
        ]):
            return EligibilityAuditRecord(
                canonical_skill_id=cid,
                skill_display_name=disp,
                eligibility_class="VALID_DOMAIN_KNOWLEDGE",
                is_eligible_for_ranking=True,
                is_standalone_competency=True,
                is_compound=False,
                is_context_only=False,
                confidence=0.85,
                decision_reason=f"Entity '{disp}' represents industry vertical or business domain knowledge.",
                evidence_sentence=first_sent,
            )

        # 7. Fallback: Default to UNCERTAIN (retained for research ranking with caution)
        return EligibilityAuditRecord(
            canonical_skill_id=cid,
            skill_display_name=disp,
            eligibility_class="UNCERTAIN",
            is_eligible_for_ranking=True,
            is_standalone_competency=False,
            is_compound=False,
            is_context_only=False,
            confidence=0.50,
            decision_reason=f"Entity '{disp}' does not trigger exclusion rules; retained as candidate competency.",
            evidence_sentence=first_sent,
        )
