# Hướng Dẫn Sử Dụng Module Baselines & Evaluation Runner

Module `skill_gap/baselines` cung cấp hạ tầng đối chuẩn (benchmarking harness) cho Module 2 (Skill Gap Detection). Hệ thống tuân thủ chặt chẽ các nguyên lý **SOLID**, đặc biệt là **Open/Closed Principle (OCP)** và **Liskov Substitution Principle (LSP)**: mọi phương pháp đối chuẩn đều kế thừa cùng interface chuẩn và có thể thêm mới mà không cần chỉnh sửa Runner.

---

## 1. Cấu Trúc Thư Mục

```text
skill_gap/
├── skill_gap/baselines/
│   ├── base.py                   # Hợp đồng dữ liệu: BaselineInput, BaselineSkillResult, BaselineMethod
│   ├── dataset.py                # Dataset loader (SRP): DatasetPair, DatasetSource, JSONDatasetSource
│   ├── priority_policies.py      # Chiến lược tính priority (WeightTimesGapPolicy, DepthScaledPriorityPolicy)
│   ├── registry.py               # BaselineRegistry: Quản lý & tra cứu động baselines / lazy factories
│   ├── registrations.py          # Tự động nạp các baseline chuẩn và factory vào registry
│   ├── runner.py                 # CLI Evaluation Runner & Experiment Manifest logger
│   ├── module_adapter.py         # Adapter bọc SkillGapOrchestrator thành ProposedModuleBaseline
│   ├── heuristics/               # Các baseline heuristic đơn giản (không tốn chi phí LLM)
│   │   ├── sim_gap.py            # B-SimGap: gap = clamp(1 - soft_match, 0, 1)
│   │   ├── binary_exact.py       # B-Binary: exact-match heuristic (gap in {0, 1})
│   │   ├── jdw.py                # B-JDW: priority = w_j
│   │   └── random_baseline.py    # B-Random: phân phối đều ngẫu nhiên có kiểm soát seed
│   ├── proficiency/
│   │   └── raw_duration.py       # B-RawDuration: ablation loại bỏ Seniority/Context/Interval union
│   └── llm/
│       ├── schemas.py            # Schema đánh giá CoT: LLMSkillAssessment, LLMZeroShotResponse
│       ├── prompts.py            # Generator prompt độc lập (không rò rỉ công thức nội bộ)
│       ├── parser.py             # Parser JSON & kiểm tra trích dẫn nguyên văn bằng Difflib
│       └── zero_shot.py          # B-LLM-Augmented & B-LLM-TextOnly (retry, audit logging, SHA-256 cache)
├── data/
│   └── mock_dataset.json         # Tập dữ liệu 3 cặp CV-JD mẫu chuẩn hóa theo schema demo.py
├── results/                      # Thư mục lưu kết quả thực nghiệm
│   └── <experiment_id>/
│       ├── predictions.jsonl     # Bản ghi chi tiết từng kỹ năng của từng cặp & baseline
│       └── manifest.json         # Siêu dữ liệu thực nghiệm (git commit, config, runtime, seed)
└── tests/baselines/              # Toàn bộ test suite kiểm thử đơn vị & tích hợp
```

---

## 2. Cách Chạy CLI

Evaluation runner được kích hoạt thông qua lệnh:

```bash
python -m skill_gap.baselines.runner [OPTIONS]
```

### Các tùy chọn dòng lệnh chính:
- `--dataset <path>`: Đường dẫn tới file dataset JSON hoặc JSONL (mặc định: `data/mock_dataset.json`).
- `--experiment-id <id>`: Mã định danh thực nghiệm (ví dụ: `exp_001`). Mặc định tự sinh theo thời gian.
- `--baselines <list>`: Danh sách các baseline cần chạy (ví dụ: `B-SimGap B-Binary` hoặc `all`).
- `--enable-llm`: **Cờ an toàn bắt buộc** để kích hoạt các baseline dùng LLM (`proposed_module`, `B-RawDuration`, `B-LLM-Augmented`, `B-LLM-TextOnly`). Mặc định tắt để chống phát sinh chi phí ngoài ý muốn.
- `--dry-run`: Chế độ xem trước kế hoạch chạy (số cặp, baseline, ước tính số lượt gọi LLM) mà không gọi API hay ghi file.
- `--seed <int>`: Thiết lập seed ngẫu nhiên cho các phương pháp stochastic (mặc định: `42`).
- `--output-dir <dir>`: Thư mục lưu kết quả (mặc định: `results`).
- `--run-id <id>`: Định danh lượt chạy để hỗ trợ chạy lặp nhiều lần (mặc định: `run_1`).
- `--model <str>`: Tùy chọn model OpenRouter (mặc định lấy từ biến môi trường `OPENROUTER_MODEL`).

---

## 3. Các Ví Dụ Thực Thi

