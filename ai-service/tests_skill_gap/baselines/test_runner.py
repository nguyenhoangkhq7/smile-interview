import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import pytest

from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from skill_gap.baselines.dataset import (
    DatasetPair,
    InMemoryDatasetSource,
    JSONDatasetSource,
    save_dataset_json,
    save_dataset_jsonl,
)
from skill_gap.baselines.llm.schemas import LLMSkillAssessment, LLMZeroShotResponse
from skill_gap.baselines.registry import BaselineRegistry
from skill_gap.baselines.registrations import register_standard_factories
from skill_gap.baselines.runner import BaselineRunner, main, parse_args
from skill_gap.domain.enums import SemanticAlignment, SkillType
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult


# ==============================================================================
# Test Fixtures & Mock Clients
# ==============================================================================


class FakeRunnerLLMClient(LLMClient):
    """
    Fake LLM client for testing runner execution without real network calls.
    Returns valid LLMZeroShotResponse dynamically according to JD skills in the prompt.
    """

    def __init__(self, model: str = "qwen/qwen3.7-flash") -> None:
        self.model = model
        self.call_count = 0
        self.prompts: List[str] = []

    def complete(self, prompt: str, schema: Type[LLMZeroShotResponse]) -> LLMZeroShotResponse:
        self.call_count += 1
        self.prompts.append(prompt)

        # Generate mock assessments based on common skill keywords in the prompt
        skills = []
        for s_id in ["kubernetes", "terraform", "linux", "gcp", "ui_ux", "python", "postgresql", "docker", "redis", "spark", "sql", "airflow", "kafka"]:
            if s_id in prompt.lower():
                skills.append(
                    LLMSkillAssessment(
                        jd_skill_id=s_id,
                        reasoning=f"Candidate assessment for {s_id}.",
                        evidence_quote=f"Quote for {s_id}.",
                        semantic_alignment=SemanticAlignment.MATCH,
                        candidate_proficiency=3.5,
                        required_proficiency=4.0,
                        gap_magnitude=0.125,
                        priority=0.15,
                    )
                )

        if not skills:
            skills.append(
                LLMSkillAssessment(
                    jd_skill_id="default_skill",
                    reasoning="Default assessment.",
                    evidence_quote="Default quote.",
                    semantic_alignment=SemanticAlignment.MATCH,
                    candidate_proficiency=3.0,
                    required_proficiency=3.0,
                    gap_magnitude=0.0,
                    priority=0.0,
                )
            )

        return LLMZeroShotResponse(skills=skills)


class FaultyBaseline(BaselineMethod):
    """Faulty baseline designed to simulate unexpected pipeline exceptions."""

    def __init__(self, name: str = "B-Faulty") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return frozenset({BaselineOutputField.GAP_MAGNITUDE})

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        raise RuntimeError("Simulated pipeline failure during execution!")


class CustomNewBaseline(BaselineMethod):
    """New baseline implementing OCP without any modifications to runner code."""

    def __init__(self, name: str = "B-CustomNew") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return frozenset({BaselineOutputField.PRIORITY})

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        return [
            BaselineSkillResult(
                jd_skill_id=jd.skill_id,
                priority=0.42,
                metadata={"custom": "ocp_verified"},
            )
            for jd in input_data.jd_skills
        ]


