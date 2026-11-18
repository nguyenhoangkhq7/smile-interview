# Truy vết Module 3 · Phỏng vấn `MIXED` 10 câu

Phiên `module3-qa-mixed10-20261118-01`, ngày 18/11/2026 (giờ Việt Nam). Vai trò giả lập là Backend Engineer — Orders & Payments. Mode `MIXED`, kênh `TEXT`, giới hạn 10 câu và 8 câu/mục tiêu. Ngân sách chuyên môn đặt là 3.600 giây để dành thời gian đọc câu hỏi và nhập từng câu trả lời trong cuộc kiểm thử.

## Cách thực thi và cách đọc dữ liệu

Tiến trình kiểm thử chạy trong container `ai_service` đang hoạt động, nạp `app.main:app` từ `/app` và gửi request qua FastAPI TestClient đến các route `/api/v2/interview/*`. Provider vẫn là `DSPyAssessmentProvider`, với `openrouter/qwen/qwen3.7-flash` theo cấu hình của container. Bộ ghi chỉ chuyển tiếp lời gọi, sao chép đối số và ghi kết quả cùng lỗi. Tiến trình có bộ nhớ và cache riêng. [Mã bộ ghi](capture.py) · [Runtime và SHA-256 của mã thực thi](run/runtime.json) · [Health của dịch vụ đang chạy](run/live-health.json).

- **Dữ liệu giả lập đã gửi** gồm hồ sơ, trích dẫn CV/JD, Skill Gap, phần tự giới thiệu và câu trả lời. Fixture có mục tiêu core đã khớp CV (`python`, `priority=0`), kỹ năng ứng viên chưa có bằng chứng (`rabbitmq`, `cv_evidence_spans=[]`), nhiệm vụ bắt buộc và nhiệm vụ tùy chọn. Các bản ghi `job_tasks` chứa `task_id`, mô tả, trích dẫn JD, mức yêu cầu, loại yêu cầu và căn cứ mức. Dữ liệu vào bắt đầu tại hợp đồng `StartRequest.skills` sau phép chiếu từ Module 2. [Fixture gốc](inbox/01-start.json).
- **Kết quả thực thi** gồm request/response thực tế của ASGI, snapshot, state công khai, các trạng thái tạm trong lời gọi thất bại, log vận hành và kết quả model quan sát tại biên DSPy. JSONL sắp thứ tự bằng `seq`, thời gian UTC và `step`. Ghép sự kiện `call` với `return` hoặc `error` bằng `call_id`. Các batch Blueprint song song nên sự kiện có thể xen kẽ. Những hàm thay đổi đối số có trường `mutated_arguments` ngay sau lời gọi. [Trace thành phần](run/components.jsonl) · [Chỉ mục thời gian](run/timeline.json).
- **Nhận xét kiểm thử** nằm trong phần đối chiếu sau diễn biến. Nội dung Judge tự sinh nằm nguyên văn dưới `judgment` hoặc `rationale`. Hai nguồn này có thể đi đến kết luận khác nhau.

Phạm vi là Module 3 ở API tính toán nội bộ. TestClient truyền nguyên snapshot HTTP 200 của bước trước vào bước sau và giữ nguyên version, ID câu hỏi hoặc ID lời thoại tương ứng. Trong ứng dụng, `EvidenceInputs` lấy Skill Gap từ hồ sơ/phiên rồi chiếu trường, còn `EvidenceStore` lưu snapshot với kiểm tra version và biên nhận lệnh. Phiên kiểm thử này quan sát các chuyển trạng thái trong Python. Luồng đăng nhập, Java/PostgreSQL persistence, trình duyệt, voice và Module 1–2 nằm ngoài lần chạy. JSONL ghi các trường hiển thị của request/completion ở lớp DSPy, bao gồm messages, nội dung trả về, token usage khi có và model được phản hồi. Header xác thực, traffic thô trên dây và suy luận nội bộ của nhà cung cấp nằm ngoài dữ liệu quan sát. [Hợp đồng backend](../../backend/src/main/java/fit/iuh/modules/evidence/EvidenceInputs.java) · [Lưu trạng thái backend](../../backend/src/main/java/fit/iuh/modules/evidence/EvidenceStore.java).

Đối chiếu ảnh container với workspace lúc xuất hiện vật cho thấy 17/19 file Python trong thư mục `evidence` trùng SHA-256. `__init__.py` khác docstring. `workflow.py` trong workspace bổ sung nội dung sửa câu hỏi mặc định cho verdict chưa có trong `ALIGNMENT_REPAIRS` và bỏ một import. Báo cáo dùng bản container đã thực thi. [Workflow đã chạy](run/executed-source/workflow.py) · [Đối chiếu hash](run/source-verification.json).

## Các thành phần và hợp đồng dữ liệu

| Thành phần | Input quan sát được | Output và vai trò |
| --- | --- | --- |
| `requirements_for` | `InterviewSkill[]` gồm task, CV/JD evidence, mức yêu cầu, trọng số và priority | Dựng yêu cầu với khóa `jd_skill_id:task_id`, mô tả và trích dẫn từ JD. |
| `BlueprintBuilder` và DSPy `blueprint` | Các yêu cầu chia batch tối đa 3, định nghĩa L1–L4, policy extension | Model trả `BlueprintDraft` gồm rubric, độ sâu, mode phù hợp. Builder kiểm coverage, gán `objective_id`, `criterion_id`, ground `claim`/JD và khóa độ sâu. |
| `plan` và `select_mode` | Blueprint đã kiểm định, `importance_weight`, `priority`, cấu hình thời gian và câu hỏi, policy | Trả các `ObjectiveState` và `queue`. Ưu tiên core, yêu cầu bắt buộc, trọng số, priority, thời lượng ước tính và ID. Ưu tiên phủ kỹ năng trước khi thêm nhiệm vụ thứ hai của cùng kỹ năng. Mode dùng ý định task, số tiêu chí thiết yếu phủ được, độ phổ biến trong kế hoạch và thứ tự đề xuất. |
| Mở đầu và tự giới thiệu | Hồ sơ giả lập, cấu hình và dữ liệu nghề nghiệp. `NEXT` và `SUBMIT_INTRODUCTION` mang snapshot, message ID và version | Sinh lời mở đầu và trạng thái `OPENING` → `SELF_INTRODUCTION` → `INTERVIEW`. Lời giới thiệu nằm trong `conversation.introduction`. Khi vào `INTERVIEW`, deadline chuyên môn mới bắt đầu và `INITIAL` tạo câu đầu. |
| Context, sinh câu và kiểm câu | Mode đã chọn, action, độ sâu, một tiêu chí, `probe_reason`, CV theo skill, tiến độ và lịch sử cùng tiêu chí. Câu từ tiêu chí khác trong cùng mục tiêu được tóm gọn phục vụ chống trùng | `Question` có văn bản, `criterion_ids`, `evidence_scope`, mode và độ sâu. Kiểm tra cục bộ xét contract, câu gộp theo heuristic và lặp văn bản. Bộ duyệt model trả verdict chuyên môn. Retry nhận lỗi và bản câu bị bác khi có. Câu hợp lệ được gán `turn_id` và đặt vào `pending_turn`. |
| `standalone_inability`, Judge, validator | Turn, một rubric đang nhắm, answer nguyên văn và số dòng, lịch sử/bằng chứng cùng tiêu chí. Trường hợp “không biết” khớp regex được xử lý tại chỗ | `Judgment` trả loại quan sát, mức, trích dẫn, lý do, thiếu sót, feedback và cờ. Validator kiểm đúng tập ID, tìm lại trích dẫn hoặc sao chép dải dòng nguyên văn và kiểm tính tương thích của các nhãn. |
| Ledger, `record_progress`, `assess` | Judgment hợp lệ, `ObjectiveState`, độ sâu thực, scope và policy | Thêm bằng chứng, đánh dấu độc lập hay đã được gợi ý, cập nhật target result, mâu thuẫn, số lượt, cờ probe, số lượt đình trệ và đánh giá mục tiêu. Bằng chứng dưới target vẫn vào ledger. Chỉ bằng chứng độc lập ở target mới có thể thay target result. |
| `next_action` và `_advance` | Mức đủ bằng chứng, observation, mâu thuẫn, tiến độ tiêu chí, coverage của mode, queue, deadline, ngân sách | Chọn làm rõ, hạ độ khó, hỏi bổ sung hoặc xác minh mâu thuẫn theo điều kiện trong mã. Dựa vào số lượt và mục tiêu đang chờ để tiếp tục, nhường lượt, mở lại mục tiêu tạm hoãn hoặc kết thúc. |
| `_finish`, lời kết và `report` | Snapshot đã đánh giá, lý do dừng, số lượt, chủ đề đã hỏi và hồ sơ; `objective_report` đọc rubric, `criterion_results`, ledger, `criterion_progress`, mâu thuẫn và policy | Sinh lời chào kết qua model hoặc mẫu dự phòng, đặt phase `CLOSING`, xóa pending/queue khi kết thúc. `report` là projection từ snapshot và trả các kết luận, điểm mạnh/yếu, bằng chứng công khai và gợi ý ôn luyện. `NEXT` chuyển sang `FINISHED`. |

