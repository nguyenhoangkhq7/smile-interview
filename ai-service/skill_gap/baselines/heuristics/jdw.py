from typing import List
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.heuristics.utils import build_match_map


class JDWBaseline(BaselineMethod):
    """
    Job Description Weight Only reference baseline (B-JDW).

    Mathematical formulation:
        Priority = w_j
        gap_magnitude = None (does not estimate candidate gap)

    Theoretical foundation:
        Static prioritization reference check: interviews questions are ordered
        purely by the structural importance (w_j) of the skill in the job description,
        completely ignoring the candidate's CV.
    """

    def __init__(self, name: str = "B-JDW") -> None:
        self._name = name
        self._produces = frozenset({BaselineOutputField.PRIORITY})

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
            w_j = match.w_j if match is not None else 0.0
            priority = min(1.0, max(0.0, float(w_j)))

            results.append(
                BaselineSkillResult(
                    jd_skill_id=jd_skill.skill_id,
                    semantic_alignment=None,
                    required_proficiency=None,
                    candidate_proficiency=None,
                    gap_magnitude=None,
                    priority=priority,
                    metadata={
                        "baseline_name": self._name,
                        "w_j": w_j,
                    },
                )
            )

        return results
