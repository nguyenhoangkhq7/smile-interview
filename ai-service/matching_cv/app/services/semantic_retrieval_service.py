"""Semantic retrieval service computing raw cosine similarity matrices and deterministic Top-K rankings."""
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from matching_cv.app.schemas.semantic_representation import (
    EmbeddingRecord,
    SemanticSimilarityPair,
    SimilarityMatrix,
    TopKRetrievalResult,
)

logger = logging.getLogger(__name__)


class SemanticRetrievalService:
    """Service computing cosine similarity matrices and deterministic Top-K candidate retrievals."""

    @staticmethod
    def compute_cosine_matrix(
        source_vectors: np.ndarray,
        target_vectors: np.ndarray,
        source_records: List[EmbeddingRecord],
        target_records: List[EmbeddingRecord],
        expected_dim: Optional[int] = None,
    ) -> SimilarityMatrix:
        """
        Compute full cosine similarity matrix in [-1.0, 1.0] between two L2-normalized vector sets.
        Validates 2D shapes, vector dimensions, finite values, non-zero norms, and L2 normalization.
        Stores unrounded full-precision scores in raw_matrix and 4-decimal presentation scores in matrix.
        """
        n_source = len(source_records)
        n_target = len(target_records)

        # Clean behavior for empty inputs on either side
        if n_source == 0 or n_target == 0 or source_vectors.size == 0 or target_vectors.size == 0:
            empty_matrix: List[List[float]] = [] if n_source == 0 else [[] for _ in range(n_source)]
            return SimilarityMatrix(
                source_ids=[r.embedding_id for r in source_records],
                target_ids=[r.embedding_id for r in target_records],
                source_labels=[r.source_text for r in source_records],
                target_labels=[r.source_text for r in target_records],
                matrix=empty_matrix,
                raw_matrix=empty_matrix,
            )

        # 1. 2D shape validation
        if source_vectors.ndim != 2:
            raise ValueError(
                f"source_vectors must be a 2D array, got ndim={source_vectors.ndim} (shape={source_vectors.shape})"
            )
        if target_vectors.ndim != 2:
            raise ValueError(
                f"target_vectors must be a 2D array, got ndim={target_vectors.ndim} (shape={target_vectors.shape})"
            )

        # 2. Row count matching records
        if source_vectors.shape[0] != n_source:
            raise ValueError(
                f"source_vectors row count ({source_vectors.shape[0]}) does not match source_records count ({n_source})"
            )
        if target_vectors.shape[0] != n_target:
            raise ValueError(
                f"target_vectors row count ({target_vectors.shape[0]}) does not match target_records count ({n_target})"
            )

        # 3. Vector dimension matching
        if source_vectors.shape[1] != target_vectors.shape[1]:
            raise ValueError(
                f"Vector dimension mismatch between source ({source_vectors.shape[1]}) and target ({target_vectors.shape[1]})"
            )
        if expected_dim is not None and source_vectors.shape[1] != expected_dim:
            raise ValueError(f"Expected vector dimension {expected_dim}, got {source_vectors.shape[1]}")

        # 4. Finite values (no NaN or Inf)
        if not np.all(np.isfinite(source_vectors)):
            raise ValueError("source_vectors contains non-finite values (NaN or Inf)")
        if not np.all(np.isfinite(target_vectors)):
            raise ValueError("target_vectors contains non-finite values (NaN or Inf)")

        # 5. Non-zero norms and L2 normalization verification
        source_norms = np.linalg.norm(source_vectors, axis=1)
        target_norms = np.linalg.norm(target_vectors, axis=1)

        if np.any(source_norms < 1e-6):
            raise ValueError("source_vectors contains zero or near-zero norm vectors")
        if np.any(target_norms < 1e-6):
            raise ValueError("target_vectors contains zero or near-zero norm vectors")

        if not np.allclose(source_norms, 1.0, atol=1e-3):
            raise ValueError("source_vectors are not L2-normalized (vector norms must equal 1.0)")
        if not np.allclose(target_norms, 1.0, atol=1e-3):
            raise ValueError("target_vectors are not L2-normalized (vector norms must equal 1.0)")

        # Dot product of normalized unit vectors = cosine similarity
        sim_matrix_raw = np.dot(source_vectors, target_vectors.T)

        # Numerical safety: clip floating point inaccuracies strictly to [-1.0, 1.0]
        sim_matrix_raw = np.clip(sim_matrix_raw, -1.0, 1.0)

        raw_matrix = [[float(val) for val in row] for row in sim_matrix_raw]
        matrix_list = [[round(float(val), 4) for val in row] for row in sim_matrix_raw]

        return SimilarityMatrix(
            source_ids=[r.embedding_id for r in source_records],
            target_ids=[r.embedding_id for r in target_records],
            source_labels=[r.source_text for r in source_records],
            target_labels=[r.source_text for r in target_records],
            matrix=matrix_list,
            raw_matrix=raw_matrix,
        )

    @staticmethod
    def retrieve_top_k(
        source_records: List[EmbeddingRecord],
        target_records: List[EmbeddingRecord],
        similarity_matrix: SimilarityMatrix,
        top_k: int = 5,
    ) -> List[TopKRetrievalResult]:
        """
        Perform deterministic Top-K candidate retrieval for each source query item.
        Ranking order:
        1. Cosine similarity descending using FULL-PRECISION raw scores.
        2. Target label alphabetical ascending (tie-breaker).
        3. Target embedding ID alphabetical ascending (secondary tie-breaker).
        """
        if not source_records or not target_records:
            return []

        # Prefer full-precision raw_matrix if available, falling back to matrix
        scores_matrix = similarity_matrix.raw_matrix or similarity_matrix.matrix
        if not scores_matrix:
            return []

        results: List[TopKRetrievalResult] = []

        for row_idx, src in enumerate(source_records):
            if row_idx >= len(scores_matrix):
                continue
            row_scores = scores_matrix[row_idx]
            if len(row_scores) != len(target_records):
                continue

            candidates_with_scores: List[Tuple[float, str, str]] = []  # (raw_score, label, id)
            for col_idx, tgt in enumerate(target_records):
                raw_score = float(row_scores[col_idx])
                candidates_with_scores.append((raw_score, tgt.source_text, tgt.embedding_id))

            # Deterministic sort using full-precision raw_score descending
            candidates_with_scores.sort(key=lambda x: (-x[0], x[1].casefold(), x[2]))

            selected_pairs: List[SemanticSimilarityPair] = []
            for rank_idx, (raw_score, tgt_label, tgt_id) in enumerate(candidates_with_scores[:top_k], start=1):
                selected_pairs.append(
                    SemanticSimilarityPair(
                        source_id=src.embedding_id,
                        target_id=tgt_id,
                        source_label=src.source_text,
                        target_label=tgt_label,
                        cosine_similarity=round(raw_score, 4),
                        raw_score=raw_score,
                        rank=rank_idx,
                    )
                )

            results.append(
                TopKRetrievalResult(
                    query_id=src.embedding_id,
                    query_label=src.source_text,
                    candidates=selected_pairs,
                )
            )

        return results


semantic_retrieval_service = SemanticRetrievalService()