Tham chiếu implementation. [Routes](../../ai-service/adaptive_questioning/evidence/routes.py) · [Schema](../../ai-service/adaptive_questioning/evidence/models.py) · [Blueprint/planner](../../ai-service/adaptive_questioning/evidence/planning.py) · [Provider](../../ai-service/adaptive_questioning/evidence/provider.py) · [Đánh giá và định tuyến](../../ai-service/adaptive_questioning/evidence/assessment.py) · [Bộ đếm](../../ai-service/adaptive_questioning/evidence/criterion_progress.py) · [Tổng hợp báo cáo](../../ai-service/adaptive_questioning/evidence/reporting.py).

## Kết quả Blueprint và lập kế hoạch

`blueprint=null` theo mặc định của `StartRequest`. Hai batch chạy song song với ba yêu cầu mỗi batch. Batch 2 xong sau 54,34 giây và batch 1 sau 58,95 giây. `/start` hoàn tất sau 60,897 giây. Blueprint đầu ra vẫn theo thứ tự batch của input. [Blueprint đã ground đầy đủ](run/blueprint.json) · [Draft, kết quả batch và planner trong trace](run/components.jsonl).

| Thứ tự | Kỹ năng và nhiệm vụ | Trọng số / priority | Mode đã chọn | Target | Rubric thiết yếu |
| --- | --- | --- | --- | --- | --- |
| 1 | PostgreSQL · chẩn đoán truy vấn đơn hàng | 0,99 / 0,198 | `DEBUGGING` | L3 | 2 |
| 2 | Python · loại trùng, giữ bản ghi đầu | 0,95 / 0 | `CODING` | L2 | 2 |
| 3 | RabbitMQ · consumer sự kiện thanh toán | 0,91 / 0,546 | `DESIGN` | L4 | 2 |
| 4 | HTTP API · idempotency khi retry sau timeout | 0,84 / 0,126 | `TECHNICAL_EXPLANATION` | L3 | 2 |
| 5 | Phối hợp QA/SRE khi có sự cố đơn hàng | 0,76 / 0,1995 | `BEHAVIORAL` | L3 | 2 |
| Tạm loại | Docker · Dockerfile triển khai ở môi trường phát triển | 0,42 / 0,02625 | `null` · `PLAN_BUDGET` | L2 | 1 |

Các target đều có `depth_basis=TASK_INTERPRETATION`. Độ sâu L1–L4 trong Module 3 phản ánh loại nhiệm vụ. `required_proficiency` của fixture nằm trên thang 1–5. Policy thực tế gồm ngưỡng core `0.7`, dự phòng follow-up `0.3`, số ngữ cảnh thất bại tối thiểu `2` và `allow_extension_probes=false`. Với năm kỹ năng core, planner còn chỗ danh nghĩa trong ngân sách ban đầu, nhưng Docker là `OPTIONAL` và vướng điều kiện dự phòng `len(queue) * max_questions_per_objective >= max_questions`. [Snapshot v1](run/http/01-start.json).

## Diễn biến theo thứ tự thực thi

### 01-start · Tạo Blueprint, lập kế hoạch và mở đầu

Fixture Skill Gap cho Backend Engineer thương mại điện tử. Tạo Blueprint mới và mở phiên TEXT / MIXED với ngân sách 10 câu.

`POST /api/v2/interview/start` → HTTP 200 trong 60.897 giây. [Request và response](run/http/01-start.json) · [Trace](run/components.jsonl) seq 1–65.

**Lời thoại thực tế của hệ thống**

```
Chào bạn Trần Hà Anh, mình là Minh, người phỏng vấn AI mô phỏng. Hôm nay chúng ta sẽ thực hành cho vị trí Backend Engineer — Orders & Payments tại An Vân Commerce (giả lập). Rất vui được gặp lại bạn trong lần thử đầu tiên này. Bạn có thể chia sẻ ngắn gọn về bản thân và kinh nghiệm liên quan đến vai trò này không?
```

**Chuyển trạng thái** · khởi tạo → v1 / OPENING. Tổng số câu đã ghi nhận 0.

Hàng đợi · ∅ → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

- `postgresql` · — → PLANNED / NOT_ASSESSED / 0 lượt.
- `python` · — → PLANNED / NOT_ASSESSED / 0 lượt.
- `rabbitmq` · — → PLANNED / NOT_ASSESSED / 0 lượt.
- `http-api` · — → PLANNED / NOT_ASSESSED / 0 lượt.
- `incident-collaboration` · — → PLANNED / NOT_ASSESSED / 0 lượt.
- `docker` · — → EXCLUDED / NOT_ASSESSED / 0 lượt / PLAN_BUDGET.

### 02-next · Chuyển sang tự giới thiệu

Ứng viên đọc lời mở đầu rồi chuyển sang phần tự giới thiệu.

`POST /api/v2/interview/conversation` → HTTP 200 trong 0.006 giây. [Request và response](run/http/02-next.json) · [Trace](run/components.jsonl) seq 66–69.

**Chuyển trạng thái** · v1 / OPENING → v2 / SELF_INTRODUCTION. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

### 03-intro · Nhận tự giới thiệu và sinh câu đầu

Ứng viên gửi phần tự giới thiệu bằng tiếng Việt. Workflow bắt đầu tính giờ chuyên môn và sinh câu 1.

`POST /api/v2/interview/conversation` → HTTP 200 trong 3.347 giây. [Request và response](run/http/03-intro.json) · [Trace](run/components.jsonl) seq 70–91.

**Phần tự giới thiệu giả lập đã gửi**

```
Em là Hà Anh. Em làm backend gần ba năm, chủ yếu với Python và PostgreSQL cho API đơn hàng. Em từng làm cùng QA để khoanh vùng lỗi đồng bộ đơn. Phần hàng đợi trong hệ thống thanh toán là mảng em mới bắt đầu tìm hiểu.
```

**Chuyển trạng thái** · v2 / SELF_INTRODUCTION → v3 / INTERVIEW. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

- `postgresql` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

Duyệt bản câu hỏi · `ALIGNED` (seq 87).

**Câu tiếp theo** · `postgresql` / `DEBUGGING` / `INITIAL` / L3 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

```
Bảng `orders` có 1 triệu bản ghi. Truy vấn sau chậm:
`SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;`

Kết quả `EXPLAIN ANALYZE` cho thấy "Seq Scan" và "Sort". Em hãy phân tích nguyên nhân chính gây chậm và đề xuất một câu lệnh SQL cụ thể để tối ưu hóa truy vấn này.
```

### 04-q01 · Câu 1 · postgresql · lần lỗi

Thiếu ý có chủ đích. Chẩn đoán đúng Seq Scan và Sort, để ngỏ thứ tự cột và chưa đưa SQL để quan sát hệ thống hỏi tiếp thế nào.

`POST /api/v2/interview/respond` → HTTP 503 trong 16.103 giây. [Request và response](run/http/04-q01.json) · [Trace](run/components.jsonl) seq 92–151.

**Câu hỏi thực tế** · `DEBUGGING` / `INITIAL` / L3 / `c1`

```
Bảng `orders` có 1 triệu bản ghi. Truy vấn sau chậm:
`SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;`

Kết quả `EXPLAIN ANALYZE` cho thấy "Seq Scan" và "Sort". Em hãy phân tích nguyên nhân chính gây chậm và đề xuất một câu lệnh SQL cụ thể để tối ưu hóa truy vấn này.
```

**Câu trả lời giả lập đã gửi**

```
Seq Scan phải đọc bảng rồi lọc các đơn pending, còn Sort phải sắp các dòng phù hợp theo created_at. Nếu số dòng giữ lại lớn thì sắp xếp có thể tốn bộ nhớ hoặc tràn xuống đĩa. Em nghĩ nên thêm chỉ mục, nhưng chưa chốt cột nào đứng trước nên chưa đưa câu lệnh SQL.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v3. Response lỗi không có snapshot thay thế.

Judgment trong lần xử lý thất bại, seq 101 · `CONTRADICTS / BELOW` · The criterion requires the candidate to 'identify the correct problem... and provide an ALTER TABLE ADD INDEX or appropriate WHERE clause optimization'. The candidate explicitly states they have not decided on the column and therefore 'have not provided the SQL command' ('chưa đưa câu lệnh SQL'). This is a direct contradiction of the requirement to provide a specific SQL statement. Furthermore, while the candidate identifies the bottleneck (Seq Scan + Sort), they fail to propose the specific solution (indexing) as required by the 'at_target' anchor, instead leaving it incomplete..

Bản sao trong bộ nhớ, seq 111 · `CONTRADICTS / BELOW` → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt. API không trả bản sao này.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 114) · `postgresql` · `ASK_EASIER` · Ask for one simpler prerequisite decision using a small concrete case.
- `EvidenceWorkflow._should_yield` (seq 116) · `postgresql` · `false`.

**Cảnh báo từ implementation**

- Seq 134 · Invalid question for session module3-qa-mixed10-20261118-01 (attempt 1/2): Match the requested depth: select a direct prerequisite for a diagnostic or the relevant anchor for a target or extension.
- Seq 149 · Invalid question for session module3-qa-mixed10-20261118-01 (attempt 2/2): Match the requested depth: select a direct prerequisite for a diagnostic or the relevant anchor for a target or extension.

Duyệt bản câu hỏi · `WRONG_DEPTH` (seq 133) → `WRONG_DEPTH` (seq 148).

### 04-q01-retry · Câu 1 · postgresql

Gửi lại nguyên văn câu 1 từ snapshot v3 sau HTTP 503. Giữ cùng turn_id và expected_state_version để kiểm chứng chuyển trạng thái có thể thử lại.

`POST /api/v2/interview/respond` → HTTP 200 trong 12.956 giây. [Request và response](run/http/04-q01-retry.json) · [Trace](run/components.jsonl) seq 152–198.

**Câu hỏi thực tế** · `DEBUGGING` / `INITIAL` / L3 / `c1`

```
Bảng `orders` có 1 triệu bản ghi. Truy vấn sau chậm:
`SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;`

