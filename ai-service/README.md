# Smile Interview — AI Research Service (Python FastAPI)

Dịch vụ AI phục vụ bài báo nghiên cứu khoa học:
> **"An Automated AI Interview Framework via Dynamic Knowledge-Gap Question Generation and Semantic CV-JD Matching"**  
> *(Khung phỏng vấn AI tự động dựa trên việc sinh câu hỏi khoảng trống kiến thức động và khớp nối ngữ nghĩa CV-JD)*

---

## 1. Kiến trúc Pipeline 3 Module (NCKH Architecture)

```
ai-service/
├── matching_cv/                        # [Module 1]: trích xuất, SBERT, đồ thị, trọng số JD và API matching
│   ├── app/schemas/module1.py          # Hợp đồng output dùng chung với Module 2
│   └── app/api/v1/endpoints/unified.py # POST /api/v1/match & POST /api/v1/pipeline/analyze
│
├── skill_gap/                          # [Module 2]: Skill-Gap Detection (Xác định khoảng trống năng lực)
│   ├── domain/                         # JobTask, SkillGapSummary, SkillGapResult, SkillGapReportSummary
│   ├── pipeline/                       # SkillGapOrchestrator
│   └── services/                       # ResumeSegmenter, JDRequirementParser, ProficiencyEstimator, GapDetector
│
├── adaptive_questioning/               # [Module 3]: Phỏng vấn thích ứng theo bằng chứng
│   ├── evidence/routes.py              # POST /api/v2/interview/start, /respond, /conversation, /stop
│   ├── evidence/assessment.py          # Kiểm tra trích dẫn, tổng hợp bằng chứng theo Criteria
│   └── evidence/models.py              # Objective, Turn, Judgment, ObjectiveState, Snapshot
│
├── app/
│   ├── config.py                       # Cấu hình môi trường & Settings
│   └── main.py                         # FastAPI App Factory & Route Mounting
│
├── tests_skill_gap/                    # Test suite kiểm thử Module 1 & Module 2
├── tests_adaptive_questioning/         # Test suite kiểm thử Module 3
└── main.py                             # Entrypoint khởi chạy uvicorn
```

---

## 2. API Endpoints Chính

| Phương thức | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `POST` | `/api/v1/match` | Module 1: So khớp ngữ nghĩa kỹ năng CV và JD |
| `POST` | `/api/v1/pipeline/analyze` | Module 2: Nhận CV + JD và trả về kết quả phân tích khoảng trống năng lực (Skill-Gap) |
| `POST` | `/api/v2/interview/start` | Module 3: Lập kế hoạch và tạo câu hỏi từ Skill-Gap và nhiệm vụ JD |
| `POST` | `/api/v2/interview/respond` | Module 3: Đánh giá bằng chứng và tạo câu hỏi tiếp theo |
| `POST` | `/api/v2/interview/stop` | Module 3: Kết thúc và trả báo cáo theo Criteria |

`/api/v1/match` trả `cv_skills`, `jd_skills`, `match_results` và `matcher_source: MATCHING_CV`. Cả hai endpoint phân tích hỗ trợ JSON văn bản và multipart. Module 2 dùng cùng văn bản đã làm sạch mà Module 1 dùng để trích dẫn. Kỹ năng JD thiếu cặp CV có `matched_cv_skill_id: "none"` và `soft_match: 0`. Confidence thiếu được ghi là `0`. Trọng số JD thiếu làm phân tích trả HTTP 503.

`/api/v1/pipeline/analyze`, `/api/v1/skill-gap/analyze` và `/api/v1/skill-gap/analyze-with-report` trả `analysis_id`, `skills[]` và `report` gồm `matching_score` và `degraded`. Điểm phù hợp CV–JD nằm trên thang 0–1 khi matcher cung cấp điểm, hoặc `null` khi chưa có điểm. Mỗi kỹ năng chỉ giữ phần tóm tắt cần cho người dùng và phỏng vấn (`priority`, `semantic_alignment`, `required_proficiency`, `importance_weight`, `cv_evidence_spans`, `job_tasks`), kèm `jd_evidence_spans` khi có trích dẫn JD cấp kỹ năng chưa gắn với nhiệm vụ; các trường chẩn đoán nội bộ (`is_substituted`, `candidate_proficiency`, `gap_magnitude`, `flags`, `degraded` cấp kỹ năng) được lược bỏ khỏi output REST.

