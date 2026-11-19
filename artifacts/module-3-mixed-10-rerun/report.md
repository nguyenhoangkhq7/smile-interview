# Kiểm thử lại Module 3 sau nâng cấp

## Kết luận

**Chưa đạt yêu cầu hoàn thành phiên `MIXED` 10 câu.** Hai phiên với Blueprint mới dừng trước câu chuyên môn đầu tiên. Phiên tái sử dụng Blueprint cũ sinh được câu đầu, nhưng cả ba lần gửi đáp án trả HTTP `503` khi sinh câu tiếp theo. API không trả snapshot mới nên số câu đã ghi nhận vẫn là **0/10**.

Hai cải tiến có bằng chứng riêng. Judge phân loại câu PostgreSQL thiếu ý là `UNCLEAR` và trường hợp Python từng bị chấm đạt nhầm nay trượt ca đối chứng. Thời gian tạo Blueprint và số lần gọi model khi chấm cũng giảm trong các lần quan sát được. Điểm nghẽn của phiên hiện tại nằm ở sinh và duyệt câu hỏi.

## Phạm vi và kết quả từng lần

Các phiên dùng cùng sáu kỹ năng, nhiệm vụ và trích dẫn CV/JD hư cấu của bộ test trước, với `TEXT`, `MIXED`, tối đa 10 câu và 3.600 giây chuyên môn. Phần mở đầu và tự giới thiệu lần này bỏ tên ứng viên, công ty và CV/JD tóm tắt. Không thay đổi mã nghiệp vụ trong đợt kiểm thử. FastAPI TestClient chạy trong tiến trình ghi riêng của chính container `ai-service` vừa dựng, gọi route thật và OpenRouter đã cấu hình. SHA-256 của cả 20 file Python trong thư mục `evidence` trên container trùng workspace. [Fixture](inbox/01-start.json) · [Runtime](run/runtime.json) · [Kiểm tra dữ liệu](verification.json) · [Health của cổng 8000](run/live-health.json).

| Phiên | Blueprint | Giai đoạn cuối đã ghi nhận | Câu được lưu | HTTP 503 |
| --- | --- | --- | --- | --- |
| Trước nâng cấp | Sinh mới | `FINISHED`, `QUESTION_BUDGET` | 10/10 | 3 lần gửi câu trả lời, đều phục hồi |
| A | Sinh mới | `SELF_INTRODUCTION`, v2 | 0/10 | 3 lần nộp phần giới thiệu |
| B | Sinh mới bằng tiến trình độc lập, giữ nguyên fixture | `SELF_INTRODUCTION`, v2 | 0/10 | 2 lần nộp phần giới thiệu |
| C | Tái sử dụng Blueprint do phiên trước sinh qua trường `StartRequest.blueprint` | `INTERVIEW`, v3, còn câu đầu đang chờ | 0/10 | 3 lần gửi câu đầu |

Diễn biến theo thời gian gồm cả các phản hồi lỗi và các chuyển trạng thái chỉ xảy ra trên bản sao trong bộ nhớ. [Phiên A](chronology.md) · [Phiên B](attempt-b/chronology.md) · [Phiên C](attempt-c/chronology.md).

## Đánh giá từng phần nâng cấp