Kết quả `EXPLAIN ANALYZE` cho thấy "Seq Scan" và "Sort". Em hãy phân tích nguyên nhân chính gây chậm và đề xuất một câu lệnh SQL cụ thể để tối ưu hóa truy vấn này.
```

**Câu trả lời giả lập đã gửi**

```
Seq Scan phải đọc bảng rồi lọc các đơn pending, còn Sort phải sắp các dòng phù hợp theo created_at. Nếu số dòng giữ lại lớn thì sắp xếp có thể tốn bộ nhớ hoặc tràn xuống đĩa. Em nghĩ nên thêm chỉ mục, nhưng chưa chốt cột nào đứng trước nên chưa đưa câu lệnh SQL.
```

**Chuyển trạng thái** · v3 / INTERVIEW → v4 / INTERVIEW. Tổng số câu đã ghi nhận 1.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `CONTRADICTS / BELOW` · The criterion requires the candidate to 'identify the correct problem... and provide an ALTER TABLE ADD INDEX or appropriate WHERE clause optimization'. The candidate explicitly states they have not decided on the column and therefore 'did not provide the SQL command' ('chưa đưa câu lệnh SQL'). This is a direct contradiction of the requirement to provide a specific SQL statement. Furthermore, while the candidate identifies the bottleneck (Seq Scan + Sort), they fail to propose the specific solution (indexing `status` or `created_at`) required for AT_TARGET performance.
  - Trích dẫn

    ```
    Em nghĩ nên thêm chỉ mục, nhưng chưa chốt cột nào đứng trước nên chưa đưa câu lệnh SQL.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

- `postgresql` · ACTIVE / NOT_ASSESSED / 0 lượt → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt.
  - `c1` · 1 lượt, +1 evidence ledger, target result `BELOW`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 174) · `postgresql` · `ASK_EASIER` · Ask for one simpler prerequisite decision using a small concrete case.
- `EvidenceWorkflow._should_yield` (seq 176) · `postgresql` · `false`.

Duyệt bản câu hỏi · `ALIGNED` (seq 193).

**Câu tiếp theo** · `postgresql` / `DEBUGGING` / `ASK_EASIER` / L2 / `c1`.

`probe_reason` · Ask for one simpler prerequisite decision using a small concrete case.

```
Để tối ưu truy vấn `SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC`, em cần chọn cột cho index.

Nếu chỉ mục được tạo trên cột `status` (ví dụ: `CREATE INDEX idx_status ON orders(status)`), liệu nó có giúp PostgreSQL tránh việc quét toàn bộ bảng (Seq Scan) để tìm các đơn hàng có trạng thái 'pending' không? Hãy giải thích ngắn gọn tại sao có hoặc không.
```

### 05-q02 · Câu 2 · postgresql

Trả lời đúng câu chẩn đoán ở mức dễ hơn, có điều kiện theo selectivity và tách phần lọc khỏi phần sắp xếp.

`POST /api/v2/interview/respond` → HTTP 200 trong 15.538 giây. [Request và response](run/http/05-q02.json) · [Trace](run/components.jsonl) seq 199–253.

**Câu hỏi thực tế** · `DEBUGGING` / `ASK_EASIER` / L2 / `c1`

```
Để tối ưu truy vấn `SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC`, em cần chọn cột cho index.

Nếu chỉ mục được tạo trên cột `status` (ví dụ: `CREATE INDEX idx_status ON orders(status)`), liệu nó có giúp PostgreSQL tránh việc quét toàn bộ bảng (Seq Scan) để tìm các đơn hàng có trạng thái 'pending' không? Hãy giải thích ngắn gọn tại sao có hoặc không.
```

**Câu trả lời giả lập đã gửi**

```
Có thể. B-tree trên status cho phép tìm các bản ghi pending mà không phải đọc tuần tự cả bảng, nhất là khi pending chiếm tỷ lệ nhỏ. Nếu phần lớn đơn hàng là pending, PostgreSQL vẫn có thể chọn Seq Scan vì đọc nhiều heap page qua index đắt hơn. Index riêng trên status cũng không cung cấp thứ tự created_at, nên vẫn có thể cần Sort.
```

**Chuyển trạng thái** · v4 / INTERVIEW → v5 / INTERVIEW. Tổng số câu đã ghi nhận 2.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `SUPPORTS / AT_TARGET` · The candidate correctly identifies that a B-tree index on `status` can avoid a sequential scan (Seq Scan) for finding 'pending' records, specifically noting the condition of selectivity (small proportion). They also correctly explain the limitation: the index does not help with sorting by `created_at`, so a Sort operation may still be required. This demonstrates an understanding of how indexes work in PostgreSQL and their limitations regarding sort order, which aligns with the AT_TARGET criterion of identifying performance issues and explaining them using concepts like EXPLAIN/Seq Scan/Index usage. The question is at depth 2 (Application), and the answer successfully applies the concept to the specific scenario.
  - Trích dẫn dòng 1–1

    ```
    Có thể. B-tree trên status cho phép tìm các bản ghi pending mà không phải đọc tuần tự cả bảng, nhất là khi pending chiếm tỷ lệ nhỏ. Nếu phần lớn đơn hàng là pending, PostgreSQL vẫn có thể chọn Seq Scan vì đọc nhiều heap page qua index đắt hơn. Index riêng trên status cũng không cung cấp thứ tự created_at, nên vẫn có thể cần Sort.
    ```


Phản hồi công khai của lượt · “Bạn đã giải thích rất rõ về cách chỉ mục B-tree giúp tránh quét toàn bộ bảng và điểm hạn chế của nó đối với việc sắp xếp.”.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

- `postgresql` · ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt → ACTIVE / INSUFFICIENT_EVIDENCE / 2 lượt.
  - `c1` · 2 lượt, +1 evidence ledger, target result `BELOW`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=true`, `deeper_spent=false`, `stop_reason=null`.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 229) · `postgresql` · `FOLLOW_UP` · Verify independent application at the required depth after diagnosis.
- `EvidenceWorkflow._should_yield` (seq 231) · `postgresql` · `false`.

**Cảnh báo từ implementation**

- Seq 211 · Invalid judge output for turn 3af2eb6f-e154-4543-b8c2-8a2b354e7ced (attempt 1/2): Evidence excerpt not found in candidate answer for criterion_id=29fb8ec0-16e2-56cd-9ad3-2d497f0f6d74:c1. Copy ONE contiguous passage from turn.answer into response_excerpt exactly; do not paraphrase, correct spelling, add quotation marks or combine passages. Put interpretation in rationale, not response_excerpt. Reassess the observation if no passage supports it; never fabricate a quote to keep a score. For code, set response_line_range=[start_line,end_line] using answer_lines (inclusive, 1-based); the server copies those original lines verbatim.

Duyệt bản câu hỏi · `ALIGNED` (seq 248).

**Câu tiếp theo** · `postgresql` / `DEBUGGING` / `FOLLOW_UP` / L3 / `c1`.

`probe_reason` · Verify independent application at the required depth after diagnosis.

```
Trước đó em nhận định index riêng trên `status` không giúp sắp xếp theo `created_at`.

Bây giờ, hãy đưa ra một câu lệnh SQL cụ thể để tạo một composite index duy nhất giải quyết cả hai vấn đề (lọc và sắp xếp) cho truy vấn:
`SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;`

Câu lệnh đó là gì?
```

### 06-q03 · Câu 3 · postgresql

Trả lời đúng với DDL PostgreSQL và lý do thứ tự cột để kiểm tra phục hồi lên target sau câu chẩn đoán.

`POST /api/v2/interview/respond` → HTTP 200 trong 12.061 giây. [Request và response](run/http/06-q03.json) · [Trace](run/components.jsonl) seq 254–300.

**Câu hỏi thực tế** · `DEBUGGING` / `FOLLOW_UP` / L3 / `c1`

```
Trước đó em nhận định index riêng trên `status` không giúp sắp xếp theo `created_at`.

Bây giờ, hãy đưa ra một câu lệnh SQL cụ thể để tạo một composite index duy nhất giải quyết cả hai vấn đề (lọc và sắp xếp) cho truy vấn:
`SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;`

Câu lệnh đó là gì?
```

**Câu trả lời giả lập đã gửi**

```
CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC);

