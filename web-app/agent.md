# 🎨 Frontend SOLID & Clean Code Rules (`web-app`)

### 🧩 1. SOLID
- **S (SRP)**: UI Component chỉ hiển thị & lắng nghe sự kiện. Bắt buộc đẩy Business Logic vào Custom Hooks (`src/hooks/`).
- **O (OCP)**: Mở rộng UI qua Props/Composition, không sửa trực tiếp component lõi.
- **L (LSP)**: Component bọc lại (wrapper) phải tuân thủ và không phá vỡ Props interface cũ.
- **I (ISP)**: Định nghĩa Props Interface vừa đủ, không ép component nhận Props thừa.
- **D (DIP)**: Không gọi trực tiếp backend/DB từ UI; bắt buộc gọi qua API Routes (`src/app/api/...`) & `axiosClient`.

---

### 🧹 2. Clean Code & Consistency
- **Nhất quán (Consistency)**: Bắt buộc tuân thủ phong cách code, cấu trúc React/Next.js có sẵn trong dự án.
- **Đặt tên**: Component = PascalCase, Hook = `use...`, Props = PascalCase + `Props`.
- **Hàm/Component**: Ngắn gọn, tách component nhỏ nếu quá dài (< 50 dòng cho UI).
- **Xử lý lỗi**: Bắt lỗi an toàn (`err as Error`), dùng `toast` (sonner), tuyệt đối không nuốt lỗi (`catch` trống).
- **Type Safety**: Tuyệt đối không dùng `any`. Định nghĩa Interface/Type rõ ràng.
- **DRY & KISS**: Tái sử dụng UI components từ `src/components/ui/`, không lặp logic.
