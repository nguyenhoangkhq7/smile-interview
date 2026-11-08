# Hồ sơ ứng tuyển và các lượt phỏng vấn

Luồng: `/applications` → tạo hồ sơ qua `/interview/new` → phân tích CV/JD → đặt tên và lưu → chi tiết hồ sơ → bắt đầu lượt → kết quả → lượt mới.

`ApplicationProfile` lưu chủ sở hữu, tên/công ty/vị trí, liên kết tài liệu, bản chụp nội dung và tên CV/JD, kết quả phân tích ban đầu. Một `Session` thuộc một hồ sơ và có số lượt riêng. Các phiên cũ không có hồ sơ vẫn sử dụng luồng cũ.

Khi lưu hồ sơ, phiên chuẩn bị đã phân tích trở thành lượt 1 chưa bắt đầu. Thao tác lưu lặp lại trả về cùng hồ sơ. Lượt tiếp theo dùng bản phân tích của hồ sơ, không gọi lại pipeline skill-gap. Bộ tiêu chí và policy được đóng băng cùng transaction bắt đầu lượt đầu; lượt sau dùng lại bộ này để sinh câu hỏi mới, khởi tạo bằng chứng/câu trả lời từ đầu.

API yêu cầu JWT:

| Phương thức | Đường dẫn | Chức năng |
|---|---|---|
| GET | `/api/v1/application-profiles` | Hồ sơ của người hiện tại |
| POST | `/api/v1/application-profiles` | Tạo từ `{sourceSessionId, title, company?}` đã phân tích |
| GET | `/api/v1/application-profiles/{id}` | Bản phân tích và lịch sử các lượt |
| GET | `/api/v1/application-profiles/{id}/competency` | Năng lực hiện tại theo bằng chứng đã lưu |
| POST | `/api/v1/application-profiles/{id}/attempts` | Tạo lượt hoặc trả lại lượt chưa bắt đầu |

Phỏng vấn tiếp tục dùng `/api/v2/sessions/{id}/interview` cùng các thao tác `start`, `respond`, `stop`. Mỗi hồ sơ chỉ có một lượt `Not started` hoặc `In progress`; khóa hồ sơ và unique index PostgreSQL bảo vệ cả khi gửi yêu cầu đồng thời.

`USER_STOP` trước câu trả lời đầu tiên tạo trạng thái `Cancelled`; sau ít nhất một câu tạo `Stopped early`. Các lý do hoàn thành khác dùng `Completed`; lý do cụ thể vẫn nằm trong report. Kết thúc và tạo lại là hai bước: chỉ tạo lượt mới sau khi lượt cũ đã được đóng. Kết quả cũ được giữ nguyên. Phiên chưa trả lời không hiển thị kết luận năng lực.

CV/JD và phân tích của hồ sơ cố định; thay đổi tài liệu cần tạo hồ sơ mới. Module ôn luyện chưa được xây dựng.

## Năng lực hiện tại

`CompetencyProjection` tạo bảng đánh giá trực tiếp từ snapshot đã lưu khi đọc hồ sơ. Không cần migration, gọi AI hoặc chạy backfill; các lượt đã kết thúc trước khi triển khai cũng được tổng hợp. Lượt chưa kết thúc và lượt không có câu trả lời không làm thay đổi kết quả.

- Tách hoàn toàn chẩn đoán tài liệu khỏi năng lực quan sát. Không cập nhật các giá trị `candidate_proficiency`/`gap_magnitude` của mốc CV–JD hoặc lấy trung bình các lượt.
- Ghép theo objective/criterion của blueprint cố định, kiểm tra mức yêu cầu, bộ tiêu chí và rubric fingerprint. Đánh giá không tương thích bị bỏ qua và có thông báo.
- Chỉ dùng bằng chứng độc lập tại đúng target depth, trích đoạn thực sự nằm trong câu trả lời và có turn gốc. Không dùng câu dễ hơn/có gợi ý để xác nhận đạt yêu cầu. Kết luận vượt yêu cầu cần cả bằng chứng extension độc lập.
- Giữ kết luận khi nội dung không được hỏi lại hoặc lượt mới không bổ sung bằng chứng quyết định. Kỹ năng có một số yêu cầu đạt nhưng chưa kiểm tra hết được ghi là chưa kiểm tra đầy đủ.
- Bằng chứng đối nghịch trên cùng tiêu chí hoặc kết luận đầy đủ trái ngược tạo trạng thái `NEEDS_VERIFICATION`. Cần hai lượt xác nhận nhất quán về sau, với bối cảnh đã biết và khác nhau, mới gỡ mâu thuẫn. Lặp lại cùng bối cảnh không đủ.
- Bằng chứng theo từng tiêu chí không tự thay thế kết luận đầy đủ của AI cho cả yêu cầu. Nếu bằng chứng mới làm kết luận cũ không còn đáng tin nhưng chưa có kết luận đầy đủ mới, hiển thị chưa đủ bằng chứng.
- Giao diện hiển thị tổng quan, từng kỹ năng/yêu cầu/tiêu chí, lượt kiểm tra gần nhất và liên kết về câu trả lời gốc. Bằng chứng không hợp lệ hoặc chưa được kiểm tra không được xem là thất bại. Hoàn thành việc học sau này chỉ cập nhật tiến độ học.

Quy tắc tổng hợp có phiên bản `competency-1`. Khi điều chỉnh quy tắc, bảng hiện tại được tính lại từ lịch sử gốc, không mất dữ liệu đánh giá của từng lượt. Trọng tâm hỏi ở lượt mới hiện vẫn do bộ lập kế hoạch phỏng vấn chọn; tính năng này chưa tự thay đổi mức ưu tiên câu hỏi theo tiến độ tổng hợp.

## Kiểm tra

Giao diện hồ sơ gồm ba tab: năng lực hiện tại, lịch sử phỏng vấn, CV & JD. Tab được giữ trong URL (`#competency`, `#history`, `#documents`). Danh sách hồ sơ có tìm kiếm không dấu và lọc theo trạng thái; bảng năng lực ưu tiên nội dung cần tập trung, hiển thị sáu kỹ năng trước và mở bằng chứng trong dialog riêng. Khu vực hồ sơ sử dụng chân trang gọn, hỗ trợ thao tác bàn phím và bố cục mobile.

- Backend và migration: `scripts/verify-evidence-backend.ps1 -JavaHome <JDK>` (PostgreSQL tạm, không chạm database ứng dụng).
- AI: `python -m pytest tests_adaptive_questioning/test_evidence_workflow.py tests_adaptive_questioning/test_evidence_depth_policy.py -q` từ `ai-service`.
- Frontend: `npm run build`, lint các file thay đổi; sau khi chạy server: `node scripts/application-profiles-smoke.mjs http://localhost:3217`, `node scripts/competency-smoke.mjs http://localhost:3217` và `node scripts/evidence-smoke.mjs http://localhost:3217`.
- Kiểm tra thiết kế, tìm kiếm/lọc, tab, bàn phím và tên dài: `node scripts/application-design-smoke.mjs http://localhost:3217`. Báo cáo toán trong tab tài liệu: `node scripts/markdown-math-smoke.mjs http://localhost:3217`.

Triển khai đồng thời backend, AI service và web app. Backend tự áp dụng Flyway V3 khi khởi động. Không sửa các migration V1/V2 hoặc tự chuyển các phiên cũ thành hồ sơ.