| Phần | Kết quả quan sát |
| --- | --- |
| **Tạo Blueprint** | `/start` giảm từ **60,897 giây, 5 lượt gọi model** ở lần trước xuống **29,624 giây** và **26,574 giây**, mỗi phiên **3 lượt gọi**. Các số gồm cả lời chào. Phiên C dùng Blueprint đã có nên thời gian 5,590 giây được ghi riêng. |
| **Tốc độ Judge** | Ba lần gửi ở phiên C, mỗi lần Judge dùng **1 lượt gọi model** và mất **3,52–4,94 giây**, trung vị **4,89 giây**. Lần trước 12/14 lần gọi Judge dùng 2 lượt model. Trung vị ở các lần gửi có Judge chạy là **10,05 giây**. Ba phép đo mới đều ở cùng câu PostgreSQL trước khi sinh câu tiếp theo thất bại, nên chưa cho thấy độ trễ của cả phiên. |
| **Judge với câu thiếu ý** | Hai đáp án mô tả đúng `Seq Scan` và `Sort` nhưng thiếu cách sửa đều nhận `UNCLEAR / UNDETERMINED`. Đáp án có thêm đề xuất SQL nhận `SUPPORTS / AT_TARGET`. Cả ba là Judgment nội bộ của request thất bại, chưa được ghi vào snapshot. |
| **Judge với code sai** | Chạy riêng bộ kiểm chứng trên đúng câu và đoạn code Python của phiên cũ. Đoạn code giữ bản ghi cuối chỉ qua **2/3** ca, được ghi `CONTRADICTS / BELOW` thay cho `AT_TARGET` lần trước. Đoạn đã sửa qua **3/3** ca. Ca này chạy trong container và không gọi model. |
| **Câu hỏi và khả năng hoàn tất** | Guard cục bộ đã bắt được các bản nháp gộp nhiệm vụ ở phiên B, nhưng vẫn có bản nháp gộp lọt ở phiên C. Bộ duyệt `GIVES_SOLUTION` từ chối cả những câu chưa cung cấp cấu trúc chỉ mục cần tìm. Retry hết hai bản nháp thì request trả `503`. |

[Số liệu so sánh và cỡ mẫu](comparison.json) · [Đối chứng Python](run/replay-coding-output.json) · [Trace Judge của phiên C](attempt-c/run/components.jsonl).

## Lỗi cần xử lý trước khi chạy lại đủ 10 câu

1. **`GIVES_SOLUTION` bắt nhầm câu hỏi hợp lệ.** Tiêu chí thực tế phiên A là xác định chỉ mục phù hợp cho truy vấn lọc và sắp xếp. Bản nháp số 96 chỉ hỏi “Hãy đề xuất cấu trúc chỉ mục phù hợp để tối ưu hóa truy vấn này” và yêu cầu giải thích lựa chọn. Đề vẫn để ứng viên tự xác định cấu trúc và thứ tự cột. Bộ duyệt vẫn trả `GIVES_SOLUTION` ở seq 105. Nên dùng cặp ca đối chứng để phân biệt câu hỏi yêu cầu tự chọn chỉ mục với câu đã nêu sẵn *composite index* hoặc thứ tự cột. [Trace A, seq 96–106](run/components.jsonl).
2. **Guard hiện tại vẫn bỏ sót một mẫu câu gộp.** Câu đầu phiên C hỏi “chỉ ra điểm nghẽn chính ... và đề xuất một thay đổi cụ thể về index hoặc query”. Bản nháp nhận `ALIGNED` ở seq 57. Nên đưa đúng mẫu “chỉ ra ... và đề xuất ...” vào ca hồi quy và kiểm Blueprint cũ có rubric gộp. [Câu đã được phát ở phiên C](attempt-c/run/http/03-intro.json) · [Trace C](attempt-c/run/components.jsonl).
3. **Lỗi sinh câu sau làm mất lần nộp đã chấm.** Phiên C lần thứ ba chấm câu đầu đạt, chọn `FOLLOW_UP` sang tiêu chí chưa hỏi, rồi bác hai bản câu tiếp theo và trả `503`. Snapshot gốc vẫn ở v3 với câu đầu đang chờ. Điều kiện ưu tiên trước lần thử kế tiếp là bộ duyệt phân loại đúng hai trường hợp ở mục 1 và retry có thể trả câu đã sửa trong ngân sách hiện tại. [Lần gửi câu đủ ý](attempt-c/run/http/04-q01-complete.json) · [Trace C, seq 190–242](attempt-c/run/components.jsonl).

Chưa đánh giá được các lượt RabbitMQ, HTTP và hành vi trong một phiên hoàn chỉnh sau nâng cấp. Một phép replay Judge tách riêng từ nhiều snapshot cũ bị cơ chế phê duyệt tự động chặn vì phạm vi gửi lại nội dung, gồm cả ca RabbitMQ, đến OpenRouter. Số liệu Judge ở trên lấy từ ba đáp án giả lập mới gửi qua luồng phiên C.
