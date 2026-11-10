"""Requirement Semantics Parser (JSI-4 Research Module).

Evaluates requirement modality, polarity, and logical group relationships:
- Modality: MUST_HAVE | PREFERRED | OPTIONAL | RESPONSIBILITY | CONTEXTUAL | UNKNOWN
- Polarity: POSITIVE | NEGATED | EXCLUDED | AMBIGUOUS
- Logical Group: SINGLE | ALTERNATIVE_GROUP (OR) | CONJUNCTIVE_GROUP (AND) | UNKNOWN

Key Invariant:
Context-sensitive: Evaluates requirement phrasing in conjunction with the containing section:
- 'Experience with X' in Requirements -> MUST_HAVE
- 'Experience with X' in Nice to Have -> PREFERRED
- 'Experience with X' in Responsibilities -> RESPONSIBILITY
- 'Experience with X' in About Us -> CONTEXTUAL
- Scope-aware negation prevents sentence-wide negation leakage.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

RequirementModality = Literal[
    "MUST_HAVE",
    "PREFERRED",
    "OPTIONAL",
    "RESPONSIBILITY",
    "CONTEXTUAL",
    "UNKNOWN",
]

PolarityType = Literal[
    "POSITIVE",
    "NEGATED",
    "EXCLUDED",
    "AMBIGUOUS",
]

LogicalRelationType = Literal[
    "SINGLE",
    "ALTERNATIVE_GROUP",
    "CONJUNCTIVE_GROUP",
    "UNKNOWN",
]


class RequirementGroupInfo(BaseModel):
    """Metadata representing a logical conjunction (AND) or disjunction (OR) of requirements."""

    group_id: str
    operator: Literal["OR", "AND", "NONE"]
    members: List[str]
    requirement_modality: RequirementModality
    is_disjunctive_substitution: bool = Field(
        default=False,
        description="True for OR groups indicating that any single member satisfies the requirement",
    )


class RequirementSemanticRecord(BaseModel):
    """Structured semantic interpretation of a single requirement mention."""

    skill_name: str
    modality: RequirementModality
    modality_weight: float
    polarity: PolarityType
    logical_relation: LogicalRelationType
    group_info: Optional[RequirementGroupInfo] = None
    matched_clause: str
    decision_reason: str


# Negation regex patterns covering explicit and responsibility exclusions
EXTENDED_NEGATION_PATTERNS = [
    re.compile(r"\b(?:not|no|neither|nor)\s+(?:required|mandatory|essential|needed|necessary)\b", re.IGNORECASE),
    re.compile(r"\b(?:not|no)\s+(?:a\s+requirement|prerequisite)\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:prior\s+)?experience\s+(?:is\s+)?(?:required|needed)\b", re.IGNORECASE),
    re.compile(r"\b(?:will\s+not\s+be\s+responsible\s+for|not\s+responsible\s+for|not\s+expected\s+to)\b", re.IGNORECASE),
    re.compile(r"\b(?:do\s+not\s+require|does\s+not\s+require|do\s+not\s+need|does\s+not\s+need|does\s+not\s+involve|without\s+requiring)\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+optional|are\s+optional)\b", re.IGNORECASE),
]

# Preferred cues
PREFERRED_CUES = [
    re.compile(r"\b(?:is\s+a\s+plus|a\s+big\s+plus|bonus|nice\s+to\s+have|good\s+to\s+have|preferred|highly\s+preferred|desirable|advantageous)\b", re.IGNORECASE),
]

# Explicit Mandatory cues
EXPLICIT_MANDATORY_CUES = [
    re.compile(r"\b(?:must\s+have|must\s+possess|must\s+be|shall\s+have|strictly\s+required|mandatory|essential|core\s+requirement)\b", re.IGNORECASE),
    re.compile(r"\b(?:minimum\s+of\s+\d+|\d+\+?\s+years(?:\s+of)?\s+(?:proven\s+|hands\-on\s+)?experience)\b", re.IGNORECASE),
    re.compile(r"\b(?:deep|expert|thorough|solid|strong|advanced|proven)\s+(?:understanding|knowledge|proficiency|experience|skills?)\b", re.IGNORECASE),
]

# Standard Qualification cues (e.g. "Experience with...", "Knowledge of...")
STANDARD_QUALIFICATION_CUES = [
    re.compile(r"\b(?:experience\s+with|experience\s+in|knowledge\s+of|background\s+in|proficiency\s+in|familiarity\s+with|ability\s+to)\b", re.IGNORECASE),
]


class RequirementSemanticsParser:
    """Parses context-aware requirement strength, negation polarity, and logical groupings."""

    @staticmethod
    def split_clauses(sentence: str) -> List[str]:
        """Split compound sentences along logical contrastive and semicolon boundaries."""
        parts = re.split(r"(?:;|\—|\–|\,\s+(?:but|however|although|whereas|while)\s+)", sentence)
        clauses = [p.strip() for p in parts if p.strip()]
        return clauses if clauses else [sentence.strip()]

    def parse_requirement(
        self,
        skill_name: str,
        sentence: str,
        section_type: Optional[str] = None,
    ) -> RequirementSemanticRecord:
        """
        Evaluate requirement modality, polarity, and logical operator for skill_name within sentence.
        """
        clean_skill = skill_name.strip()
        sec = (section_type or "unknown").strip().lower()

        # Step 1: Isolate target clause containing the skill
        clauses = self.split_clauses(sentence)
        pattern = re.compile(r"\b" + re.escape(clean_skill) + r"\b", re.IGNORECASE)

        target_clause = sentence
        for c in clauses:
            if pattern.search(c):
                target_clause = c
                break

        lower_clause = target_clause.lower()

        # Step 2: Check Polarity & Negation
        is_negated = False
        polarity: PolarityType = "POSITIVE"
        for neg_pat in EXTENDED_NEGATION_PATTERNS:
            if neg_pat.search(lower_clause):
                is_negated = True
                polarity = "NEGATED" if "not responsible" not in lower_clause else "EXCLUDED"
                break

        if is_negated:
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="OPTIONAL" if "optional" in lower_clause else "CONTEXTUAL",
                modality_weight=0.00,
                polarity=polarity,
                logical_relation="SINGLE",
                matched_clause=target_clause,
                decision_reason=f"Skill '{clean_skill}' is explicitly negated or excluded in clause: '{target_clause}'.",
            )

        # Step 3: Check Logical Relationship (OR vs AND)
        logical_relation: LogicalRelationType = "SINGLE"
        group_info: Optional[RequirementGroupInfo] = None

        has_or = bool(re.search(r"\b(?:or|either\s+[\w\s]+\s+or)\b", lower_clause, re.IGNORECASE))
        has_and = bool(re.search(r"\b(?:and|both\s+[\w\s]+\s+and)\b", lower_clause, re.IGNORECASE))

        # Detect disjunction (OR)
        if has_or and not has_and:
            logical_relation = "ALTERNATIVE_GROUP"
            # Extract potential alternatives around 'or'
            or_parts = re.split(r"\s+or\s+", target_clause, flags=re.IGNORECASE)
            members = [p.strip().strip(".,;:()") for p in or_parts if len(p.strip()) > 1]
            group_info = RequirementGroupInfo(
                group_id=f"alt_grp_{abs(hash(target_clause)) % 100000}",
                operator="OR",
                members=members if len(members) > 1 else [clean_skill],
                requirement_modality="MUST_HAVE" if sec == "requirements" else "PREFERRED",
                is_disjunctive_substitution=True,
            )
        elif has_and:
            logical_relation = "CONJUNCTIVE_GROUP"
            and_parts = re.split(r"\s+and\s+", target_clause, flags=re.IGNORECASE)
            members = [p.strip().strip(".,;:()") for p in and_parts if len(p.strip()) > 1]
            group_info = RequirementGroupInfo(
                group_id=f"conj_grp_{abs(hash(target_clause)) % 100000}",
                operator="AND",
                members=members if len(members) > 1 else [clean_skill],
                requirement_modality="MUST_HAVE" if sec == "requirements" else "RESPONSIBILITY",
                is_disjunctive_substitution=False,
            )

        # Step 4: Context-Sensitive Modality Determination
        # 4a. Check Explicit Preferred cues
        if any(p.search(lower_clause) for p in PREFERRED_CUES) or sec == "nice_to_have":
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="PREFERRED",
                modality_weight=0.50,
                polarity="POSITIVE",
                logical_relation=logical_relation,
                group_info=group_info,
                matched_clause=target_clause,
                decision_reason=f"Skill '{clean_skill}' is qualified with preferred/bonus phrasing or appears in nice_to_have section.",
            )

        # 4b. Check Explicit Mandatory cues
        if any(p.search(lower_clause) for p in EXPLICIT_MANDATORY_CUES):
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="MUST_HAVE",
                modality_weight=1.00,
                polarity="POSITIVE",
                logical_relation=logical_relation,
                group_info=group_info,
                matched_clause=target_clause,
                decision_reason=f"Skill '{clean_skill}' carries explicit mandatory phrasing ('must have', 'years of experience', 'solid/strong').",
            )

        # 4c. Section-Aware Standard Qualification Resolution
        # Standard phrasing like "Experience with X" or "Knowledge of X"
        if any(p.search(lower_clause) for p in STANDARD_QUALIFICATION_CUES):
            if sec == "requirements":
                # In Requirements section, standard qualification statements express core expectations
                return RequirementSemanticRecord(
                    skill_name=clean_skill,
                    modality="MUST_HAVE",
                    modality_weight=1.00,
                    polarity="POSITIVE",
                    logical_relation=logical_relation,
                    group_info=group_info,
                    matched_clause=target_clause,
                    decision_reason=f"Standard qualification phrase ('{target_clause[:40]}...') inside Requirements section expresses mandatory candidate expectation.",
                )
            elif sec == "responsibilities":
                return RequirementSemanticRecord(
                    skill_name=clean_skill,
                    modality="RESPONSIBILITY",
                    modality_weight=0.75,
                    polarity="POSITIVE",
                    logical_relation=logical_relation,
                    group_info=group_info,
                    matched_clause=target_clause,
                    decision_reason=f"Skill mentioned inside operational Responsibilities section.",
                )
            else:
                return RequirementSemanticRecord(
                    skill_name=clean_skill,
                    modality="CONTEXTUAL",
                    modality_weight=0.35,
                    polarity="POSITIVE",
                    logical_relation=logical_relation,
                    group_info=group_info,
                    matched_clause=target_clause,
                    decision_reason=f"Skill mentioned in non-qualification section ({sec}).",
                )

        # 4d. Fallback based on containing section
        if sec == "requirements":
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="MUST_HAVE",
                modality_weight=0.85,
                polarity="POSITIVE",
                logical_relation=logical_relation,
                group_info=group_info,
                matched_clause=target_clause,
                decision_reason=f"Skill appears as line item inside Requirements section.",
            )
        elif sec == "responsibilities":
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="RESPONSIBILITY",
                modality_weight=0.75,
                polarity="POSITIVE",
                logical_relation=logical_relation,
                group_info=group_info,
                matched_clause=target_clause,
                decision_reason=f"Skill appears inside Responsibilities section.",
            )
        elif sec == "about":
            return RequirementSemanticRecord(
                skill_name=clean_skill,
                modality="CONTEXTUAL",
                modality_weight=0.25,
                polarity="POSITIVE",
                logical_relation=logical_relation,
                group_info=group_info,
                matched_clause=target_clause,
                decision_reason=f"Skill appears in company background section.",
            )

        return RequirementSemanticRecord(
            skill_name=clean_skill,
            modality="UNKNOWN",
            modality_weight=0.50,
            polarity="POSITIVE",
            logical_relation=logical_relation,
            group_info=group_info,
            matched_clause=target_clause,
            decision_reason=f"Unclassified requirement context in section '{sec}'.",
        )
