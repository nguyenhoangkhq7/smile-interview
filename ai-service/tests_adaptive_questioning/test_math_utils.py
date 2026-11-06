"""
Unit tests for Stage 1 mathematical invariants (Prior Mapping, TV Distance,
Simplex Convex Interpolation, and Expected Proficiency).
"""

import math
import pytest

from adaptive_questioning.config import CENTROIDS, CONVERGENCE_PROB_THRESHOLD, TAU_PRIOR
from adaptive_questioning.core.math_utils import (
    expected_proficiency,
    map_rubric_level,
    simplex_convex_update_detailed,
    temperature_softmax_prior,
    tv_distance,
    verified_skill_gap,
)
from adaptive_questioning.schemas.state import MetamorphicTag, RubricLevel


class TestTemperatureSoftmaxPrior:
    """Verify Prior Belief Initialization B_0 on the Probability Simplex."""

    @pytest.mark.parametrize("s_cv", [0.0, 1.0, 1.5, 2.2, 3.0, 3.8, 4.5, 5.0])
    def test_prior_simplex_sum_and_prevent_turn1_saturation(self, s_cv: float):
        """
        Verify:
        1) sum(B_0) == 1.0
        2) All probabilities in (0, 1)
        3) max(B_0) < 0.75 (tau_prior = 2.0 prevents premature Turn-1 saturation)
        """
        b0 = temperature_softmax_prior(s_cv)
        assert len(b0) == 3
        assert math.isclose(sum(b0), 1.0, rel_tol=1e-12, abs_tol=1e-12)
        assert all(0.0 < p < 1.0 for p in b0)
        assert max(b0) < CONVERGENCE_PROB_THRESHOLD

    def test_prior_at_exact_centroid_1_5(self):
        """Verify exact analytical values at s_cv = 1.5 with tau_prior = 2.0."""
        b0 = temperature_softmax_prior(1.5, centroids=CENTROIDS, tau_prior=TAU_PRIOR)
        # Distances: |1.5 - 1.5| = 0, |1.5 - 3.0| = 1.5, |1.5 - 4.5| = 3.0
        w0 = math.exp(0.0)
        w1 = math.exp(-1.5 / 2.0)
        w2 = math.exp(-3.0 / 2.0)
        z = w0 + w1 + w2
        expected = [w0 / z, w1 / z, w2 / z]

        for actual, exp in zip(b0, expected):
            assert math.isclose(actual, exp, rel_tol=1e-9)
        assert b0[0] > b0[1] > b0[2]
        assert b0[0] < 0.75  # ~0.5900 < 0.75

    def test_prior_symmetry_at_3_0(self):
        """At s_cv = 3.0 (Med centroid), Low and High probabilities must be symmetric."""
        b0 = temperature_softmax_prior(3.0)
        assert math.isclose(b0[0], b0[2], rel_tol=1e-12)
        assert b0[1] > b0[0]

    def test_invalid_tau_prior_raises(self):
        with pytest.raises(ValueError):
            temperature_softmax_prior(3.0, tau_prior=0.0)


