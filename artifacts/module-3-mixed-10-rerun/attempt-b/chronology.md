### 01-start · Tạo Blueprint, lập kế hoạch và mở đầu

Khởi tạo độc lập với cùng dữ liệu và cấu hình giả lập. Dùng tiến trình mới để tránh tái sử dụng Blueprint trong cache.

`POST /api/v2/interview/start` → HTTP 200 trong 26.574 giây. [Request và response](run/http/01-start.json) · [Trace](run/components.jsonl) seq 1–64.

**Lời thoại thực tế của hệ thống**

```
Xin chào bạn, tôi là Minh, người phỏng vấn AI mô phỏng. Hôm nay chúng ta sẽ cùng thảo luận về vị trí Backend Engineer, tập trung vào các kỹ năng như Python, PostgreSQL và RabbitMQ mà bạn đã thể hiện qua các dự án FastAPI và tối ưu truy vấn. Bạn có thể dành vài phút để giới thiệu ngắn gọn về bản thân và kinh nghiệm liên quan của mình không?
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

`POST /api/v2/interview/conversation` → HTTP 200 trong 0.006 giây. [Request và response](run/http/02-next.json) · [Trace](run/components.jsonl) seq 65–68.

**Chuyển trạng thái** · v1 / OPENING → v2 / SELF_INTRODUCTION. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

### 03-intro · Nhận tự giới thiệu và sinh câu đầu

Nộp lời tự giới thiệu giả lập, không dùng tên riêng hoặc thông tin hồ sơ thật.

`POST /api/v2/interview/conversation` → HTTP 503 trong 6.313 giây. [Request và response](run/http/03-intro.json) · [Trace](run/components.jsonl) seq 69–101.

**Phần tự giới thiệu giả lập đã gửi**

```
Em làm backend gần ba năm, chủ yếu với Python và PostgreSQL cho API đơn hàng. Em từng phối hợp với QA xử lý lỗi đồng bộ giả lập. Hàng đợi trong hệ thống thanh toán là phần em mới tìm hiểu.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v2. Response lỗi không có snapshot thay thế.

**Cảnh báo từ implementation**

- Seq 83 · Invalid question for session module3-qa-rerun-mixed10-20261118-b (attempt 1/2): Ask exactly ONE response task; remove independent subquestions or numbered requests
- Seq 100 · Invalid question for session module3-qa-rerun-mixed10-20261118-b (attempt 2/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 99).

### 03-intro-retry · Gửi lại phần tự giới thiệu và sinh câu đầu

Thử lại trong phiên độc lập sau HTTP 503, giữ nguyên snapshot và lời giới thiệu.

`POST /api/v2/interview/conversation` → HTTP 503 trong 7.732 giây. [Request và response](run/http/03-intro-retry.json) · [Trace](run/components.jsonl) seq 102–128.

**Phần tự giới thiệu giả lập đã gửi**

```
Em làm backend gần ba năm, chủ yếu với Python và PostgreSQL cho API đơn hàng. Em từng phối hợp với QA xử lý lỗi đồng bộ giả lập. Hàng đợi trong hệ thống thanh toán là phần em mới tìm hiểu.
```

**Phản hồi lỗi thực tế**

```
{
  "detail": "AI chưa tạo được câu hỏi phù hợp. Dữ liệu đã lưu được giữ nguyên; vui lòng thử lại."
}
```

Lần gửi sử dụng v2. Response lỗi không có snapshot thay thế.

**Cảnh báo từ implementation**

- Seq 116 · Invalid question for session module3-qa-rerun-mixed10-20261118-b (attempt 1/2): Ask exactly ONE response task; remove independent subquestions or numbered requests
- Seq 127 · Invalid question for session module3-qa-rerun-mixed10-20261118-b (attempt 2/2): Ask exactly ONE response task; remove independent subquestions or numbered requests

