# ☕ Backend SOLID & Clean Code Rules (`services`)

### 🧩 1. SOLID
- **S (SRP)**: Thin Controllers (chỉ nhận request & gọi Service). Package-by-Feature. 1 Class = 1 nghiệp vụ.
- **O (OCP)**: Mở rộng nghiệp vụ qua Interface & Strategy Pattern, hạn chế `if-else` lồng nhau.
- **L (LSP)**: Class triển khai phải thay thế hoàn toàn cho Interface, không quăng `UnsupportedOperationException`.
- **I (ISP)**: Chia nhỏ Interface theo từng nghiệp vụ cụ thể, tránh Interface phình to.
- **D (DIP)**: Phụ thuộc vào Abstraction (Interface). Bắt buộc dùng Constructor Dependency Injection.

---

### 🧹 2. Clean Code & Consistency
- **Nhất quán (Consistency)**: Bắt buộc tuân thủ phong cách code Java 21 / Node.js và cấu trúc có sẵn của dự án.
- **Đặt tên**: Package-by-Feature, DTO dùng `record` (Java). Đặt tên rõ nghĩa, chuẩnRESTful/gRPC.
- **Hàm**: Ngắn gọn (< 25 dòng), ≤ 3 tham số, chỉ xử lý 1 việc.
- **Xử lý lỗi**: Không nuốt lỗi (`catch` trống). Xử lý tập trung qua `@RestControllerAdvice` (Java) / Error Middleware (Node).
- **Tách biệt**: Không trộn lẫn Controller, DB queries và Business logic trong 1 nơi.
- **DRY & KISS**: Dùng MapStruct mapper, không lặp code thủ công, giữ logic tối giản.
