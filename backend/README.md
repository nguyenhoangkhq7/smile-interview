# Backend

## Database

`src/main/resources/db/migration/V1__init_schema.sql` is the initial schema for
the current pipeline. It creates six application tables and the existing
development ADMIN account (HR role and evaluations were removed in V11). PostgreSQL 17 is supported without extensions.

CV and JD text is stored only in `raw_text`. Upload endpoints also accept the
legacy input names `parsed_content` and `extracted_text`, and store their values
in `raw_text`.

The previous V1–V17 history has been replaced before deployment. Start with an
empty development database when using this revision; an existing database with
the old Flyway history cannot be upgraded with this V1. Changing migration files
does not reset an existing database or Docker volume.

## Verification

With Java 21+ and an empty test PostgreSQL database, set
`SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, and
`SPRING_DATASOURCE_PASSWORD`, then run `./mvnw test` (`mvnw.cmd test` on Windows).
The tests run Flyway, validate Hibernate mappings, and check persistence and
foreign-key cleanup for the current pipeline. Use a separate test database:
Flyway creates its schema and development accounts during application startup.

## JWT signing key

Set `JWT_SECRET` in `backend/.env` for Docker Compose or in the process environment
when running Spring directly. Generate a separate key for each environment with
`openssl rand -base64 48`. Spring requires a signing key of at least 32 bytes at
startup. The test runtime generates its own key.

## Thông báo khi phân tích CV/JD hoàn tất

Chạy `node scripts/init-web-push.mjs` từ thư mục gốc để tạo một cặp khóa VAPID trong `backend/.env`. Docker Compose nạp các biến này vào backend. Khi triển khai, dùng cùng `WEB_PUSH_PUBLIC_KEY` và `WEB_PUSH_PRIVATE_KEY` trên các replica và qua các lần khởi động. Đặt `WEB_PUSH_SUBJECT` thành URI liên hệ của đơn vị vận hành, ví dụ `mailto:ops@example.org`. Chạy lại backend và web-app với bản build mới để áp dụng migration V10 và phục vụ service worker. Khi chạy Spring ngoài Compose, truyền các biến qua môi trường của tiến trình.

Khi hệ thống nhận hồ sơ để phân tích, trang tự hỏi **Nhận thông báo khi phân tích xong?**. Chọn **Bật thông báo** để cấp quyền của trình duyệt. Chọn **Bỏ qua** để ẩn lời mời cho tài khoản này trên trình duyệt này. Người dùng vẫn có thể bật lại bằng nút **Báo cho tôi khi phân tích xong**. Một lần bật áp dụng cho các lượt phân tích tiếp theo của tài khoản trên trình duyệt đó. Nút này cũng cho phép tắt. Dùng HTTPS hoặc localhost để đăng ký service worker. Trên iPhone/iPad, dùng ứng dụng web đã thêm vào Màn hình chính nếu trình duyệt yêu cầu.

Backend ghi yêu cầu gửi thông báo trong transaction chốt kết quả. Payload được mã hóa và chỉ chứa ID của phiên và job. Bấm thông báo mở kết quả qua luồng xác thực. Worker gửi lại khi dịch vụ push tạm lỗi và xóa đăng ký khi nhà cung cấp trả 404/410.