status đứng đầu vì điều kiện là so sánh bằng. Trong đoạn index tương ứng với status = 'pending', các mục đã theo thứ tự created_at giảm dần, nên PostgreSQL có thể dùng index để lọc và trả đúng thứ tự mà không cần Sort riêng. Em sẽ so sánh EXPLAIN (ANALYZE, BUFFERS) trước và sau vì planner vẫn phụ thuộc tỷ lệ đơn pending.
```

**Chuyển trạng thái** · v5 / INTERVIEW → v6 / INTERVIEW. Tổng số câu đã ghi nhận 3.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `SUPPORTS / AT_TARGET` · The candidate provides the correct composite index syntax `CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC);` which addresses both filtering and sorting. They correctly explain the rationale: `status` is first for equality filtering, and `created_at DESC` leverages the B-tree order to avoid a separate Sort operation. This aligns with the AT_TARGET criterion of identifying the problem and providing the appropriate SQL optimization.
  - Trích dẫn

    ```
    CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC);
    
    status đứng đầu vì điều kiện là so sánh bằng. Trong đoạn index tương ứng với status = 'pending', các mục đã theo thứ tự created_at giảm dần, nên PostgreSQL có thể dùng index để lọc và trả đúng thứ tự mà không cần Sort riêng. Em sẽ so sánh EXPLAIN (ANALYZE, BUFFERS) trước và sau vì planner vẫn phụ thuộc tỷ lệ đơn pending.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql`.

- `postgresql` · ACTIVE / INSUFFICIENT_EVIDENCE / 2 lượt → PLANNED / INSUFFICIENT_EVIDENCE / 3 lượt.
  - `c1` · 3 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=1`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=true`, `deeper_spent=false`, `stop_reason=null`.
- `python` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 276) · `postgresql` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 278) · `postgresql` · `true`.

Duyệt bản câu hỏi · `ALIGNED` (seq 295).

**Câu tiếp theo** · `python` / `CODING` / `INITIAL` / L2 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

```
Em đã từng triển khai API xử lý sự kiện đơn hàng. Hãy viết một hàm Python `deduplicate_events(events)` nhận vào danh sách các dict, mỗi dict có khóa `'event_id'`. Hàm cần trả về danh sách mới chỉ giữ lại lần xuất hiện đầu tiên của mỗi `event_id`, duy trì thứ tự ban đầu. Em sẽ dùng cấu trúc dữ liệu nào để đảm bảo hiệu năng tốt?
```

### 07-q04 · Câu 4 · python

Trả lời sai có chủ đích bằng một lỗi Python thực tế. Dict giữ thứ tự chèn khóa nhưng comprehension ghi đè giá trị khi event_id lặp.

`POST /api/v2/interview/respond` → HTTP 200 trong 12.711 giây. [Request và response](run/http/07-q04.json) · [Trace](run/components.jsonl) seq 301–347.

**Câu hỏi thực tế** · `CODING` / `INITIAL` / L2 / `c1`

```
Em đã từng triển khai API xử lý sự kiện đơn hàng. Hãy viết một hàm Python `deduplicate_events(events)` nhận vào danh sách các dict, mỗi dict có khóa `'event_id'`. Hàm cần trả về danh sách mới chỉ giữ lại lần xuất hiện đầu tiên của mỗi `event_id`, duy trì thứ tự ban đầu. Em sẽ dùng cấu trúc dữ liệu nào để đảm bảo hiệu năng tốt?
```

**Câu trả lời giả lập đã gửi**

```
def deduplicate_events(events):
    by_id = {event['event_id']: event for event in events}
    return list(by_id.values())

Em dùng dict vì tra theo khóa nhanh. Dict giữ thứ tự lần đầu thêm khóa nên theo em mỗi mã sẽ giữ nguyên sự kiện đầu tiên.
```

**Chuyển trạng thái** · v6 / INTERVIEW → v7 / INTERVIEW. Tổng số câu đã ghi nhận 4.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `SUPPORTS / AT_TARGET` · The candidate implemented the function using a dictionary comprehension to deduplicate events based on 'event_id'. This approach achieves O(n) time complexity, which is significantly better than the nested loop (O(n^2)) mentioned in the below_target criteria. The candidate correctly identified that Python dictionaries maintain insertion order (since version 3.7+), ensuring that the first occurrence of each event_id is preserved and subsequent duplicates are overwritten/ignored when converting back to a list. The explanation explicitly links the data structure choice to both performance ('tra theo khóa nhanh') and order preservation ('giữ thứ tự lần đầu thêm khóa').
  - Trích dẫn dòng 1–5

    ```
    def deduplicate_events(events):
        by_id = {event['event_id']: event for event in events}
        return list(by_id.values())
    
    Em dùng dict vì tra theo khóa nhanh. Dict giữ thứ tự lần đầu thêm khóa nên theo em mỗi mã sẽ giữ nguyên sự kiện đầu tiên.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql`.

- `python` · ACTIVE / NOT_ASSESSED / 0 lượt → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt.
  - `c1` · 1 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 323) · `python` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 325) · `python` · `false`.

Duyệt bản câu hỏi · `ALIGNED` (seq 342).

**Câu tiếp theo** · `python` / `CODING` / `FOLLOW_UP` / L2 / `c2`.

`probe_reason` · Collect initial evidence for an untested essential criterion.

```
Em đã viết hàm `deduplicate_events`. Hãy cập nhật nó để xử lý an toàn khi đầu vào là `None` hoặc danh sách rỗng. Với các trường hợp này, hàm cần trả về một danh sách rỗng thay vì gây lỗi. Em sẽ thêm kiểm tra điều kiện nào ngay đầu hàm?
```

### 08-q05 · Câu 5 · python

Trả lời đúng và ngắn đúng phạm vi câu hỏi mới về None và danh sách rỗng. Không nộp lại phần dedup của câu trước.

`POST /api/v2/interview/respond` → HTTP 200 trong 10.047 giây. [Request và response](run/http/08-q05.json) · [Trace](run/components.jsonl) seq 348–392.

**Câu hỏi thực tế** · `CODING` / `FOLLOW_UP` / L2 / `c2`

```
Em đã viết hàm `deduplicate_events`. Hãy cập nhật nó để xử lý an toàn khi đầu vào là `None` hoặc danh sách rỗng. Với các trường hợp này, hàm cần trả về một danh sách rỗng thay vì gây lỗi. Em sẽ thêm kiểm tra điều kiện nào ngay đầu hàm?
```

**Câu trả lời giả lập đã gửi**

```
if not events:
    return []

Em đặt đoạn này ở đầu hàm. Theo kiểu đầu vào của câu hỏi, cả None và danh sách rỗng đều đi vào nhánh này. Danh sách có phần tử đi tiếp vào phần xử lý.
```

**Chuyển trạng thái** · v7 / INTERVIEW → v8 / INTERVIEW. Tổng số câu đã ghi nhận 5.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c2` · `SUPPORTS / AT_TARGET` · The candidate correctly identifies that `if not events:` handles both `None` and empty lists, returning an empty list as required. This satisfies the 'at_target' criterion of handling invalid inputs safely without crashing.
  - Trích dẫn

    ```
    if not events:
        return []
    
    Em đặt đoạn này ở đầu hàm. Theo kiểu đầu vào của câu hỏi, cả None và danh sách rỗng đều đi vào nhánh này. Danh sách có phần tử đi tiếp vào phần xử lý.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql`.

- `python` · ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt → CLOSED / DEMONSTRATED_AT_TARGET / 2 lượt / SUFFICIENT_EVIDENCE.
  - `c2` · 1 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.
- `rabbitmq` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 370) · `python` · `null`.

Duyệt bản câu hỏi · `ALIGNED` (seq 387).

**Câu tiếp theo** · `rabbitmq` / `DESIGN` / `INITIAL` / L4 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

```
Em đang thiết kế consumer RabbitMQ cho hệ thống thanh toán. Để đảm bảo không ghi nhận thanh toán hai lần (double-spending) khi tin nhắn bị gửi lại, em sẽ thiết kế cơ chế idempotency như thế nào? Hãy mô tả cách kết hợp `payment_id` với trạng thái giao dịch trong database để xử lý tin nhắn trùng lặp và xác định điểm commit transaction rõ ràng giữa việc cập nhật DB và ack message.
```

### 09-q06 · Câu 6 · rabbitmq

Trả lời đầy đủ cho bài thiết kế RabbitMQ, phân biệt cửa sổ lỗi trước commit và sau commit nhưng trước ACK.

`POST /api/v2/interview/respond` → HTTP 200 trong 18.212 giây. [Request và response](run/http/09-q06.json) · [Trace](run/components.jsonl) seq 393–454.

**Câu hỏi thực tế** · `DESIGN` / `INITIAL` / L4 / `c1`

```
Em đang thiết kế consumer RabbitMQ cho hệ thống thanh toán. Để đảm bảo không ghi nhận thanh toán hai lần (double-spending) khi tin nhắn bị gửi lại, em sẽ thiết kế cơ chế idempotency như thế nào? Hãy mô tả cách kết hợp `payment_id` với trạng thái giao dịch trong database để xử lý tin nhắn trùng lặp và xác định điểm commit transaction rõ ràng giữa việc cập nhật DB và ack message.
```