@pytest.fixture
def mock_dataset_pairs() -> List[DatasetPair]:
    """Provides 3 mock CV-JD pairs matching demo.py format."""
    p1 = DatasetPair(
        pair_id="pair_devops_001",
        cv_text="Alice - DevOps Engineer with Kubernetes and Terraform experience.",
        jd_text="Requirements: Kubernetes, Terraform, Linux.",
        cv_skills=[
            ExtractedCVSkill(skill_id="kubernetes", type=SkillType.EXPLICIT, confidence=0.98, evidence_spans=["Kubernetes exp"]),
            ExtractedCVSkill(skill_id="terraform", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["Terraform exp"]),
        ],
        jd_skills=[
            ExtractedJDSkill(skill_id="kubernetes", type=SkillType.EXPLICIT, confidence=0.99, evidence_spans=["Kubernetes req"]),
            ExtractedJDSkill(skill_id="terraform", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["Terraform req"]),
            ExtractedJDSkill(skill_id="linux", type=SkillType.EXPLICIT, confidence=0.90, evidence_spans=["Linux req"]),
        ],
        match_results=[
            MatchResult(jd_skill_id="kubernetes", w_j=0.4, matched_cv_skill_id="kubernetes", soft_match=1.0),
            MatchResult(jd_skill_id="terraform", w_j=0.3, matched_cv_skill_id="terraform", soft_match=1.0),
            MatchResult(jd_skill_id="linux", w_j=0.3, matched_cv_skill_id="kubernetes", soft_match=0.2),
        ],
    )
    p2 = DatasetPair(
        pair_id="pair_backend_002",
        cv_text="Bob - Python Backend Developer with Docker.",
        jd_text="Requirements: Python, Docker.",
        cv_skills=[
            ExtractedCVSkill(skill_id="python", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["Python exp"]),
            ExtractedCVSkill(skill_id="docker", type=SkillType.EXPLICIT, confidence=0.90, evidence_spans=["Docker exp"]),
        ],
        jd_skills=[
            ExtractedJDSkill(skill_id="python", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["Python req"]),
            ExtractedJDSkill(skill_id="docker", type=SkillType.EXPLICIT, confidence=0.90, evidence_spans=["Docker req"]),
        ],
        match_results=[
            MatchResult(jd_skill_id="python", w_j=0.6, matched_cv_skill_id="python", soft_match=1.0),
            MatchResult(jd_skill_id="docker", w_j=0.4, matched_cv_skill_id="docker", soft_match=1.0),
        ],
    )
    p3 = DatasetPair(
        pair_id="pair_data_003",
        cv_text="Charlie - Data Engineer with SQL.",
        jd_text="Requirements: SQL, Spark.",
        cv_skills=[
            ExtractedCVSkill(skill_id="sql", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["SQL exp"]),
        ],
        jd_skills=[
            ExtractedJDSkill(skill_id="sql", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=["SQL req"]),
            ExtractedJDSkill(skill_id="spark", type=SkillType.EXPLICIT, confidence=0.90, evidence_spans=["Spark req"]),
        ],
        match_results=[
            MatchResult(jd_skill_id="sql", w_j=0.5, matched_cv_skill_id="sql", soft_match=1.0),
            MatchResult(jd_skill_id="spark", w_j=0.5, matched_cv_skill_id="sql", soft_match=0.3),
        ],
    )
    return [p1, p2, p3]


# ==============================================================================
# 1. Test Dry-Run: Không gọi LLM Client, không ghi file
# ==============================================================================


