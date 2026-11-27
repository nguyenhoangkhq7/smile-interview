# Độ ổn định luồng phỏng vấn Text ngày 27/11/2026

Trên cùng 100 ca giả lập, luồng có đối chiếu CV/JD hoàn tất 69 ca trước sửa và 58 ca sau sửa. Có 9 ca chuyển từ lỗi sang hoàn tất và 20 ca chuyển theo chiều ngược lại. Hai lần chạy này chưa chứng minh độ ổn định tăng.

## Kết quả theo điều kiện

Mỗi ô thể hiện số đo trước → sau. Độ trễ tính từ lúc chuẩn bị câu đầu đến khi chấm câu trả lời kịch bản và sinh câu kế tiếp hoặc kết thúc hợp lệ. Hai phân vị dùng cùng các ca hoàn tất ở cả hai lần, theo phương pháp hạng gần nhất.

| Điều kiện Text | Hoàn tất trên 100 ca | Ca hoàn tất ở cả hai lần | p50 (giây) | p95 (giây) |
|---|---:|---:|---:|---:|
| Gọi mô hình trực tiếp | 87 → 91 | 78 | 3,590 → 3,597 | 5,184 → 5,704 |
| Luồng thích ứng, tắt đối chiếu nguồn | 64 → 60 | 47 | 12,520 → 11,855 | 21,094 → 19,736 |
| Luồng thích ứng, bật đối chiếu nguồn | 69 → 58 | 49 | 15,053 → 15,130 | 27,223 → 25,509 |

## Lần thử đầu và lần thử lại

Trong mỗi đợt, từng cặp ca và điều kiện chạy một lần. Trong lần chạy đó, ứng dụng có thể yêu cầu sinh lại câu, chấm lại hoặc thử lại lời gọi mô hình sau lỗi tạm thời.

| Kết quả của luồng đầy đủ | Trước, trên 100 | Sau, trên 100 |
|---|---:|---:|
| Hoàn tất, không ghi nhận lần thử lại bên trong luồng | 36 | 30 |
| Hoàn tất sau ít nhất một lần thử lại bên trong luồng | 33 | 28 |
| Hết các lần thử và kết thúc bằng lỗi | 31 | 42 |

Cả hai đợt đều có 0 ca được khởi chạy lại từ đầu. Phép đo chỉ đếm những lần thử lại quan sát được từ bộ sinh câu và nhật ký mô hình. Với điều kiện gọi trực tiếp, SDK không ghi các lần thử mạng nội bộ theo từng ca.

## Bước lỗi và thay đổi sau phép đo

| Bước cuối cùng bị lỗi trong luồng đầy đủ | Trước | Sau |
|---|---:|---:|
| Sinh câu đầu | 1 | 1 |
| Sinh câu chẩn đoán ở mức dễ hơn (`ASK_EASIER`) | 17 | 32 |
| Sinh câu làm rõ (`CLARIFY`) | 13 | 9 |

Cả 42 ca thất bại ở lần sau kết thúc với `QuestionUnavailableError`. Bộ hỏi đã dùng hết các lần tạo câu mà vẫn chưa có đề qua kiểm tra. Ở hai điều kiện đối chứng, lỗi cuối cùng do phía dịch vụ mô hình lần lượt là 13 → 9 ca khi gọi trực tiếp và 2 → 1 ca khi chạy luồng thích ứng tắt đối chiếu nguồn. Phân loại này dựa vào lỗi cuối của mỗi ca. Một lần gọi dịch vụ gặp trục trặc vẫn có thể phục hồi trong cùng ca.

Sau khi quan sát 32 ca lỗi chẩn đoán, nhóm phát triển đã bổ sung cho bộ duyệt hành động và độ khó của câu trước, đồng thời làm rõ yêu cầu đo một quyết định tiền đề thuộc cùng tiêu chí. Test hồi quy ngoại tuyến đi qua module DSPy đã biên dịch để kiểm tra thông tin bộ duyệt thực sự nhận. Hai lần chạy OpenRouter đã kết thúc trước sửa đổi cuối này. Hiệu quả của nó trên mô hình thật còn cần đo.

## Điều kiện đo và dữ liệu

- Dùng [bộ 100 ca cố định](module3_100_cases.json) với CV/JD giả lập, blueprint đóng băng và câu trả lời kịch bản. SHA-256 của tệp trong cả hai phiên bản là `bd0f4926ca6a3635fa67bfc681552e7eb9fecca1a94f396fa2360183ad0eec15`.
- Bản trước lấy từ commit `6b0efd81e28c615edbc1c2950dc85b3fc69e9cd6`. Hai lần dùng cùng cấu hình OpenRouter, model `qwen/qwen3.7-flash`, 3 worker, và cùng 3 điều kiện, tổng cộng 600 lượt chạy. Mốc 68/100 thuộc báo cáo lịch sử riêng.
- [Dữ liệu so sánh theo từng ca](module3_reliability_2026-11-27.json) gồm kết quả lần đầu, bước lỗi, loại lỗi, thời gian chờ thử lại và phân vị theo điều kiện. Trường `elapsed_seconds` của bản trước để trống vì runner cũ chỉ đo các giai đoạn. Với bản trước, bước lỗi được suy ra từ câu hỏi và kết quả chấm đã lưu.
- [Bộ tổng hợp ngoại tuyến](../benchmark_reliability.py) đọc hai tệp JSONL. Trong workspace nghiệm thu, chúng ở `artifacts/recheck-benchmark/before.jsonl` và `artifacts/recheck-benchmark/after.jsonl`. Đơn vị “hoàn tất” ở đây chỉ tính đoạn hội thoại ngắn của benchmark. Nghiệm thu Voice dùng Chromium cùng dữ liệu HTTP và âm thanh giả lập riêng.
