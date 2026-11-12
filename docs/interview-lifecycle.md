# Mở đầu, giới thiệu và chào kết thúc phỏng vấn

Phiên mới qua backend đi theo `OPENING → SELF_INTRODUCTION → INTERVIEW → CLOSING → FINISHED` cho cả TEXT và VOICE. Cơ chế blueprint, sinh câu hỏi theo tiêu chí, Judge và ngân sách câu chuyên môn giữ nguyên.

## Mở đầu và tự giới thiệu

Backend gửi `opening` khi gọi AI `/start`, lấy tên công ty từ hồ sơ ứng tuyển và vị trí từ session. Tên người phỏng vấn mặc định là Minh, được nói rõ là người phỏng vấn AI mô phỏng. Không sinh thêm thông tin về công ty. Contract nội bộ hỗ trợ `interviewer_name`, `company_description` nếu nguồn dữ liệu cung cấp; không có UI nhập các trường này trong đợt này.

Lời mở đầu dùng mẫu có biến, được lưu một lần. TEXT hiển thị lời chào trong cùng khung trao đổi và tự chuyển sang nhận phần giới thiệu, không có nút chuyển bước. VOICE phát qua Simli và chuyển khi avatar xác nhận đã đọc xong. Màn hình luôn có ba vùng: avatar AI, nội dung AI đang hỏi/nói và bản ghi câu trả lời voice chỉ đọc của ứng viên. Lời mở đầu, câu hỏi chuyên môn và lời tạm biệt dùng chung vùng nội dung AI; không mở các màn giai đoạn riêng. Tiến độ, thời gian và kết thúc phiên nằm trong phần tùy chỉnh. Nút tiếp tục thủ công chỉ hiện khi giọng đọc lỗi; người dùng cũng có thể chủ động dừng giọng đọc.

Phần tự giới thiệu có 120 giây riêng, cho phép gửi hoặc bỏ qua. Hết khoảng chờ sẽ chuyển sang chuyên môn, không tự nộp nội dung đang viết/ghi âm. Lời mở đầu có khoảng chờ 180 giây để kết nối thiết bị. Phần chuyên môn chỉ bắt đầu tính đủ `duration_seconds` khi đã gửi/bỏ qua giới thiệu.

Nội dung giới thiệu lưu ở `conversation.introduction`, ngoài `turns`. Không gọi Judge, không tăng số câu, không đưa nội dung tự giới thiệu vào context sinh câu hỏi hoặc rubric. Câu chuyên môn đầu nhận lời dẫn ghi nhận trung tính. Lịch sử TEXT có mục riêng cho mở đầu và tự giới thiệu.

## Kết thúc

Hoàn tất kế hoạch, hết số câu, hết giờ hoặc xác nhận dừng sớm đều lưu lời tạm biệt theo nguyên nhân. `is_finished` đánh dấu phần đánh giá đã chốt; `conversation.phase=CLOSING` giữ giao diện trò chuyện trước trang kết quả. `FINISHED` đánh dấu đã đi qua phần chào kết thúc. Dừng lại lần nữa không tạo lời tạm biệt mới.

TEXT hiện lời chào trong cùng khung trao đổi, giữ câu trả lời vừa gửi và có nút **Xem kết quả**. VOICE tắt tiếp nhận lời nói, giữ avatar và chờ sự kiện `silent` sau gói audio cuối cùng, ổn định 300 ms, rồi tự hiện kết quả; không mở màn hình tạm biệt riêng. Tải xong TTS không được coi là đọc xong. Nếu người dùng đã tạm dừng micro trước khi kết thúc, lời chào vẫn được phát. Nếu TTS/avatar lỗi, người dùng có thể tiếp tục bằng nút **Xem kết quả**. Tải lại tại CLOSING cần thao tác kết nối lại để nghe tiếp theo chính sách không tự mở thiết bị; không cần cấp lại quyền micro.

Speech/avatar cho phần hội thoại kiểm tra chủ phiên, VOICE, message ID, version và hạn hội thoại riêng. Nhờ đó có thể đọc lời tạm biệt trong 120 giây sau khi kết thúc đánh giá, kể cả hết hạn chuyên môn. STT chỉ cho phép SELF_INTRODUCTION và INTERVIEW. Client không gửi văn bản tùy ý để đọc.

## Lưu trữ và tương thích

- `conversation` lưu trong snapshot, public state và dynamic state; không cần migration database.
- `POST /api/v2/sessions/{id}/interview/conversation` nhận `request_id`, `message_id`, `expected_state_version`, `action`, `introduction`. Các action là `NEXT`, `SUBMIT_INTRODUCTION`, `SKIP_INTRODUCTION`.
- Receipt và compare-and-swap dùng chung cơ chế phiên hiện có; retry không ghi trùng phần giới thiệu hoặc chuyển giai đoạn hai lần. Lỗi sinh câu chuyên môn đầu tiên không commit mất phần tự giới thiệu: client giữ bản nháp và request ID để gửi lại.
- Snapshot cũ không có `conversation` giữ nguyên luồng đang chạy. API tính toán nội bộ `/start` không có `opening` tiếp tục hỗ trợ contract cũ; backend public luôn gửi `opening` cho phiên mới.
- Reload không tự mở micro. Reload tại SELF_INTRODUCTION tiếp tục phần tự giới thiệu, không đọc lại lời mở đầu.

## Kiểm tra

Python: `tests_adaptive_questioning/test_interview_lifecycle.py` cùng hồi quy adaptive/voice. Backend: `EvidenceVoiceTest`, `EvidenceServiceTest` và các kiểm thử contract/client hiện có. Frontend: TypeScript, ESLint, `voice-recognition-test.mjs`, `simli-audio-test.mjs`, `interview-lifecycle-smoke.mjs` và hồi quy start/expiry/voice.

Browser smoke dùng API, micro và SDK Simli giả lập trên localhost; không sửa dữ liệu thật hoặc gọi model có phí. Cần thử với micro và Simli/TTS thật để đánh giá nhịp nói, phát âm và sự kiện kết thúc trên môi trường triển khai.
