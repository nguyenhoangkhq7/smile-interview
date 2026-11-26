# 🤖 SOLID & Clean Code Rules

### 🧩 1. SOLID
- **S (SRP)**: Một lớp/hàm chỉ làm 1 việc duy nhất. Tách biệt UI và Business Logic.
- **O (OCP)**: Mở rộng tính năng bằng Interface/Polymorphism, không sửa code lõi.
- **L (LSP)**: Lớp con phải thay thế hoàn toàn được cho lớp cha.
- **I (ISP)**: Chia nhỏ interface, tránh interface phình to.
- **D (DIP)**: Phụ thuộc vào Abstraction, áp dụng Dependency Injection.

---

### 🧹 2. Clean Code & Consistency
- **Nhất quán (Consistency)**: Bắt buộc tuân thủ phong cách code, cấu trúc và quy chuẩn có sẵn trong dự án.
- **Đặt tên**: Rõ ràng, bộc lộ ý nghĩa (`fetchUser`, `isAvailable`). Tránh tên vô nghĩa.
- **Hàm**: Ngắn gọn (< 20 dòng), ≤ 3 tham số, chỉ làm 1 việc.
- **Xử lý lỗi**: Không nuốt lỗi (silent catch). Xử lý tập trung qua Middleware/Advice.
- **Tách biệt**: Không trộn lẫn UI, DB truy vấn và API call trong cùng 1 hàm.
- **Type Safety**: Không dùng `any`, không dùng Magic Numbers/Strings.
- **DRY & KISS**: Không lặp code, giữ giải pháp tối giản nhất.
