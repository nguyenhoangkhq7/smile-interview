"""JSI-4 Hardened JD Skill Importance Estimator (v4).

Integrates:
1. Document Layout & Structure Remediation (Phase E).
2. Competency Eligibility Gating (Phase B).
3. Context-Sensitive Requirement Semantics & Group Detection (Phase C).
4. Anchor-Aware Multi-Resolution Salience Aggregation (Phase D).

Maintains V1 (JSI-2 Baseline), V2 (Gated), V3 (Semantics), and V4 (Full Hardened)
for controlled ablation comparisons.

Strict Invariants:
- Preserves output score bounds [0.10, 1.00] via fixed monotonic mapping.
- Gating excludes non-competency actor mentions ('backend engineers') and hardware targets ('tablet').
- Zero modifications to production inference services, GNN architecture, or checkpoints.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
import numpy as np

from matching_cv.app.services.semantic_embedding_service import semantic_embedding_service
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.unified_embedding_contract import canonical_id_to_display_name
from matching_cv.research.skill_importance.competency_gater import CompetencyEligibilityGater, EligibilityAuditRecord
from matching_cv.research.skill_importance.config import JSIConfig, default_jsi_config
from matching_cv.research.skill_importance.job_salience import JobSalienceScorer
from matching_cv.research.skill_importance.job_title_extractor import JobTitleExtractor
from matching_cv.research.skill_importance.layout_remediator import DocumentLayoutRemediator, RemediationResult
from matching_cv.research.skill_importance.models import (
    JDEstimationResult,
    JDSectionSpan,
    JobSalienceResult,
    JobTitleResult,
    SegmentSalienceResult,
    SentenceSalienceResult,
    SkillImportanceOutput,
    SkillImportanceProvenance,
    SkillImportanceScore,
    SkillSentenceOccurrence,
)
from matching_cv.research.skill_importance.requirement_semantics_parser import RequirementGroupInfo, RequirementSemanticsParser
from matching_cv.research.skill_importance.section_parser import JDSectionParser
from matching_cv.research.skill_importance.segment_salience import SegmentSalienceScorer
from matching_cv.research.skill_importance.sentence_mapper import SkillSentenceMapper
from matching_cv.research.skill_importance.sentence_salience import SentenceSalienceScorer

EstimatorVariant = Literal["V1_baseline", "V2_gated", "V3_semantics", "V4_hardened"]


class HardenedSkillImportanceAggregator:
    """Combines salience dimensions with anchor alignment and missing-dimension renormalization."""

    def __init__(self, config: Optional[JSIConfig] = None) -> None:
        self.config = config or default_jsi_config

    def aggregate(
        self,
        sentence_salience: float,
        segment_salience: Optional[float],
        job_salience: float,
        is_title_anchor: bool = False,
        occurrences: Optional[List[SkillSentenceOccurrence]] = None,
        job_title: Optional[str] = None,
        dimension_breakdown: Optional[Dict[str, Any]] = None,
        group_info: Optional[RequirementGroupInfo] = None,
        variant: EstimatorVariant = "V4_hardened",
    ) -> Tuple[SkillImportanceScore, SkillImportanceProvenance]:
        """
        Aggregate salience scores into final raw importance and transformed w_j.
        In V4_hardened, applies calibrated anchor alignment boost when skill is in job title.
        """
        raw_weights: Dict[str, float] = {}
        values: Dict[str, float] = {}
        available_dims: List[str] = []

        # 1. Sentence Salience
        if sentence_salience is not None:
            raw_weights["sentence"] = self.config.weight_sentence
            values["sentence"] = float(sentence_salience)
            available_dims.append("sentence")

        # 2. Segment Salience
        if segment_salience is not None:
            raw_weights["segment"] = self.config.weight_segment
            values["segment"] = float(segment_salience)
            available_dims.append("segment")

        # 3. Job Salience
        if job_salience is not None:
            raw_weights["job"] = self.config.weight_job
            # In V4, apply anchor alignment boost if skill explicitly appears in Job Title
            if variant == "V4_hardened" and is_title_anchor:
                # Direct technology anchor in job title receives a calibrated boost in Job Salience
                boosted_job = min(1.0, float(job_salience) * 1.25)
                values["job"] = boosted_job
            else:
                values["job"] = float(job_salience)
            available_dims.append("job")

        # Renormalize across available dimensions
        total_weight = sum(raw_weights.values())
        norm_weights = {k: w / total_weight for k, w in raw_weights.items()}
        raw_score = sum(norm_weights[k] * values[k] for k in available_dims)
        raw_score = max(0.0, min(1.0, raw_score))

        # Fixed monotonic transformation into [0.10, 1.00]
        w_j = self.config.scale_min + (self.config.scale_max * raw_score)
        w_j = max(0.10, min(1.00, round(w_j, 4)))

        score_contract = SkillImportanceScore(
            sentence_salience=round(sentence_salience, 6),
            segment_salience=round(segment_salience, 6) if segment_salience is not None else None,
            job_salience=round(values.get("job", job_salience), 6),
            importance_score_raw=round(raw_score, 6),
            w_j=w_j,
            available_dimensions=available_dims,
            normalization_method=self.config.normalization_method,
        )

        occ_list = occurrences or []
        src_sentences = list(dict.fromkeys(occ.source_sentence for occ in occ_list if occ.source_sentence))
        src_sections = list(dict.fromkeys(occ.section_type for occ in occ_list if occ.section_type))

        bd = dict(dimension_breakdown or {})
        if group_info:
            bd["requirement_group"] = group_info.model_dump()
        bd["is_title_anchor"] = is_title_anchor
        bd["estimator_variant"] = variant

        provenance_contract = SkillImportanceProvenance(
            source_sentences=src_sentences,
            source_sections=src_sections,
            job_title=job_title,
            scoring_version=f"jsi-4-{variant.lower()}",
            dimension_breakdown=bd,
        )

        return score_contract, provenance_contract


class JSI4HardenedEstimator:
    """Coordinator executing hardened skill importance estimation."""

    def __init__(self, config: Optional[JSIConfig] = None) -> None:
        self.config = config or default_jsi_config
        self.sbert = semantic_embedding_service._get_model()

        # Components
        self.layout_remediator = DocumentLayoutRemediator()
        self.section_parser = JDSectionParser()
        self.title_extractor = JobTitleExtractor()
        self.sentence_mapper = SkillSentenceMapper()
        self.competency_gater = CompetencyEligibilityGater()
        self.semantics_parser = RequirementSemanticsParser()
        self.sentence_salience_scorer = SentenceSalienceScorer(self.config)
        self.segment_salience_scorer = SegmentSalienceScorer(self.config)
        self.job_salience_scorer = JobSalienceScorer(self.config)
        self.aggregator = HardenedSkillImportanceAggregator(self.config)

    def _is_direct_title_anchor(self, skill_display_name: str, canonical_id: str, job_title: Optional[str]) -> bool:
        """Check if skill is explicitly present as an anchor technology in the Job Title."""
        if not job_title:
            return False
        clean_title = job_title.lower()
        clean_name = skill_display_name.lower().strip()
        clean_id = canonical_id.lower().strip().replace("_", "-")

        # Direct word boundary match in title
        if re.search(r"\b" + re.escape(clean_name) + r"\b", clean_title):
            return True
        if re.search(r"\b" + re.escape(clean_id) + r"\b", clean_title):
            return True

        # Special tech aliases (e.g. 'js' -> 'javascript', 'ts' -> 'typescript')
        if clean_id == "spring-boot" and "spring boot" in clean_title:
            return True
        if clean_id == "golang" and re.search(r"\bgo\b", clean_title):
            return True
        return False

    def estimate_importance(
        self,
        jd_text: str,
        explicit_skills: Sequence[Dict[str, Any]],
        implicit_skills: Sequence[Dict[str, Any]],
        job_title: Optional[str] = None,
        filename: Optional[str] = None,
        variant: EstimatorVariant = "V4_hardened",
        remediate_layout: bool = True,
    ) -> JDEstimationResult:
        """
        Execute skill importance estimation with configurable research variant:
        - V1_baseline: Original JSI-2
        - V2_gated: V1 + Competency Eligibility Gating
        - V3_semantics: V2 + Requirement Semantics & Group Detection
        - V4_hardened: Full Hardened (Layout Recovery + Gating + Semantics + Anchor Alignment)
        """
        # Step 0: Layout Remediation (if V4 or explicitly requested)
        if (variant == "V4_hardened" or remediate_layout) and jd_text:
            rem_res = self.layout_remediator.remediate_layout(jd_text)
            effective_jd_text = rem_res.remediated_text
        else:
            effective_jd_text = jd_text

        # Step 1: Section Parsing
        sections = self.section_parser.parse_sections(effective_jd_text)

        # Step 2: Job Title Extraction
        if job_title and job_title.strip():
            title_result = JobTitleResult(
                job_title=job_title.strip(),
                title_confidence=1.0,
                detection_method="explicit_parameter",
                detection_status="RESOLVED",
            )
        else:
            title_result = self.title_extractor.extract_title(effective_jd_text, filename)

        # Step 3: Sentence & Section Mapping
        occurrences_by_skill = self.sentence_mapper.map_skills_to_sentences(
            jd_text=effective_jd_text,
            explicit_skills=explicit_skills,
            implicit_skills=implicit_skills,
            sections=sections,
        )

        # Step 4: Requirement Sentences & Job Salience Context
        # Extract requirement sentences for centroid
        req_spans = [s for s in sections if s.section_type == "requirements"]
        target_spans = req_spans if req_spans else [s for s in sections if s.section_type == "responsibilities"]
        req_sentences: List[str] = []
        if target_spans:
            for span in target_spans:
                section_text = effective_jd_text[span.start : span.end]
                for line in section_text.splitlines():
                    cleaned = line.strip("-•* \t\r")
                    if len(cleaned) > 5:
                        req_sentences.append(cleaned)
        else:
            for line in effective_jd_text.splitlines():
                cleaned = line.strip("-•* \t\r")
                if len(cleaned) > 15:
                    req_sentences.append(cleaned)

        self.job_salience_scorer.prepare_context(
            job_title=title_result.job_title,
            requirement_sentences=req_sentences,
        )

        # Step 5: Merge unique skill entities
        skill_metadata_map: Dict[str, Dict[str, Any]] = {}
        for s in explicit_skills:
            raw_id = s.get("canonical_skill_id") or s.get("skill_id") or s.get("name")
            if raw_id:
                cid = normalize_canonical_skill(raw_id) or str(raw_id).strip().lower()
                skill_metadata_map[cid] = {
                    "canonical_skill_id": cid,
                    "skill_display_name": s.get("skill_display_name") or s.get("name") or cid,
                    "type": "explicit",
                }
        for s in implicit_skills:
            raw_id = s.get("canonical_skill_id") or s.get("skill_id") or s.get("name")
            if raw_id:
                cid = normalize_canonical_skill(raw_id) or str(raw_id).strip().lower()
                if cid not in skill_metadata_map:
                    skill_metadata_map[cid] = {
                        "canonical_skill_id": cid,
                        "skill_display_name": s.get("skill_display_name") or s.get("name") or cid,
                        "type": "implicit",
                    }

        # Precompute embeddings
        all_display_names = [m["skill_display_name"] for m in skill_metadata_map.values()]
        if all_display_names:
            skill_embs = self.sbert.encode(all_display_names, normalize_embeddings=True)
            emb_map = {name: np.asarray(emb, dtype=np.float32) for name, emb in zip(all_display_names, skill_embs)}
        else:
            emb_map = {}

        scored_skills: List[SkillImportanceOutput] = []

        for cid, meta in skill_metadata_map.items():
            display_name = meta["skill_display_name"]
            stype = meta["type"]
            occurrences = occurrences_by_skill.get(cid, [])
            skill_vec = emb_map.get(display_name)
            evidence_sentences = [occ.source_sentence for occ in occurrences]

            # --- Gating (V2, V3, V4) ---
            eligibility_record = self.competency_gater.evaluate_eligibility(
                canonical_skill_id=cid,
                skill_display_name=display_name,
                evidence_sentences=evidence_sentences,
                extraction_type=stype,
            )

            # In gated variants, if entity is not eligible, we flag it in provenance
            # (In research filtered output, ineligible entities can be suppressed from top-K)
            is_eligible = eligibility_record.is_eligible_for_ranking

            # --- Dimension 1: Sentence Salience ---
            sentence_results: List[SentenceSalienceResult] = []
            group_info: Optional[RequirementGroupInfo] = None
            req_modality_weight: float = 1.0

            if occurrences:
                for occ in occurrences:
                    # In V3 & V4, use RequirementSemanticsParser for context-sensitive modality
                    if variant in ("V3_semantics", "V4_hardened"):
                        sem_rec = self.semantics_parser.parse_requirement(
                            skill_name=display_name,
                            sentence=occ.source_sentence,
                            section_type=occ.section_type,
                        )
                        mod_cat = sem_rec.modality
                        mod_score = sem_rec.modality_weight
                        is_neg = sem_rec.polarity in ("NEGATED", "EXCLUDED")
                        if sem_rec.group_info:
                            group_info = sem_rec.group_info
                        req_modality_weight = mod_score

                        # SBERT cosine
                        sent_emb = self.sbert.encode(occ.source_sentence.strip(), normalize_embeddings=True)
                        cos = float(np.dot(skill_vec, sent_emb))
                        cos = max(-1.0, min(1.0, cos))
                        trans_sim = (cos + 1.0) / 2.0

                        # In V4, calibrate implicit skills: if implicit, don't penalize lack of literal token match
                        if variant == "V4_hardened" and stype == "implicit":
                            trans_sim = max(trans_sim, 0.65)

                        final_sent = 0.0 if is_neg else (0.50 * trans_sim + 0.50 * mod_score)
                        s_res = SentenceSalienceResult(
                            raw_cosine=round(cos, 6),
                            transformed_similarity=round(trans_sim, 6),
                            modality_category=mod_cat,
                            modality_score=round(mod_score, 4),
                            is_negated=is_neg,
                            sentence_salience=round(final_sent, 6),
                            matched_clause=sem_rec.matched_clause,
                        )
                    else:
                        # V1 and V2 use original sentence scorer
                        s_res = self.sentence_salience_scorer.score_sentence(
                            skill_display_name=display_name,
                            sentence=occ.source_sentence,
                            modifier_text=occ.modifier_text,
                            skill_embedding=skill_vec,
                        )
                    sentence_results.append(s_res)

                best_sentence_res = max(sentence_results, key=lambda r: r.sentence_salience)
                final_sentence_salience = best_sentence_res.sentence_salience
            else:
                best_sentence_res = None
                final_sentence_salience = 0.50

            # --- Dimension 2: Segment Salience ---
            seg_res = self.segment_salience_scorer.score_occurrences(occurrences)
            if seg_res.is_available and seg_res.segment_salience is not None:
                # In V4, interact segment prior with requirement modality
                if variant == "V4_hardened" and req_modality_weight < 0.50:
                    final_segment_salience = seg_res.segment_salience * req_modality_weight
                else:
                    final_segment_salience = seg_res.segment_salience
            else:
                final_segment_salience = None

            # --- Dimension 3: Job Salience ---
            job_res = self.job_salience_scorer.score_skill(
                skill_display_name=display_name,
                evidence_sentences=evidence_sentences,
                skill_embedding=skill_vec,
            )
            final_job_salience = job_res.job_salience

            # Title Anchor check (only valid technologies/competencies can be title anchors)
            is_anchor = (
                is_eligible and
                eligibility_record.eligibility_class in ("VALID_TECHNOLOGY", "VALID_COMPETENCY") and
                self._is_direct_title_anchor(display_name, cid, title_result.job_title)
            )

            # Breakdown metadata
            dim_breakdown = {
                "sentence": best_sentence_res.model_dump() if best_sentence_res else None,
                "segment": seg_res.model_dump(),
                "job": job_res.model_dump(),
                "eligibility": eligibility_record.model_dump(),
            }

            # --- Aggregation ---
            score_out, prov_out = self.aggregator.aggregate(
                sentence_salience=final_sentence_salience,
                segment_salience=final_segment_salience,
                job_salience=final_job_salience,
                is_title_anchor=is_anchor,
                occurrences=occurrences,
                job_title=title_result.job_title,
                dimension_breakdown=dim_breakdown,
                group_info=group_info,
                variant=variant,
            )

            # In V2, V3, V4: if entity is ineligible (actor or form factor), down-weight or flag
            if variant in ("V2_gated", "V3_semantics", "V4_hardened") and not is_eligible:
                # Demote ineligible contextual actors to scale_min (0.10)
                score_out = SkillImportanceScore(
                    sentence_salience=score_out.sentence_salience,
                    segment_salience=score_out.segment_salience,
                    job_salience=score_out.job_salience,
                    importance_score_raw=0.00,
                    w_j=0.10,
                    available_dimensions=score_out.available_dimensions,
                    normalization_method="gated_ineligible_suppression",
                )

            scored_skills.append(
                SkillImportanceOutput(
                    canonical_skill_id=cid,
                    skill_display_name=display_name,
                    type=stype,
                    importance=score_out,
                    provenance=prov_out,
                )
            )

        # Sort descending by w_j
        scored_skills.sort(key=lambda s: s.importance.w_j, reverse=True)

        w_vals = [s.importance.w_j for s in scored_skills]
        metadata = {
            "total_skills_scored": len(scored_skills),
            "eligible_skills_count": sum(1 for s in scored_skills if s.provenance.dimension_breakdown.get("eligibility", {}).get("is_eligible_for_ranking", True)),
            "ineligible_skills_count": sum(1 for s in scored_skills if not s.provenance.dimension_breakdown.get("eligibility", {}).get("is_eligible_for_ranking", True)),
            "detected_job_title": title_result.job_title,
            "title_detection_status": title_result.detection_status,
            "mean_w_j": round(float(np.mean(w_vals)), 4) if w_vals else 0.0,
            "min_w_j": round(float(np.min(w_vals)), 4) if w_vals else 0.0,
            "max_w_j": round(float(np.max(w_vals)), 4) if w_vals else 0.0,
            "variant": variant,
        }

        return JDEstimationResult(
            job_title_result=title_result,
            sections=sections,
            skills=scored_skills,
            metadata=metadata,
        )