### A. Xem trước kế hoạch với chế độ Dry-Run
```bash
python -m skill_gap.baselines.runner --dry-run
```
In ra bảng phân tích chi tiết số cặp, danh sách baseline và ước tính số lượt gọi LLM.

### B. Chạy các baseline Heuristic (Không tốn chi phí LLM)
```bash
python -m skill_gap.baselines.runner --experiment-id exp_heuristics_01 --output-dir results
```
Tự động lọc và chạy các baseline thuần heuristic (`B-Binary`, `B-JDW`, `B-Random`, `B-SimGap`).

### C. Chạy chọn lọc baseline cụ thể
```bash
python -m skill_gap.baselines.runner --experiment-id exp_quick_check --baselines B-SimGap B-Binary
```

### D. Chạy toàn bộ bao gồm cả LLM Baselines
```bash
python -m skill_gap.baselines.runner --experiment-id exp_full_benchmark --enable-llm
```

### E. Tính năng Tự Động Tiếp Tục (Resumption)
Nếu quá trình chạy bị gián đoạn, chỉ cần chạy lại cùng lệnh với cùng `--experiment-id`:
Runner tự động đọc `predictions.jsonl`, bỏ qua toàn bộ các cặp `(pair_id, method, run_id)` đã hoàn thành thành công và chỉ xử lý tiếp những phần còn dang dở.

---

## 4. Định Dạng Đầu Ra

Mỗi thực nghiệm được lưu trong `results/<experiment_id>/`:

### 1. `predictions.jsonl`
Mỗi dòng là một bản ghi JSON ứng với một kỹ năng được đánh giá:
```json
{
  "pair_id": "pair_devops_001",
  "method": "B-SimGap",
  "run_id": "run_1",
  "skill": "linux",
  "jd_skill_id": "linux",
  "semantic_alignment": "MATCH",
  "required_proficiency": null,
  "candidate_proficiency": null,
  "gap_magnitude": 0.8,
  "priority": 0.24,
  "metadata": {"w_j": 0.3},
  "duration_ms": 0.05,
  "status": "OK",
  "error_message": null,
  "timestamp": "2026-10-13T09:50:08.372688+00:00"
}
```

### 2. `manifest.json`
Lưu đầy đủ dấu vết kiểm toán (audit trail):
```json
{
  "experiment_id": "exp_heuristics_01",
  "timestamp": "2026-10-13T09:50:29+00:00",
  "git_commit": "4897c5846868a995159b592b68ec6831b626fd4d",
  "python_version": "3.14.7",
  "model_name": "qwen/qwen3.7-flash",
  "selected_baselines": ["B-Binary", "B-JDW", "B-Random", "B-SimGap"],
  "pair_count": 3,
  "total_records": 52,
  "seed": 42,
  "enable_llm": false,
  "dataset_path": "data\\mock_dataset.json",
  "output_dir": "results\\exp_heuristics_01",
  "duration_seconds": 0.02,
  "resumed": false,
  "config": {
    "identity_threshold": 0.85,
    "floor_threshold": 0.40,
    "recency_years_threshold": 3.0,
    "reference_date": "2024-06-01"
  }
}
```

---

## 5. Cách Thêm Một Baseline Mới (Không Cần Sửa Runner)

Hệ thống được thiết kế theo nguyên lý Open/Closed: thêm baseline mới chỉ cần tạo class và đăng ký vào registry.

### Bước 1: Tạo file baseline mới (ví dụ `skill_gap/baselines/heuristics/my_baseline.py`)
```python
from typing import List
from skill_gap.baselines.base import BaselineMethod, BaselineInput, BaselineSkillResult, BaselineOutputField
from skill_gap.baselines.registry import baseline_registry

class MyCustomBaseline(BaselineMethod):
    def __init__(self, name: str = "B-MyCustom") -> None:
        self._name = name
        self._produces = frozenset({BaselineOutputField.GAP_MAGNITUDE, BaselineOutputField.PRIORITY})

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._produces

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        results = []
        for jd in input_data.jd_skills:
            # Thuật toán tính gap và priority tùy biến ở đây
            results.append(BaselineSkillResult(
                jd_skill_id=jd.skill_id,
                gap_magnitude=0.5,
                priority=0.25,
                metadata={"baseline_name": self._name}
            ))
        return results

# Tự động đăng ký vào registry toàn cục
baseline_registry.register(MyCustomBaseline())
```

### Bước 2: Import module trong `skill_gap/baselines/registrations.py` hoặc CLI
```python
import skill_gap.baselines.heuristics.my_baseline
```

### Bước 3: Chạy trực tiếp từ dòng lệnh
```bash
python -m skill_gap.baselines.runner --baselines B-MyCustom
```
`runner.py` sẽ tự động phát hiện, kiểm tra schema, chạy và ghi kết quả của baseline mới mà **không cần sửa một dòng code nào trong `runner.py`**.
