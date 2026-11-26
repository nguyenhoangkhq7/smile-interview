"""Job-Level Salience Scorer (Component F).

Estimates S_job(skill) by combining:
1. SBERT semantic similarity between skill and the canonical Job Title.
2. SBERT semantic similarity between skill and the requirements centroid vector.
3. Leave-One-Out (LOO) centroid calculation to eliminate self-influence.

Strict invariants:
- If Job Title is available:
    S_job = config.job_title_weight * title_sim + config.job_req_weight * req_sim
- If Job Title is unavailable:
    S_job = req_sim (renormalized to 100% requirements centroid) with is_title_available = False.
- Raw cosine is linearly mapped to [0, 1] via (cos + 1.0) / 2.0.
- Preserves both full requirements similarity and LOO similarity in JobSalienceResult.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import numpy as np

from matching_cv.app.services.semantic_embedding_service import semantic_embedding_service
from matching_cv.research.skill_importance.config import JSIConfig, default_jsi_config
from matching_cv.research.skill_importance.models import JobSalienceResult


class JobSalienceScorer:
    """Estimates the macro-level salience of a skill relative to the entire job."""

    def __init__(self, config: Optional[JSIConfig] = None) -> None:
        self.config = config or default_jsi_config
        self.sbert = semantic_embedding_service._get_model()

        # Context state
        self._job_title: Optional[str] = None
        self._title_embedding: Optional[np.ndarray] = None
        self._requirement_sentences: List[str] = []
        self._req_embeddings: Optional[np.ndarray] = None  # Shape: (N, 768)
        self._full_centroid: Optional[np.ndarray] = None    # Shape: (768,)

    def prepare_context(
        self,
        job_title: Optional[str],
        requirement_sentences: Sequence[str],
    ) -> None:
        """
        Precompute SBERT embeddings for Job Title and requirement sentences.
        Calculates the full requirements centroid.
        """
        # Job Title
        clean_title = job_title.strip() if job_title else None
        if clean_title:
            self._job_title = clean_title
            emb = self.sbert.encode(clean_title, normalize_embeddings=True)
            self._title_embedding = np.asarray(emb, dtype=np.float32)
        else:
            self._job_title = None
            self._title_embedding = None

        # Requirement sentences
        valid_sentences = [s.strip() for s in requirement_sentences if s and len(s.strip()) > 3]
        self._requirement_sentences = valid_sentences

        if valid_sentences:
            embs = self.sbert.encode(valid_sentences, normalize_embeddings=True)
            self._req_embeddings = np.asarray(embs, dtype=np.float32)
            # Full centroid: average of all requirement vectors
            raw_centroid = np.mean(self._req_embeddings, axis=0)
            norm = float(np.linalg.norm(raw_centroid))
            if norm > 1e-12:
                self._full_centroid = raw_centroid / norm
            else:
                self._full_centroid = raw_centroid
        else:
            self._req_embeddings = None
            self._full_centroid = None

    def _compute_loo_centroid(
        self,
        excluded_sentences: Sequence[str],
    ) -> Optional[np.ndarray]:
        """
        Compute Leave-One-Out (LOO) centroid vector by omitting sentences matching excluded_sentences.
        If no sentences remain, falls back to full centroid.
        """
        if self._req_embeddings is None or len(self._requirement_sentences) == 0:
            return None

        excluded_set: Set[str] = {s.strip().lower() for s in excluded_sentences if s}
        if not excluded_set:
            return self._full_centroid

        # Identify indices to keep
        keep_indices: List[int] = [
            i for i, s in enumerate(self._requirement_sentences)
            if s.lower() not in excluded_set
        ]

        if not keep_indices:
            # All sentences excluded; fall back to full centroid
            return self._full_centroid

        loo_subset = self._req_embeddings[keep_indices]
        raw_centroid = np.mean(loo_subset, axis=0)
        norm = float(np.linalg.norm(raw_centroid))
        if norm > 1e-12:
            return raw_centroid / norm
        return raw_centroid

    @staticmethod
    def _cosine_to_sim(v1: np.ndarray, v2: np.ndarray) -> Tuple[float, float]:
        """Compute cosine similarity and map linearly to [0, 1]."""
        dot = float(np.dot(v1, v2))
        n1 = float(np.linalg.norm(v1))
        n2 = float(np.linalg.norm(v2))
        cos = dot / (n1 * n2 + 1e-12)
        cos = max(-1.0, min(1.0, cos))
        sim = max(0.0, min(1.0, (cos + 1.0) / 2.0))
        return cos, sim

    def score_skill(
        self,
        skill_display_name: str,
        evidence_sentences: Optional[Sequence[str]] = None,
        skill_embedding: Optional[np.ndarray] = None,
    ) -> JobSalienceResult:
        """
        Compute Job-level salience for a skill entity.
        Calculates:
        - title_similarity (if title available)
        - requirements_similarity (full centroid)
        - loo_requirements_similarity (LOO centroid omitting skill evidence)
        - job_salience
        """
        clean_skill = skill_display_name.strip()
        if skill_embedding is None:
            emb = self.sbert.encode(clean_skill, normalize_embeddings=True)
            skill_vec = np.asarray(emb, dtype=np.float32)
        else:
            skill_vec = np.asarray(skill_embedding, dtype=np.float32)

        # 1. Title Similarity
        is_title_avail = self._title_embedding is not None
        title_sim: Optional[float] = None
        if is_title_avail:
            _, t_sim = self._cosine_to_sim(skill_vec, self._title_embedding)
            title_sim = round(t_sim, 6)

        # 2. Requirements Centroid Similarity (Full)
        if self._full_centroid is not None:
            _, full_req_sim = self._cosine_to_sim(skill_vec, self._full_centroid)
            req_sim = round(full_req_sim, 6)
        else:
            # No requirements sentences found in JD
            req_sim = 0.50

        # 3. LOO Requirements Similarity
        loo_req_sim: Optional[float] = None
        if self._req_embeddings is not None and len(self._requirement_sentences) > 0:
            loo_centroid = self._compute_loo_centroid(evidence_sentences or [])
            if loo_centroid is not None:
                _, loo_sim = self._cosine_to_sim(skill_vec, loo_centroid)
                loo_req_sim = round(loo_sim, 6)

        # Effective requirements similarity to use for S_job:
        # Prefer LOO similarity to avoid self-influence; fall back to full if LOO unavailable
        effective_req_sim = loo_req_sim if loo_req_sim is not None else req_sim

        # 4. Aggregation into S_job
        if is_title_avail and title_sim is not None:
            # Both Title and Requirements available
            w_title = self.config.job_title_weight
            w_req = self.config.job_req_weight
            # Ensure proper proportion
            job_score = (w_title * title_sim) + (w_req * effective_req_sim)
        else:
            # Title unavailable: renormalize 100% to requirements
            job_score = effective_req_sim

        job_score = max(0.0, min(1.0, job_score))

        return JobSalienceResult(
            title_similarity=title_sim,
            requirements_similarity=req_sim,
            loo_requirements_similarity=loo_req_sim,
            is_title_available=is_title_avail,
            job_salience=round(job_score, 6),
        )
