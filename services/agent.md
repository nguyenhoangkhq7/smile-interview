# ☕ Backend Agent Guidelines — `services`

Tài liệu này quy định các rào cản kỹ thuật cứng và nguyên tắc bắt buộc khi code trên các microservices.

---

### 🏛️ 1. Tech Stack
*   **Java Services** (`matching-service`, `ai-inference-service`): Spring Boot 3.3.x, gRPC Server.
*   **Node Service** (`streaming-service`): Express, Socket.io, gRPC Client.
*   **Databases & Caches**: PostgreSQL (pgvector), Flyway migrations, Redis cache.

---

### 🛡️ 2. Rào Cản Kỹ Thuật Cứng (Hard Constraints)

#### Phiên bản ngôn ngữ & Runtime:
*   *Bắt buộc* sử dụng **Java 21** cho các dịch vụ Java. Tuyệt đối không dùng cú pháp Java cũ hơn. Tận dụng Records, Pattern Matching, Virtual Threads.
*   *Bắt buộc* dùng **Node.js >= 24** và **Express** (ES Modules) cho `streaming-service`.

#### Cấu hình & Biến môi trường:
*   *Bắt buộc* nạp biến môi trường từ file `.env` **bên trong thư mục của TỪNG SERVICE cụ thể**. 
*   *Tuyệt đối không* lưu trữ hay nạp file `.env` chung ở thư mục root của dự án.
*   *Bắt buộc* cấu hình mock client cho Redis và OpenRouter khi chạy test (Xem cấu hình mock tại [redis.js](file:///d:/projects/smile-interview/services/streaming-service/src/config/redis.js) và fallback key trong [application.yaml](file:///d:/projects/smile-interview/services/ai-inference-service/src/main/resources/application.yaml)).

---

### 📂 3. Quy ước viết Code (Coding Conventions)

#### Naming & Structure:
*   *Package-by-Feature*: Gom toàn bộ class cùng nghiệp vụ vào một package (Ví dụ: `fit.iuh.modules.assessment`). Đặt phạm vi `package-private` cho Repository/Helpers.
*   *DTOs*: Dùng Java `record` thay cho class thông thường. Dùng MapStruct mapper cho việc chuyển đổi Entity và DTO.
*   *Thin Controllers*: Controller chỉ nhận HTTP/gRPC, validate dữ liệu đầu vào (`@Valid`), và gọi duy nhất 1 phương thức xử lý từ Service. Không chứa logic nghiệp vụ.

#### Database & Integration:
*   *pgvector*: Dùng cho tìm kiếm ngữ nghĩa. Truy vấn vector bằng toán tử `<=>`.
*   *Flyway*: Đặt file script SQL thay đổi database tại `src/main/resources/db/migration/`.
*   *gRPC*: Giao tiếp đồng bộ độ trễ thấp giữa Node.js và Java Services.

#### Quản lý lỗi:
*   Không nuốt ngoại lệ (silent catch).
*   Bắt lỗi dùng safe casting: `const error = err as Error`.
*   Java: Xử lý ngoại lệ tập trung qua `@RestControllerAdvice` (Ví dụ: [EvaluationServiceImpl.java](file:///d:/projects/smile-interview/services/ai-inference-service/src/main/java/fit/iuh/modules/evaluation/service/EvaluationServiceImpl.java)).
*   Node.js: Dùng middleware xử lý lỗi Express tập trung.

---

### 🧪 4. Testing
*   *Unit Tests*: Sử dụng Mockito để cô lập hoàn toàn các dịch vụ bên ngoài.
*   *Integration Tests*: Đánh dấu `@Disabled` hoặc dùng Testcontainers đối với các test yêu cầu database/Redis thật.
*   *Node.js Tests*: Chạy với `NODE_ENV=test` sử dụng Redis Mock Client (Ví dụ: [streaming.test.js](file:///d:/projects/smile-interview/services/streaming-service/test/streaming.test.js)).
