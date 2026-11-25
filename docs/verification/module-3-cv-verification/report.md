# Đối chứng xác minh CV theo tiêu chí

Hai lượt chạy dùng cùng một CV và JD giả lập, cùng rubric đã định trước, cùng cấu hình mô hình và giới hạn ba câu TEXT. Câu trả lời được cố định theo tiêu chí và số lượt đã hỏi tiêu chí đó. Nội dung hỏi và kết quả chấm do provider đang cấu hình sinh ra. [Trước thay đổi](before.json) · [Sau thay đổi](after.json)

| Chỉ số | Trước | Sau |
| --- | ---: | ---: |
| Chi tiết có bằng chứng đạt theo rubric | 2/2 | 2/2 |
| Câu lạc tiêu chí hoặc lặp ý | 0/3 | 0/3 |
| Tiêu chí thiết yếu được hỏi | 2/2 | 2/2 |
| Chi tiết chuẩn bị sẵn từ trích dẫn CV đã xác minh | 0 | 2 |

Đối chiếu câu trả lời với hai tiêu chí đã đặt trước. Câu trả lời về nhận diện yêu cầu lặp nêu khóa giữ nguyên khi client gửi lại và cách server đối chiếu với bản ghi đã lưu. Câu trả lời về xử lý yêu cầu đã hoàn tất nêu việc trả lại kết quả của lần xử lý gốc. Chỉ số lạc tiêu chí hoặc lặp ý được kiểm tra trực tiếp trên hai bản ghi. Lượt làm rõ được tính là phù hợp khi nó tập trung vào phần thiếu trong câu trả lời trước.

Ở bản sau thay đổi, bước chuẩn bị xác định hai điểm cần làm rõ từ cùng đoạn CV. Sau câu “Em kiểm tra trong database”, Module 3 hỏi trường dữ liệu nào dùng làm định danh ổn định. Sau câu trả lời có bằng chứng đạt, Module 3 hỏi tiêu chí thứ hai. Hai lượt cho cùng kết quả trên ca này. Cần nhiều cặp CV–JD và người chấm độc lập để ước lượng hiệu quả trên tập nghiên cứu rộng hơn.

Từ thư mục `ai-service`, chạy lại ca giả lập với mô hình trong cấu hình của dự án.

```powershell
python -m scripts.verify_cv_verification --output ../artifacts/module-3-cv-verification/replay.json
```
