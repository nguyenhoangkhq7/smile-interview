import datetime
import hashlib
import json
import os
import uuid
from abc import abstractmethod
from typing import List, Optional

from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.llm.parser import parse_and_validate_response
from skill_gap.baselines.llm.prompts import (
    build_augmented_prompt,
    build_text_only_prompt,
    load_rubric,
)
from skill_gap.baselines.llm.schemas import LLMZeroShotResponse, RunAuditRecord


class BaseLLMZeroShotBaseline(BaselineMethod):
    """
    Base orchestrator for Zero-Shot LLM baselines with Chain-of-Thought (CoT).
    Features:
    - Retries up to max_retries on schema or validation errors.
    - Flags failures explicitly as FAILED without inserting default/fabricated numbers.
    - Caching via SHA256(prompt + model + run_id).
    - Structured audit logging to disk for post-hoc qualitative analysis.
    - Support for repeated runs (n_runs) with unique run_ids.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        name: str,
        config: Optional[AppConfig] = None,
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        audit_log_dir: Optional[str] = None,
        rubric_path: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self._llm_client = llm_client
        self._name = name
        self._config = config or AppConfig()
        self._max_retries = max_retries
        self._cache_dir = cache_dir
        self._audit_log_dir = audit_log_dir
        self._rubric_text = load_rubric(rubric_path)
        self._run_id = run_id

        self._produces = frozenset(
            {
                BaselineOutputField.ALIGNMENT,
                BaselineOutputField.P_JD,
                BaselineOutputField.P_CV,
                BaselineOutputField.GAP_MAGNITUDE,
                BaselineOutputField.PRIORITY,
            }
        )

        if self._cache_dir:
            os.makedirs(self._cache_dir, exist_ok=True)
        if self._audit_log_dir:
            os.makedirs(self._audit_log_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._produces

    @property
    def requires_llm(self) -> bool:
        return True

    @property
    def estimated_llm_calls_per_pair(self) -> int:
        return 1

    @abstractmethod
    def _construct_prompt(self, input_data: BaselineInput) -> str:
        """Construct prompt specific to this variant."""
        pass

    def _compute_cache_key(self, prompt: str, run_id: str) -> str:
        model_name = getattr(self._llm_client, "model", "generic_model")
        key_raw = f"{prompt}__{model_name}__{run_id}"
        return hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

    def _execute_with_cache_and_audit(
        self, prompt: str, run_id: str
    ) -> LLMZeroShotResponse:
        prompt_hash = self._compute_cache_key(prompt, run_id)
        cache_file = (
            os.path.join(self._cache_dir, f"{prompt_hash}.json")
            if self._cache_dir
            else None
        )

        # 1. Check cache
        if cache_file and os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return LLMZeroShotResponse.model_validate(data)

        # 2. Call LLM
        response = self._llm_client.complete(prompt, LLMZeroShotResponse)

        # 3. Write cache if enabled
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(response.model_dump_json(indent=2))

        # 4. Save audit log if enabled
        if self._audit_log_dir:
            audit_file = os.path.join(
                self._audit_log_dir, f"{run_id}_{prompt_hash[:8]}.json"
            )
            audit_record = RunAuditRecord(
                run_id=run_id,
                prompt_hash=prompt_hash,
                baseline_name=self._name,
                model_name=getattr(self._llm_client, "model", "generic_model"),
                prompt_text=prompt,
                raw_response_text=response.model_dump_json(),
                assessments=[a.model_dump() for a in response.skills],
                created_at=datetime.datetime.now().isoformat(),
            )
            with open(audit_file, "w", encoding="utf-8") as f:
                f.write(audit_record.model_dump_json(indent=2))

        return response

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        """
        Executes zero-shot assessment on the input data with retry logic.
        """
        expected_ids = [s.skill_id for s in input_data.jd_skills]
        if not expected_ids:
            return []

        active_run_id = self._run_id or f"run_{uuid.uuid4().hex[:8]}"
        prompt = self._construct_prompt(input_data)

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                response = self._execute_with_cache_and_audit(prompt, active_run_id)
                results = parse_and_validate_response(
                    response=response,
                    expected_skill_ids=expected_ids,
                    cv_text=input_data.cv_text,
                    baseline_name=self._name,
                    fuzzy_threshold=self._config.phase3.evidence_fuzzy_threshold,
                )
                # Attach run_id to metadata
                for r in results:
                    r.metadata["run_id"] = active_run_id
                    r.metadata["attempt"] = attempt + 1
                return results
            except Exception as e:
                last_error = e

        # Retries exhausted: mark as FAILED explicitly without fabricating default values
        error_msg = f"Exhausted {self._max_retries} retries. Error: {str(last_error)}"
        return [
            BaselineSkillResult(
                jd_skill_id=sid,
                semantic_alignment=None,
                required_proficiency=None,
                candidate_proficiency=None,
                gap_magnitude=None,
                priority=None,
                metadata={
                    "baseline_name": self._name,
                    "status": "FAILED",
                    "failure_reason": error_msg,
                    "run_id": active_run_id,
                },
            )
            for sid in expected_ids
        ]

    def run_multiple(
        self, input_data: BaselineInput, n_runs: int = 1
    ) -> List[List[BaselineSkillResult]]:
        """
        Executes n_runs independent iterations, each with its own run_id.
        """
        base_id = self._run_id or f"run_{uuid.uuid4().hex[:6]}"
        all_runs: List[List[BaselineSkillResult]] = []
        for i in range(n_runs):
            run_variant = f"{base_id}_iter_{i+1}"
            orig_run_id = self._run_id
            self._run_id = run_variant
            try:
                run_results = self.run(input_data)
                all_runs.append(run_results)
            finally:
                self._run_id = orig_run_id
        return all_runs


class LLMAugmentedBaseline(BaseLLMZeroShotBaseline):
    """
    Main LLM Zero-Shot Baseline (B-LLM-Augmented):
    Supplies CV text, JD text, and Module 1 structured extractions (w_j, soft_match, extracted spans)
    to evaluate whether end-to-end prompting can outperform the discrete mathematical pipeline.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        name: str = "B-LLM-Augmented",
        config: Optional[AppConfig] = None,
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        audit_log_dir: Optional[str] = None,
        rubric_path: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            name=name,
            config=config,
            max_retries=max_retries,
            cache_dir=cache_dir,
            audit_log_dir=audit_log_dir,
            rubric_path=rubric_path,
            run_id=run_id,
        )

    def _construct_prompt(self, input_data: BaselineInput) -> str:
        return build_augmented_prompt(
            cv_text=input_data.cv_text,
            jd_text=input_data.jd_text,
            cv_skills=input_data.cv_skills,
            jd_skills=input_data.jd_skills,
            match_results=input_data.match_results,
            rubric_text=self._rubric_text,
        )


class LLMTextOnlyBaseline(BaseLLMZeroShotBaseline):
    """
    Reference Text-Only LLM Baseline (B-LLM-TextOnly):
    Evaluates candidate deficit purely from raw CV text and raw JD text.
    Cannot run in Oracle mode since it does not consume Module 1 extracted representations.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        name: str = "B-LLM-TextOnly",
        config: Optional[AppConfig] = None,
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        audit_log_dir: Optional[str] = None,
        rubric_path: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            name=name,
            config=config,
            max_retries=max_retries,
            cache_dir=cache_dir,
            audit_log_dir=audit_log_dir,
            rubric_path=rubric_path,
            run_id=run_id,
        )

    def _construct_prompt(self, input_data: BaselineInput) -> str:
        return build_text_only_prompt(
            cv_text=input_data.cv_text,
            jd_text=input_data.jd_text,
            jd_skills=input_data.jd_skills,
            rubric_text=self._rubric_text,
        )
