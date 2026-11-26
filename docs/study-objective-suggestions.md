# Gợi ý ôn tập theo objective và criterion

API `GET /api/v1/application-profiles/{id}/study-plan/knowledge-gaps` bổ sung
`objectiveSuggestions`. Các trường cũ được giữ tương thích. Mỗi objective đã được
kiểm tra có danh sách criterion, trạng thái năng lực hiện tại, lý do gợi ý,
kết quả cần đạt và nguồn đánh giá. Các objective chỉ có tiêu chí đã đạt vẫn được
trả về để theo dõi đầu việc đã tạo, nhưng được ẩn khỏi danh sách lỗ hổng.

| Loại | Ý nghĩa | Chọn mặc định |
|---|---|---|
| REVIEW | Có bằng chứng dưới yêu cầu | Có |
| VERIFY | Bằng chứng mâu thuẫn hoặc đã hỏi nhưng chưa đủ kết luận | Có |
| REINFORCE | Đã đạt, nhưng từng gặp khó khăn trong lượt kiểm tra liên quan gần nhất | Không |
| UNASSESSED | Chưa có thông tin kiểm tra tiêu chí | Không |
| MET | Đã có bằng chứng đạt yêu cầu | Không |

Ví dụ: objective có 5 criteria, hỏi 3 criteria khác nhau, 1 đạt và 2 chưa đạt:
chỉ 2 criteria chưa đạt được chọn sẵn. Người dùng có thể chọn thêm 2 criteria
chưa hỏi. Nhiều câu hỏi cùng criterion chỉ tạo một gợi ý.

`StudySuggestionProjection` dùng kết luận từ `CompetencyProjection`, bổ sung
thông tin thực hành từ snapshot đã kết thúc và tương thích blueprint. Phạm vi
lịch sử theo `sourceSessionId` của kế hoạch. Không gọi thêm AI và không thay đổi
kết luận năng lực khi người dùng hoàn thành đầu việc.

Bấm thêm hoặc kéo thả một objective mở bản nháp. Người dùng sửa tên, chọn
criteria, sửa nội dung checklist và thêm ghi chú trước khi lưu. Lỗi lưu giữ
nguyên bản nháp. Cột thả được dùng làm trạng thái ban đầu của đầu việc.

Migration V8 thêm `gap_source_objective_id` cho đầu việc và nguồn criterion,
session, số lượt cho từng checklist. Nguồn vẫn được giữ khi sửa nội dung hoặc
đánh dấu checklist hoàn thành. Backend kiểm tra objective/criterion thuộc hồ sơ
và nguồn session thuộc hồ sơ. Dữ liệu cũ tiếp tục hoạt động.

Đầu việc theo objective chỉ được thông báo đã cải thiện khi tất cả criteria có
liên kết nguồn trong checklist có kết luận đạt với bằng chứng mới hơn mốc nguồn
của từng mục. Thông báo không tự đóng đầu việc.

Kiểm tra:

- Backend: `StudySuggestionProjectionTest`, `StudyPlanHttpTest`, `CompetencyProjectionTest`.
- Frontend: `npx tsc --noEmit`, lint các file thay đổi.
- Với web app chạy tại cổng 3217: `node scripts/study-suggestions-smoke.mjs` từ `web-app`.
  Kiểm tra chọn 2/5, chọn thêm, hủy, thử lại, kéo thả, nguồn dữ liệu, cải thiện
  từng criterion và dialog trên mobile; API được giả lập, không ghi dữ liệu thật.

Cần chạy phiên bản backend và web app mới cùng nhau; Flyway tự áp dụng V8 khi
backend khởi động.
