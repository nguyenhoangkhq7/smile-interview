### 01-start · Tạo Blueprint, lập kế hoạch và mở đầu

Kiểm tra nhánh sử dụng lại Blueprint từ phiên cũ. Giữ nguyên fixture và cấu hình, gửi đúng Blueprint do hệ thống đã sinh ở lần trước.

`POST /api/v2/interview/start` → HTTP 200 trong 5.59 giây. [Request và response](run/http/01-start.json) · [Trace](run/components.jsonl) seq 1–33.

**Lời thoại thực tế của hệ thống**

```
Chào bạn, tôi là Minh, người phỏng vấn AI mô phỏng. Hôm nay chúng ta sẽ cùng thảo luận về vị trí Backend Engineer, tập trung vào các kỹ năng như PostgreSQL, Python và RabbitMQ mà bạn đã thể hiện qua kinh nghiệm thực tế. Rất vui được gặp lại bạn trong buổi luyện tập này; xin mời bạn bắt đầu bằng một lời giới thiệu ngắn gọn về bản thân và những trải nghiệm liên quan nhất nhé.
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

Ứng viên giả lập đọc lời chào và chuyển đến phần tự giới thiệu.

`POST /api/v2/interview/conversation` → HTTP 200 trong 0.007 giây. [Request và response](run/http/02-next.json) · [Trace](run/components.jsonl) seq 34–37.

**Chuyển trạng thái** · v1 / OPENING → v2 / SELF_INTRODUCTION. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

### 03-intro · Nhận tự giới thiệu và sinh câu đầu

Nộp lời tự giới thiệu giả lập, không dùng tên riêng hoặc thông tin hồ sơ thật.

`POST /api/v2/interview/conversation` → HTTP 200 trong 4.536 giây. [Request và response](run/http/03-intro.json) · [Trace](run/components.jsonl) seq 38–61.

**Phần tự giới thiệu giả lập đã gửi**

```
Em làm backend gần ba năm, chủ yếu với Python và PostgreSQL cho API đơn hàng. Em từng phối hợp với QA xử lý lỗi đồng bộ giả lập. Hàng đợi trong hệ thống thanh toán là phần em mới tìm hiểu.
```

**Chuyển trạng thái** · v2 / SELF_INTRODUCTION → v3 / INTERVIEW. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

- `postgresql` · PLANNED / NOT_ASSESSED / 0 lượt → ACTIVE / NOT_ASSESSED / 0 lượt.

Duyệt bản câu hỏi · `ALIGNED` (seq 57).

**Câu tiếp theo** · `postgresql` / `DEBUGGING` / `INITIAL` / L3 / `c1`.

`probe_reason` · Initial evidence for an essential criterion.

````
Bạn đang phân tích truy vấn lọc đơn hàng theo `status` và sắp xếp theo `created_at`. Kết quả `EXPLAIN ANALYZE` cho thấy:

```text
Sort  (cost=12000.00..12500.00 rows=1000 width=32) (actual time=450.00..460.00 rows=1000 loops=1)
  Sort Key: created_at DESC
  -> Seq Scan on orders  (cost=0.00..8000.00 rows=1000 width=32) (actual time=0.00..300.00 rows=1000 loops=1)
        Filter: (status = 'PENDING')
```

Truy vấn này chạy chậm trên bảng lớn. Hãy chỉ ra điểm nghẽn chính trong kết quả trên và đề xuất một thay đổi cụ thể về index hoặc query để cải thiện hiệu năng.
````

### 04-q01 · Câu 1 · postgresql · lần lỗi

Trả lời đúng phần đọc plan, bỏ ngỏ đề xuất index/query để kiểm tra phân biệt thiếu ý với mâu thuẫn.

`POST /api/v2/interview/respond` → HTTP 503 trong 11.245 giây. [Request và response](run/http/04-q01.json) · [Trace](run/components.jsonl) seq 62–120.

**Câu hỏi thực tế** · `DEBUGGING` / `INITIAL` / L3 / `c1`

````
Bạn đang phân tích truy vấn lọc đơn hàng theo `status` và sắp xếp theo `created_at`. Kết quả `EXPLAIN ANALYZE` cho thấy:

```text
Sort  (cost=12000.00..12500.00 rows=1000 width=32) (actual time=450.00..460.00 rows=1000 loops=1)
  Sort Key: created_at DESC
  -> Seq Scan on orders  (cost=0.00..8000.00 rows=1000 width=32) (actual time=0.00..300.00 rows=1000 loops=1)
        Filter: (status = 'PENDING')
