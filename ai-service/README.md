# Smile Interview — AI Research Service (Python FastAPI)

Dịch vụ AI phục vụ bài báo nghiên cứu khoa học:
> **"An Automated AI Interview Framework via Dynamic Knowledge-Gap Question Generation and Semantic CV-JD Matching"**  
> *(Khung phỏng vấn AI tự động dựa trên việc sinh câu hỏi khoảng trống kiến thức động và khớp nối ngữ nghĩa CV-JD)*

---

## 1. Kiến trúc Pipeline 3 Module (NCKH Architecture)

```
ai-service/
├── matching_cv/                        # [Module 1]: trích xuất, SBERT, đồ thị và ước lượng trọng số JD
├── module1_matcher/
│   ├── schemas.py                      # Hợp đồng Module1Output dùng chung với Module 2
│   └── router.py                       # POST /api/v1/match & POST /api/v1/pipeline/analyze
│
├── skill_gap/                                # [Module 2]: Skill-Gap Detection (Xác định khoảng trống năng lực)
│   ├── domain/                         # SkillNode, StaticGapAuditReport, SkillGapResult
│   ├── pipeline/                       # SkillGapPipeline
│   └── services/                       # GraphEngine, DependencyResolver
│
├── adaptive_questioning/               # [Module 3]: Phỏng vấn thích ứng theo bằng chứng
│   ├── evidence/routes.py             # POST /api/v2/interview/start, /respond, /stop
│   ├── evidence/assessment.py         # Kiểm tra trích dẫn, tổng hợp bằng chứng theo Criteria
│   └── evidence/models.py             # Objective, Turn, Judgment, ObjectiveState, Snapshot
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

`/api/v1/pipeline/analyze` trả thêm `report.matching_score` trên thang 0–1 khi checkpoint GNN cho kết quả. Khi điểm không khả dụng, trường này là `null` và báo cáo skill gap vẫn được trả về.

Module 2 dùng điểm năng lực CV/JD và độ thiếu hụt tất định; không khởi tạo phân phối xác suất năng lực. Module 3 không yêu cầu hoặc cập nhật `raw_belief`, `belief`, `tag` hay TV. Engine phỏng vấn cũ đã được gỡ; API AI `/api/v1/interview/*` trả HTTP 410. Dataset và bộ tối ưu DSPy được khôi phục, chuyển sang schema bằng chứng V2; xem [hướng dẫn compile/load](adaptive_questioning/optimization/README.md). Backend vẫn phục vụ báo cáo cũ đã lưu, không gọi AI để tính lại. Snapshot V2 cũ được đọc bằng cách bỏ qua các field đã loại bỏ; lần chuyển trạng thái thành công tiếp theo lưu cấu trúc mới. Xem [tài liệu V2](../docs/evidence-interview-v2.md).

---

## 3. Khởi chạy & Kiểm thử

### Khởi chạy dịch vụ:
```bash
cd ai-service
pip install -r requirements.txt
python main.py
```
Dịch vụ sẽ lắng nghe tại `http://localhost:8000`. Swagger UI có tại `http://localhost:8000/docs`.

### Chạy kiểm thử tự động (Unit & Integration Tests):
```bash
pytest tests_skill_gap tests_adaptive_questioning -q
```
Kết quả kiểm thử thay đổi theo phiên bản; chạy lệnh trên để kiểm tra mã hiện tại.
