"""Segment-Level (Section) Salience Scorer (Component E).

Estimates S_seg(skill) based on hierarchical section priors:
- requirements: 1.00
- responsibilities: 0.80
- nice_to_have: 0.50
- about: 0.30
- benefits: 0.05

Strict invariants:
- Unresolved sections ('unknown', 'header' with low confidence, None) return segment_salience = None and is_available = False.
- Multi-section skills use max-pooling.
- Never sums section scores to prevent repeated mentions from inflating importance.
"""
from __future__ import annotations

from typing import List, Optional, Set
from matching_cv.research.skill_importance.config import JSIConfig, default_jsi_config
from matching_cv.research.skill_importance.models import SegmentSalienceResult, SkillSentenceOccurrence


class SegmentSalienceScorer:
    """Estimates the structural importance of a skill based on its containing JD section(s)."""

    def __init__(self, config: Optional[JSIConfig] = None) -> None:
        self.config = config or default_jsi_config

    def score_section(
        self,
        section_type: Optional[str],
        section_confidence: float = 1.0,
    ) -> SegmentSalienceResult:
        """
        Evaluate segment salience for a single section type.
        Returns SegmentSalienceResult with segment_salience = None if section is unresolvable.
        """
        if not section_type or section_type in ("header", "unknown"):
            # Unresolved section: mark dimension as unavailable
            return SegmentSalienceResult(
                section_type=section_type,
                section_prior_weight=None,
                section_confidence=section_confidence,
                is_available=False,
                segment_salience=None,
                multi_occurrence_strategy=self.config.multi_occurrence_strategy,
            )

        norm_sec = section_type.strip().lower()
        if norm_sec not in self.config.section_priors:
            return SegmentSalienceResult(
                section_type=section_type,
                section_prior_weight=None,
                section_confidence=section_confidence,
                is_available=False,
                segment_salience=None,
                multi_occurrence_strategy=self.config.multi_occurrence_strategy,
            )

        prior_weight = self.config.section_priors[norm_sec]
        return SegmentSalienceResult(
            section_type=norm_sec,
            section_prior_weight=prior_weight,
            section_confidence=section_confidence,
            is_available=True,
            segment_salience=prior_weight,
            multi_occurrence_strategy=self.config.multi_occurrence_strategy,
        )

    def score_occurrences(
        self,
        occurrences: List[SkillSentenceOccurrence],
    ) -> SegmentSalienceResult:
        """
        Aggregate segment salience across all occurrences of a skill using max-pooling.
        Never sums section scores.
        """
        if not occurrences:
            return SegmentSalienceResult(
                section_type=None,
                section_prior_weight=None,
                section_confidence=0.0,
                is_available=False,
                segment_salience=None,
                multi_occurrence_strategy=self.config.multi_occurrence_strategy,
            )

        scored_results: List[SegmentSalienceResult] = []
        for occ in occurrences:
            res = self.score_section(occ.section_type, occ.section_confidence)
            if res.is_available and res.segment_salience is not None:
                scored_results.append(res)

        if not scored_results:
            # All occurrences were in unresolved or missing sections
            best_conf = max(occ.section_confidence for occ in occurrences)
            sec_types = list(dict.fromkeys(occ.section_type for occ in occurrences if occ.section_type))
            return SegmentSalienceResult(
                section_type=sec_types[0] if sec_types else None,
                section_prior_weight=None,
                section_confidence=best_conf,
                is_available=False,
                segment_salience=None,
                multi_occurrence_strategy=self.config.multi_occurrence_strategy,
            )

        # Max pooling across available section priors
        best_res = max(scored_results, key=lambda r: (r.segment_salience or 0.0))
        return SegmentSalienceResult(
            section_type=best_res.section_type,
            section_prior_weight=best_res.section_prior_weight,
            section_confidence=best_res.section_confidence,
            is_available=True,
            segment_salience=best_res.segment_salience,
            multi_occurrence_strategy="max_pooling",
        )
