# 🤖 Smile Interview — Monorepo Architecture & Hard Constraints

Tài liệu này quy định các rào cản kỹ thuật cứng và nguyên tắc bắt buộc khi phát triển Smile Interview.

---

### 🏛️ 1. Cấu trúc Monorepo & Cổng Dịch Vụ
*   **Thư mục gốc**: [d:\projects\smile-interview](file:///d:/projects/smile-interview)
*   **web-app**: Frontend Next.js 16 (App Router) + React 19 + Zustand + Tailwind CSS v4. Cổng: `3000`.
*   **services/matching-service**: Backend Java 21 Spring Boot + PostgreSQL (pgvector). Cổng: `8081`.
*   **services/ai-inference-service**: Backend Java 21 Spring Boot gRPC. Cổng: `9091`.
*   **services/streaming-service**: Real-time Node.js Express + WebSockets + WebRTC. Cổng: `8001`.
*   **PostgreSQL**: Cơ sở dữ liệu lưu trữ `smile_interview_db`. Cổng: `5432`.
*   **Redis**: Cache và quản lý active sessions. Cổng: `6379`.

---

### 🛡️ 2. Rào Cản Kỹ Thuật Cứng (Hard Constraints)

#### Runtime & Phiên bản ngôn ngữ:
*   *Bắt buộc* sử dụng **Java 21** cho các dịch vụ Java (`matching-service`, `ai-inference-service`). Tuyệt đối không dùng cú pháp Java cũ hơn. Tận dụng Records, Pattern Matching, Virtual Threads.
*   *Bắt buộc* dùng **Node.js >= 24** và **Express** (ES Modules) cho `streaming-service`.

#### Cấu trúc Hạ tầng & Cấu hình:
*   *Bắt buộc* đặt và nạp các file biến môi trường `.env` **bên trong thư mục của TỪNG SERVICE cụ thể**. 
*   *Tuyệt đối không* lưu trữ hay nạp file `.env` chung ở thư mục root của dự án.
*   *Bắt buộc* cấu hình mock client cho Redis và OpenRouter khi chạy test (Xem cấu hình mock tại [redis.js](file:///d:/projects/smile-interview/services/streaming-service/src/config/redis.js) và fallback key trong [application.yaml](file:///d:/projects/smile-interview/services/ai-inference-service/src/main/resources/application.yaml)).

#### Quy định thiết kế UI/UX (Frontend):
*   *Ưu tiên giao diện Dark Mode*: Xây dựng giao diện tối ưu hóa mặc định cho chế độ tối (Dark Mode).
*   *Thiết kế Low Cognitive Load*: Giảm tải nhận thức tối đa, bố cục thoáng rộng, chia nhỏ quy trình phức tạp thành các bước riêng biệt, giấu bớt thông tin phụ bằng collapsible/modals.
*   *Nền Slate-950*: Sử dụng nền Slate-950 (`bg-slate-950`) cho các vùng chứa chính (Trang chủ, Admin dashboard, Phòng phỏng vấn).
*   *Card tương phản cao*: Hiển thị thông tin nổi bật bằng card có nền tương phản rõ rệt (`bg-slate-900`, `bg-zinc-900` hoặc `.glass-dark`), viền mỏng (`border-white/10` hoặc `border-slate-800`), hover sáng dần để định vị thị giác.

---

### 📂 3. Cấu trúc Code & Quy ước (Conventions)

#### Quy ước đặt tên:
*   Components: PascalCase (Ví dụ: `ActiveSessionsPanel.tsx`). Tên file trùng tên component.
*   Hooks: camelCase có tiền tố `use` (Ví dụ: [useNewInterview.ts](file:///d:/projects/smile-interview/web-app/src/hooks/useNewInterview.ts)).
*   DTOs/Mappers: Dùng Java `record` cho DTOs. Sử dụng MapStruct cho mappers trong Spring Boot.

#### Kiến trúc phân lớp:
*   *Package-by-Feature*: Gom toàn bộ class cùng nghiệp vụ vào một package (Ví dụ: `fit.iuh.modules.assessment`). Đặt phạm vi `package-private` cho Repository/Helpers.
*   *Isolate Logic*: Tách 100% logic phức tạp ra khỏi components UI đưa vào Custom Hooks.
*   *BFF Pattern*: Client chỉ gọi API Routes (`src/app/api/...`) thông qua [axiosClient](file:///d:/projects/smile-interview/web-app/src/lib/utils.ts). Không gọi trực tiếp Java Services hay Database.

#### Xử lý lỗi & Kiểu dữ liệu:
*   Không nuốt ngoại lệ (silent catch).
*   Sử dụng an toàn kiểu dữ liệu khi ép kiểu lỗi: `const error = err as Error`.
*   Java: Xử lý ngoại lệ tập trung qua `@RestControllerAdvice` (Ví dụ: [EvaluationServiceImpl.java](file:///d:/projects/smile-interview/services/ai-inference-service/src/main/java/fit/iuh/modules/evaluation/service/EvaluationServiceImpl.java)).
*   Node.js: Dùng middleware xử lý lỗi Express tập trung.

---

### ⚙️ 4. Tích hợp & Vận hành (Integration & Dev Commands)

#### Cơ sở dữ liệu & Tương tác:
*   *pgvector*: Dùng cho tìm kiếm ngữ nghĩa/vector trong `matching-service`. Truy vấn vector bằng toán tử `<=>`.
*   *Flyway*: Quản lý schema database. File migration đặt tại `src/main/resources/db/migration/`.
*   *gRPC*: Giao tiếp đồng bộ độ trễ thấp giữa `streaming-service` (Client) và `ai-inference-service` (Server).

#### Lệnh vận hành:
*   Khởi chạy toàn bộ stack Docker: `docker-compose up -d --build` (từ root).
*   Chạy dev frontend: `cd web-app && npm run dev`
*   Chạy lint frontend: `cd web-app && npm run lint` (Cấu hình tại [eslint.config.mjs](file:///d:/projects/smile-interview/web-app/eslint.config.mjs)).
*   Chạy test backend Java: `./mvnw clean test` (trong thư mục service tương ứng).
*   Chạy test Node.js: `npm test` (trong `streaming-service`).

#### Quy tắc hoàn thành tác vụ:
*   *Bảo tồn hợp đồng API*: Sửa DTO ở backend phải cập nhật client service tương ứng ở frontend.
*   *Type-Check*: Luôn chạy `npx tsc --noEmit` ở frontend và pass 100% trước khi hoàn thành.
*   *Unit test*: Tham khảo file [EvaluationServiceTest.java](file:///d:/projects/smile-interview/services/ai-inference-service/src/test/java/fit/iuh/modules/evaluation/EvaluationServiceTest.java) trước khi viết kiểm thử.
