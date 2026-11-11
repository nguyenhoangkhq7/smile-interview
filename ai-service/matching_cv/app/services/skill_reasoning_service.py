"""Service for Sprint 2 Phase 1 & 1B: Ontology-Free LLM Skill Semantic Reasoning."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union
from openai import AsyncOpenAI

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.semantic_reasoning import (
    BatchSkillPairReasoningRequest,
    BatchSkillPairReasoningResponse,
    DirectionType,
    GraphRelationStatus,
    IdentityDecision,
    RelationshipType,
    ResolutionMethod,
    SkillPairReasoningInput,
    SkillPairReasoningResult,
    SkillRef,
)
from matching_cv.app.schemas.semantic_representation import SemanticRepresentationResponse
from matching_cv.app.services.prompt_templates import (
    SKILL_CRITIC_SYSTEM_PROMPT,
    SKILL_REASONING_PROMPT_VERSION,
    SKILL_REASONING_SYSTEM_PROMPT,
    SKILL_REASONING_SYSTEM_PROMPT_V1,
    SKILL_REASONING_SYSTEM_PROMPT_V2,
)

logger = logging.getLogger(__name__)


def normalize_skill_string(text: str) -> str:
    """Normalize skill name string for hashing and deduplication."""
    return "".join(c for c in text.lower() if c.isalnum() or c in ("+", "#", "."))


class SkillReasoningService:
    """
    Service executing ontology-free LLM semantic reasoning on skill pairs.
    Handles skill identity resolution (equivalent vs distinct vs uncertain),
    semantic relationship classification (related, prerequisite, specialization, alternative, unrelated),
    deterministic contradiction detection, and selective semantic critic refinement.
    """

    def __init__(self) -> None:
        self.api_key: str = settings.OPENROUTER_API_KEY
        self.base_url: str = settings.OPENROUTER_BASE_URL
        self.model: str = settings.OPENROUTER_MODEL
        self.default_headers = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Inference Service - Skill Semantic Reasoning",
        }

    def _get_client(self) -> AsyncOpenAI:
        current_key = settings.OPENROUTER_API_KEY or self.api_key
        return AsyncOpenAI(
            api_key=current_key or "not_configured",
            base_url=settings.OPENROUTER_BASE_URL or self.base_url,
            default_headers=self.default_headers,
        )

    @staticmethod
    def _detect_contradictions(
        identity: str,
        relationship: Optional[str],
        direction: Optional[str],
        summary: str,
    ) -> Tuple[bool, List[str]]:
        """
        General, domain-agnostic semantic contradiction detection between labels and textual rationale.
        Identifies cases where rationale explicitly disproves or conflicts with the predicted relationship.
        """
        anomalies: List[str] = []
        lower_summary = summary.lower()

        # Check 1: Alternative contradiction (label is alternative, but rationale states they are not substitutes / different roles)
        if relationship == "alternative":
            negative_substitute_phrases = [
                "not substitute",
                "not direct substitute",
                "not a substitute",
                "not interchangeable",
                "not direct competitor",
                "different functional role",
                "different role",
                "different architectural layer",
                "different layer",
                "complementary rather than",
                "complementary instead of",
                "do not replace",
                "cannot replace",
                "not competing",
            ]
            if any(p in lower_summary for p in negative_substitute_phrases):
                anomalies.append("Alternative claimed but rationale asserts non-substitutability or different functional roles.")

        # Check 2: Specialization contradiction (label is specialization, but rationale states metric, feature, or distinct practice)
        if relationship == "specialization":
            non_subtyping_phrases = [
                "is a metric",
                "set of metrics",
                "performance metrics",
                "measurement of",
                "performance criteria",
                "framework feature",
                "feature rather than",
                "tool used to achieve",
                "tool rather than a sub",
                "diagnostic procedure",
                "diagnostic test",
                "imaging procedure",
                "not a sub-specialty",
                "not a specialization",
                "supporting tool",
            ]
            if any(p in lower_summary for p in non_subtyping_phrases):
                anomalies.append("Specialization claimed but rationale identifies concept as a metric, tool, feature, or procedure rather than a genus-species subtype.")

        # Check 3: Equivalent contradiction (label is equivalent, but rationale identifies distinct scope or tool vs underlying platform)
        if identity == "equivalent":
            positive_equivalence_phrases = [
                "same underlying technology",
                "same underlying concept",
                "same underlying tool",
                "same underlying standard",
                "exact same underlying",
                "refer to the same",
                "naming variant",
                "naming variation",
                "official alias",
                "informal abbreviation",
                "standard name",
                "transliteration",
            ]
            has_positive_equiv = any(p in lower_summary for p in positive_equivalence_phrases)

            distinct_scope_phrases = [
                "brand name for",
                "implementation of",
                "specific implementation",
                "implementation rather than",
                "service subset",
                "subset of services",
                "component services",
                "services of the",
                "underlying engine",
                "underlying platform",
                "distinct concept",
                "separate concept",
                "built upon",
                "built on top of",
                "broader concept",
                "narrower concept",
                "platform rather than",
                "ecosystem implementation",
            ]
            for p in distinct_scope_phrases:
                if p in lower_summary:
                    if p in ("underlying engine", "underlying platform") and has_positive_equiv:
                        continue
                    anomalies.append(f"Equivalence claimed but rationale notes distinct scope, implementation vs platform, or service subset ('{p}').")
                    break

        # Check 4: Prerequisite contradiction (label is prerequisite, but rationale notes mere co-occurrence, optional usage, or independence)
        if relationship == "prerequisite":
            non_prereq_phrases = [
                "not a prerequisite",
                "not a strict prerequisite",
                "not required for",
                "optional rather than",
                "mere co-occurrence",
                "co-occur rather than",
                "can be used independently",
                "independent of each other",
                "orthogonal concepts",
                "not a dependency",
                "not dependent on",
                "just an implementation",
                "one of many tools to build",
            ]
            if any(p in lower_summary for p in non_prereq_phrases):
                anomalies.append("Prerequisite claimed but rationale describes mere co-occurrence, optional tool usage, or independent concepts.")

            # Directional Inversion Contradiction:
            # If direction is a_to_b (claiming A is prerequisite for B), but rationale states B is the prerequisite / underlying technology for A
            target_is_prereq_phrases = [
                "meaning react is the underlying",
                "is the underlying library and prerequisite",
                "is the underlying technology and prerequisite",
                "is a prerequisite for skill a",
                "skill b is a prerequisite",
                "skill b is the prerequisite",
                "skill b is foundational for skill a",
            ]
            source_is_prereq_phrases = [
                "is a prerequisite for skill b",
                "skill a is a prerequisite",
                "skill a is the prerequisite",
                "skill a is foundational for skill b",
            ]
            if direction == "a_to_b" and any(p in lower_summary for p in target_is_prereq_phrases):
                anomalies.append("Prerequisite direction contradiction: rationale asserts target/underlying library is prerequisite for source, but direction was marked a_to_b.")
            elif direction == "b_to_a" and any(p in lower_summary for p in source_is_prereq_phrases):
                anomalies.append("Prerequisite direction contradiction: rationale asserts source is prerequisite for target, but direction was marked b_to_a.")

        # Check 5: Related contradiction (label is related, but rationale asserts no meaningful connection)
        if relationship == "related":
            non_related_phrases = [
                "no direct connection",
                "no technical connection",
                "no functional relationship",
                "entirely unrelated",
                "coincidental co-occurrence",
            ]
            if any(p in lower_summary for p in non_related_phrases):
                anomalies.append("Related claimed but rationale notes lack of direct technical or functional connection.")

        # Check 6: Unrelated with explicit dependency rationale
        if relationship == "unrelated":
            related_phrases = [
                "frequently used together",
                "closely related",
                "direct dependency",
                "prerequisite for",
            ]
            if any(p in lower_summary for p in related_phrases):
                anomalies.append("Unrelated claimed but rationale describes close functional co-usage or dependency.")

        contradiction_detected = len(anomalies) > 0
        return contradiction_detected, anomalies

    @staticmethod
    def _compute_graph_relation_status(
        identity: str,
        relationship: Optional[str],
        contradiction_detected: bool,
        error_status: Optional[str],
        requires_external_verification: bool,
    ) -> GraphRelationStatus:
        """
        Determine Stage 4 graph eligibility:
        - 'eligible': Passed structural and semantic integrity checks, permitted as typed graph edge candidate.
        - 'candidate_only': Tentative relation, uncertain, or lacking strong contextual backing.
        - 'rejected': Failed validation, unresolvable contradiction, or execution error.
        """
        if error_status is not None:
            return "rejected"
        if contradiction_detected:
            return "candidate_only"
        if requires_external_verification or identity == "uncertain" or relationship == "uncertain":
            return "candidate_only"
        if identity == "equivalent":
            return "eligible"
        if identity == "distinct" and relationship in ("prerequisite", "specialization", "alternative", "related"):
            return "eligible"
        if relationship == "unrelated":
            return "candidate_only"
        return "candidate_only"

    def _validate_and_sanitize_result(
        self,
        raw_dict: Dict[str, Any],
        pair: SkillPairReasoningInput,
        model_id: str,
        prompt_version: str,
        latency_ms: float,
    ) -> SkillPairReasoningResult:
        """Enforce pairwise consistency rules, provenance invariants, and valid enumerated fields."""
        raw_identity = str(raw_dict.get("identity", "uncertain")).strip().lower()
        if raw_identity not in ("equivalent", "distinct", "uncertain"):
            raw_identity = "uncertain"

        raw_rel = raw_dict.get("relationship")
        if raw_rel is not None:
            raw_rel = str(raw_rel).strip().lower()
            if raw_rel not in ("related", "prerequisite", "specialization", "alternative", "unrelated", "uncertain"):
                raw_rel = "uncertain"

        raw_dir = raw_dict.get("direction")
        if raw_dir is not None:
            raw_dir = str(raw_dir).strip().lower()
            if raw_dir not in ("a_to_b", "b_to_a", "bidirectional", "none"):
                raw_dir = "none"

        # Rule 1: Equivalent identity constraint
        if raw_identity == "equivalent":
            # An equivalent pair cannot be unrelated, prerequisite, or alternative
            if raw_rel in ("unrelated", "prerequisite", "alternative", "specialization"):
                raw_rel = None
            raw_dir = "none"

        # Rule 2: Directional relationship must have a valid direction
        if raw_identity == "distinct":
            if raw_rel in ("prerequisite", "specialization") and raw_dir not in ("a_to_b", "b_to_a"):
                raw_dir = "a_to_b"  # Default canonical direction if unspecified
            elif raw_rel in ("alternative", "unrelated", "uncertain", "related") and raw_dir in ("a_to_b", "b_to_a"):
                raw_dir = "none"

        # Rule 3: Uncertain identity defaults to uncertain relationship
        if raw_identity == "uncertain":
            raw_rel = "uncertain"
            raw_dir = "none"

        summary = raw_dict.get("reasoning_summary") or f"Reasoning evaluated between {pair.skill_a_name} and {pair.skill_b_name}."

        # Provenance Invariant:
        # If NO context was provided for either skill, verification_status MUST NOT be context_verified!
        has_context = bool((pair.skill_a_context and pair.skill_a_context.strip()) or
                           (pair.skill_b_context and pair.skill_b_context.strip()))

        basis = raw_dict.get("evidence_basis", "model_knowledge")
        if not has_context and basis == "context_grounded":
            basis = "model_knowledge"
        if basis not in ("context_grounded", "model_knowledge", "exact_string_match", "insufficient_evidence"):
            basis = "model_knowledge"

        verif = raw_dict.get("verification_status", "model_inferred")
        if not has_context and verif == "context_verified":
            verif = "model_inferred"
        if verif not in ("model_inferred", "context_verified", "deterministic_verified", "uncertain", "error"):
            verif = "model_inferred"

        req_ext = bool(raw_dict.get("requires_external_verification", False))
        if raw_identity == "uncertain" or raw_rel == "uncertain":
            req_ext = True

        # Contradiction Detection
        contradiction_detected, anomalies = self._detect_contradictions(
            identity=raw_identity,
            relationship=raw_rel,
            direction=raw_dir,
            summary=summary,
        )

        graph_status = self._compute_graph_relation_status(
            identity=raw_identity,
            relationship=raw_rel,
            contradiction_detected=contradiction_detected,
            error_status=None,
            requires_external_verification=req_ext,
        )

        return SkillPairReasoningResult(
            pair_id=pair.pair_id or f"{pair.skill_a_id}__{pair.skill_b_id}",
            skill_a=SkillRef(
                skill_id=pair.skill_a_id,
                name=pair.skill_a_name,
                context=pair.skill_a_context,
                source=pair.skill_a_source,
            ),
            skill_b=SkillRef(
                skill_id=pair.skill_b_id,
                name=pair.skill_b_name,
                context=pair.skill_b_context,
                source=pair.skill_b_source,
            ),
            identity=raw_identity,  # type: ignore
            relationship=raw_rel,  # type: ignore
            direction=raw_dir,  # type: ignore
            reasoning_summary=summary,
            evidence_basis=basis,  # type: ignore
            verification_status=verif,  # type: ignore
            requires_external_verification=req_ext,
            model_id=model_id,
            prompt_version=prompt_version,
            retrieval_cosine=pair.retrieval_cosine,
            source_occurrence_ids=pair.source_occurrence_ids,
            latency_ms=round(latency_ms, 2),
            cached_from_symmetric=False,
            error_status=None,
            graph_relation_status=graph_status,
            resolution_method="llm_direct",
            initial_decision=None,
            critic_assessment=None,
            contradiction_detected=contradiction_detected,
        )

    async def _run_critic(
        self,
        pair: SkillPairReasoningInput,
        initial_result: SkillPairReasoningResult,
        client: AsyncOpenAI,
        model: str,
        timeout: float = 15.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute an independent selective semantic critic pass to verify and repair detected contradictions.
        """
        user_msg = (
            f"Audit the following skill pair classification for semantic consistency and label-rationale contradictions:\n\n"
            f"Skill A: {pair.skill_a_name} (ID: {pair.skill_a_id})\n"
            f"Context A: {pair.skill_a_context or 'None'}\n\n"
            f"Skill B: {pair.skill_b_name} (ID: {pair.skill_b_id})\n"
            f"Context B: {pair.skill_b_context or 'None'}\n\n"
            f"Initial Classification:\n"
            f"- Identity: {initial_result.identity}\n"
            f"- Relationship: {initial_result.relationship}\n"
            f"- Direction: {initial_result.direction}\n"
            f"- Reasoning Summary: {initial_result.reasoning_summary}\n"
        )

        messages = [
            {"role": "system", "content": SKILL_CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        try:
            completion = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                ),
                timeout=timeout,
            )
            result_str = ""
            if completion.choices and len(completion.choices) > 0:
                first_msg = completion.choices[0].message
                result_str = str(first_msg.content or "").strip()

            if result_str.startswith("```json"):
                result_str = result_str[7:]
            elif result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
            result_str = result_str.strip()

            if not result_str:
                return None
            return json.loads(result_str)
        except Exception as exc:
            logger.warning(f"Semantic critic pass failed or timed out for {pair.skill_a_name} <-> {pair.skill_b_name}: {exc}")
            return None

    async def reason_pair(
        self,
        pair: SkillPairReasoningInput,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        include_cosine: bool = False,
        prompt_version: str = "sprint2-v2",
        enable_critic: bool = False,
    ) -> SkillPairReasoningResult:
        """
        Evaluate a single skill pair for semantic identity and relationship.
        Includes exact-label fast path, structured prompt reasoning, contradiction detection,
        and selective semantic critic verification.
        """
        start_time = time.perf_counter()
        active_model = model or settings.OPENROUTER_MODEL or self.model

        # Fast-Path 1: Identical normalized skill names -> always equivalent
        norm_a = normalize_skill_string(pair.skill_a_name)
        norm_b = normalize_skill_string(pair.skill_b_name)
        if norm_a and norm_b and norm_a == norm_b:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return SkillPairReasoningResult(
                pair_id=pair.pair_id or f"{pair.skill_a_id}__{pair.skill_b_id}",
                skill_a=SkillRef(
                    skill_id=pair.skill_a_id,
                    name=pair.skill_a_name,
                    context=pair.skill_a_context,
                    source=pair.skill_a_source,
                ),
                skill_b=SkillRef(
                    skill_id=pair.skill_b_id,
                    name=pair.skill_b_name,
                    context=pair.skill_b_context,
                    source=pair.skill_b_source,
                ),
                identity="equivalent",
                relationship=None,
                direction="none",
                reasoning_summary="Identical canonical or normalized skill names resolved via deterministic exact-label rule.",
                evidence_basis="exact_string_match",
                verification_status="deterministic_verified",
                requires_external_verification=False,
                model_id=active_model,
                prompt_version=prompt_version,
                retrieval_cosine=pair.retrieval_cosine,
                source_occurrence_ids=pair.source_occurrence_ids,
                latency_ms=round(elapsed, 2),
                cached_from_symmetric=False,
                error_status=None,
                graph_relation_status="eligible",
                resolution_method="exact_label_rule",
                initial_decision=None,
                critic_assessment=None,
                contradiction_detected=False,
            )

        # Build prompt user content
        user_msg = (
            f"Analyze the relationship between the following two skills:\n\n"
            f"Skill A: {pair.skill_a_name} (ID: {pair.skill_a_id})\n"
            f"Context A: {pair.skill_a_context or 'None provided'}\n"
            f"Source Document A: {pair.skill_a_source or 'Unspecified'}\n\n"
            f"Skill B: {pair.skill_b_name} (ID: {pair.skill_b_id})\n"
            f"Context B: {pair.skill_b_context or 'None provided'}\n"
            f"Source Document B: {pair.skill_b_source or 'Unspecified'}\n"
        )
        if include_cosine and pair.retrieval_cosine is not None:
            user_msg += f"\nRetrieval Cosine Score: {pair.retrieval_cosine:.4f}\n"

        system_prompt = (
            SKILL_REASONING_SYSTEM_PROMPT_V1
            if prompt_version == "sprint2-v1"
            else SKILL_REASONING_SYSTEM_PROMPT_V2
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        active_client = client or self._get_client()

        try:
            async def _call_llm():
                try:
                    return await active_client.chat.completions.create(
                        model=active_model,
                        messages=messages,
                        temperature=0.0,
                        response_format={"type": "json_object"},
                        extra_body={"reasoning": {"effort": "none"}},
                    )
                except Exception:
                    return await active_client.chat.completions.create(
                        model=active_model,
                        messages=messages,
                        temperature=0.0,
                        response_format={"type": "json_object"},
                    )

            completion = await asyncio.wait_for(_call_llm(), timeout=timeout)
            elapsed = (time.perf_counter() - start_time) * 1000.0

            result_str = ""
            if completion.choices and len(completion.choices) > 0:
                first_msg = completion.choices[0].message
                if getattr(first_msg, "content", None):
                    result_str = str(first_msg.content).strip()
                elif getattr(first_msg, "reasoning", None):
                    result_str = str(first_msg.reasoning).strip()
                elif getattr(first_msg, "reasoning_content", None):
                    result_str = str(first_msg.reasoning_content).strip()

            if result_str.startswith("```json"):
                result_str = result_str[7:]
            elif result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
            result_str = result_str.strip()

            if not result_str:
                raise ValueError("LLM returned an empty response string.")

            raw_dict = json.loads(result_str)
            initial_res = self._validate_and_sanitize_result(
                raw_dict, pair, active_model, prompt_version, elapsed
            )

            # Selective Critic Pass
            # Triggered if explicitly enabled OR if contradiction was detected
            if (enable_critic or initial_res.contradiction_detected) and active_client:
                critic_data = await self._run_critic(
                    pair=pair,
                    initial_result=initial_res,
                    client=active_client,
                    model=active_model,
                    timeout=min(15.0, timeout),
                )
                if critic_data:
                    c_detected = bool(critic_data.get("contradiction_detected", False))
                    rev_id = critic_data.get("revised_identity")
                    rev_rel = critic_data.get("revised_relationship")
                    rev_dir = critic_data.get("revised_direction")

                    if c_detected and (rev_id or rev_rel):
                        # Store pre-critic initial decision for complete auditing
                        initial_res.initial_decision = {
                            "identity": initial_res.identity,
                            "relationship": initial_res.relationship,
                            "direction": initial_res.direction,
                            "reasoning_summary": initial_res.reasoning_summary,
                        }
                        initial_res.critic_assessment = critic_data
                        initial_res.resolution_method = "llm_critic_refined"
                        initial_res.contradiction_detected = True

                        if rev_id in ("equivalent", "distinct", "uncertain"):
                            initial_res.identity = rev_id
                        if rev_rel in ("related", "prerequisite", "specialization", "alternative", "unrelated", "uncertain"):
                            initial_res.relationship = rev_rel
                        if rev_dir in ("a_to_b", "b_to_a", "bidirectional", "none"):
                            initial_res.direction = rev_dir
                        elif rev_rel in ("prerequisite", "specialization") and not rev_dir:
                            initial_res.direction = "a_to_b"
                        elif rev_rel in ("alternative", "unrelated", "uncertain", "related"):
                            initial_res.direction = "none"

                        if initial_res.identity == "equivalent":
                            initial_res.relationship = None
                            initial_res.direction = "none"

                        c_assessment_text = critic_data.get("critic_assessment", "")
                        initial_res.reasoning_summary = f"{initial_res.reasoning_summary} [Critic Refinement: {c_assessment_text}]"

                        # Recompute graph status after refinement
                        initial_res.graph_relation_status = self._compute_graph_relation_status(
                            identity=initial_res.identity,
                            relationship=initial_res.relationship,
                            contradiction_detected=False,  # Resolved by critic
                            error_status=None,
                            requires_external_verification=initial_res.requires_external_verification,
                        )
                    else:
                        initial_res.critic_assessment = critic_data

            return initial_res

        except json.JSONDecodeError as exc:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"JSON decode error evaluating skill pair {pair.skill_a_name} <-> {pair.skill_b_name}: {exc}")
            return SkillPairReasoningResult(
                pair_id=pair.pair_id or f"{pair.skill_a_id}__{pair.skill_b_id}",
                skill_a=SkillRef(skill_id=pair.skill_a_id, name=pair.skill_a_name, context=pair.skill_a_context, source=pair.skill_a_source),
                skill_b=SkillRef(skill_id=pair.skill_b_id, name=pair.skill_b_name, context=pair.skill_b_context, source=pair.skill_b_source),
                identity="uncertain",
                relationship="uncertain",
                direction="none",
                reasoning_summary=f"JSON decode error: {str(exc)}",
                evidence_basis="insufficient_evidence",
                verification_status="error",
                requires_external_verification=True,
                model_id=active_model,
                prompt_version=prompt_version,
                retrieval_cosine=pair.retrieval_cosine,
                source_occurrence_ids=pair.source_occurrence_ids,
                latency_ms=round(elapsed, 2),
                cached_from_symmetric=False,
                error_status=f"JSON decode error: {str(exc)}",
                graph_relation_status="rejected",
                resolution_method="fallback_error",
                initial_decision=None,
                critic_assessment=None,
                contradiction_detected=False,
            )
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            logger.warning(f"Timeout ({timeout}s) evaluating skill pair: {pair.skill_a_name} <-> {pair.skill_b_name}")
            return SkillPairReasoningResult(
                pair_id=pair.pair_id or f"{pair.skill_a_id}__{pair.skill_b_id}",
                skill_a=SkillRef(skill_id=pair.skill_a_id, name=pair.skill_a_name, context=pair.skill_a_context, source=pair.skill_a_source),
                skill_b=SkillRef(skill_id=pair.skill_b_id, name=pair.skill_b_name, context=pair.skill_b_context, source=pair.skill_b_source),
                identity="uncertain",
                relationship="uncertain",
                direction="none",
                reasoning_summary=f"Evaluation timed out after {timeout} seconds.",
                evidence_basis="insufficient_evidence",
                verification_status="error",
                requires_external_verification=True,
                model_id=active_model,
                prompt_version=prompt_version,
                retrieval_cosine=pair.retrieval_cosine,
                source_occurrence_ids=pair.source_occurrence_ids,
                latency_ms=round(elapsed, 2),
                cached_from_symmetric=False,
                error_status="timeout",
                graph_relation_status="rejected",
                resolution_method="fallback_error",
                initial_decision=None,
                critic_assessment=None,
                contradiction_detected=False,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Error evaluating skill pair {pair.skill_a_name} <-> {pair.skill_b_name}: {exc}", exc_info=True)
            return SkillPairReasoningResult(
                pair_id=pair.pair_id or f"{pair.skill_a_id}__{pair.skill_b_id}",
                skill_a=SkillRef(skill_id=pair.skill_a_id, name=pair.skill_a_name, context=pair.skill_a_context, source=pair.skill_a_source),
                skill_b=SkillRef(skill_id=pair.skill_b_id, name=pair.skill_b_name, context=pair.skill_b_context, source=pair.skill_b_source),
                identity="uncertain",
                relationship="uncertain",
                direction="none",
                reasoning_summary=f"Inference error: {str(exc)}",
                evidence_basis="insufficient_evidence",
                verification_status="error",
                requires_external_verification=True,
                model_id=active_model,
                prompt_version=prompt_version,
                retrieval_cosine=pair.retrieval_cosine,
                source_occurrence_ids=pair.source_occurrence_ids,
                latency_ms=round(elapsed, 2),
                cached_from_symmetric=False,
                error_status=str(exc),
                graph_relation_status="rejected",
                resolution_method="fallback_error",
                initial_decision=None,
                critic_assessment=None,
                contradiction_detected=False,
            )

    async def reason_batch(
        self,
        request: BatchSkillPairReasoningRequest,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
    ) -> BatchSkillPairReasoningResponse:
        """
        Batch evaluate multiple skill pairs with concurrency control, deduplication, and symmetry caching.
        """
        start_batch_time = time.perf_counter()
        run_id = f"reason_run_{uuid.uuid4().hex[:8]}"
        active_model = model or settings.OPENROUTER_MODEL or self.model
        active_client = client or self._get_client()

        semaphore = asyncio.Semaphore(request.concurrency)

        unique_pairs_to_evaluate: Dict[Tuple[str, str], SkillPairReasoningInput] = {}
        # key -> list of (idx, is_inverted, pair_input)
        key_to_indices: Dict[Tuple[str, str], List[Tuple[int, bool, SkillPairReasoningInput]]] = {}

        for idx, p in enumerate(request.pairs):
            k_dir = (normalize_skill_string(p.skill_a_name), normalize_skill_string(p.skill_b_name))
            k_rev = (normalize_skill_string(p.skill_b_name), normalize_skill_string(p.skill_a_name))

            if k_dir in unique_pairs_to_evaluate:
                key_to_indices[k_dir].append((idx, False, p))
            elif k_rev in unique_pairs_to_evaluate:
                key_to_indices[k_rev].append((idx, True, p))
            else:
                unique_pairs_to_evaluate[k_dir] = p
                key_to_indices[k_dir] = [(idx, False, p)]

        async def _eval_with_sem(pair: SkillPairReasoningInput):
            async with semaphore:
                return await self.reason_pair(
                    pair,
                    client=active_client,
                    model=active_model,
                    timeout=request.timeout_seconds,
                    include_cosine=request.include_cosine_in_prompt,
                    prompt_version=request.prompt_version,
                    enable_critic=request.enable_critic,
                )

        unique_keys = list(unique_pairs_to_evaluate.keys())
        tasks = [_eval_with_sem(unique_pairs_to_evaluate[k]) for k in unique_keys]

        evaluated_results = await asyncio.gather(*tasks) if tasks else []
        evaluated_map: Dict[Tuple[str, str], SkillPairReasoningResult] = dict(zip(unique_keys, evaluated_results))

        results_by_idx: List[Tuple[int, SkillPairReasoningResult]] = []
        cached_count = 0

        for k, items in key_to_indices.items():
            base_res = evaluated_map[k]
            for i, (idx, is_inverted, p) in enumerate(items):
                if i == 0 and not is_inverted:
                    # Original directly evaluated pair
                    results_by_idx.append((idx, base_res))
                elif not is_inverted:
                    # Duplicate of direct pair
                    cached_res = base_res.model_copy(deep=True)
                    cached_res.pair_id = p.pair_id or f"{p.skill_a_id}__{p.skill_b_id}"
                    cached_res.skill_a = SkillRef(skill_id=p.skill_a_id, name=p.skill_a_name, context=p.skill_a_context, source=p.skill_a_source)
                    cached_res.skill_b = SkillRef(skill_id=p.skill_b_id, name=p.skill_b_name, context=p.skill_b_context, source=p.skill_b_source)
                    cached_res.retrieval_cosine = p.retrieval_cosine
                    cached_res.source_occurrence_ids = p.source_occurrence_ids
                    cached_res.latency_ms = 0.0
                    cached_res.resolution_method = "cache_dedup"
                    cached_res.cached_from_symmetric = False
                    results_by_idx.append((idx, cached_res))
                    cached_count += 1
                else:
                    # Inverted symmetric pair
                    new_dir: Optional[DirectionType] = base_res.direction
                    if base_res.direction == "a_to_b":
                        new_dir = "b_to_a"
                    elif base_res.direction == "b_to_a":
                        new_dir = "a_to_b"

                    sym_res = SkillPairReasoningResult(
                        pair_id=p.pair_id or f"{p.skill_a_id}__{p.skill_b_id}",
                        skill_a=SkillRef(skill_id=p.skill_a_id, name=p.skill_a_name, context=p.skill_a_context, source=p.skill_a_source),
                        skill_b=SkillRef(skill_id=p.skill_b_id, name=p.skill_b_name, context=p.skill_b_context, source=p.skill_b_source),
                        identity=base_res.identity,
                        relationship=base_res.relationship,
                        direction=new_dir,
                        reasoning_summary=f"Derived by symmetry from ({p.skill_b_name}, {p.skill_a_name}): {base_res.reasoning_summary}",
                        evidence_basis=base_res.evidence_basis,
                        verification_status=base_res.verification_status,
                        requires_external_verification=base_res.requires_external_verification,
                        model_id=base_res.model_id,
                        prompt_version=base_res.prompt_version,
                        retrieval_cosine=p.retrieval_cosine,
                        source_occurrence_ids=p.source_occurrence_ids,
                        latency_ms=0.0,
                        cached_from_symmetric=True,
                        error_status=base_res.error_status,
                        graph_relation_status=base_res.graph_relation_status,
                        resolution_method="derived_by_symmetry",
                        initial_decision=base_res.initial_decision,
                        critic_assessment=base_res.critic_assessment,
                        contradiction_detected=base_res.contradiction_detected,
                    )
                    results_by_idx.append((idx, sym_res))
                    cached_count += 1

        results_by_idx.sort(key=lambda x: x[0])
        final_results = [r[1] for r in results_by_idx]

        total_duration = (time.perf_counter() - start_batch_time) * 1000.0
        failed_count = sum(1 for r in final_results if r.error_status is not None)
        critic_count = sum(1 for r in final_results if r.critic_assessment is not None)
        contradictions_count = sum(1 for r in final_results if r.resolution_method == "llm_critic_refined")
        evaluated_count = len(unique_pairs_to_evaluate)

        return BatchSkillPairReasoningResponse(
            run_id=run_id,
            results=final_results,
            total_pairs=len(request.pairs),
            evaluated_pairs=evaluated_count,
            cached_dedup_pairs=cached_count,
            failed_pairs=failed_count,
            critic_invocations=critic_count,
            contradictions_resolved=contradictions_count,
            model_id=active_model,
            prompt_version=request.prompt_version,
            duration_ms=round(total_duration, 2),
        )

    def extract_and_budget_topk_pairs(
        self,
        stage3_response: Union[Dict[str, Any], SemanticRepresentationResponse],
        max_pairs: int = 25,
        min_cosine: float = 0.3,
        selection_strategy: str = "balanced_coverage",
    ) -> Tuple[List[SkillPairReasoningInput], Dict[str, Any]]:
        """
        Extract candidate skill pairs from Stage 3 SBERT Top-K retrieval output with explicit budgeting and coverage audit.

        Selection strategies:
        - 'balanced_coverage': Stratified round-robin across CV skills to prevent starving lower-ranked skills.
        - 'global_top_cosine': Global Top-N highest cosine similarity pairs across all skills.
        """
        if isinstance(stage3_response, SemanticRepresentationResponse):
            ret_map = stage3_response.top_k_retrievals or {}
        elif isinstance(stage3_response, dict):
            ret_map = stage3_response.get("top_k_retrievals", {})
        else:
            ret_map = {}

        skill_retrievals = ret_map.get("cv_skills_to_jd_skills") or ret_map.get("skill_to_skill") or []

        total_retrievable_pairs = 0
        all_cv_skill_ids: Set[str] = set()
        all_jd_skill_ids: Set[str] = set()
        cv_query_order: List[str] = []
        per_cv_candidate_pairs: Dict[str, List[SkillPairReasoningInput]] = {}
        unique_pair_map: Dict[Tuple[str, str], SkillPairReasoningInput] = {}

        for ret in skill_retrievals:
            if isinstance(ret, dict):
                q_id = ret.get("query_id", "")
                q_label = ret.get("query_label", "")
                candidates = ret.get("candidates", [])
            else:
                q_id = getattr(ret, "query_id", "")
                q_label = getattr(ret, "query_label", "")
                candidates = getattr(ret, "candidates", [])

            if not q_id:
                continue

            if q_id not in all_cv_skill_ids:
                all_cv_skill_ids.add(q_id)
                cv_query_order.append(q_id)
                per_cv_candidate_pairs[q_id] = []

            for cand in candidates:
                total_retrievable_pairs += 1
                if isinstance(cand, dict):
                    t_id = cand.get("target_id", "")
                    t_label = cand.get("target_label", "")
                    score = float(cand.get("cosine_similarity", 0.0))
                else:
                    t_id = getattr(cand, "target_id", "")
                    t_label = getattr(cand, "target_label", "")
                    score = float(getattr(cand, "cosine_similarity", 0.0))

                if t_id:
                    all_jd_skill_ids.add(t_id)

                if score < min_cosine:
                    continue

                pair_input = SkillPairReasoningInput(
                    skill_a_id=q_id,
                    skill_a_name=q_label,
                    skill_a_source="CV",
                    skill_b_id=t_id,
                    skill_b_name=t_label,
                    skill_b_source="JD",
                    retrieval_cosine=score,
                    source_occurrence_ids=[q_id, t_id],
                )

                pair_key = (min(q_label.casefold(), t_label.casefold()), max(q_label.casefold(), t_label.casefold()))
                if pair_key not in unique_pair_map:
                    unique_pair_map[pair_key] = pair_input
                    per_cv_candidate_pairs[q_id].append(pair_input)

        total_unique_pairs = len(unique_pair_map)

        selected_pairs: List[SkillPairReasoningInput] = []
        selected_keys: Set[Tuple[str, str]] = set()

        if selection_strategy == "global_top_cosine":
            # Global Top-N sort by cosine descending, with deterministic secondary sort
            sorted_candidates = sorted(
                unique_pair_map.values(),
                key=lambda p: (
                    -float(p.retrieval_cosine if p.retrieval_cosine is not None else 0.0),
                    p.skill_a_name.casefold(),
                    p.skill_b_name.casefold(),
                ),
            )
            selected_pairs = sorted_candidates[:max_pairs]
        else:
            # Default: 'balanced_coverage' (stratified round-robin across CV skills)
            # Round 0: take top candidate for CV 1, CV 2, ...
            # Round 1: take 2nd candidate for CV 1, CV 2, ...
            max_cands_per_cv = max((len(cands) for cands in per_cv_candidate_pairs.values()), default=0)
            for rank_idx in range(max_cands_per_cv):
                added_in_round = False
                for q_id in cv_query_order:
                    cands = per_cv_candidate_pairs.get(q_id, [])
                    if rank_idx < len(cands):
                        p = cands[rank_idx]
                        k = (min(p.skill_a_name.casefold(), p.skill_b_name.casefold()), max(p.skill_a_name.casefold(), p.skill_b_name.casefold()))
                        if k not in selected_keys:
                            selected_keys.add(k)
                            selected_pairs.append(p)
                            added_in_round = True
                            if len(selected_pairs) >= max_pairs:
                                break
                if len(selected_pairs) >= max_pairs or not added_in_round:
                    break

        # Compute coverage statistics
        cv_covered_ids = {p.skill_a_id for p in selected_pairs if p.skill_a_id}
        jd_covered_ids = {p.skill_b_id for p in selected_pairs if p.skill_b_id}

        cv_total = len(all_cv_skill_ids)
        jd_total = len(all_jd_skill_ids)
        cv_covered_count = len(cv_covered_ids)
        jd_covered_count = len(jd_covered_ids)

        cv_coverage_pct = round((cv_covered_count / cv_total * 100.0), 2) if cv_total > 0 else 0.0
        jd_coverage_pct = round((jd_covered_count / jd_total * 100.0), 2) if jd_total > 0 else 0.0
        skipped_by_budget = max(0, total_unique_pairs - len(selected_pairs))

        coverage_metrics = {
            "total_retrievable_pairs": total_retrievable_pairs,
            "total_unique_pairs": total_unique_pairs,
            "selected_pairs": len(selected_pairs),
            "skipped_by_budget_pairs": skipped_by_budget,
            "cv_skills_total": cv_total,
            "cv_skills_covered": cv_covered_count,
            "cv_skill_coverage_pct": cv_coverage_pct,
            "jd_skills_total": jd_total,
            "jd_skills_covered": jd_covered_count,
            "jd_skill_coverage_pct": jd_coverage_pct,
            "selection_strategy": selection_strategy,
            "reasoning_budget": max_pairs,
            "min_cosine_threshold": min_cosine,
            "budget_constrained": skipped_by_budget > 0,
            "retrieval_recall_vs_evaluation_coverage": (
                f"SBERT Top-K retrieval retrieved {total_retrievable_pairs} candidate pairs ({total_unique_pairs} unique >= {min_cosine}). "
                f"LLM semantic reasoning evaluated {len(selected_pairs)} pairs ({selection_strategy}) covering "
                f"{cv_covered_count}/{cv_total} ({cv_coverage_pct}%) CV skills and {jd_covered_count}/{jd_total} ({jd_coverage_pct}%) JD skills. "
                f"{skipped_by_budget} pairs deferred due to budget limit ({max_pairs})."
            ),
        }

        for idx, p in enumerate(selected_pairs, 1):
            p.pair_id = f"pair_{idx:03d}"

        return selected_pairs, coverage_metrics

    def extract_topk_pairs_from_stage3(
        self,
        stage3_response: Union[Dict[str, Any], SemanticRepresentationResponse],
        max_pairs: int = 25,
        min_cosine: float = 0.3,
        selection_strategy: str = "balanced_coverage",
    ) -> List[SkillPairReasoningInput]:
        """
        Extract candidate skill pairs from Stage 3 SBERT Top-K retrieval output.
        Preserves backward compatibility while supporting balanced candidate selection.
        """
        pairs, _ = self.extract_and_budget_topk_pairs(
            stage3_response=stage3_response,
            max_pairs=max_pairs,
            min_cosine=min_cosine,
            selection_strategy=selection_strategy,
        )
        return pairs

    async def reason_stage3_topk(
        self,
        stage3_response: Union[Dict[str, Any], SemanticRepresentationResponse],
        max_pairs: int = 25,
        min_cosine: float = 0.3,
        selection_strategy: str = "balanced_coverage",
        concurrency: int = 5,
        timeout_seconds: float = 30.0,
        enable_critic: bool = False,
        prompt_version: str = "sprint2-v2",
    ) -> BatchSkillPairReasoningResponse:
        """
        End-to-end integration: extract Top-K candidate pairs from Stage 3 SBERT output and reason on them.
        """
        pairs, coverage_metrics = self.extract_and_budget_topk_pairs(
            stage3_response,
            max_pairs=max_pairs,
            min_cosine=min_cosine,
            selection_strategy=selection_strategy,
        )
        if not pairs:
            return BatchSkillPairReasoningResponse(
                run_id=f"topk_empty_{uuid.uuid4().hex[:6]}",
                results=[],
                total_pairs=0,
                evaluated_pairs=0,
                cached_dedup_pairs=0,
                failed_pairs=0,
                critic_invocations=0,
                contradictions_resolved=0,
                model_id=settings.OPENROUTER_MODEL or self.model,
                prompt_version=prompt_version,
                duration_ms=0.0,
                coverage_metrics=coverage_metrics,
            )

        req = BatchSkillPairReasoningRequest(
            pairs=pairs,
            concurrency=concurrency,
            timeout_seconds=timeout_seconds,
            include_cosine_in_prompt=False,
            enable_critic=enable_critic,
            prompt_version=prompt_version,
        )
        batch_resp = await self.reason_batch(req)
        batch_resp.coverage_metrics = coverage_metrics
        return batch_resp


skill_reasoning_service = SkillReasoningService()