class TestTVDistanceAndSimplexConvexUpdate:
    """Verify Total Variation distance and Calibrated PBA Simplex Convex Update."""

    def test_tv_distance_properties(self):
        p = [1.0, 0.0, 0.0]
        q = [0.0, 0.0, 1.0]
        assert math.isclose(tv_distance(p, p), 0.0, abs_tol=1e-12)
        assert math.isclose(tv_distance(p, q), 1.0, abs_tol=1e-12)
        assert math.isclose(tv_distance(p, q), tv_distance(q, p), abs_tol=1e-12)

    def test_invariant_tag_keeps_belief_unchanged(self):
        """INVARIANT -> delta_max = 0.00 -> alpha_t = 0.0 -> P_t == P_{t-1}."""
        p_prev = temperature_softmax_prior(2.2)
        p_raw = [0.01, 0.04, 0.95]  # Extreme raw shift proposed by LLM
        p_updated, tv_raw, alpha_t, tv_delta = simplex_convex_update_detailed(
            p_prev, p_raw, MetamorphicTag.INVARIANT
        )
        assert tv_raw > 0.4
        assert alpha_t == 0.0
        assert tv_delta == 0.0
        for u, prev in zip(p_updated, p_prev):
            assert math.isclose(u, prev, abs_tol=1e-12)

    @pytest.mark.parametrize(
        "tag,delta_max",
        [
            (MetamorphicTag.INVARIANT, 0.00),
            (MetamorphicTag.MINOR_SHIFT, 0.12),
            (MetamorphicTag.MODERATE_SHIFT, 0.25),
            (MetamorphicTag.DECISIVE_SHIFT, 0.45),
        ],
    )
    def test_simplex_convex_update_bounds_tv_and_preserves_simplex(
        self, tag: MetamorphicTag, delta_max: float
    ):
        """
        Verify for all Metamorphic Tags:
        1) sum(P_t) == 1.0
        2) TV(P_t, P_{t-1}) <= delta_max
        3) When TV_raw > delta_max, TV(P_t, P_{t-1}) == delta_max exactly
        """
        p_prev = temperature_softmax_prior(2.2)
        p_raw = [0.0, 0.0, 1.0]  # Extreme shift so TV_raw > 0.45

        p_updated, tv_raw, alpha_t, tv_delta = simplex_convex_update_detailed(p_prev, p_raw, tag)

        assert math.isclose(sum(p_updated), 1.0, abs_tol=1e-12)
        assert all(0.0 <= x <= 1.0 for x in p_updated)
        assert tv_delta <= delta_max + 1e-12
        assert math.isclose(tv_delta, delta_max, abs_tol=1e-9)

    def test_small_raw_shift_passes_through_with_alpha_one(self):
        """When TV_raw <= delta_max, alpha_t == 1.0 and P_t == P_t^raw."""
        p_prev = [0.30, 0.50, 0.20]
        p_raw = [0.25, 0.55, 0.20]  # TV_raw = 0.05 <= 0.12 (MINOR_SHIFT)
        p_updated, tv_raw, alpha_t, tv_delta = simplex_convex_update_detailed(
            p_prev, p_raw, MetamorphicTag.MINOR_SHIFT
        )
        assert math.isclose(tv_raw, 0.05, abs_tol=1e-9)
        assert math.isclose(alpha_t, 1.0, abs_tol=1e-9)
        assert math.isclose(tv_delta, 0.05, abs_tol=1e-9)
        for u, r in zip(p_updated, p_raw):
            assert math.isclose(u, r, abs_tol=1e-9)


class TestExpectedProficiencyAndRubricMapping:
    """Verify Phase 4 expectation over centroids and MAP Rubric Level."""

    def test_expected_proficiency_at_vertices_and_uniform(self):
        assert math.isclose(expected_proficiency([1.0, 0.0, 0.0]), 1.5, abs_tol=1e-9)
        assert math.isclose(expected_proficiency([0.0, 1.0, 0.0]), 3.0, abs_tol=1e-9)
        assert math.isclose(expected_proficiency([0.0, 0.0, 1.0]), 4.5, abs_tol=1e-9)
        assert math.isclose(expected_proficiency([1 / 3, 1 / 3, 1 / 3]), 3.0, abs_tol=1e-9)

    def test_map_rubric_level(self):
        assert map_rubric_level([0.70, 0.20, 0.10]) == RubricLevel.LOW
        assert map_rubric_level([0.15, 0.65, 0.20]) == RubricLevel.MED
        assert map_rubric_level([0.05, 0.15, 0.80]) == RubricLevel.HIGH

    def test_verified_skill_gap(self):
        assert math.isclose(verified_skill_gap(4.0, 2.8), 1.2, abs_tol=1e-9)
        assert math.isclose(verified_skill_gap(3.5, 4.2), 0.0, abs_tol=1e-9)
