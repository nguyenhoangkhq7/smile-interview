# 🎨 Frontend Agent Guidelines — `web-app`

Tài liệu này quy định các rào cản kỹ thuật cứng và nguyên tắc bắt buộc khi code trên `web-app`.

---

### 🏛️ 1. Tech Stack
*   **Next.js 16.2.9 (App Router)** & **React 19.2.4**.
*   **Base UI** (`^1.6.0`) & **Tailwind CSS v4** (`^4.3.2`).
*   **Zustand** (`^5.0.14`) & **Three.js** (`^0.185.0`) + **R3F** (`^9.6.1`).

---

### 🛡️ 2. Rào Cản Kỹ Thuật Cứng (Hard Constraints)

#### Quản lý cấu hình & Biến môi trường:
*   *Bắt buộc* nạp biến môi trường từ file `.env.local` đặt trong thư mục [web-app](file:///d:/projects/smile-interview/web-app) này. Tuyệt đối không load từ root.

#### Quy định thiết kế UI/UX:
*   *Ưu tiên Dark Mode*: Giao diện được tối ưu mặc định cho chế độ tối.
*   *Low Cognitive Load*: Giảm tải nhận thức tối đa, chia nhỏ các bước xử lý (Upload -> Match -> Start), tăng khoảng trắng (`gap-6`, `p-6`).
*   *Nền Slate-950*: Sử dụng màu nền chính là Slate-950 (`bg-slate-950` hoặc tương đương) cho Trang chủ, Admin và Phòng phỏng vấn.
*   *Card tương phản cao*: Các thẻ Card phải có nền tương phản rõ rệt với nền chính (`bg-slate-900`, `bg-zinc-900` hoặc `.glass-dark`), viền mỏng (`border-white/10` hoặc `border-slate-800`), hover sáng viền.
*   *WOW Factor*: Sử dụng Glassmorphism (`.glass-dark` định nghĩa trong [globals.css](file:///d:/projects/smile-interview/web-app/src/globals.css)), góc bo tròn lớn (`rounded-2xl`, `rounded-3xl`), và hiệu ứng chuyển cảnh mượt mà (`transition-all`, `animate-fade-up`).

---

### 📂 3. Quy ước viết Code (Coding Conventions)

#### Naming Conventions:
*   Components: PascalCase (Tên file trùng tên component).
*   Hooks: camelCase có tiền tố `use` (Ví dụ: [useNewInterview.ts](file:///d:/projects/smile-interview/web-app/src/hooks/useNewInterview.ts)).
*   Props/Interfaces: PascalCase kèm hậu tố `Props` (Ví dụ: `ActiveSessionsPanelProps`).

#### Cấu trúc Layer (Atomic-ish Design):
*   `src/app/`: App Router và API Routes (BFF proxy).
*   `src/components/ui/`: Nguyên tử UI nguyên bản từ Base UI/shadcn. Đóng gói icon tại [src/components/ui/icons/index.tsx](file:///d:/projects/smile-interview/web-app/src/components/ui/icons/index.tsx).
*   `src/components/features/`: Component nghiệp vụ theo domain (home, history, admin, interview).
*   `src/hooks/`: Chứa 100% logic phức tạp và state. Component UI chỉ bind handlers/data từ Hook trả về.

#### Gọi API & Xử lý lỗi:
*   Client chỉ gọi API Routes qua [axiosClient](file:///d:/projects/smile-interview/web-app/src/lib/axiosClient.ts). Không gọi trực tiếp dịch vụ Java hay DB.
*   Bắt lỗi dùng safe casting: `const error = err as Error`.
*   Hiển thị thông báo bằng `toast` từ `sonner`. Không dùng `alert`.

---

### ⚡ 4. Tối ưu hóa (Performance)
*   *RSC mặc định*: Tận dụng React Server Components. Chỉ khai báo `'use client'` khi có tương tác người dùng.
*   *Lazy Loading 3D*: Bắt buộc dùng `next/dynamic` với `ssr: false` cho component 3D (Ví dụ: `InterviewerModel` và `InterviewerAvatar`).
*   *Tối ưu hình ảnh*: Dùng thẻ `<Image />` từ `next/image` thay cho thẻ `<img>`.
