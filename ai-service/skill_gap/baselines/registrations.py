from typing import Any, Optional
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.pipeline.orchestrator import SkillGapOrchestrator
from skill_gap.baselines.registry import BaselineRegistry, baseline_registry
from skill_gap.baselines.module_adapter import ProposedModuleBaseline
from skill_gap.baselines.proficiency.raw_duration import RawDurationBaseline
from skill_gap.baselines.llm.zero_shot import LLMAugmentedBaseline, LLMTextOnlyBaseline

# Ensure heuristic baselines are registered
import skill_gap.baselines.heuristics.sim_gap  # noqa: F401
import skill_gap.baselines.heuristics.binary_exact  # noqa: F401
import skill_gap.baselines.heuristics.jdw  # noqa: F401
import skill_gap.baselines.heuristics.random_baseline  # noqa: F401


def register_standard_factories(registry: BaselineRegistry) -> None:
    """
    Registers lazy factories for all model-based, structural, and LLM baselines
    into the specified BaselineRegistry instance.
    Enables dependency injection (LLM client, config, run_id, seed) at runtime.
    """
    # 1. Proposed Full Module Baseline
    def create_proposed_module(
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        name: str = "proposed_module",
        **kwargs: Any,
    ) -> ProposedModuleBaseline:
        cfg = config or AppConfig()
        orchestrator = SkillGapOrchestrator(llm_client=llm_client, config=cfg)
        return ProposedModuleBaseline(orchestrator=orchestrator, name=name)

    if "proposed_module" not in registry.list_available():
        registry.register_factory(
            name="proposed_module",
            factory=create_proposed_module,
            requires_llm=True,
            estimated_llm_calls_per_pair=2,
        )

    # 2. B-RawDuration Baseline (Structural Ablation)
    def create_raw_duration(
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        name: str = "B-RawDuration",
        **kwargs: Any,
    ) -> RawDurationBaseline:
        cfg = config or AppConfig()
        return RawDurationBaseline(llm_client=llm_client, config=cfg, name=name)

    if "B-RawDuration" not in registry.list_available():
        registry.register_factory(
            name="B-RawDuration",
            factory=create_raw_duration,
            requires_llm=True,
            estimated_llm_calls_per_pair=2,
        )

    # 3. B-LLM-Augmented Baseline (Zero-Shot CoT with Structured Evidence)
    def create_llm_augmented(
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        name: str = "B-LLM-Augmented",
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        audit_log_dir: Optional[str] = None,
        rubric_path: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMAugmentedBaseline:
        cfg = config or AppConfig()
        return LLMAugmentedBaseline(
            llm_client=llm_client,
            name=name,
            config=cfg,
            max_retries=max_retries,
            cache_dir=cache_dir,
            audit_log_dir=audit_log_dir,
            rubric_path=rubric_path,
            run_id=run_id,
        )

    if "B-LLM-Augmented" not in registry.list_available():
        registry.register_factory(
            name="B-LLM-Augmented",
            factory=create_llm_augmented,
            requires_llm=True,
            estimated_llm_calls_per_pair=1,
        )

    # 4. B-LLM-TextOnly Baseline (Zero-Shot CoT Pure Raw Text)
    def create_llm_text_only(
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        name: str = "B-LLM-TextOnly",
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        audit_log_dir: Optional[str] = None,
        rubric_path: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMTextOnlyBaseline:
        cfg = config or AppConfig()
        return LLMTextOnlyBaseline(
            llm_client=llm_client,
            name=name,
            config=cfg,
            max_retries=max_retries,
            cache_dir=cache_dir,
            audit_log_dir=audit_log_dir,
            rubric_path=rubric_path,
            run_id=run_id,
        )

    if "B-LLM-TextOnly" not in registry.list_available():
        registry.register_factory(
            name="B-LLM-TextOnly",
            factory=create_llm_text_only,
            requires_llm=True,
            estimated_llm_calls_per_pair=1,
        )


# Automatically populate the global baseline_registry with standard factories
register_standard_factories(baseline_registry)
