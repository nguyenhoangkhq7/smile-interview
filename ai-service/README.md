# Smile Interview — AI Research Service (Python FastAPI)

Dịch vụ AI độc lập phục vụ bài báo nghiên cứu khoa học:
> **"An Automated AI Interview Framework via Dynamic Knowledge-Gap Question Generation and Semantic CV-JD Matching"**  
> *(Khung phỏng vấn AI tự động dựa trên việc sinh câu hỏi khoảng trống kiến thức động và khớp nối ngữ nghĩa CV-JD)*

---

## 1. Kiến trúc phân tách (Clean Architecture + Anti-Corruption Layer)

```
ai-service/app/
├── research/                       # PHÒNG THÍ NGHIỆM KHOA HỌC (Độc lập với hệ thống Web)
│   ├── models.py                   # Data classes khoa học (SkillNode, DependencyEdge, SkillGapResult...)
│   ├── sbert_gnn_matcher.py        # [Đóng góp 1]: Sentence-BERT + GNN Skill Dependency Graph
│   ├── skill_gap_detector.py       # [Đóng góp 2]: Thuật toán phát hiện Khoảng trống năng lực (Skill-Gap)
│   └── adaptive_question_chain.py  # [Đóng góp 3]: Cơ chế Prompt-Chaining sinh câu hỏi thích ứng
├── adapters/                       # TẦNG CHUYỂN ĐỔI (Anti-Corruption Layer)
│   └── system_dto_adapter.py       # Dịch Output nghiên cứu <-> DTO chuẩn của Spring Boot & Next.js
├── schemas/                        # Hợp đồng dữ liệu JSON (Pydantic Schemas)
│   ├── cv_jd_schema.py
│   └── question_schema.py
└── routers/                        # REST API Endpoints
    ├── cv_jd.py                    # POST /api/ai/cv-jd/match
    ├── questions.py                # POST /api/ai/questions/generate & /regenerate-single
    └── interview.py                # POST /api/ai/interview/evaluate
```

---

## 2. Hướng dẫn thay thế thuật toán nghiên cứu

Bạn chỉ cần làm việc trong thư mục `app/research/` mà không cần lo lắng về cấu trúc Database hay Frontend:

1. **Đóng góp 1 (`app/research/sbert_gnn_matcher.py`)**:
   - Thay hàm `_compute_sbert_node_similarities()` bằng mô hình `SentenceTransformer` của bạn.
   - Thay hàm `_propagate_gnn_scores()` bằng mạng `GCNConv` / `GATConv` (PyTorch Geometric).
2. **Đóng góp 2 (`app/research/skill_gap_detector.py`)**:
   - Tùy biến thuật toán `detect_gaps()` trên đồ thị phụ thuộc kỹ năng.
3. **Đóng góp 3 (`app/research/adaptive_question_chain.py`)**:
   - Tùy biến 3 bước Prompt-Chaining (`_step1_analyze_gap_focus`, `_step2_generate_grounded_question`, `_step3_calibrate_rubric`).

---

## 3. Khởi chạy và Kết nối với Spring Boot

### Khởi chạy AI Service:
```bash
cd ai-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Kích hoạt ở Spring Boot Backend:
Đặt biến môi trường `AI_PROVIDER=fastapi` hoặc trong `backend/src/main/resources/application.yaml`:
```yaml
app:
  ai:
    provider: ${AI_PROVIDER:fastapi}
    fastapi:
      base-url: ${FASTAPI_AI_BASE_URL:http://localhost:8000}
```
