# Smile Interview — AI Research Service (Python FastAPI)

Dịch vụ AI phục vụ bài báo nghiên cứu khoa học:
> **"An Automated AI Interview Framework via Dynamic Knowledge-Gap Question Generation and Semantic CV-JD Matching"**  
> *(Khung phỏng vấn AI tự động dựa trên việc sinh câu hỏi khoảng trống kiến thức động và khớp nối ngữ nghĩa CV-JD)*

---

## 1. Kiến trúc Pipeline 3 Module (NCKH Architecture)

```
ai-service/
├── module1_matcher/                    # [Module 1]: SBERT + GNN Adapter (Trích xuất & So khớp kỹ năng)
│   ├── schemas.py                      # ExtractedCVSkill, ExtractedJDSkill, MatchResult
│   ├── extractor.py                    # Pluggable Extractor & Semantic Matcher
│   └── router.py                       # POST /api/v1/match & POST /api/v1/pipeline/analyze
│
├── src/                                # [Module 2]: Skill-Gap Detection (Xác định khoảng trống năng lực)
│   ├── domain/                         # SkillNode, StaticGapAuditReport, SkillGapResult
│   ├── pipeline/                       # SkillGapPipeline
│   └── services/                       # GraphEngine, DependencyResolver
│
├── adaptive_questioning/               # [Module 3]: Bayesian Adaptive Interviewing (Phỏng vấn thích ứng)
│   ├── api/routes.py                   # POST /interview/start, POST /interview/respond, GET /interview/report/{session_id}
│   ├── core/engine.py                  # State machine & Bayesian Belief Update (Blow, Bmed, Bhigh)
│   └── graph/state.py                  # AuditableHITLReport, ReflectiveInsight
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
| `POST` | `/api/v1/interview/start` | Module 3: Khởi tạo buổi phỏng vấn thích ứng dựa trên output Skill-Gap |
| `POST` | `/api/v1/interview/respond` | Module 3: Nhận câu trả lời của ứng viên, cập nhật Bayesian và trả về câu hỏi tiếp theo |
| `GET` | `/api/v1/interview/report/{id}` | Module 3: Trả về Báo cáo Thẩm định Năng lực HITL hoàn chỉnh |

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
*(Hiện tại 132/132 tests đều pass)*