**Câu trả lời giả lập đã gửi**

```
Em dùng payment_id ổn định làm khóa UNIQUE trong bảng ghi nhận. Consumer dùng manual ack. Trong một transaction PostgreSQL, em thử INSERT bản ghi khóa theo payment_id với ON CONFLICT DO NOTHING. Chỉ giao dịch INSERT thành công mới cập nhật số tiền và trạng thái thanh toán, trong cùng transaction. Nếu xung đột với bản ghi đã commit, em bỏ qua cập nhật. Với cả hai trường hợp, em chỉ ACK sau khi transaction đã commit. Crash trước commit sẽ rollback và RabbitMQ giao lại để xử lý. Crash sau commit nhưng trước ACK sẽ gặp khóa đã tồn tại, bỏ qua ghi lần hai rồi ACK. Cách này giả định tác dụng cần bảo vệ là ghi nhận trong DB, cùng phạm vi transaction.
```

**Chuyển trạng thái** · v8 / INTERVIEW → v9 / INTERVIEW. Tổng số câu đã ghi nhận 6.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `SUPPORTS / ABOVE` · The candidate demonstrates an AT_TARGET level by using a unique key (payment_id) with `ON CONFLICT DO NOTHING` to detect duplicates and performing the update within the same transaction. Crucially, they address the ABOVE_TARGET criteria by explicitly defining the transaction boundary: ensuring that the message acknowledgment (`ack`) only occurs *after* the database transaction commits. This prevents double-processing in case of a crash between commit and ack, and ensures atomicity. They also correctly identify that a rollback on failure allows RabbitMQ to redeliver, which is part of the robust design.
  - Trích dẫn dòng 1–1

    ```
    Em dùng payment_id ổn định làm khóa UNIQUE trong bảng ghi nhận. Consumer dùng manual ack. Trong một transaction PostgreSQL, em thử INSERT bản ghi khóa theo payment_id với ON CONFLICT DO NOTHING. Chỉ giao dịch INSERT thành công mới cập nhật số tiền và trạng thái thanh toán, trong cùng transaction. Nếu xung đột với bản ghi đã commit, em bỏ qua cập nhật. Với cả hai trường hợp, em chỉ ACK sau khi transaction đã commit. Crash trước commit sẽ rollback và RabbitMQ giao lại để xử lý. Crash sau commit nhưng trước ACK sẽ gặp khóa đã tồn tại, bỏ qua ghi lần hai rồi ACK. Cách này giả định tác dụng cần bảo vệ là ghi nhận trong DB, cùng phạm vi transaction.
    ```


Phản hồi công khai của lượt · “Cách thiết kế của em rất tốt, đặc biệt là việc đảm bảo ACK chỉ xảy ra sau khi commit transaction để tránh mất tin nhắn hoặc xử lý trùng lặp khi có sự cố. Đây là một mẫu thiết kế idempotent và mạnh mẽ cho hệ thống thanh toán.”.

Hàng đợi · `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql`.

- `rabbitmq` · ACTIVE / NOT_ASSESSED / 0 lượt → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt.
  - `c1` · 1 lượt, +1 evidence ledger, target result `ABOVE`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 415) · `rabbitmq` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 417) · `rabbitmq` · `false`.

**Cảnh báo từ implementation**

- Seq 435 · Invalid question for session module3-qa-mixed10-20261118-01 (attempt 1/2): Ask the candidate to perform the behavior in the selected criterion. Remove the substitute task.

Duyệt bản câu hỏi · `WRONG_SKILL` (seq 434) → `ALIGNED` (seq 449).

**Câu tiếp theo** · `rabbitmq` / `DESIGN` / `FOLLOW_UP` / L4 / `c2`.

`probe_reason` · Collect initial evidence for an untested essential criterion.

```
Em đang thiết kế consumer RabbitMQ cho hệ thống thanh toán. Để đảm bảo độ tin cậy cao, em sẽ cấu hình như thế nào cho channel và queue? Hãy mô tả cụ thể việc sử dụng manual acknowledgement (channel.basic_ack) kết hợp với các thuộc tính durable của queue để tránh mất tin nhắn khi consumer gặp sự cố giữa chừng.
```

### 10-q07 · Câu 7 · rabbitmq · lần lỗi

Trả lời đúng tiêu chí cấu hình broker sau khi được hỏi sâu, phân biệt consumer crash và broker restart.

`POST /api/v2/interview/respond` → HTTP 503 trong 11.327 giây. [Request và response](run/http/10-q07.json) · [Trace](run/components.jsonl) seq 455–476.

**Câu hỏi thực tế** · `DESIGN` / `FOLLOW_UP` / L4 / `c2`

```
Em đang thiết kế consumer RabbitMQ cho hệ thống thanh toán. Để đảm bảo độ tin cậy cao, em sẽ cấu hình như thế nào cho channel và queue? Hãy mô tả cụ thể việc sử dụng manual acknowledgement (channel.basic_ack) kết hợp với các thuộc tính durable của queue để tránh mất tin nhắn khi consumer gặp sự cố giữa chừng.
```

**Câu trả lời giả lập đã gửi**

```
Em đặt auto_ack=False và gọi basic_ack trên cùng channel chỉ sau khi ghi nhận giao dịch thành công. Nếu consumer hoặc channel chết trước ACK, message chưa ACK có thể được giao lại. Em khai báo queue durable=True và exchange durable; để message có thể tồn tại qua lần khởi động lại broker, phía publish cũng đánh dấu message là persistent. Durable giữ cấu hình queue, còn việc gửi message thành công có thể xác nhận bằng publisher confirms.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa thể chấm câu trả lời một cách hợp lệ. Câu trả lời chưa bị chấm điểm; vui lòng thử gửi lại."
}
```

Lần gửi sử dụng v9. Response lỗi không có snapshot thay thế.

Judgment trong lần xử lý thất bại, seq 464 · `SUPPORTS / AT_TARGET` · Candidate correctly identifies the use of manual acknowledgement (auto_ack=False, basic_ack) after successful transaction recording to ensure message reliability. They also specify configuring queue and exchange as durable (durable=True) to persist configuration across broker restarts. This aligns with the 'at_target' evidence which requires manual acknowledgement and durable queue/exchange configuration. The candidate does not explicitly analyze trade-offs between throughput and reliability or propose specific prefetch count configurations to avoid memory overflow, which is required for 'above_target'..

Judgment trong lần xử lý thất bại, seq 472 · `SUPPORTS / AT_TARGET` · The candidate explicitly states setting `auto_ack=False` and calling `basic_ack` only after successful transaction recording, which aligns with the 'at_target' requirement for manual acknowledgement to ensure messages are not deleted until processing is complete. They also specify configuring the queue and exchange as `durable=True` to persist configuration across broker restarts, matching the expected evidence. The candidate does not analyze trade-offs between throughput and reliability or propose specific prefetch count configurations to avoid memory overflow, which is required for 'above_target'. Therefore, the performance is assessed as AT_TARGET..

**Cảnh báo từ implementation**

- Seq 467 · Invalid judge output for turn b885bb57-a6ba-45db-9d82-8b2cfebd9881 (attempt 1/2): Evidence excerpt not found in candidate answer for criterion_id=9bba5d04-deb3-5dba-b886-0a4d32a374d7:c2. Copy ONE contiguous passage from turn.answer into response_excerpt exactly; do not paraphrase, correct spelling, add quotation marks or combine passages. Put interpretation in rationale, not response_excerpt. Reassess the observation if no passage supports it; never fabricate a quote to keep a score. For code, set response_line_range=[start_line,end_line] using answer_lines (inclusive, 1-based); the server copies those original lines verbatim.
- Seq 475 · Invalid judge output for turn b885bb57-a6ba-45db-9d82-8b2cfebd9881 (attempt 2/2): A passed criterion cannot have unresolved required aspects

### 10-q07-retry · Câu 7 · rabbitmq

Gửi lại nguyên văn câu 7 từ snapshot v9 sau HTTP 503 của Judge.

`POST /api/v2/interview/respond` → HTTP 200 trong 18.923 giây. [Request và response](run/http/10-q07-retry.json) · [Trace](run/components.jsonl) seq 477–531.

**Câu hỏi thực tế** · `DESIGN` / `FOLLOW_UP` / L4 / `c2`

```
Em đang thiết kế consumer RabbitMQ cho hệ thống thanh toán. Để đảm bảo độ tin cậy cao, em sẽ cấu hình như thế nào cho channel và queue? Hãy mô tả cụ thể việc sử dụng manual acknowledgement (channel.basic_ack) kết hợp với các thuộc tính durable của queue để tránh mất tin nhắn khi consumer gặp sự cố giữa chừng.
```

**Câu trả lời giả lập đã gửi**

```
Em đặt auto_ack=False và gọi basic_ack trên cùng channel chỉ sau khi ghi nhận giao dịch thành công. Nếu consumer hoặc channel chết trước ACK, message chưa ACK có thể được giao lại. Em khai báo queue durable=True và exchange durable; để message có thể tồn tại qua lần khởi động lại broker, phía publish cũng đánh dấu message là persistent. Durable giữ cấu hình queue, còn việc gửi message thành công có thể xác nhận bằng publisher confirms.
```