def test_dry_run_makes_zero_llm_calls_and_no_file_writes(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử chế độ dry-run:
    - In kế hoạch ước tính số lần gọi LLM.
    - Không gọi API LLM (call_count == 0).
    - Không tạo file dự đoán hay thư mục kết quả.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_llm = FakeRunnerLLMClient()
        source = InMemoryDatasetSource(mock_dataset_pairs)

        registry = BaselineRegistry()
        from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
        registry.register(SimGapBaseline())
        register_standard_factories(registry)

        runner = BaselineRunner(
            registry=registry,
            dataset_source=source,
            output_dir=tmp_dir,
            experiment_id="exp_dry_run_test",
            enable_llm=True,
            llm_client=fake_llm,
        )

        plan = runner.dry_run(baseline_names=["B-SimGap", "B-LLM-Augmented"])

        # 1. Đảm bảo FakeLLMClient không bị gọi bất kỳ lần nào
        assert fake_llm.call_count == 0
        assert len(fake_llm.prompts) == 0

        # 2. Đảm bảo kế hoạch tính toán đúng số lượng
        assert plan["pair_count"] == 3
        # B-SimGap: 0 calls; B-LLM-Augmented: 1 call * 3 pairs = 3 calls
        assert plan["total_estimated_llm_calls"] == 3

        # 3. Đảm bảo không có file output nào được ghi ra disk trong dry-run
        exp_dir = Path(tmp_dir) / "exp_dry_run_test"
        assert not exp_dir.exists()


# ==============================================================================
# 2. Test Execution & Output Schema Validation
# ==============================================================================


def test_runner_executes_and_validates_jsonl_and_manifest(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử runner thực thi trên 3 cặp mock:
    - Ghi đúng từng dòng JSONL với đầy đủ trường dữ liệu.
    - Ghi manifest.json chứa commit hash, cấu hình, seed, model, v.v.
    - Giá trị tính tay: Pair 1 có 3 JD skills, Pair 2 có 2 JD skills, Pair 3 có 2 JD skills.
      Tổng cộng = 3 + 2 + 2 = 7 skills.
      Chạy 2 baselines: 7 * 2 = 14 records trong JSONL.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_llm = FakeRunnerLLMClient()
        source = InMemoryDatasetSource(mock_dataset_pairs)

        registry = BaselineRegistry()
        from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
        registry.register(SimGapBaseline())
        register_standard_factories(registry)

        runner = BaselineRunner(
            registry=registry,
            dataset_source=source,
            output_dir=tmp_dir,
            experiment_id="exp_full_run",
            run_id="run_test",
            enable_llm=True,
            seed=42,
            llm_client=fake_llm,
            model_name="qwen/test-model",
        )

        res = runner.run(baseline_names=["B-SimGap", "B-LLM-Augmented"])

        pred_file = Path(res["predictions_path"])
        manifest_file = Path(res["manifest_path"])

        assert pred_file.exists()
        assert manifest_file.exists()

        # Kiểm tra nội dung predictions.jsonl
        records = []
        with open(pred_file, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                records.append(rec)

        # Tính tay: (3 + 2 + 2) skills * 2 methods = 14 records
        assert len(records) == 14
        assert res["records_written"] == 14

        # Kiểm tra schema từng record
        for r in records:
            assert "pair_id" in r
            assert "method" in r and r["method"] in ["B-SimGap", "B-LLM-Augmented"]
            assert r["run_id"] == "run_test"
            assert "skill" in r
            assert "jd_skill_id" in r
            assert r["status"] == "OK"
            assert r["error_message"] is None
            assert r["duration_ms"] >= 0.0
            assert "timestamp" in r

        # B-SimGap hand-calculated check trên Pair 1:
        # linux: soft_match = 0.20 -> gap = clamp(1 - 0.20, 0, 1) = 0.80
        # priority = w_j * gap = 0.3 * 0.8 = 0.24
        p1_linux = [
            r for r in records
            if r["pair_id"] == "pair_devops_001" and r["skill"] == "linux" and r["method"] == "B-SimGap"
        ][0]
        assert p1_linux["gap_magnitude"] == pytest.approx(0.80, abs=1e-5)
        assert p1_linux["priority"] == pytest.approx(0.24, abs=1e-5)

        # Kiểm tra manifest.json
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        assert manifest_data["experiment_id"] == "exp_full_run"
        assert manifest_data["git_commit"] != ""
        assert manifest_data["python_version"] != ""
        assert manifest_data["model_name"] == "qwen/test-model"
        assert manifest_data["selected_baselines"] == ["B-SimGap", "B-LLM-Augmented"]
        assert manifest_data["pair_count"] == 3
        assert manifest_data["total_records"] == 14
        assert manifest_data["seed"] == 42
        assert manifest_data["enable_llm"] is True
        assert manifest_data["resumed"] is False
        assert "identity_threshold" in manifest_data["config"]


# ==============================================================================
# 3. Test Resumability: Chạy lại bỏ qua bản ghi đã có
# ==============================================================================


def test_runner_resumability_skips_completed_evaluations(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử tính năng tiếp tục khi gián đoạn (resumable):
    - Lượt 1: Chạy B-SimGap trên 3 cặp -> ghi 7 dòng.
    - Lượt 2: Chạy lại cùng experiment_id và run_id -> phát hiện đã xong, ghi 0 dòng mới.
    - File predictions.jsonl vẫn giữ nguyên 7 dòng, không bị nhân đôi.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        source = InMemoryDatasetSource(mock_dataset_pairs)
        registry = BaselineRegistry()
        from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
        registry.register(SimGapBaseline())

        runner = BaselineRunner(
            registry=registry,
            dataset_source=source,
            output_dir=tmp_dir,
            experiment_id="exp_resume_test",
            run_id="run_1",
        )

        # Chạy lần đầu
        res_1 = runner.run(baseline_names=["B-SimGap"])
        assert res_1["records_written"] == 7

        # Chạy lần hai với cùng tham số
        res_2 = runner.run(baseline_names=["B-SimGap"])
        assert res_2["records_written"] == 0
        assert res_2["manifest"].resumed is True

        # Đọc lại file xem có đúng vẫn là 7 dòng không
        with open(res_2["predictions_path"], "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 7


# ==============================================================================
# 4. Test Error Isolation: Lỗi một baseline/cặp không làm dừng cả lượt
# ==============================================================================


def test_runner_error_isolation_and_continues_on_failure(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử khả năng cách ly lỗi:
    - B-Faulty ném lỗi RuntimeError trong quá trình chạy.
    - B-SimGap vẫn chạy bình thường và ghi kết quả status='OK'.
    - B-Faulty ghi nhận status='FAILED' cùng chi tiết lỗi.
    - Toàn bộ quá trình chạy không bị crash.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        source = InMemoryDatasetSource(mock_dataset_pairs)
        registry = BaselineRegistry()
        from skill_gap.baselines.heuristics.sim_gap import SimGapBaseline
        registry.register(SimGapBaseline())
        registry.register(FaultyBaseline())

        runner = BaselineRunner(
            registry=registry,
            dataset_source=source,
            output_dir=tmp_dir,
            experiment_id="exp_fault_isolation",
            run_id="run_fault",
        )

        res = runner.run(baseline_names=["B-SimGap", "B-Faulty"])

        # Kiểm tra file predictions
        records = []
        with open(res["predictions_path"], "r", encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))

        sim_records = [r for r in records if r["method"] == "B-SimGap"]
        fault_records = [r for r in records if r["method"] == "B-Faulty"]

        # B-SimGap hoàn toàn thành công
        assert len(sim_records) == 7
        for r in sim_records:
            assert r["status"] == "OK"
            assert r["error_message"] is None

        # B-Faulty được ghi nhận FAILED độc lập
        assert len(fault_records) == 7
        for r in fault_records:
            assert r["status"] == "FAILED"
            assert "Simulated pipeline failure" in r["error_message"]
            assert r["gap_magnitude"] is None


# ==============================================================================
# 5. Test Open/Closed Principle (Thêm baseline mới không sửa runner)
# ==============================================================================


def test_open_closed_principle_new_baseline_works_without_modifying_runner(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử nguyên lý Open/Closed (OCP):
    - Đăng ký một baseline hoàn toàn mới (CustomNewBaseline) vào registry.
    - Runner chạy trơn tru mà không cần bất kỳ dòng code nào sửa đổi trong runner.py.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        source = InMemoryDatasetSource(mock_dataset_pairs)
        registry = BaselineRegistry()
        registry.register(CustomNewBaseline())

        runner = BaselineRunner(
            registry=registry,
            dataset_source=source,
            output_dir=tmp_dir,
            experiment_id="exp_ocp_test",
        )

        res = runner.run(baseline_names=["B-CustomNew"])

        records = []
        with open(res["predictions_path"], "r", encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))

        assert len(records) == 7
        for r in records:
            assert r["method"] == "B-CustomNew"
            assert r["status"] == "OK"
            assert r["priority"] == 0.42
            assert r["metadata"]["custom"] == "ocp_verified"


# ==============================================================================
# 6. Test Dataset Loader: JSON, JSONL và Edge cases
# ==============================================================================


def test_dataset_loader_json_and_jsonl(mock_dataset_pairs: List[DatasetPair]) -> None:
    """
    Kiểm thử DatasetLoader hỗ trợ cả file .json và file .jsonl,
    tự động gán pair_id khi bị thiếu trong dữ liệu thô.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = Path(tmp_dir) / "data.json"
        jsonl_path = Path(tmp_dir) / "data.jsonl"

        save_dataset_json(mock_dataset_pairs, json_path)
        save_dataset_jsonl(mock_dataset_pairs, jsonl_path)

        source_json = JSONDatasetSource(json_path)
        source_jsonl = JSONDatasetSource(jsonl_path)

        pairs_from_json = source_json.load()
        pairs_from_jsonl = source_jsonl.load()

        assert len(pairs_from_json) == 3
        assert len(pairs_from_jsonl) == 3
        assert pairs_from_json[0].pair_id == "pair_devops_001"
        assert pairs_from_jsonl[0].pair_id == "pair_devops_001"

        # Edge case: file không tồn tại
        with pytest.raises(FileNotFoundError):
            JSONDatasetSource(Path(tmp_dir) / "nonexistent.json").load()


# ==============================================================================
# 7. Test CLI Entry Point & Safety Checks
# ==============================================================================


def test_cli_safety_checks_and_argument_parsing(tmp_path, mock_dataset_pairs) -> None:
    """
    Kiểm thử CLI:
    - Báo lỗi và dừng lại khi chọn LLM baseline mà không truyền --enable-llm.
    - Báo lỗi khi baseline không tồn tại.
    - Dry-run mode trả về exit code 0.
    """
    dataset = tmp_path / "mock_dataset.json"
    save_dataset_json(mock_dataset_pairs, dataset)
    # 1. Chạy LLM baseline không có --enable-llm -> Exit code 1
    code_llm_block = main(["--dataset", str(dataset), "--baselines", "B-LLM-Augmented"])
    assert code_llm_block == 1

    # 2. Chạy baseline không tồn tại -> Exit code 1
    code_invalid = main(["--dataset", str(dataset), "--baselines", "NonexistentBaseline"])
    assert code_invalid == 1

    # 3. Dry-run mode -> Exit code 0
    code_dry = main(["--dataset", str(dataset), "--dry-run"])
    assert code_dry == 0
