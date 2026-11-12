# Theo dõi bước chuẩn bị phỏng vấn

`docker compose logs -f backend ai-service` hiển thị tiến trình theo `session_id`.

- Backend: nhận yêu cầu bắt đầu, số kỹ năng, tái sử dụng blueprint, bắt đầu/kết thúc gọi AI và commit phiên.
- AI: `request.started`, `blueprint.started`, `blueprint.batch_started`, `blueprint.progress`, `preparation.ready`, `question.started`, `question.ready`, `request.completed` hoặc `request.failed`.
- Nhà cung cấp: `model.started`, `model.retry` với mã HTTP và thời gian chờ, `model.failed` sau khi hết số lần thử.

Log không chứa CV, JD, prompt, nội dung câu hỏi/câu trả lời hay khóa API. Access log của Uvicorn chỉ xuất hiện khi request hoàn tất; log tiến trình dùng logger `uvicorn.error` để luôn hiện ở mức INFO trong Docker.

Giao diện giữ trạng thái chờ và tự gửi lại lệnh bắt đầu đúng một lần sau 5 giây nếu API trả 503. Lệnh bắt đầu idempotent và dùng lại cache batch; nếu vẫn lỗi thì hiện thông báo và cho phép thử thủ công. Không tự retry thao tác gửi câu trả lời hay ghi đè dữ liệu đã lưu.

Giữ nguyên mô hình `OPENROUTER_MODEL`. Tối đa ba lần gọi mô hình đồng thời trong một process; lỗi 429/timeout/5xx được thử lại tối đa hai lần, chờ 5 rồi 15 giây, có tôn trọng `Retry-After`. Lỗi xác thực/thanh toán không retry. Khi hết số lần thử, API trả 503 cùng thông báo rõ để người dùng thử lại, không commit phiên dở dang.

Những batch blueprint đã thành công được giữ trong bộ nhớ tối đa 15 phút, tối đa 256 batch. Retry dùng lại kết quả cho cùng nội dung yêu cầu và policy sinh; không cache lỗi, không cache câu trả lời hay kết quả chấm. Cache mất khi restart process. Mỗi lần đọc lấy bản sao để việc grounding không thay đổi bản gốc. Hai yêu cầu trùng nhau cùng chờ một batch đang chạy.

Phiên có lời mở đầu bắt đầu ở `OPENING`; câu chuyên môn đầu tiên được sinh sau phần tự giới thiệu, có log riêng `question.started`/`question.ready`.

Kiểm tra Qwen thật bằng dữ liệu giả lập, không đọc hồ sơ hay ghi dữ liệu backend:

```powershell
docker compose exec -T ai-service python scripts/verify_interview_preparation.py --skills 36
```

Phép thử có gọi nhà cung cấp AI thật. Kết quả đạt khi đã qua lời mở đầu và nhận được câu chuyên môn ở phase `INTERVIEW`; lỗi 429 kéo dài vẫn phụ thuộc vào hạn mức hiện tại của nhà cung cấp.