```

Truy vấn này chạy chậm trên bảng lớn. Hãy chỉ ra điểm nghẽn chính trong kết quả trên và đề xuất một thay đổi cụ thể về index hoặc query để cải thiện hiệu năng.
````

**Câu trả lời giả lập đã gửi**

```
Em thấy Seq Scan đọc toàn bộ orders rồi mới lọc status, khoảng 300 ms ở node đó. Node Sort phải sắp các dòng giữ lại theo created_at. Em mới xác định được hai điểm này trong plan, chưa chốt thứ tự cột của index hay thay đổi query cụ thể.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v3. Response lỗi không có snapshot thay thế.

Judgment trong lần xử lý thất bại, seq 72 · `UNCLEAR / UNDETERMINED` · The candidate correctly identifies the bottleneck (Seq Scan reading the whole table) and explains the Sort node. However, the criterion requires proposing a specific change to an index or query to improve performance. The candidate explicitly states they have not yet decided on the column order for the index or the specific query change ('chưa chốt thứ tự cột của index hay thay đổi query cụ thể'). Therefore, there is no evidence of the required proposal, making the observation UNCLEAR regarding the full requirement..

Bản sao trong bộ nhớ, seq 82 · `UNCLEAR / UNDETERMINED` → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt. API không trả bản sao này.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 85) · `postgresql` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 87) · `postgresql` · `false`.

**Cảnh báo từ implementation**

- Seq 107 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 118 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 2/2): The question repeats a prior turn; use a new focused question instead

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 106).

### 04-q01-retry · Câu 1 · postgresql · lần lỗi

Gửi lại nguyên văn câu 1 từ snapshot v3 sau HTTP 503.

`POST /api/v2/interview/respond` → HTTP 503 trong 10 giây. [Request và response](run/http/04-q01-retry.json) · [Trace](run/components.jsonl) seq 121–179.

**Câu hỏi thực tế** · `DEBUGGING` / `INITIAL` / L3 / `c1`

````
Bạn đang phân tích truy vấn lọc đơn hàng theo `status` và sắp xếp theo `created_at`. Kết quả `EXPLAIN ANALYZE` cho thấy:

```text
Sort  (cost=12000.00..12500.00 rows=1000 width=32) (actual time=450.00..460.00 rows=1000 loops=1)
  Sort Key: created_at DESC
  -> Seq Scan on orders  (cost=0.00..8000.00 rows=1000 width=32) (actual time=0.00..300.00 rows=1000 loops=1)
        Filter: (status = 'PENDING')
```

Truy vấn này chạy chậm trên bảng lớn. Hãy chỉ ra điểm nghẽn chính trong kết quả trên và đề xuất một thay đổi cụ thể về index hoặc query để cải thiện hiệu năng.
````

**Câu trả lời giả lập đã gửi**

