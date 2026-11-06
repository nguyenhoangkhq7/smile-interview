from typing import List, Optional, Set
from src.domain.enums import SemanticAlignment
from src.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from src.baselines.heuristics.utils import build_match_map
from src.baselines.priority_policies import PriorityPolicy, WeightTimesGapPolicy


class BinaryExactBaseline(BaselineMethod):
    """
    Exact-match heuristic baseline (B-Binary).

    Mathematical formulation:
        gap_magnitude = 0.0 if jd_skill_id in cv_skill_ids else 1.0
        semantic_alignment = MATCH if jd_skill_id in cv_skill_ids else MISSING
        Priority = w_j * gap_magnitude (via WeightTimesGapPolicy)

    Theoretical foundation:
        Lexical exact-match heuristic: verifies verbatim skill ID presence in candidate
        extracted skills without semantic substitution (PARTIAL) and without soft_match.
    """

    def __init__(
        self,
        name: str = "B-Binary",
        priority_policy: Optional[PriorityPolicy] = None,
    ) -> None:
        self._name = name
        self._priority_policy = priority_policy or WeightTimesGapPolicy()
        self._produces = frozenset(
            {
                BaselineOutputField.ALIGNMENT,
                BaselineOutputField.GAP_MAGNITUDE,
                BaselineOutputField.PRIORITY,
            }
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._produces

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        cv_skill_ids: Set[str] = {s.skill_id for s in input_data.cv_skills}
        match_map = build_match_map(input_data.match_results)
        results: List[BaselineSkillResult] = []

        for jd_skill in input_data.jd_skills:
            is_present = jd_skill.skill_id in cv_skill_ids
            gap_magnitude = 0.0 if is_present else 1.0
            alignment = (
                SemanticAlignment.MATCH if is_present else SemanticAlignment.MISSING
            )

            match = match_map.get(jd_skill.skill_id)
            w_j = match.w_j if match is not None else 0.0

            priority = self._priority_policy.compute_priority(
                w_j=w_j,
                gap_magnitude=gap_magnitude,
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
                        "is_exact_matched": is_present,
                        "w_j": w_j,
                    },
                )
            )

        return results
