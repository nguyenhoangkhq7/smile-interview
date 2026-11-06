import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from src.adapters.config import AppConfig, load_config
from src.adapters.llm_client import LLMClient, OpenRouterClient
from src.baselines.base import BaselineMethod
from src.baselines.dataset import DatasetPair, DatasetSource, JSONDatasetSource
from src.baselines.registry import BaselineRegistry, baseline_registry
import src.baselines.registrations  # noqa: F401 - ensures all standard baselines and factories are registered

logger = logging.getLogger(__name__)


def get_git_commit() -> str:
    """Retrieve current git HEAD commit hash, or 'unknown' if not available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


class PredictionRecord(BaseModel):
    """
    Standardized atomic JSONL record logged for every evaluated skill.
    Captures input identification, baseline outputs, runtime latency, and execution status.
    """

    pair_id: str
    method: str
    run_id: str
    skill: str
    jd_skill_id: str
    semantic_alignment: Optional[str] = None
    required_proficiency: Optional[float] = None
    candidate_proficiency: Optional[float] = None
    gap_magnitude: Optional[float] = None
    priority: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float
    status: str  # "OK" or "FAILED"
    error_message: Optional[str] = None
    timestamp: str


class ExperimentManifest(BaseModel):
    """
    Audit manifest persisting experiment metadata, environmental state, and configuration.
    """

    experiment_id: str
    timestamp: str
    git_commit: str
    python_version: str
    model_name: Optional[str] = None
    selected_baselines: List[str]
    pair_count: int
    total_records: int
    seed: Optional[int] = None
    enable_llm: bool
    dataset_path: str
    output_dir: str
    duration_seconds: float
    resumed: bool
    config: Dict[str, Any] = Field(default_factory=dict)


class BaselineRunner:
    """
    Evaluation runner executing registered baselines across CV-JD dataset pairs.
    Handles dry-run calculations, fault isolation, resumption, and audit persistence.
    Complies strictly with Open/Closed Principle: baselines are discovered and instantiated
    via BaselineRegistry without modifying runner code.
    """

    def __init__(
        self,
        registry: BaselineRegistry,
        dataset_source: DatasetSource,
        output_dir: Union[str, Path] = "results",
        experiment_id: Optional[str] = None,
        run_id: str = "run_1",
        enable_llm: bool = False,
        seed: int = 42,
        config: Optional[AppConfig] = None,
        llm_client: Optional[LLMClient] = None,
        model_name: Optional[str] = None,
        dataset_path_str: str = "custom_source",
    ) -> None:
        self.registry = registry
        self.dataset_source = dataset_source
        self.output_dir = Path(output_dir)
        self.experiment_id = experiment_id or f"exp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.run_id = run_id
        self.enable_llm = enable_llm
        self.seed = seed
        self.config = config or AppConfig()
        self.llm_client = llm_client
        self.model_name = model_name
        self.dataset_path_str = dataset_path_str

    def resolve_baselines(self, requested_names: Optional[List[str]] = None) -> List[str]:
        """
        Determines the list of baseline method names to execute based on CLI input
        and the --enable-llm safety constraint.
        """
        all_available = self.registry.list_available()

        if not requested_names or requested_names == ["all"]:
            if not self.enable_llm:
                selected = [name for name in all_available if not self.registry.is_llm_required(name)]
            else:
                selected = all_available
            return selected

        # User explicitly requested specific baselines
        selected = []
        for name in requested_names:
            if name not in all_available:
                available_str = ", ".join(all_available)
                raise KeyError(f"Requested baseline '{name}' not found. Available baselines: {available_str}")
            if self.registry.is_llm_required(name) and not self.enable_llm:
                raise ValueError(
                    f"Baseline '{name}' requires LLM execution, but --enable-llm flag was not specified. "
                    "Provide --enable-llm to run LLM-based baselines."
                )
            selected.append(name)
        return selected

    def dry_run(self, baseline_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generates and displays execution plan without calling LLM APIs or writing output files.
        Calculates pair count, baselines, and estimated LLM invocations.
        """
        pairs = self.dataset_source.load()
        pair_count = len(pairs)
        all_available = self.registry.list_available()

        is_all_requested = not baseline_names or baseline_names == ["all"]
        target_names = all_available if is_all_requested else baseline_names

        plan_entries = []
        total_estimated_llm_calls = 0

        for name in target_names:
            if name not in all_available:
                raise KeyError(f"Requested baseline '{name}' not found.")

            llm_req = self.registry.is_llm_required(name)
            calls_per_pair = self.registry.get_estimated_llm_calls(name)

            if llm_req and not self.enable_llm:
                status_note = "SKIPPED (requires --enable-llm)"
                active_calls = 0
            else:
                status_note = "ACTIVE"
                active_calls = calls_per_pair * pair_count

            total_estimated_llm_calls += active_calls
            plan_entries.append(
                {
                    "name": name,
                    "requires_llm": llm_req,
                    "calls_per_pair": calls_per_pair,
                    "estimated_total_calls": active_calls,
                    "status": status_note,
                }
            )

        print("\n" + "=" * 80)
        print("EXPERIMENT EXECUTION PLAN (DRY-RUN)")
        print("=" * 80)
        print(f"Experiment ID       : {self.experiment_id}")
        print(f"Dataset Path        : {self.dataset_path_str}")
        print(f"Total CV-JD Pairs   : {pair_count}")
        print(f"Enable LLM Flag     : {self.enable_llm}")
        print(f"Random Seed         : {self.seed}")
        print("-" * 80)
        print(f"{'Method Name':<20} | {'LLM Req':<8} | {'Calls/Pair':<10} | {'Est. Calls':<12} | {'Status'}")
        print("-" * 80)
        for entry in plan_entries:
            req_str = "Yes" if entry["requires_llm"] else "No"
            print(
                f"{entry['name']:<20} | {req_str:<8} | {entry['calls_per_pair']:<10} | "
                f"{entry['estimated_total_calls']:<12} | {entry['status']}"
            )
        print("-" * 80)
        print(f"Total Estimated LLM Invocations: {total_estimated_llm_calls}")
        print("=" * 80)
        print("Plan verified successfully. No LLM APIs were called and no records were written.\n")

        return {
            "experiment_id": self.experiment_id,
            "pair_count": pair_count,
            "enable_llm": self.enable_llm,
            "total_estimated_llm_calls": total_estimated_llm_calls,
            "entries": plan_entries,
        }

    def _load_completed_evaluations(self, predictions_path: Path) -> Set[Tuple[str, str, str]]:
        """
        Reads existing predictions.jsonl and extracts successfully completed (pair_id, method, run_id) tuples.
        Allows exact resumption of partially completed experiment runs.
        """
        completed = set()
        if not predictions_path.exists():
            return completed

        with open(predictions_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("status") == "OK":
                        completed.add((data["pair_id"], data["method"], data["run_id"]))
                except Exception:
                    continue
        return completed

    def run(self, baseline_names: Optional[List[str]] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes baseline evaluations across all dataset pairs.
        Writes atomic JSONL records and experiment manifest to disk.
        """
        if dry_run:
            return self.dry_run(baseline_names=baseline_names)

        selected_names = self.resolve_baselines(requested_names=baseline_names)
        pairs = self.dataset_source.load()
        pair_count = len(pairs)

        exp_dir = self.output_dir / self.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        predictions_path = exp_dir / "predictions.jsonl"
        manifest_path = exp_dir / "manifest.json"

        completed_keys = self._load_completed_evaluations(predictions_path)
        is_resumed = len(completed_keys) > 0
        if is_resumed:
            print(f"[Runner] Resuming experiment '{self.experiment_id}': found {len(completed_keys)} completed evaluations.")

        # Instantiate baselines lazily via registry
        instantiated_methods: Dict[str, BaselineMethod] = {}
        for name in selected_names:
            method = self.registry.get(
                name,
                llm_client=self.llm_client,
                config=self.config,
                seed=self.seed,
                run_id=self.run_id,
                cache_dir=str(exp_dir / "llm_cache"),
                audit_log_dir=str(exp_dir / "llm_audit"),
            )
            instantiated_methods[name] = method

        start_time_all = time.perf_counter()
        records_written = 0

        with open(predictions_path, "a", encoding="utf-8") as f:
            for pair_idx, pair in enumerate(pairs, start=1):
                input_data = pair.to_baseline_input()
                for method_name in selected_names:
                    eval_key = (pair.pair_id, method_name, self.run_id)
                    if eval_key in completed_keys:
                        print(
                            f"[Runner] Skipping completed pair '{pair.pair_id}' on '{method_name}' (run_id: {self.run_id})"
                        )
                        continue

                    method_instance = instantiated_methods[method_name]
                    t0 = time.perf_counter()
                    try:
                        results = method_instance.run(input_data)
                        duration_ms = (time.perf_counter() - t0) * 1000.0

                        per_skill_latency = duration_ms / max(1, len(results))
                        for res in results:
                            record = PredictionRecord(
                                pair_id=pair.pair_id,
                                method=method_name,
                                run_id=self.run_id,
                                skill=res.jd_skill_id,
                                jd_skill_id=res.jd_skill_id,
                                semantic_alignment=(
                                    res.semantic_alignment.value if res.semantic_alignment else None
                                ),
                                required_proficiency=res.required_proficiency,
                                candidate_proficiency=res.candidate_proficiency,
                                gap_magnitude=res.gap_magnitude,
                                priority=res.priority,
                                metadata=res.metadata,
                                duration_ms=round(per_skill_latency, 3),
                                status="OK",
                                error_message=None,
                                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            )
                            f.write(record.model_dump_json() + "\n")
                            records_written += 1
                        f.flush()

                    except Exception as e:
                        duration_ms = (time.perf_counter() - t0) * 1000.0
                        logger.warning(
                            f"[Runner] Evaluation FAILED on pair '{pair.pair_id}' for '{method_name}': {e}"
                        )
                        # Isolate failure: log FAILED records for each JD skill without interrupting run
                        jd_skills_to_log = pair.jd_skills or [None]
                        for s in jd_skills_to_log:
                            s_id = s.skill_id if s else "unknown"
                            record = PredictionRecord(
                                pair_id=pair.pair_id,
                                method=method_name,
                                run_id=self.run_id,
                                skill=s_id,
                                jd_skill_id=s_id,
                                semantic_alignment=None,
                                required_proficiency=None,
                                candidate_proficiency=None,
                                gap_magnitude=None,
                                priority=None,
                                metadata={},
                                duration_ms=round(duration_ms, 3),
                                status="FAILED",
                                error_message=f"{type(e).__name__}: {str(e)}",
                                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            )
                            f.write(record.model_dump_json() + "\n")
                            records_written += 1
                        f.flush()

        total_duration = time.perf_counter() - start_time_all

        # Count total records in predictions.jsonl
        total_records_in_file = 0
        with open(predictions_path, "r", encoding="utf-8") as f:
            total_records_in_file = sum(1 for line in f if line.strip())

        manifest = ExperimentManifest(
            experiment_id=self.experiment_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            git_commit=get_git_commit(),
            python_version=sys.version.split()[0],
            model_name=self.model_name or os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.7-flash"),
            selected_baselines=selected_names,
            pair_count=pair_count,
            total_records=total_records_in_file,
            seed=self.seed,
            enable_llm=self.enable_llm,
            dataset_path=self.dataset_path_str,
            output_dir=str(exp_dir),
            duration_seconds=round(total_duration, 3),
            resumed=is_resumed,
            config={
                "identity_threshold": self.config.thresholds.identity_threshold,
                "floor_threshold": self.config.thresholds.floor_threshold,
                "recency_years_threshold": self.config.recency_years_threshold,
                "reference_date": self.config.reference_date,
            },
        )

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

        print(f"\n[Runner] Experiment '{self.experiment_id}' completed successfully in {total_duration:.2f}s.")
        print(f"[Runner] Saved {records_written} new predictions to: {predictions_path}")
        print(f"[Runner] Saved manifest to: {manifest_path}\n")

        return {
            "experiment_id": self.experiment_id,
            "manifest": manifest,
            "predictions_path": str(predictions_path),
            "manifest_path": str(manifest_path),
            "records_written": records_written,
        }


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Configures and parses CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Skill Gap Evaluation Runner: Executes registered baselines across CV-JD datasets."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/mock_dataset.json",
        help="Path to JSON or JSONL dataset file containing CV-JD pairs.",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Unique experiment identifier (e.g. 'exp_devops_001'). If omitted, an ID with timestamp is generated.",
    )
    parser.add_argument(
        "--baselines",
        nargs="+",
        default=["all"],
        help="Names of baselines to execute (default: 'all').",
    )
    parser.add_argument(
        "--enable-llm",
        action="store_true",
        default=False,
        help="Permits execution of LLM-based baselines. Required when running LLM models to prevent accidental API usage.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Prints the execution plan, baseline breakdown, and estimated LLM calls without calling APIs or writing predictions.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for stochastic baselines (default: 42).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory to save experiment results and manifests (default: 'results').",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="run_1",
        help="Run identifier tag for repeated evaluations (default: 'run_1').",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenRouter model identifier override (defaults to OPENROUTER_MODEL env or config).",
    )
    return parser.parse_args(args)


def main(cli_args: Optional[List[str]] = None) -> int:
    """CLI Entry point for baseline evaluation runner."""
    args = parse_args(cli_args)
    config = load_config()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[Error] Dataset file not found: {dataset_path}", file=sys.stderr)
        return 1

    dataset_source = JSONDatasetSource(dataset_path)

    llm_client: Optional[LLMClient] = None
    model_name = args.model or os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.7-flash")
    if args.enable_llm:
        # Only initialize real LLMClient when explicitly enabled
        llm_client = OpenRouterClient(model=model_name)

    runner = BaselineRunner(
        registry=baseline_registry,
        dataset_source=dataset_source,
        output_dir=args.output_dir,
        experiment_id=args.experiment_id,
        run_id=args.run_id,
        enable_llm=args.enable_llm,
        seed=args.seed,
        config=config,
        llm_client=llm_client,
        model_name=model_name,
        dataset_path_str=str(dataset_path),
    )

    try:
        runner.run(baseline_names=args.baselines, dry_run=args.dry_run)
        return 0
    except Exception as e:
        print(f"\n[Error] Runner execution failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