Module 2 dùng điểm năng lực CV/JD và độ thiếu hụt tất định; không khởi tạo phân phối xác suất năng lực. Module 3 không yêu cầu hoặc cập nhật `raw_belief`, `belief`, `tag` hay TV. Engine phỏng vấn cũ đã được gỡ; API AI `/api/v1/interview/*` trả HTTP 410. Dataset và bộ tối ưu DSPy được khôi phục, chuyển sang schema bằng chứng V2; xem [hướng dẫn compile/load](adaptive_questioning/optimization/README.md). Backend vẫn phục vụ báo cáo cũ đã lưu, không gọi AI để tính lại. Schema V2 áp dụng `extra="forbid"`, nên snapshot/turn chứa các field đã loại bỏ (`engine_version`, `rubric_version`, `question.assistance`, `objective.inferred`, `objective.extension_criterion_ids`, `objective_state.clarification_spent`, `conversation.introduction_skipped`) sẽ bị từ chối khi xác thực. Xem [tài liệu V2](../docs/evidence-interview-v2.md).

Module extract explicit skill trong `matching_cv` dùng DSPy Signature và metric F0.5 ưu tiên precision. Dataset có ví dụ phân biệt skill thực tế với bằng cấp/ngành học, chức danh, lĩnh vực của nhà tuyển dụng và coursework. Compile bộ few-shot ban đầu từ thư mục `ai-service` bằng `python -m matching_cv.dspy_modules.compiler`; module được lưu ở `matching_cv/dspy_modules/compiled_modules/explicit_skill_extractor.json`. So sánh prompt cũ với DSPy trên holdout bằng `python -m matching_cv.dspy_modules.benchmark` (cần OpenRouter key và gửi văn bản holdout cho model). Khi bật `MATCHING_CV_DSPY_EXPLICIT_ENABLED=true`, cache extract không có `extractor_version=explicit_dspy_v1` hoặc metadata schema `dspy_explicit_v1` sẽ bị bỏ qua để tránh dùng kết quả trước DSPy. Nếu chưa có artifact đã compile, runtime nạp bộ ví dụ gold cục bộ làm few-shot seed.

---

## 3. Khởi chạy & Kiểm thử

### Khởi chạy dịch vụ:
```bash
cd ai-service
pip install -r requirements.txt
python main.py
```
Dịch vụ sẽ lắng nghe tại `http://localhost:8000`. Swagger UI có tại `http://localhost:8000/docs`.

Lần chạy đầu, tải trước model SBERT vào volume cache trước khi phân tích CV/JD để thời gian tải không nằm trong timeout 180 giây của backend. Chạy từ thư mục gốc repository:

```bash
docker compose run --rm --no-deps ai-service python -c "from matching_cv.app.core.config import settings; from matching_cv.app.core.model_loader import model_loader; model_loader.load_model(settings.STAGE3_MODEL_NAME, revision=settings.STAGE3_MODEL_REVISION)"
```

Chờ lệnh hoàn tất rồi gửi yêu cầu phân tích. Volume `sbert_cache` giữ model qua các lần tạo lại container. Có thể thêm `HF_TOKEN` vào `ai-service/.env` để dùng hạn mức tải có xác thực.

Compose mount trọng số GNN từ `ai-service/matching_cv/data/checkpoints/paper_aligned_gnn/`, hoặc từ thư mục tuyệt đối đặt qua `GNN_CHECKPOINT_DIR` trong `.env` gốc. Dịch vụ local có thể chạy chế độ chẩn đoán khi chưa có checkpoint v4. Xem hướng dẫn staging để chạy chế độ yêu cầu checkpoint.

Image Docker dùng `requirements-docker.lock` cho Python 3.14 trên Linux amd64 và arm64. Khi cập nhật dependencies, tạo lại lockfile từ `requirements-docker.in` bằng lệnh `uv pip compile` ở đầu lockfile. Điền SHA-256 của hai wheel PyTorch CPU `cp314-cp314` cho `x86_64` và `aarch64` từ liên kết trên chỉ mục PyTorch trong file `.in`, rồi build lại image AI.

### Chạy kiểm thử tự động (Unit & Integration Tests):
```bash
pip install -r requirements-dev.txt
pytest tests_skill_gap tests_adaptive_questioning -q
```
Kết quả kiểm thử thay đổi theo phiên bản; chạy lệnh trên để kiểm tra mã hiện tại.
