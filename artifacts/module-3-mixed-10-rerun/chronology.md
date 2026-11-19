### 01-start · Tạo Blueprint, lập kế hoạch và mở đầu

Dùng lại 6 kỹ năng nhiệm vụ và trích dẫn hư cấu của fixture trước, với lời mở đầu không có tên, công ty, CV/JD tóm tắt hay dữ liệu người dùng.

`POST /api/v2/interview/start` → HTTP 200 trong 29.624 giây. [Request và response](run/http/01-start.json) · [Trace](run/components.jsonl) seq 1–64.

**Lời thoại thực tế của hệ thống**

```
Xin chào, tôi là Minh, người phỏng vấn AI mô phỏng của bạn. Chào mừng bạn đến với buổi thực hành cho vị trí Backend Engineer. Hôm nay chúng ta sẽ cùng khám phá các kỹ năng như Python, PostgreSQL và RabbitMQ thông qua các tình huống thực tế. Bạn có thể chia sẻ ngắn gọn về bản thân và kinh nghiệm liên quan không?
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

`POST /api/v2/interview/conversation` → HTTP 200 trong 0.005 giây. [Request và response](run/http/02-next.json) · [Trace](run/components.jsonl) seq 65–68.

**Chuyển trạng thái** · v1 / OPENING → v2 / SELF_INTRODUCTION. Tổng số câu đã ghi nhận 0.

Hàng đợi · `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration` → `postgresql` → `python` → `rabbitmq` → `http-api` → `incident-collaboration`.

### 03-intro · Nhận tự giới thiệu và sinh câu đầu

Nộp lời tự giới thiệu giả lập, không dùng tên riêng hoặc thông tin hồ sơ thật.

`POST /api/v2/interview/conversation` → HTTP 503 trong 6.677 giây. [Request và response](run/http/03-intro.json) · [Trace](run/components.jsonl) seq 69–107.

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

- Seq 89 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 106 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 2/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 88) → `GIVES_SOLUTION` (seq 105).

### 03-intro-retry · Gửi lại phần tự giới thiệu và sinh câu đầu

Gửi lại nguyên văn lời tự giới thiệu từ v2 sau khi bước tạo câu đầu trả 503.

`POST /api/v2/interview/conversation` → HTTP 503 trong 7.222 giây. [Request và response](run/http/03-intro-retry.json) · [Trace](run/components.jsonl) seq 108–140.

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

- Seq 128 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 139 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 2/2): The question repeats a prior turn; use a new focused question instead

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 127).

### 03-intro-retry2 · Gửi lại phần tự giới thiệu và sinh câu đầu

Lần gửi thứ ba với cùng snapshot, message ID và nội dung giới thiệu.

`POST /api/v2/interview/conversation` → HTTP 503 trong 7.459 giây. [Request và response](run/http/03-intro-retry2.json) · [Trace](run/components.jsonl) seq 141–179.

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

- Seq 161 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 1/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.
- Seq 178 · Invalid question for session module3-qa-rerun-mixed10-20261118 (attempt 2/2): Keep the problem inputs and constraints. Remove the method or answer the candidate must derive.

Duyệt bản câu hỏi · `GIVES_SOLUTION` (seq 160) → `GIVES_SOLUTION` (seq 177).

