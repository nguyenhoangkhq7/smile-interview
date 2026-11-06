import random
from typing import List, Optional
from src.domain.enums import SemanticAlignment
from src.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)


class RandomBaseline(BaselineMethod):
    """
    Random Uniform reference baseline (B-Random).

    Mathematical formulation:
        gap_magnitude ~ Uniform(0.0, 1.0)
        Priority ~ Uniform(0.0, 1.0)
        P_JD ~ Uniform(1.0, 5.0)
        P_CV ~ Uniform(1.0, 5.0)
        semantic_alignment ~ Uniform({MATCH, PARTIAL, MISSING})

    Theoretical foundation:
        Lower-bound sanity check: guarantees that any proposed or adapted
        model achieves statistically significant improvement over chance.
        Uses an isolated random.Random instance (no global RNG contamination).
    """

    def __init__(self, name: str = "B-Random", seed: Optional[int] = 42) -> None:
        self._name = name
        self._seed = seed
        self._produces = frozenset(
            {
                BaselineOutputField.ALIGNMENT,
                BaselineOutputField.P_JD,
                BaselineOutputField.P_CV,
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
        # Isolated pseudo-random generator initialized with the configured seed
        rng = random.Random(self._seed)
        results: List[BaselineSkillResult] = []

        alignment_choices = [
            SemanticAlignment.MATCH,
            SemanticAlignment.PARTIAL,
            SemanticAlignment.MISSING,
        ]

        for jd_skill in input_data.jd_skills:
            gap = rng.uniform(0.0, 1.0)
            priority = rng.uniform(0.0, 1.0)
            p_jd = rng.uniform(1.0, 5.0)
            p_cv = rng.uniform(1.0, 5.0)
            alignment = rng.choice(alignment_choices)

            results.append(
                BaselineSkillResult(
                    jd_skill_id=jd_skill.skill_id,
                    semantic_alignment=alignment,
                    required_proficiency=p_jd,
                    candidate_proficiency=p_cv,
                    gap_magnitude=gap,
                    priority=priority,
                    metadata={
                        "baseline_name": self._name,
                        "seed": self._seed,
                    },
                )
            )

        return results
