"""
Scientific mathematical functions for Pipeline V2.2 powered by `numpy` and `scipy`:
  - Prior Belief Initialization via `scipy.special.softmax`
  - Total Variation Distance via `scipy.spatial.distance.cityblock` (0.5 * L1 distance)
  - Calibrated PBA Simplex Convex Interpolation via vectorized `numpy` operations
  - Expected Proficiency & MAP Rubric Level via `numpy.dot` and `numpy.argmax`
"""

from typing import Dict, List, Sequence, Tuple, Union

import numpy as np
from scipy.spatial.distance import cityblock
from scipy.special import softmax

from adaptive_questioning.config import CENTROIDS, DELTA_BOUNDS, RUBRIC_LEVELS, TAU_PRIOR
from adaptive_questioning.schemas.state import MetamorphicTag, RubricLevel


def normalize_simplex(probs: Sequence[float]) -> List[float]:
    """Project / normalize a non-negative vector onto the probability simplex using NumPy."""
    arr = np.asarray(probs, dtype=np.float64)
    if arr.shape != (len(CENTROIDS),):
        raise ValueError(
            f"Expected probability vector of length {len(CENTROIDS)}, got {arr.shape}"
        )

    clamped = np.clip(arr, a_min=0.0, a_max=None)
    total = float(np.sum(clamped))
    if total <= 1e-12:
        n = len(CENTROIDS)
        return [1.0 / n] * n

    normalized = clamped / total
    # Correct minor floating-point residual on the last component
    normalized[-1] = max(0.0, 1.0 - float(np.sum(normalized[:-1])))
    final_sum = float(np.sum(normalized))
    if abs(final_sum - 1.0) > 1e-15:
        normalized = normalized / final_sum
    return [float(x) for x in normalized]


def temperature_softmax_prior(
    s_cv: float,
    centroids: Sequence[float] = CENTROIDS,
    tau_prior: float = TAU_PRIOR,
) -> List[float]:
    """
    Map candidate_proficiency (s_cv) to prior probability distribution B_0 = [P_0(Low), P_0(Med), P_0(High)]
    via Temperature-Scaled Distance Softmax (`scipy.special.softmax`):
        P_0(z_d = l) = exp(-|s_cv - c_l| / tau_prior) / sum_j exp(-|s_cv - c_j| / tau_prior)
    """
    if tau_prior <= 0.0:
        raise ValueError("tau_prior must be strictly positive.")

    c_arr = np.asarray(centroids, dtype=np.float64)
    logits = -np.abs(float(s_cv) - c_arr) / float(tau_prior)
    probs = softmax(logits)
    return normalize_simplex(probs.tolist())


def tv_distance(p: Sequence[float], q: Sequence[float]) -> float:
    """
    Compute Total Variation (TV) distance between two discrete distributions on the simplex
    using `scipy.spatial.distance.cityblock` (Manhattan / L1 distance):
        TV(P, Q) = 0.5 * ||P - Q||_1
    """
    p_arr = np.asarray(p, dtype=np.float64)
    q_arr = np.asarray(q, dtype=np.float64)
    if p_arr.shape != q_arr.shape:
        raise ValueError(
            f"Length mismatch between p ({p_arr.shape}) and q ({q_arr.shape})"
        )
    return 0.5 * float(cityblock(p_arr, q_arr))


def compute_interpolation_alpha(
    tv_raw: float,
    tag: Union[MetamorphicTag, str],
    delta_bounds: Dict[str, float] = DELTA_BOUNDS,
) -> float:
    """
    Compute bounded interpolation weight alpha_t in [0, 1]:
        alpha_t = 0.0 if Tag == INVARIANT or TV_raw == 0
        alpha_t = min(1.0, delta_max / TV_raw) otherwise
    """
    tag_key = tag.value if isinstance(tag, MetamorphicTag) else str(tag)
    if tag_key not in delta_bounds:
        raise ValueError(f"Unknown MetamorphicTag: {tag_key}")

    delta_max = delta_bounds[tag_key]
    if tag_key == MetamorphicTag.INVARIANT.value or tv_raw <= 1e-12 or delta_max <= 0.0:
        return 0.0

    return float(min(1.0, float(delta_max) / float(tv_raw)))


def simplex_convex_update(
    p_prev: Sequence[float],
    p_raw: Sequence[float],
    tag: Union[MetamorphicTag, str],
    delta_bounds: Dict[str, float] = DELTA_BOUNDS,
) -> List[float]:
    """
    Update posterior belief via Calibrated PBA Simplex Convex Interpolation:
        P_t = (1 - alpha_t) * P_{t-1} + alpha_t * P_t^{raw}
    Guarantees sum_l P_t(l) = 1.0 and TV(P_t, P_{t-1}) <= delta_max without non-linear clipping distortion.
    """
    updated, _, _, _ = simplex_convex_update_detailed(p_prev, p_raw, tag, delta_bounds)
    return updated


def simplex_convex_update_detailed(
    p_prev: Sequence[float],
    p_raw: Sequence[float],
    tag: Union[MetamorphicTag, str],
    delta_bounds: Dict[str, float] = DELTA_BOUNDS,
) -> Tuple[List[float], float, float, float]:
    """
    Perform vectorized Simplex Convex Interpolation with NumPy and return:
        (p_updated, tv_raw, alpha_t, tv_delta)
    """
    p_prev_norm = np.asarray(normalize_simplex(p_prev), dtype=np.float64)
    p_raw_norm = np.asarray(normalize_simplex(p_raw), dtype=np.float64)

    tv_raw = tv_distance(p_raw_norm, p_prev_norm)
    alpha_t = compute_interpolation_alpha(tv_raw, tag, delta_bounds)

    if alpha_t == 0.0:
        return p_prev_norm.tolist(), tv_raw, 0.0, 0.0

    p_updated_arr = (1.0 - alpha_t) * p_prev_norm + alpha_t * p_raw_norm
    p_updated = normalize_simplex(p_updated_arr.tolist())
    tv_delta = tv_distance(p_updated, p_prev_norm)
    return p_updated, tv_raw, alpha_t, tv_delta


def expected_proficiency(
    probs: Sequence[float],
    centroids: Sequence[float] = CENTROIDS,
) -> float:
    """
    Compute Verified Proficiency Score (s_hat_final) on the 5.0 scale via inner product (`numpy.dot`):
        s_hat_final = 1.5 * P_T(Low) + 3.0 * P_T(Med) + 4.5 * P_T(High)
    """
    p_norm = np.asarray(normalize_simplex(probs), dtype=np.float64)
    c_arr = np.asarray(centroids, dtype=np.float64)
    return float(np.dot(c_arr, p_norm))


def map_rubric_level(probs: Sequence[float]) -> RubricLevel:
    """
    Compute Maximum A Posteriori (MAP) Rubric Level via `numpy.argmax`:
        z_hat_d = arg max_{l in {Low, Med, High}} P_T(l)
    """
    p_norm = np.asarray(normalize_simplex(probs), dtype=np.float64)
    best_idx = int(np.argmax(p_norm))
    return RubricLevel(RUBRIC_LEVELS[best_idx])


def verified_skill_gap(s_jd: float, s_hat_final: float) -> float:
    """
    Compute Verified Skill Gap:
        Verified_Gap = max(0.0, s_jd - s_hat_final)
    """
    return float(max(0.0, float(s_jd) - float(s_hat_final)))
