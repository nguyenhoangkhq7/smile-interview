from typing import Callable, List, Optional
from skill_gap.domain.enums import SemanticAlignment
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.heuristics.utils import build_match_map
from skill_gap.baselines.priority_policies import PriorityPolicy, WeightTimesGapPolicy


class SimGapBaseline(BaselineMethod):
    """
    Direct Semantic Similarity-as-Gap baseline (B-SimGap).

    Mathematical formulation:
        gap_magnitude = clamp(1.0 - soft_match, 0.0, 1.0)
        Priority = w_j * gap_magnitude (via WeightTimesGapPolicy)

    Theoretical foundation:
        Information retrieval semantic distance approach: direct inversion of SBERT
        cosine similarity (soft_match) to represent candidate deficit, without
        proficiency modeling or requirement depth estimation.
    """

    def __init__(
        self,
        name: str = "B-SimGap",
        priority_policy: Optional[PriorityPolicy] = None,
        alignment_fn: Optional[Callable[[float], SemanticAlignment]] = None,
    ) -> None:
        self._name = name
        self._priority_policy = priority_policy or WeightTimesGapPolicy()
        self._alignment_fn = alignment_fn

        fields = {
            BaselineOutputField.GAP_MAGNITUDE,
            BaselineOutputField.PRIORITY,
        }
        if self._alignment_fn is not None:
            fields.add(BaselineOutputField.ALIGNMENT)
        self._produces = frozenset(fields)

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._produces

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        match_map = build_match_map(input_data.match_results)
        results: List[BaselineSkillResult] = []

        for jd_skill in input_data.jd_skills:
            match = match_map.get(jd_skill.skill_id)
            soft_match = match.soft_match if match is not None else 0.0
            w_j = match.w_j if match is not None else 0.0

            # gap_magnitude = clamp(1 - soft_match, 0, 1)
            raw_gap = 1.0 - soft_match
            gap_magnitude = min(1.0, max(0.0, float(raw_gap)))

            priority = self._priority_policy.compute_priority(
                w_j=w_j,
                gap_magnitude=gap_magnitude,
            )

            alignment = (
                self._alignment_fn(soft_match)
                if self._alignment_fn is not None
                else None
            )

            results.append(
                BaselineSkillResult(
                    jd_skill_id=jd_skill.skill_id,
                    semantic_alignment=alignment,
                    required_proficiency=None,
                    candidate_proficiency=None,
                    gap_magnitude=gap_magnitude,
                    priority=priority,
                    metadata={
                        "baseline_name": self._name,
                        "soft_match": soft_match,
                        "w_j": w_j,
                    },
                )
            )

        return results
