# Quy trình Đánh giá Thực nghiệm Người dùng (User Study & SUS Protocol)

Tài liệu này cung cấp kịch bản thực nghiệm chuẩn hóa (~25 phút/người) dành cho **Chương 5 (Thực nghiệm và Đánh giá)** của Khóa luận Tốt nghiệp **Smile Interview**, giúp thu thập bằng chứng định lượng (điểm SUS, mức độ hữu ích theo từng tính năng) và định tính từ sinh viên CNTT.

---

## 1. Mục tiêu và Đối tượng khảo sát

- **Mục tiêu:** Đánh giá tính khả dụng (Usability), giá trị ôn luyện phỏng vấn thực tế và sự khác biệt của phiên bản nâng cấp (Practice/Assessment, Clarify/Hint, CodeMirror 6 + Sandbox Runner, Weighted Readiness & Recheck) so với cách ôn luyện truyền thống (tự đọc tài liệu, hỏi đáp rời rạc trên ChatGPT).
- **Cỡ mẫu khuyến nghị:** **10 – 15 sinh viên** năm 3 – năm 4 ngành Công nghệ Thông tin / Kỹ thuật Phần mềm (FIT-IUH) đang chuẩn bị ứng tuyển vị trí Thực tập sinh (Intern) hoặc Fresher (Backend, Frontend, Full-stack, Data).
- **Điều kiện thực hiện:** Mỗi người tham gia dùng 1 máy tính có trình duyệt Chrome/Edge, chuẩn bị sẵn 1 tệp **CV cá nhân (PDF)** và chọn 1 **JD mẫu** (hoặc JD vị trí đang muốn ứng tuyển).

---

## 2. Kịch bản trải nghiệm có hướng dẫn (25 phút / người tham gia)

| Giai đoạn | Thời lượng | Hoạt động của người tham gia | Quan sát của người điều phối |
| :--- | :---: | :--- | :--- |
| **Bước 1: Tạo hồ sơ & Phân tích CV–JD** | 4 phút | Đăng nhập, tải CV và dán JD, xem báo cáo khoảng cách kỹ năng (Skill Gap) từ mô-đun GNN v4. | Ghi nhận thời gian hoàn tất, mức độ dễ hiểu của danh sách kỹ năng thiếu/cần xác minh. |
| **Bước 2: Phỏng vấn ở chế độ Luyện tập (`PRACTICE`)** | 9 phút | Tạo lượt mới, chọn chế độ **Luyện tập (Practice)**, dạng **Tổng hợp** hoặc **Lập trình (Coding)**. Thực hiện tối thiểu 3 câu hỏi, trong đó bắt buộc thử: **(a)** bấm *Hỏi làm rõ đề bài* (`/clarify`), **(b)** bấm *Xin gợi ý nhỏ*, **(c)** viết code trong trình soạn thảo CodeMirror 6 và bấm *Chạy thử* (`/run-code`) trước khi nộp. | Ghi nhận số lần gặp trục trặc (nếu có), phản ứng khi dùng nút làm rõ/gợi ý và khi thấy kết quả pass/fail của test mẫu. |
| **Bước 3: Xem báo cáo & Vòng lặp Kiểm chứng (`Recheck`)** | 7 phút | Mở trang Kết quả phỏng vấn: đọc **Mức độ sẵn sàng có trọng số Core**, nhãn **Cốt lõi / L1–L4**, **Đáp án mẫu tham khảo (`reference_answer`)** và **Gợi ý trình bày (`delivery_notes`)**. Sau đó sang tab Kế hoạch ôn tập, chọn 1 tiêu chí yếu để chạy **Kiểm chứng lại (Recheck)** và quay về trang Hồ sơ ứng tuyển xem **Biểu đồ tiến bộ (`CompetencyProgressTimeline`)**. | Kiểm tra người dùng có phân biệt được điểm sẵn sàng có trọng số Core với tỷ lệ câu đúng thông thường hay không; có hiểu cách tách phiên Practice khỏi hồ sơ chính thức hay không. |
| **Bước 4: Điền phiếu khảo sát SUS & Phỏng vấn ngắn** | 5 phút | Điền bảng câu hỏi **SUS (10 câu)**, **5 câu đánh giá chuyên biệt** và 2 câu hỏi mở so sánh với phương pháp ôn tập trước đây. | Thu thập nguyên văn góp ý cải tiến và lỗi trải nghiệm nhỏ nếu phát sinh. |

---

## 3. Phiếu khảo sát System Usability Scale (SUS — Chuẩn hóa Tiếng Việt)

Người tham gia đánh giá từng phát biểu theo thang Likert 5 mức:
**1 = Hoàn toàn không đồng ý · 2 = Không đồng ý · 3 = Trung lập · 4 = Đồng ý · 5 = Hoàn toàn đồng ý**