**Chuyển trạng thái** · v9 / INTERVIEW → v10 / INTERVIEW. Tổng số câu đã ghi nhận 7.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c2` · `SUPPORTS / AT_TARGET` · The candidate explicitly states setting `auto_ack=False` and calling `basic_ack` only after successful transaction recording, which satisfies the manual acknowledgement requirement. They also specify declaring the queue with `durable=True` and the exchange as durable, satisfying the durability configuration requirement. The answer does not provide an analysis of trade-offs between throughput and reliability or propose specific prefetch counts to avoid memory overflow, which are required for the 'above_target' level. Therefore, the performance is assessed as AT_TARGET.
  - Trích dẫn

    ```
    Em đặt auto_ack=False và gọi basic_ack trên cùng channel chỉ sau khi ghi nhận giao dịch thành công. Nếu consumer hoặc channel chết trước ACK, message chưa ACK có thể được giao lại. Em khai báo queue durable=True và exchange durable; để message có thể tồn tại qua lần khởi động lại broker, phía publish cũng đánh dấu message là persistent.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `http-api` → `incident-collaboration` → `postgresql`.

- `rabbitmq` · ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt → CLOSED / DEMONSTRATED_AT_TARGET / 2 lượt / SUFFICIENT_EVIDENCE.
  - `c2` · 1 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.
- `http-api` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 509) · `rabbitmq` · `null`.

**Cảnh báo từ implementation**

- Seq 489 · Invalid judge output for turn b885bb57-a6ba-45db-9d82-8b2cfebd9881 (attempt 1/2): Evidence excerpt not found in candidate answer for criterion_id=9bba5d04-deb3-5dba-b886-0a4d32a374d7:c2. Copy ONE contiguous passage from turn.answer into response_excerpt exactly; do not paraphrase, correct spelling, add quotation marks or combine passages. Put interpretation in rationale, not response_excerpt. Reassess the observation if no passage supports it; never fabricate a quote to keep a score. For code, set response_line_range=[start_line,end_line] using answer_lines (inclusive, 1-based); the server copies those original lines verbatim.

Duyệt bản câu hỏi · `ALIGNED` (seq 526).

**Câu tiếp theo** · `http-api` / `TECHNICAL_EXPLANATION` / `INITIAL` / L3 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

```
Em đã tích hợp retry qua SDK HTTP khi gọi dịch vụ vận chuyển. Giả sử client gửi yêu cầu `POST /orders` nhưng gặp timeout, hệ thống sẽ tự động thử lại. Em hãy phân tích rủi ro cụ thể của việc này so với phương thức `PUT`. Nếu không thể thay đổi sang `PUT`, em sẽ đề xuất cơ chế nào (ví dụ: header hoặc logic phía server) để đảm bảo đơn hàng không bị tạo trùng?
```

### 11-q08 · Câu 8 · http-api · lần lỗi

Ứng viên nói chưa biết. Dùng câu tự nhiên khớp nhánh standalone_inability để xem workflow xử lý mà không gọi Judge.

`POST /api/v2/interview/respond` → HTTP 503 trong 5.147 giây. [Request và response](run/http/11-q08.json) · [Trace](run/components.jsonl) seq 532–572.

**Câu hỏi thực tế** · `TECHNICAL_EXPLANATION` / `INITIAL` / L3 / `c1`

```
Em đã tích hợp retry qua SDK HTTP khi gọi dịch vụ vận chuyển. Giả sử client gửi yêu cầu `POST /orders` nhưng gặp timeout, hệ thống sẽ tự động thử lại. Em hãy phân tích rủi ro cụ thể của việc này so với phương thức `PUT`. Nếu không thể thay đổi sang `PUT`, em sẽ đề xuất cơ chế nào (ví dụ: header hoặc logic phía server) để đảm bảo đơn hàng không bị tạo trùng?
```

**Câu trả lời giả lập đã gửi**