```
Em thấy Seq Scan đọc toàn bộ orders rồi mới lọc status, khoảng 300 ms ở node đó. Node Sort phải sắp các dòng giữ lại theo created_at. Em mới xác định được hai điểm này trong plan, chưa chốt thứ tự cột của index hay thay đổi query cụ thể.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v3. Response lỗi không có snapshot thay thế.

Judgment trong lần xử lý thất bại, seq 131 · `UNCLEAR / UNDETERMINED` · The candidate correctly identifies the bottleneck (Seq Scan reading the whole table) and explains the Sort node, which aligns with the 'at_target' requirement to identify the problem. However, the criterion explicitly requires proposing a specific change (index or query adjustment). The candidate explicitly states they have not yet decided on the column order for the index or the specific query change ('chưa chốt thứ tự cột của index hay thay đổi query cụ thể'). Since the required proposal is missing and no alternative valid optimization is offered, we cannot determine if they can meet the target or above-target criteria. It is not BELOW because the identification of the issue is correct; it is UNCLEAR/UNDETERMINED because the critical second half of the task (proposal) is incomplete..

Bản sao trong bộ nhớ, seq 141 · `UNCLEAR / UNDETERMINED` → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt. API không trả bản sao này.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 144) · `postgresql` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 146) · `postgresql` · `false`.

**Cảnh báo từ implementation**

- Seq 166 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 177 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 2/2): The question repeats a prior turn; use a new focused question instead

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 165).

### 04-q01-complete · Câu 1 · postgresql · lần lỗi

Hai lần nộp câu trả lời thiếu ý không được commit; ứng viên bổ sung đề xuất SQL khi gửi lại câu đang chờ. Đây là đầu vào khác với hai lần trước.

`POST /api/v2/interview/respond` → HTTP 503 trong 9.845 giây. [Request và response](run/http/04-q01-complete.json) · [Trace](run/components.jsonl) seq 180–244.

**Câu hỏi thực tế** · `DEBUGGING` / `INITIAL` / L3 / `c1`

````
Bạn đang phân tích truy vấn lọc đơn hàng theo `status` và sắp xếp theo `created_at`. Kết quả `EXPLAIN ANALYZE` cho thấy:

```text
Sort  (cost=12000.00..12500.00 rows=1000 width=32) (actual time=450.00..460.00 rows=1000 loops=1)
  Sort Key: created_at DESC
  -> Seq Scan on orders  (cost=0.00..8000.00 rows=1000 width=32) (actual time=0.00..300.00 rows=1000 loops=1)
        Filter: (status = 'PENDING')
```

Truy vấn này chạy chậm trên bảng lớn. Hãy chỉ ra điểm nghẽn chính trong kết quả trên và đề xuất một thay đổi cụ thể về index hoặc query để cải thiện hiệu năng.
````

**Câu trả lời giả lập đã gửi**

```
Seq Scan phải đọc toàn bộ bảng orders để lọc status, mất khoảng 300 ms trong số liệu trên; sau đó Sort sắp kết quả theo created_at. Em sẽ thử CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC); vì status là điều kiện bằng và trong nhóm này thứ tự created_at đã có sẵn trong B-tree. Em sẽ kiểm chứng lại bằng EXPLAIN ANALYZE với cùng tham số truy vấn.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v3. Response lỗi không có snapshot thay thế.

Judgment trong lần xử lý thất bại, seq 190 · `SUPPORTS / AT_TARGET` · The candidate correctly identifies the bottleneck (Seq Scan due to lack of index) and explains the performance impact based on the EXPLAIN output. They propose a specific composite index `CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC)` which directly addresses the filtering and sorting requirements. The rationale for using a B-tree index is sound. This meets the 'at_target' criteria of identifying the issue, explaining it, and proposing a correct index solution..

Bản sao trong bộ nhớ, seq 200 · `SUPPORTS / AT_TARGET` → ACTIVE / INSUFFICIENT_EVIDENCE / 1 lượt. API không trả bản sao này.

**Các lời gọi định tuyến quan sát được**

- `workflow.next_action` (seq 203) · `postgresql` · `FOLLOW_UP` · Collect initial evidence for an untested essential criterion.
- `EvidenceWorkflow._should_yield` (seq 205) · `postgresql` · `false`.

**Cảnh báo từ implementation**

- Seq 225 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 242 · Invalid question for session module3-qa-rerun-mixed10-20261118-c (attempt 2/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 224) → `GIVES_SOLUTION` (seq 241).

