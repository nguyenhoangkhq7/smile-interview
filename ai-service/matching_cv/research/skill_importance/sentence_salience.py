"""Sentence-Level Salience Scorer (Component D).

Estimates S_sent(skill, sentence) by combining:
1. Semantic relevance between skill display name and evidence sentence via SBERT cosine similarity.
2. Clause-aware deontic modality detection (Mandatory=1.00, Operational=0.75, Preferred=0.50, Contextual=0.25, Negated=0.00).

Strict invariants:
- Preserves raw cosine and transformed similarity separately.
- Implements explicit negation precedence ('Java is not required' -> 0.00).
- Clause-aware matching prevents cross-clause semantic bleed.
- Grammatical contextual checks for qualifiers ('expert knowledge required' vs 'expert team').
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple
import numpy as np

from matching_cv.app.services.semantic_embedding_service import semantic_embedding_service
from matching_cv.research.skill_importance.config import JSIConfig, default_jsi_config
from matching_cv.research.skill_importance.models import SentenceSalienceResult


# Negation regex patterns that explicitly invalidate skill necessity
NEGATION_PATTERNS = [
    re.compile(r"\b(?:not|no|neither|nor)\s+(?:required|mandatory|essential|needed|necessary)\b", re.IGNORECASE),
    re.compile(r"\b(?:not|no)\s+(?:a\s+requirement|prerequisite)\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:prior\s+)?experience\s+(?:is\s+)?(?:required|needed)\b", re.IGNORECASE),
    re.compile(r"\bwithout\s+(?:requiring|needing)\b", re.IGNORECASE),
]

# Mandatory modality cues
MANDATORY_PATTERNS = [
    re.compile(r"\b(?:must\s+have|must\s+possess|must\s+be|shall\s+have|is\s+required|are\s+required|strictly\s+required|mandatory)\b", re.IGNORECASE),
    re.compile(r"\b(?:minimum\s+of\s+\d+|\d+\+?\s+years(?:\s+of)?\s+(?:proven\s+|hands\-on\s+)?experience)\b", re.IGNORECASE),
    re.compile(r"\b(?:deep|expert|thorough|solid|strong|advanced|proven)\s+(?:understanding|knowledge|proficiency|experience|skills?)\s+(?:in|of|with)\b", re.IGNORECASE),
    re.compile(r"\b(?:essential|core|fundamental)\s+requirements?\b", re.IGNORECASE),
]

# Preferred modality cues
PREFERRED_PATTERNS = [
    re.compile(r"\b(?:is\s+a\s+plus|a\s+big\s+plus|would\s+be\s+a\s+plus|is\s+preferred|are\s+preferred|highly\s+preferred)\b", re.IGNORECASE),
    re.compile(r"\b(?:nice\s+to\s+have|good\s+to\s+have|bonus|bonus\s+points|desirable|advantageous)\b", re.IGNORECASE),
    re.compile(r"\b(?:familiarity\s+with|exposure\s+to|some\s+knowledge\s+of|working\s+knowledge\s+of)\b", re.IGNORECASE),
]

# Operational duty cues
OPERATIONAL_PATTERNS = [
    re.compile(r"\b(?:responsible\s+for|will\s+design|will\s+build|will\s+develop|will\s+architect|will\s+lead|will\s+manage)\b", re.IGNORECASE),
    re.compile(r"\b(?:design,\s*build|build\s+and\s+maintain|architect\s+and\s+scale|implement\s+and\s+test|lead\s+the\s+development)\b", re.IGNORECASE),
    re.compile(r"\b(?:partner\s+with|collaborate\s+with|work\s+closely\s+with|own\s+the)\b", re.IGNORECASE),
]


class SentenceSalienceScorer:
    """Estimates the salience of a skill within its containing sentence."""

    def __init__(self, config: Optional[JSIConfig] = None) -> None:
        self.config = config or default_jsi_config
        self.sbert = semantic_embedding_service._get_model()

    @staticmethod
    def split_into_clauses(sentence: str) -> List[str]:
        """Split a compound sentence into logical sub-clauses based on punctuation and contrastive conjunctions."""
        # Split on semicolons, em-dashes, or conjunction boundaries (', but ', ', however ', ', although ')
        parts = re.split(r"(?:;|\—|\–|\,\s+(?:but|however|although|whereas|while)\s+)", sentence)
        clauses = [p.strip() for p in parts if p.strip()]
        return clauses if clauses else [sentence.strip()]

    def analyze_modality(
        self,
        skill_display_name: str,
        sentence: str,
        modifier_text: Optional[str] = None,
    ) -> Tuple[str, float, bool, Optional[str]]:
        """
        Evaluate deontic modality for the skill within sentence.
        Returns: (modality_category, modality_score, is_negated, matched_clause)
        """
        clean_skill = skill_display_name.strip()
        skill_pattern = re.compile(r"\b" + re.escape(clean_skill) + r"\b", re.IGNORECASE)

        clauses = self.split_into_clauses(sentence)
        target_clause: Optional[str] = None

        # Find the specific clause containing the skill mention
        for c in clauses:
            if skill_pattern.search(c):
                target_clause = c
                break

        eval_text = target_clause or sentence
        mod_text = (modifier_text or "").strip().lower()

        # Step 1: Check Negation Rule (Strict Precedence)
        for neg_pat in NEGATION_PATTERNS:
            if neg_pat.search(eval_text) or neg_pat.search(mod_text):
                # Check for contrastive exception within the local eval_text:
                # e.g. "Java is not mandatory, but familiarity is preferred."
                if any(pref_pat.search(eval_text) for pref_pat in PREFERRED_PATTERNS):
                    return "Preferred", self.config.modality_values["Preferred"], False, eval_text
                return "Negated", self.config.modality_values["Negated"], True, eval_text

        # Step 2: Check Explicit Modifier Text
        if mod_text:
            if any(w in mod_text for w in ["required", "must", "mandatory", "expert", "primary", "proven"]):
                return "Mandatory", self.config.modality_values["Mandatory"], False, eval_text
            if any(w in mod_text for w in ["preferred", "plus", "bonus", "nice", "basic", "some"]):
                return "Preferred", self.config.modality_values["Preferred"], False, eval_text

        # Step 3: Check Mandatory Modality in local clause / sentence
        for mand_pat in MANDATORY_PATTERNS:
            if mand_pat.search(eval_text):
                # Verify that 'expert' or 'proven' is modifying the requirement, not an unlinked company slogan
                match_str = mand_pat.search(eval_text).group(0).lower()
                if "expert" in match_str or "proven" in match_str:
                    # Must be followed or accompanied by skill/knowledge/experience nouns
                    if re.search(r"\b(knowledge|experience|skills?|proficiency|understanding|background)\b", eval_text, re.IGNORECASE):
                        return "Mandatory", self.config.modality_values["Mandatory"], False, eval_text
                else:
                    return "Mandatory", self.config.modality_values["Mandatory"], False, eval_text

        # Step 4: Check Operational Duty Modality
        for op_pat in OPERATIONAL_PATTERNS:
            if op_pat.search(eval_text):
                return "Operational", self.config.modality_values["Operational"], False, eval_text

        # Step 5: Check Preferred Modality
        for pref_pat in PREFERRED_PATTERNS:
            if pref_pat.search(eval_text):
                return "Preferred", self.config.modality_values["Preferred"], False, eval_text

        # Step 6: Fallback to Contextual Baseline
        return "Contextual", self.config.modality_values["Contextual"], False, eval_text

    def score_sentence(
        self,
        skill_display_name: str,
        sentence: str,
        modifier_text: Optional[str] = None,
        skill_embedding: Optional[np.ndarray] = None,
        sentence_embedding: Optional[np.ndarray] = None,
    ) -> SentenceSalienceResult:
        """
        Compute sentence-level salience for a skill in a sentence.
        Uses SBERT cosine similarity + clause-aware deontic modality.
        """
        clean_skill = skill_display_name.strip()
        clean_sentence = sentence.strip()

        # Generate SBERT vectors if not passed in
        if skill_embedding is None:
            skill_embedding = self.sbert.encode(clean_skill, normalize_embeddings=True)
        if sentence_embedding is None:
            sentence_embedding = self.sbert.encode(clean_sentence, normalize_embeddings=True)

        # Compute raw cosine similarity in [-1, 1]
        dot_product = float(np.dot(skill_embedding, sentence_embedding))
        norm_s = float(np.linalg.norm(skill_embedding))
        norm_c = float(np.linalg.norm(sentence_embedding))
        raw_cosine = dot_product / (norm_s * norm_c + 1e-12)
        raw_cosine = max(-1.0, min(1.0, raw_cosine))

        # Linear monotonic mapping into [0, 1]
        # Clearly documented: monotonic score, not a calibrated probability
        transformed_sim = (raw_cosine + 1.0) / 2.0

        # Modality analysis
        mod_cat, mod_score, is_neg, matched_clause = self.analyze_modality(
            clean_skill, clean_sentence, modifier_text
        )

        # Final sentence salience aggregation
        if is_neg:
            final_salience = 0.0
        else:
            final_salience = (
                self.config.sentence_cosine_weight * transformed_sim
                + self.config.sentence_modality_weight * mod_score
            )
            final_salience = max(0.0, min(1.0, final_salience))

        return SentenceSalienceResult(
            raw_cosine=round(raw_cosine, 6),
            transformed_similarity=round(transformed_sim, 6),
            modality_category=mod_cat,
            modality_score=round(mod_score, 4),
            is_negated=is_neg,
            sentence_salience=round(final_salience, 6),
            matched_clause=matched_clause,
        )