```
Em không biết ạ.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v10. Response lỗi không có snapshot thay thế.

Bản sao trong bộ nhớ, seq 542 · `NO_EVIDENCE / UNDETERMINED` → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt. API không trả bản sao này.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 545) · `http-api` · `ASK_EASIER` · Ask for one simpler prerequisite decision using a small concrete case.
- `EvidenceWorkflow._should_yield` (seq 547) · `http-api` · `true`.

**Cảnh báo từ implementation**

- Seq 560 · Invalid question for session module3-qa-mixed10-20261118-01 (attempt 1/2): Ask exactly ONE response task; remove independent subquestions or numbered requests
- Seq 570 · Invalid question for session module3-qa-mixed10-20261118-01 (attempt 2/2): Ask exactly ONE response task; remove independent subquestions or numbered requests

### 11-q08-retry · Câu 8 · http-api

Gửi lại cùng câu không biết từ snapshot v10, sau khi lời đáp đã đi qua nhánh tất định nhưng bước sinh câu tiếp theo trả 503.

`POST /api/v2/interview/respond` → HTTP 200 trong 2.903 giây. [Request và response](run/http/11-q08-retry.json) · [Trace](run/components.jsonl) seq 573–610.

**Câu hỏi thực tế** · `TECHNICAL_EXPLANATION` / `INITIAL` / L3 / `c1`

```
Em đã tích hợp retry qua SDK HTTP khi gọi dịch vụ vận chuyển. Giả sử client gửi yêu cầu `POST /orders` nhưng gặp timeout, hệ thống sẽ tự động thử lại. Em hãy phân tích rủi ro cụ thể của việc này so với phương thức `PUT`. Nếu không thể thay đổi sang `PUT`, em sẽ đề xuất cơ chế nào (ví dụ: header hoặc logic phía server) để đảm bảo đơn hàng không bị tạo trùng?
```

**Câu trả lời giả lập đã gửi**

```
Em không biết ạ.
```

**Chuyển trạng thái** · v10 / INTERVIEW → v11 / INTERVIEW. Tổng số câu đã ghi nhận 8.

**Judgment đã ghi nhận** · `explicit_inability=true` · `feedback_contains_hint=false`

- `c1` · `NO_EVIDENCE / UNDETERMINED` · Ứng viên cho biết chưa trả lời được câu hỏi này.
  - Trích dẫn

    ```
    Em không biết ạ.
    ```


Phản hồi công khai của lượt · “Cảm ơn bạn đã chia sẻ.”.

Hàng đợi · `http-api` → `incident-collaboration` → `postgresql` → `incident-collaboration` → `http-api` → `postgresql`.

- `http-api` · ACTIVE / NOT_ASSESSED / 0 lượt → PLANNED / INSUFFICIENT_EVIDENCE / 1 lượt.
  - `c1` · 1 lượt, +1 evidence ledger, target result `∅`, `stagnant_turns=1`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.
- `incident-collaboration` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 586) · `http-api` · `ASK_EASIER` · Ask for one simpler prerequisite decision using a small concrete case.
- `EvidenceWorkflow._should_yield` (seq 588) · `http-api` · `true`.

Duyệt bản câu hỏi · `ALIGNED` (seq 605).

**Câu tiếp theo** · `incident-collaboration` / `BEHAVIORAL` / `INITIAL` / L3 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

```
Trong sự cố đơn hàng, SRE đang thực hiện rollback và Dev cần hotfix. Em hãy phân công cụ thể trách nhiệm của QA trong giai đoạn giảm thiểu tác động này để đảm bảo chất lượng mà không làm chậm trễ việc khôi phục hệ thống.
```

### 12-q09 · Câu 9 · incident-collaboration

Trả lời tình huống phối hợp với QA bằng các trách nhiệm, tiêu chí go/no-go và giao tiếp có thể quan sát.

`POST /api/v2/interview/respond` → HTTP 200 trong 11.909 giây. [Request và response](run/http/12-q09.json) · [Trace](run/components.jsonl) seq 611–657.

**Câu hỏi thực tế** · `BEHAVIORAL` / `INITIAL` / L3 / `c1`

```
Trong sự cố đơn hàng, SRE đang thực hiện rollback và Dev cần hotfix. Em hãy phân công cụ thể trách nhiệm của QA trong giai đoạn giảm thiểu tác động này để đảm bảo chất lượng mà không làm chậm trễ việc khôi phục hệ thống.
```

**Câu trả lời giả lập đã gửi**

```
Em để SRE rollback ngay theo runbook, không chờ QA chạy toàn bộ regression. Trong lúc đó, QA tái hiện lỗi bằng mã đơn thử, chốt hai luồng smoke là tạo đơn và đồng bộ trạng thái, rồi xác nhận trên bản rollback và bản hotfix thử nghiệm mà Dev chuẩn bị. QA đăng kết quả pass/fail cùng mã đơn và timestamp vào incident channel. Nếu hotfix vẫn làm lệch trạng thái đơn thì QA báo no-go, SRE giữ bản ổn định và Dev sửa tiếp. Em cũng nhờ QA xác nhận một lượt smoke sau khi SRE báo hệ thống đã phục hồi.
```

**Chuyển trạng thái** · v11 / INTERVIEW → v12 / INTERVIEW. Tổng số câu đã ghi nhận 9.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c1` · `SUPPORTS / AT_TARGET` · The candidate clearly defines the QA role in the mitigation phase: performing targeted smoke tests (reproducing the error, checking specific flows) on both the rollback and the hotfix, rather than running full regression. They specify communication protocols (posting pass/fail results with metadata to the incident channel) and decision-making authority (QA can block the hotfix if it causes state drift). This aligns with the 'at_target' anchor of clear division of labor (QA for quality verification) and synchronized coordination.
  - Trích dẫn dòng 1–1

    ```
    Em để SRE rollback ngay theo runbook, không chờ QA chạy toàn bộ regression. Trong lúc đó, QA tái hiện lỗi bằng mã đơn thử, chốt hai luồng smoke là tạo đơn và đồng bộ trạng thái, rồi xác nhận trên bản rollback và bản hotfix thử nghiệm mà Dev chuẩn bị. QA đăng kết quả pass/fail cùng mã đơn và timestamp vào incident channel. Nếu hotfix vẫn làm lệch trạng thái đơn thì QA báo no-go, SRE giữ bản ổn định và Dev sửa tiếp. Em cũng nhờ QA xác nhận một lượt smoke sau khi SRE báo hệ thống đã phục hồi.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `incident-collaboration` → `http-api` → `postgresql` → `incident-collaboration` → `http-api` → `postgresql`.

- `incident-collaboration` · ACTIVE / NOT_ASSESSED / 0 lượt → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt.
  - `c1` · 1 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 633) · `incident-collaboration` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 635) · `incident-collaboration` · `false`.

Duyệt bản câu hỏi · `ALIGNED` (seq 652).

**Câu tiếp theo** · `incident-collaboration` / `BEHAVIORAL` / `FOLLOW_UP` / L3 / `c2`.

`probe_reason` · Collect initial evidence for an untested essential criterion.

```
Sau khi sự cố đồng bộ đơn hàng được khắc phục tạm thời, em hãy viết nội dung bàn giao (handover) cho team trực ca tiếp theo. Bao gồm: các bước đã thực hiện, root cause hypothesis, và danh sách các metric cần theo dõi. Em sẽ chỉ định ai là người phụ trách chính cho mỗi task?
```

### 13-q10 · Câu 10 · incident-collaboration

Trả lời đầy đủ câu cuối bằng ghi chú bàn giao với trạng thái, giả thuyết, metric và người phụ trách. Chờ hệ thống tự chốt ngân sách.

`POST /api/v2/interview/respond` → HTTP 200 trong 12.635 giây. [Request và response](run/http/13-q10.json) · [Trace](run/components.jsonl) seq 658–691.

**Câu hỏi thực tế** · `BEHAVIORAL` / `FOLLOW_UP` / L3 / `c2`

```
Sau khi sự cố đồng bộ đơn hàng được khắc phục tạm thời, em hãy viết nội dung bàn giao (handover) cho team trực ca tiếp theo. Bao gồm: các bước đã thực hiện, root cause hypothesis, và danh sách các metric cần theo dõi. Em sẽ chỉ định ai là người phụ trách chính cho mỗi task?
```

**Câu trả lời giả lập đã gửi**

```
Bàn giao INC-024, 15:40. SRE đã rollback worker đồng bộ về bản ổn định lúc 15:26. QA đã smoke luồng tạo đơn, thanh toán và cập nhật trạng thái trên canary. Dev tạm khóa đợt deploy mới. Giả thuyết chưa xác nhận: bản worker mới đánh dấu sự kiện đã xử lý trước khi ghi trạng thái, nên một số lần retry không cập nhật đơn. Ca sau theo dõi trong 60 phút: SRE trực giữ dashboard backlog, tuổi sự kiện cũ nhất và tỷ lệ xử lý lỗi, báo incident lead nếu backlog lại tăng trong 5 phút. QA đối soát 20 đơn bị ảnh hưởng với log thanh toán và gắn kết quả vào ticket. Dev phụ trách xác minh giả thuyết bằng trace ID và chỉ đề xuất mở lại rollout sau khi sửa và test tái hiện. Em ghi ticket, link dashboard và checklist owner vào incident log, rồi yêu cầu người trực ca sau xác nhận đã nhận bàn giao.
```

**Lời thoại thực tế của hệ thống**

```
Cảm ơn Hà Anh đã tham gia buổi phỏng vấn cho vị trí Backend Engineer tại An Vân Commerce. Chúng ta đã cùng thảo luận về Python, PostgreSQL, RabbitMQ và cách phối hợp xử lý sự cố, rất vui được gặp bạn. Bạn có thể xem lại kết quả chi tiết của buổi phỏng vấn này ngay bây giờ.
```

**Chuyển trạng thái** · v12 / INTERVIEW → v13 / CLOSING. Tổng số câu đã ghi nhận 10.

**Judgment đã ghi nhận** · `explicit_inability=false` · `feedback_contains_hint=false`

- `c2` · `SUPPORTS / AT_TARGET` · The candidate provides a comprehensive handover that includes: 1) Summary of actions taken (rollback, smoke tests, deploy pause); 2) Root cause hypothesis (worker marking events before state write causing retry issues); 3) Metrics to monitor (backlog dashboard, oldest event age, error rate) with specific thresholds/actions; 4) Assignment of primary owners for each task (SRE for monitoring, QA for reconciliation, Dev for verification). The response explicitly mentions logging this into the incident log and requesting confirmation from the next shift. This aligns perfectly with the 'at_target' criteria.
  - Trích dẫn

    ```
    Bàn giao INC-024, 15:40. SRE đã rollback worker đồng bộ về bản ổn định lúc 15:26. QA đã smoke luồng tạo đơn, thanh toán và cập nhật trạng thái trên canary. Dev tạm khóa đợt deploy mới. Giả thuyết chưa xác nhận: bản worker mới đánh dấu sự kiện đã xử lý trước khi ghi trạng thái, nên một số lần retry không cập nhật đơn. Ca sau theo dõi trong 60 phút: SRE trực giữ dashboard backlog, tuổi sự kiện cũ nhất và tỷ lệ xử lý lỗi, báo incident lead nếu backlog lại tăng trong 5 phút. QA đối soát 20 đơn bị ảnh hưởng với log thanh toán và gắn kết quả vào ticket. Dev phụ trách xác minh giả thuyết bằng trace ID và chỉ đề xuất mở lại rollout sau khi sửa và test tái hiện. Em ghi ticket, link dashboard và checklist owner vào incident log, rồi yêu cầu người trực ca sau xác nhận đã nhận bàn giao.
    ```


Phản hồi công khai của lượt · rỗng.

Hàng đợi · `incident-collaboration` → `http-api` → `postgresql` → ∅.

- `postgresql` · PLANNED / INSUFFICIENT_EVIDENCE / 3 lượt → CLOSED / INSUFFICIENT_EVIDENCE / 3 lượt / QUESTION_BUDGET.
- `http-api` · PLANNED / INSUFFICIENT_EVIDENCE / 1 lượt → CLOSED / INSUFFICIENT_EVIDENCE / 1 lượt / QUESTION_BUDGET.
- `incident-collaboration` · ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt → CLOSED / DEMONSTRATED_AT_TARGET / 2 lượt / QUESTION_BUDGET.
  - `c2` · 1 lượt, +1 evidence ledger, target result `AT_TARGET`, `stagnant_turns=0`, contradiction 0.
  - Cờ tiêu chí · `clarification_spent=false`, `easier_spent=false`, `deeper_spent=false`, `stop_reason=null`.

Lý do kết thúc phần chuyên môn · `QUESTION_BUDGET`.

### 14-finish · Xác nhận xem kết quả

Ứng viên xác nhận xem kết quả sau lời chào kết. Thực thi chuyển CLOSING sang FINISHED.

`POST /api/v2/interview/conversation` → HTTP 200 trong 0.009 giây. [Request và response](run/http/14-finish.json) · [Trace](run/components.jsonl) seq 692–695.

**Chuyển trạng thái** · v13 / CLOSING → v14 / FINISHED. Tổng số câu đã ghi nhận 10.

Hàng đợi · ∅ → ∅.

Lý do kết thúc phần chuyên môn · `QUESTION_BUDGET`.

## Kết quả đã chốt

Phiên có **10 câu được ghi nhận qua 13 lần gửi câu trả lời**, cộng bốn request tạo phiên và chuyển giai đoạn. Ba lần `503` đều được gửi lại nguyên văn từ snapshot trước lỗi. Có 14 response HTTP 200 và 3 response HTTP 503 trong trace của phiên. Snapshot v13 đã chứa báo cáo tại `CLOSING`. Request `NEXT` chuyển sang v14 `FINISHED` và trả cùng báo cáo, cả khi gọi endpoint trực tiếp qua cổng 8000 bằng cùng payload. [Snapshot v14 và PublicSession](run/http/14-finish.json) · [Đối chiếu API trên cổng 8000](run/live-final-transition.json) · [Kết quả kiểm tra tính toàn vẹn](run/verification.json).

| Mục tiêu | Câu | Kết luận thực tế của hệ thống | Căn cứ lưu trong trạng thái cuối |
| --- | --- | --- | --- |
| PostgreSQL | 1–3 | `INSUFFICIENT_EVIDENCE` | `c1` đạt target qua câu 3 sau diagnostic L2. `c2` chưa hỏi. Mục tiêu đã nhường lượt và được đóng ở `QUESTION_BUDGET`. |
| Python | 4–5 | `DEMONSTRATED_AT_TARGET` | Judge ghi `AT_TARGET` cho cả `c1` và `c2`. Đóng `SUFFICIENT_EVIDENCE`. Kết luận `c1` sai theo phép chạy code đối chứng bên dưới. |
| RabbitMQ | 6–7 | `DEMONSTRATED_AT_TARGET` | Ledger ghi `ABOVE` ở câu 6 và `AT_TARGET` ở câu 7, đều tại L4 là target của mục tiêu. Báo cáo kết luận hai tiêu chí đạt target. Đóng `SUFFICIENT_EVIDENCE`. |
| HTTP API | 8 | `INSUFFICIENT_EVIDENCE` | `c1` có một lần `NO_EVIDENCE / UNDETERMINED`, `c2` chưa hỏi. Mục tiêu nhường chỗ để hỏi kỹ năng còn chưa được phủ. Đóng `QUESTION_BUDGET`. |
| Phối hợp QA/SRE | 9–10 | `DEMONSTRATED_AT_TARGET` | Cả hai tiêu chí đạt. Engine chốt đánh giá của câu 10 trước khi đóng mục tiêu bằng `QUESTION_BUDGET`. |
| Docker | 0 | `NOT_ASSESSED` | Snapshot nội bộ ghi `EXCLUDED / PLAN_BUDGET`. Báo cáo công khai có mục Docker và không có evidence, `stop_reason=null`. |

`report()` chạy ở mỗi lần trả `public`, duyệt toàn bộ mục tiêu trong snapshot. `assessment` lấy từ `ObjectiveState`; `criterion_report` dùng kết quả ở target, progress và các quy tắc đủ bằng chứng. Điểm mạnh lấy lý do của target result dương không còn mâu thuẫn. Điểm yếu lấy target result `BELOW` không còn mâu thuẫn và các lần thừa nhận chưa biết. `evidence` công khai chỉ giữ bằng chứng độc lập đúng target có quan sát thực chất hoặc thừa nhận chưa biết. Vì vậy PostgreSQL công khai câu 1 và 3, trong khi câu 2 vẫn nằm trong ledger nội bộ. Gợi ý ôn tập cho PostgreSQL dựa vào quá trình gặp khó rồi phục hồi ở `c1`, còn HTTP API có gợi ý cho `c1` dựa vào lần thừa nhận chưa biết. [Báo cáo thực tế](run/final-report.json) · [Hàm tổng hợp](../../ai-service/adaptive_questioning/evidence/reporting.py).

## Đối chiếu chất lượng và hướng cải thiện

1. **Judge chấm đạt cho lỗi Python có thể tái hiện.** Câu 4 yêu cầu giữ *bản ghi* xuất hiện đầu tiên. Dict comprehension chỉ giữ vị trí chèn đầu tiên của *khóa* và cập nhật giá trị thành bản ghi cuối cùng. Với đầu vào `A:first, B:other, A:last`, Python 3.11.18 trả `A:last, B:other`. Judge lại chấm `SUPPORTS / AT_TARGET` và lý giải rằng bản ghi đầu tiên được giữ. Engine bỏ qua xác minh `c1`, chuyển sang `c2` và đóng mục tiêu Python đạt sau câu 5. Kiểm tra tính nguyên văn của trích dẫn đã hoạt động, nhưng không xác minh được tính đúng của code. Nên bổ sung ca đối chứng trùng ID với payload khác nhau cho đánh giá `TEXT/CODING` và dùng kết quả chạy trong môi trường cô lập làm tín hiệu xác minh khi bài có oracle rõ ràng. [Câu 4](run/http/07-q04.json) · [Câu 5](run/http/08-q05.json) · [Phản ví dụ chạy Python](run/coding-counterexample.json).

2. **Thiếu một phần câu trả lời PostgreSQL bị gán là mâu thuẫn.** Judge thừa nhận ứng viên giải thích đúng Seq Scan và Sort, rồi gán `CONTRADICTS / BELOW` vì ứng viên chưa đưa DDL. `JudgeSignature` hướng dẫn dùng `UNCLEAR / UNDETERMINED` cho bằng chứng một phần chưa đủ anchor. Đầu ra phù hợp schema nên vẫn qua kiểm tra, làm engine hạ độ khó thay vì làm rõ phần SQL còn thiếu. Nên thêm ví dụ đối chiếu giữa phát biểu sai và thiếu một vế, dùng `unresolved_aspects` để biểu diễn phần SQL chưa quan sát được. Rubric cũng đưa ví dụ `ALTER TABLE ADD INDEX` cho PostgreSQL. Đối chiếu trên bảng tạm cho thấy cú pháp đó bị từ chối, còn `CREATE INDEX ... ON ...` của câu 3 chạy thành công và được Judge chấp nhận trong phiên. Nên kiểm tra cú pháp ví dụ theo hệ quản trị trước khi khóa rubric. [Lần chấm câu 1 và retry](run/http/04-q01-retry.json) · [Câu 3](run/http/06-q03.json) · [Đối chiếu PostgreSQL](run/postgresql-ddl-check.txt).

3. **Validator bảo vệ snapshot nhưng việc sinh hoặc chấm lỗi làm gián đoạn phiên.** Câu 1 gặp hai verdict `WRONG_DEPTH` cho hai bản nháp giống nhau ở lần đầu. Câu 7 bị từ chối lần lượt vì trích dẫn ghép bằng dấu `...` và vì Judge liệt kê phần còn thiếu của mức cao hơn trong một kết luận `AT_TARGET`. Câu 8 xử lý `standalone_inability` thành công trong bộ nhớ, nhưng bước sinh câu `BEHAVIORAL` sau khi nhường lượt lại thất bại hai lần do câu gộp. Cả ba lỗi trả `503`; kiểm tra trace xác nhận mỗi câu chỉ xuất hiện một lần trong danh sách đã trả lời cuối. Nên ưu tiên dải dòng cho bằng chứng dài, tăng tính cụ thể của hướng dẫn sửa theo từng dạng lỗi và loại ngay những bản nháp trùng bản vừa bị bác. Nếu cần giảm số lần ứng viên phải gửi lại, có thể thiết kế trạng thái trung gian có version để giữ một câu trả lời đã được chấm hợp lệ trong lúc tạo lại câu tiếp theo. [Trace seq 125–151, 464–475 và 545–570](run/components.jsonl).

4. **Nhãn `ABOVE` của câu RabbitMQ không khớp điều kiện extension.** Judge gán `ABOVE` ở câu 6 vì ứng viên nêu ranh giới commit/ACK. Mục tiêu đang ở L4, `extension_depth=null` và `allow_extension_probes=false`. Anchor cao hơn cũng nêu backoff và DLQ, hai phần không xuất hiện trong câu trả lời. Validator đã chấp nhận observation, nên `evidence.performance` công khai vẫn là `ABOVE` trong khi kết luận tiêu chí và mục tiêu đều là `DEMONSTRATED_AT_TARGET`. Nên kiểm tra sự tương thích của `ABOVE` với `extension_depth` tại bước validate và thống nhất cách hiển thị mức của một bằng chứng với mức kết luận của mục tiêu. [Câu 6](run/http/09-q06.json) · [Bằng chứng công khai cuối phiên](run/final-report.json).

## Độ bao phủ quan sát được

- Các action đã thành câu hỏi thực tế là `INITIAL`, `ASK_EASIER` và `FOLLOW_UP`. Chuỗi PostgreSQL xác minh đường L3 → L2 → L3 và sự khác biệt giữa điểm trên diagnostic với mức của mục tiêu. RabbitMQ và tình huống phối hợp đều hỏi tiếp tiêu chí thiết yếu chưa có bằng chứng ở cùng độ sâu. Câu 8 xác minh `standalone_inability` đi qua logic tất định và ưu tiên một lượt cho kỹ năng chưa hỏi khi ngân sách sát mức dự phòng.
- Phiên này không phát sinh `CLARIFY`, `VERIFY_CONTRADICTION` hoặc `PROBE_DEEPER`. `PROBE_DEEPER` bị tắt bởi policy thực tế. Không có lần quay lại mục tiêu đã nhường, không có tái phân bổ Docker, và phiên kết thúc do số câu. Các đường hết giờ, dừng tay và hoàn tất kế hoạch trước ngân sách nằm ngoài kết quả thực nghiệm này.
- Trace chứa 695 sự kiện và 60 kết quả thực thi ở biên DSPy, tất cả trả model `qwen/qwen3.7-flash`. Đây là số quan sát của một phiên với fixture và cấu hình hiện tại. Các kết luận về thiết kế API, quy tắc chấm và độ đủ bằng chứng trong báo cáo dẫn chiếu snapshot hoặc mã thực thi tương ứng. [Trace đầy đủ](run/components.jsonl) · [Chỉ mục từng bước](run/timeline.json).