| STT | Nội dung phát biểu (SUS) | Chiều tính điểm |
| :---: | :--- | :---: |
| 1 | Tôi nghĩ mình sẽ muốn sử dụng hệ thống Smile Interview thường xuyên để chuẩn bị cho các buổi phỏng vấn. | Tích cực ($x_1 - 1$) |
| 2 | Tôi thấy hệ thống này phức tạp hơn mức cần thiết. | Tiêu cực ($5 - x_2$) |
| 3 | Tôi nghĩ hệ thống này dễ sử dụng. | Tích cực ($x_3 - 1$) |
| 4 | Tôi nghĩ mình cần sự hỗ trợ của người có chuyên môn kỹ thuật để có thể sử dụng được hệ thống này. | Tiêu cực ($5 - x_4$) |
| 5 | Tôi thấy các chức năng trong hệ thống (phân tích CV–JD, luyện phỏng vấn, chạy code, kế hoạch ôn tập) được tích hợp chặt chẽ với nhau. | Tích cực ($x_5 - 1$) |
| 6 | Tôi thấy có quá nhiều điểm thiếu nhất quán trong hệ thống này. | Tiêu cực ($5 - x_6$) |
| 7 | Tôi tin rằng hầu hết sinh viên CNTT sẽ học cách sử dụng hệ thống này rất nhanh. | Tích cực ($x_7 - 1$) |
| 8 | Tôi thấy hệ thống này khá rườm rà khi thao tác. | Tiêu cực ($5 - x_8$) |
| 9 | Tôi cảm thấy tự tin khi sử dụng hệ thống này. | Tích cực ($x_9 - 1$) |
| 10 | Tôi phải tìm hiểu rất nhiều thứ trước khi có thể bắt đầu sử dụng hệ thống này. | Tiêu cực ($5 - x_{10}$) |

### Công thức tính điểm SUS (Brooke, 1996)
Với mỗi người tham gia, tổng điểm quy đổi về thang `0 – 100`:

$$\text{SUS} = 2.5 \times \left(\sum_{i \in \{1,3,5,7,9\}} (x_i - 1) + \sum_{i \in \{2,4,6,8,10\}} (5 - x_i)\right)$$

- **Thang tham chiếu học thuật (Bangor et al., 2009):**
  - $\ge 80.3$: Xuất sắc (Hạng A)
  - $68.0 – 80.2$: Tốt, đạt chuẩn sản phẩm (Hạng B / Trên trung bình ngành 68)
  - $51.0 – 67.9$: Chấp nhận được nhưng cần cải thiện (Hạng C–D)
  - $< 51.0$: Kém (Hạng F)

---

## 4. Câu hỏi đánh giá chuyên biệt về giá trị ôn luyện phỏng vấn (Thang 1 – 5)

| Mã | Tiêu chí đánh giá chuyên biệt |
| :---: | :--- |
| **Q1** | Câu hỏi phỏng vấn bám sát nội dung CV và yêu cầu thực tế của JD đã nộp. |
| **Q2** | Chế độ **Luyện tập (Practice)** kết hợp nút **Hỏi làm rõ đề bài** và **Xin gợi ý nhỏ** giúp tôi bớt áp lực và học hiệu quả hơn so với chỉ thi thử một chiều. |
| **Q3** | Trình soạn thảo **CodeMirror 6** và tính năng **Chạy thử code** trực tiếp giúp bài phỏng vấn lập trình sát thực tế hơn so với nhập văn bản thông thường. |
| **Q4** | **Đáp án mẫu tham khảo**, **Gợi ý cách trình bày** và **Điểm sẵn sàng có trọng số Core** giúp tôi biết rõ lỗ hổng nào cần ưu tiên ôn trước. |
| **Q5** | So với việc tự luyện phỏng vấn bằng ChatGPT thông thường, Smile Interview giúp tôi theo dõi tiến bộ qua nhiều lượt (nhờ Kế hoạch ôn tập, Kiểm chứng lại và Biểu đồ tiến bộ) hiệu quả hơn. |

### Câu hỏi mở (Định tính)
1. **Điểm hữu ích nhất** của Smile Interview đối với bạn trong quá trình chuẩn bị đi phỏng vấn là gì?
2. Bạn gặp **khó khăn hoặc điểm chưa hài lòng** nào trong phiên trải nghiệm (tốc độ phản hồi, độ khó câu hỏi, giao diện, giọng nói/code) và muốn cải thiện điều gì đầu tiên?

---

## 5. Mẫu bảng tổng hợp kết quả cho Chương 5 Khóa luận

### 5.1. Bảng tổng hợp định lượng ($N = \dots$ sinh viên)

| Chỉ số đánh giá | Giá trị trung bình (Mean) | Độ lệch chuẩn (SD) | Min – Max | Ghi chú / Ngưỡng mục tiêu |
| :--- | :---: | :---: | :---: | :--- |
| **Điểm khả dụng hệ thống (SUS)** | `__/100` | `±__` | `__ – __` | Mục tiêu $\ge 75/100$ (vượt chuẩn 68) |
| **Q1 – Độ sát CV & JD** | `__/5.0` | `±__` | `__ – __` | |
| **Q2 – Hữu ích của Practice / Clarify / Hint** | `__/5.0` | `±__` | `__ – __` | |
| **Q3 – Trải nghiệm Code IDE & Chạy thử** | `__/5.0` | `±__` | `__ – __` | |
| **Q4 – Rõ ràng của Báo cáo & Đáp án mẫu** | `__/5.0` | `±__` | `__ – __` | |
| **Q5 – Lợi thế theo dõi tiến bộ so với ChatGPT** | `__/5.0` | `±__` | `__ – __` | |
| **Tỷ lệ hoàn tất luồng không lỗi (`Completion Rate`)** | `__%` | — | — | Mục tiêu $\ge 95\%$ |

### 5.2. Bảng ghi nhận phiên trải nghiệm chi tiết

| Mã SV | Năm học / Định hướng | Thời gian hoàn tất (phút) | Số lượt Clarify/Hint đã dùng | Đã chạy thử Code? | Điểm SUS | Nhận xét nổi bật |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| SV01 | Năm 4 – Backend | | | Có / Không | | |
| SV02 | Năm 4 – Frontend | | | Có / Không | | |
| ... | ... | | | | | |
