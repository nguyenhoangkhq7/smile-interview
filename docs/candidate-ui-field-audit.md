# Rà soát thông tin trên giao diện người dùng

Phạm vi: phân tích CV/JD mới, tab CV & JD của hồ sơ đã lưu, thiết lập và kết quả phỏng vấn (bao gồm phiên cũ). Không thay đổi giao diện HR/admin.

| Thông tin trước đây | Hiển thị cho người dùng sau điều chỉnh |
| --- | --- |
| Mã phân tích, P_JD/P_CV, Gap, Priority, chiến lược hỏi | Loại khỏi phần phân tích dành cho người dùng |
| MATCH/PARTIAL/MISSING | CV thể hiện phù hợp / CV có kinh nghiệm liên quan / CV chưa thể hiện |
| Hai tỷ lệ độ khớp với cách tính khác nhau | Một mức phù hợp từ nội dung tài liệu, có giải thích chưa phải đánh giá qua phỏng vấn |
| Báo cáo kiểm toán Markdown trong phân tích mới và hồ sơ đã lưu | Tóm tắt có cấu trúc, bối cảnh công việc và trích dẫn CV mở theo nhu cầu |
| Danh sách xếp theo Priority nội bộ | Hiển thị kỹ năng CV chưa thể hiện và kinh nghiệm liên quan trước |
| Coding, Debugging, Behavioral; mã kỹ năng | Nhãn tiếng Việt và tên kỹ năng dễ đọc |
| Bao phủ bằng chứng; lý do kết thúc dạng mã | Nội dung đã đánh giá; lý do diễn đạt dễ hiểu, có thông báo chung khi mã chưa được nhận diện |
| Nhiều chỉ số trùng lặp ở kết quả phỏng vấn | Bốn chỉ số chính; chi tiết câu hỏi và nhận xét nằm trong phần riêng |
| Judge, bảng điểm rubric và suy luận khởi tạo ở phiên cũ | Nhận xét từ AI, kết quả theo kỹ năng; không đưa suy luận nội bộ vào bản CSV tải từ màn hình này |
| Bước “Phòng phỏng vấn AI” khi thao tác thực tế là lưu hồ sơ | Bước “Lưu hồ sơ” |

Không suy ra người dùng thiếu năng lực chỉ vì CV chưa có thông tin. Phân tích không đầy đủ hiển thị thông báo dễ hiểu; danh sách rỗng hướng dẫn kiểm tra tài liệu.

Phần phân tích dùng tổng quan một hàng, bộ lọc theo trạng thái và ô tìm kiếm. Danh sách chỉ hiển thị tối đa 5 kỹ năng mỗi trang. Chọn kỹ năng để mở bối cảnh và trích dẫn trong hộp chi tiết có vùng cuộn riêng; số lượng kỹ năng và độ dài trích dẫn không kéo dài trang chính.

Tên kỹ năng tiếng Việt: bộ tạo slug và schema trích xuất giữ Unicode; tên gốc được truyền riêng qua `skill_name` → `jd_skill_name` / `matched_cv_skill_name` và được backend lưu cùng kết quả. Giao diện phân tích ưu tiên tên gốc. Với hồ sơ cũ, chỉ khôi phục tên khi một cụm từ trong trích dẫn JD tạo ra đúng mã ASCII cũ và không có cách đọc khác. Không thay mã trong hồ sơ/phiên đã lưu. Tab Năng lực dùng cùng tên từ phân tích ban đầu.

API bổ sung các trường tên hiển thị tùy chọn để giữ nguyên tiếng Việt. Cơ chế phân quyền backend và giao diện nghiệp vụ HR/admin được giữ nguyên.

Kiểm tra: TypeScript, ESLint, kiểm tra trình duyệt bằng fixture cho phân tích mới/hồ sơ đã lưu/phiên cũ/trạng thái rỗng và phân tích thiếu dữ liệu; luồng phỏng vấn văn bản, hiển thị mobile và truy cập trang HR bằng tài khoản thường. Kiểm tra bảng công thức Markdown được chuyển sang trang HR, nơi báo cáo chi tiết vẫn được sử dụng.
